from html import escape
from io import BytesIO
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from docx import Document
import fitz
from openai import OpenAI
import streamlit as st

load_dotenv()

SYSTEM_PROMPT = """
You are an expert resume writer and ATS optimization specialist.
Refine the user's resume so it better matches the provided job description.

Requirements:
- Preserve factual accuracy and do not invent experience, skills, achievements, dates, or certifications.
- Improve ATS compatibility with clear section headings, relevant keywords, concise bullet points, and strong action verbs.
- Prioritize the most relevant experience and skills for the target role.
- Keep the output polished, professional, and easy to scan.
- Keep the same major sections, section order, bullet structure, and similar line density as the original resume so it can fit back into the same layout.
- Keep each entry aligned to its original role and section. Do not merge, reorder, or expand entries in a way that would change the visual template.
- Return plain resume text only.
- Do not use markdown.
- Do not use **, __, #, or --- separators.
- Preserve heading lines and bullet lines so the text can be written back into the original PDF boxes.
""".strip()

BULLET_REWRITE_PROMPT = """
You are refining resume bullet points for ATS optimization.
Rewrite only the provided bullets.

Rules:
- Preserve factual meaning and do not invent anything.
- Keep each bullet aligned to the same role and section.
- Keep each bullet close to its original length and within the provided min/max character range.
- Improve clarity, action verbs, keywords, and measurable impact when supported by the original bullet.
- Return only the rewritten bullets in the exact format: index::bullet text
- Output one line per bullet and nothing else.
- Every rewritten bullet must begin with the bullet symbol: •
""".strip()

SUGGESTIONS_PROMPT = """
Analyze this resume against the job description and provide exactly 5 specific improvements the candidate should make.
Focus on ATS alignment, missing skills, stronger phrasing, measurable impact, and content prioritization.
Return only 5 concise bullet points.
""".strip()

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "in", "is", "it",
    "of", "on", "or", "that", "the", "to", "with", "you", "your", "will", "this", "have",
    "has", "our", "their", "they", "them", "we", "us", "but", "not", "all", "can", "any",
    "who", "what", "when", "where", "why", "how", "job", "role", "work", "working", "candidate",
    "experience", "preferred", "required", "requirements", "qualification", "qualifications", "skills",
    "skill", "ability", "abilities", "team", "teams", "plus", "including", "etc", "using", "used",
}

SAFE_FONT_REGULAR = "helv"
SAFE_FONT_BOLD = "hebo"
SAFE_FONT_ITALIC = "heit"
SAFE_FONT_BOLD_ITALIC = "hebi"
MAX_FONT_SIZE = 12.5
MIN_FONT_SIZE = 5.5
MAX_BATCH_BULLETS = 12
DATE_PATTERN = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?(?:\s*[-–]\s*(?:present|current|(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)(?:\s+\d{4})?))?\b|\b\d{4}\s*[-–]\s*(?:\d{4}|present)\b",
    re.IGNORECASE,
)
ROLE_KEYWORDS = {
    "intern", "analyst", "associate", "manager", "director", "consultant", "engineer",
    "assistant", "coordinator", "specialist", "lead", "founder", "member", "president",
    "educator", "researcher", "officer", "operations", "finance", "financial",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text.strip())


def clean_resume_output(text: str) -> str:
    cleaned = text.replace("\r\n", "\n")
    cleaned = re.sub(r"\*\*(.*?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"__(.*?)__", r"\1", cleaned)
    cleaned = re.sub(r"^#{1,6}\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^---+$", "", cleaned, flags=re.MULTILINE)
    cleaned = cleaned.replace("â€¢", "•")
    cleaned = cleaned.replace("ï‚·", "•")
    cleaned = re.sub(r"(?m)^[ \t]*[?\uFFFD\uf0b7\u2022\u25cf\u25cb\u25aa\uf0a7][ \t]+", "• ", cleaned)
    cleaned = re.sub(r"(?m)^[ \t]*[\-*][ \t]*", "- ", cleaned)
    cleaned = re.sub(r"[ \t]+", " ", cleaned)
    cleaned = re.sub(r"\n[ \t]+\n", "\n\n", cleaned)
    return collapse_blank_lines(cleaned)


def normalize_bullet_text(text: str) -> str:
    cleaned = clean_resume_output(text).strip()
    cleaned = re.sub(r"^[•\-*?\s]+", "", cleaned).strip()
    return f"• {cleaned}" if cleaned else ""


_PDF_BULLET_CHARS = {
    "\uFFFD",  # Unicode replacement character (shown as ? in many PDF viewers)
    "\uf0b7",  # Private-use Wingdings/Symbol bullet
    "\u2022",  # Standard bullet •
    "\u25cf",  # Black circle ●
    "\u25cb",  # White circle ○
    "\u25aa",  # Small black square ▪
    "\uf0a7",  # Private-use Wingdings bullet §
}


def normalize_pdf_bullet_chars(text: str) -> str:
    """Replace known non-standard bullet glyphs at line starts with standard •."""
    lines = text.split("\n")
    result = []
    for line in lines:
        stripped = line.lstrip(" \t")
        if stripped and stripped[0] in _PDF_BULLET_CHARS and len(stripped) >= 2 and stripped[1] in " \t":
            line = line.replace(stripped[0], "•", 1)
        result.append(line)
    return "\n".join(result)


def is_bullet_text(text: str) -> bool:
    return bool(re.match(r"^[ \t]*[•\-*?\uFFFD\uf0b7\u2022\u25cf\u25cb\u25aa\uf0a7]\s+", text.strip()))


def safe_pdf_font_name(font_name: str) -> str:
    name = (font_name or "").lower()
    is_bold = "bold" in name or "black" in name
    is_italic = "italic" in name or "oblique" in name
    if is_bold and is_italic:
        return SAFE_FONT_BOLD_ITALIC
    if is_bold:
        return SAFE_FONT_BOLD
    if is_italic:
        return SAFE_FONT_ITALIC
    return SAFE_FONT_REGULAR


def pdf_color_tuple(color_value: int) -> tuple[float, float, float]:
    red = ((color_value >> 16) & 255) / 255
    green = ((color_value >> 8) & 255) / 255
    blue = (color_value & 255) / 255
    return red, green, blue


def sanitize_block_text(lines: list[str]) -> str:
    sanitized_lines = [re.sub(r"[ \t]+", " ", line.strip()) for line in lines if line.strip()]
    return "\n".join(sanitized_lines).strip()


def is_structural_block(block: dict[str, Any]) -> bool:
    text = block.get("text", "").strip()
    return not text or len(text) <= 2


def classify_text_block(text: str, font_size: float, font_name: str) -> str:
    stripped = text.strip()
    if not stripped:
        return "EMPTY"
    if is_bullet_text(stripped):
        return "BULLET_POINT"
    if re.fullmatch(r"[A-Z0-9 &/,+.-]{3,}", stripped) and len(stripped) <= 80:
        return "SECTION_TITLE"
    if DATE_PATTERN.search(stripped) and len(stripped) <= 90:
        return "DATE"
    if stripped.count("|") >= 3 and len(stripped) <= 160:
        return "SKILLS_LIST"
    if font_size >= 14.5 and len(stripped) <= 120:
        return "HEADER"
    lowered = stripped.lower()
    if any(keyword in lowered for keyword in ROLE_KEYWORDS) and len(stripped) <= 120:
        return "ROLE"
    if "|" in stripped and len(stripped) <= 120 and not stripped.endswith("."):
        return "COMPANY"
    return "BODY"


def calculate_line_height(lines: list[dict[str, Any]], fallback_size: float) -> float:
    heights: list[float] = []
    for line in lines:
        bbox = line.get("bbox") or [0, 0, 0, 0]
        height = max(0.0, float(bbox[3]) - float(bbox[1]))
        if height > 0:
            heights.append(height)
    average_height = sum(heights) / len(heights) if heights else fallback_size * 1.15
    ratio = average_height / max(fallback_size, 1.0)
    return max(0.95, min(1.35, ratio))


@st.cache_data(show_spinner=False)
def extract_resume_data(file_bytes: bytes, file_extension: str) -> dict[str, Any]:
    if file_extension == "pdf":
        document = fitz.open(stream=file_bytes, filetype="pdf")
        pages: list[dict[str, Any]] = []
        page_text: list[str] = []
        bullets: list[dict[str, Any]] = []

        for page_index, page in enumerate(document):
            page_dict = page.get_text("dict")
            blocks: list[dict[str, Any]] = []
            for block in page_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue

                lines = block.get("lines", [])
                text_lines: list[str] = []
                span_items: list[dict[str, Any]] = []
                font_name = SAFE_FONT_REGULAR
                font_size = 10.0
                color_value = 0

                for line in lines:
                    spans = line.get("spans", [])
                    line_text_parts: list[str] = []
                    for span in spans:
                        span_text = span.get("text", "")
                        if not span_text:
                            continue
                        line_text_parts.append(span_text)
                        span_bbox = span.get("bbox") or line.get("bbox") or block.get("bbox", [0, 0, 0, 0])
                        span_items.append(
                            {
                                "text": span_text,
                                "bbox": span_bbox,
                                "font": span.get("font", SAFE_FONT_REGULAR),
                                "size": float(span.get("size", 10.0)),
                                "line_height": max(0.0, float(span_bbox[3]) - float(span_bbox[1])),
                            }
                        )
                    line_text = "".join(line_text_parts).strip()
                    if line_text:
                        text_lines.append(line_text)
                    if spans:
                        sample = spans[0]
                        font_name = sample.get("font", SAFE_FONT_REGULAR)
                        font_size = max(font_size, float(sample.get("size", 10.0)))
                        color_value = int(sample.get("color", 0))

                text = normalize_pdf_bullet_chars(sanitize_block_text(text_lines))
                line_height = calculate_line_height(lines, font_size)
                classification = classify_text_block(text, font_size, font_name)
                block_index = len(blocks)
                block_data = {
                    "rect": block.get("bbox", [0, 0, 0, 0]),
                    "text": text,
                    "text_lines": [line for line in text.splitlines() if line.strip()],
                    "font": font_name,
                    "size": font_size,
                    "color": color_value,
                    "line_count": max(1, len(text_lines)),
                    "char_count": max(1, len(text)),
                    "line_height": line_height,
                    "spans": span_items,
                    "classification": classification,
                    "is_structural": False,
                }
                block_data["is_structural"] = is_structural_block(block_data)

                if classification == "BULLET_POINT" and not block_data["is_structural"]:
                    bullet_id = len(bullets)
                    normalized_bullet = normalize_bullet_text(text)
                    bullet_data = {
                        "id": bullet_id,
                        "page_index": page_index,
                        "block_index": block_index,
                        "text": normalized_bullet or text,
                        "original_text": normalized_bullet or text,
                        "char_count": len(normalized_bullet or text),
                        "rect": block_data["rect"],
                        "font": font_name,
                        "size": font_size,
                        "line_height": line_height,
                        "color": color_value,
                    }
                    bullets.append(bullet_data)
                    block_data["bullet_id"] = bullet_id
                    block_data["text"] = normalized_bullet or text
                    block_data["text_lines"] = [line for line in block_data["text"].splitlines() if line.strip()]
                blocks.append(block_data)
                if block_data["text"]:
                    page_text.append(block_data["text"])

            # ── Second pass: handle lone bullet-glyph blocks ─────────────────
            # Some PDFs store the bullet glyph (•, ?) in its own tiny structural
            # block separate from the content.  Three cases:
            #   A) Next block is already BULLET_POINT on same line → widen rect.
            #   B) Next block is BODY/HEADER, same line, indented, no pipe →
            #      promote to BULLET_POINT.
            #   C) Everything else (glyph before company/date/header) →
            #      just erase the stray glyph so it doesn't show in output.
            _LONE_BULLET_CHARS = {"•", "?", "-", "–", "—", "*", "·", "○", "▪", "▸"}
            for i, blk in enumerate(blocks):
                if not (blk.get("is_structural") and blk.get("text", "").strip() in _LONE_BULLET_CHARS):
                    continue

                # Always mark stray glyph for removal.
                blk["needs_redact"] = True

                if i + 1 >= len(blocks):
                    continue
                nxt = blocks[i + 1]
                if nxt.get("is_structural"):
                    continue

                glyph_x0 = float(blk["rect"][0])
                glyph_y0 = float(blk["rect"][1])
                content_x0 = float(nxt["rect"][0])
                content_y0 = float(nxt["rect"][1])
                font_h = float(blk.get("size", 10.0)) * 2.0

                same_line = abs(glyph_y0 - content_y0) < font_h
                is_indented = content_x0 > glyph_x0 + 2
                no_pipe = "|" not in nxt.get("text", "")

                if not same_line:
                    continue

                if nxt.get("classification") == "BULLET_POINT" and not nxt.get("is_structural"):
                    # Case A: already a bullet — widen its rect to include glyph position.
                    nxt["bullet_glyph_rect"] = list(blk["rect"])
                    blk["glyph_paired"] = True  # atomic with content block in build_refined_pdf

                elif (
                    nxt.get("classification") in ("BODY", "HEADER")
                    and not nxt.get("is_structural")
                    and is_indented
                    and no_pipe
                ):
                    # Case B: promote genuine bullet content to BULLET_POINT.
                    nxt["classification"] = "BULLET_POINT"
                    nxt["bullet_glyph_rect"] = list(blk["rect"])
                    blk["glyph_paired"] = True  # atomic with content block in build_refined_pdf
                    bullet_id = len(bullets)
                    normalized_bullet = normalize_bullet_text(nxt["text"])
                    line_count = len([ln for ln in nxt["text"].splitlines() if ln.strip()])
                    bullet_data = {
                        "id": bullet_id,
                        "page_index": page_index,
                        "block_index": i + 1,
                        "text": normalized_bullet or nxt["text"],
                        "original_text": normalized_bullet or nxt["text"],
                        "char_count": len(normalized_bullet or nxt["text"]),
                        "line_count": max(1, line_count),
                        "rect": nxt["rect"],
                        "font": nxt.get("font", SAFE_FONT_REGULAR),
                        "size": nxt.get("size", 10.0),
                        "line_height": nxt.get("line_height", 1.05),
                        "color": nxt.get("color", 0),
                    }
                    bullets.append(bullet_data)
                    nxt["bullet_id"] = bullet_id
                    nxt["text"] = normalized_bullet or nxt["text"]
                # Case C: glyph already marked for removal, content stays unchanged.
            # ─────────────────────────────────────────────────────────────────

            # Backfill line_count on bullets registered in the first pass.
            for blk in blocks:
                if blk.get("classification") == "BULLET_POINT" and "bullet_id" in blk:
                    bid = blk["bullet_id"]
                    if bid < len(bullets) and "line_count" not in bullets[bid]:
                        lc = len([ln for ln in blk.get("text", "").splitlines() if ln.strip()])
                        bullets[bid]["line_count"] = max(1, lc)

            pages.append({"page_index": page_index, "blocks": blocks})

        document.close()
        return {
            "text": collapse_blank_lines("\n\n".join(page_text)),
            "pages": pages,
            "bullets": bullets,
        }

    if file_extension == "docx":
        document = Document(BytesIO(file_bytes))
        paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
        return {"text": collapse_blank_lines("\n".join(paragraphs)), "pages": [], "bullets": []}

    raise ValueError("Unsupported file type. Please upload a PDF or DOCX resume.")


def extract_keywords(job_description: str, limit: int = 20) -> list[str]:
    tokens = re.findall(r"[A-Za-z][A-Za-z+/#.&-]{1,}", job_description)
    counts = Counter(token for token in tokens if normalize_text(token) not in STOPWORDS)
    multi_word = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b", job_description)
    for phrase in multi_word:
        counts[phrase] += 2
    ordered = [keyword for keyword, _ in counts.most_common(limit * 3)]
    seen: set[str] = set()
    result: list[str] = []
    for keyword in ordered:
        normalized = normalize_text(keyword)
        if normalized in seen:
            continue
        seen.add(normalized)
        result.append(keyword.strip())
        if len(result) >= limit:
            break
    return result


def calculate_ats_score(resume_text: str, keywords: list[str]) -> tuple[int, list[str], list[str]]:
    normalized_resume = normalize_text(resume_text)
    matched = [keyword for keyword in keywords if normalize_text(keyword) in normalized_resume]
    missing = [keyword for keyword in keywords if normalize_text(keyword) not in normalized_resume]
    if not keywords:
        return 0, matched, missing
    score = round((len(matched) / len(keywords)) * 100)
    return score, matched, missing


def create_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing. Add it to your .env file and restart the app.")
    return OpenAI(api_key=api_key)


def refine_resume(client: OpenAI, resume_text: str, job_description: str) -> str:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Resume:\n{resume_text}\n\nJob Description:\n{job_description}"},
        ],
    )
    return clean_resume_output(response.output_text)


def generate_improvement_suggestions(client: OpenAI, resume_text: str, job_description: str) -> list[str]:
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": SUGGESTIONS_PROMPT},
            {"role": "user", "content": f"Resume:\n{resume_text}\n\nJob Description:\n{job_description}"},
        ],
    )
    lines = [re.sub(r"^[-*\d.\s]+", "", line).strip() for line in response.output_text.splitlines() if line.strip()]
    return lines[:5]


def generate_download_filename(original_filename: str) -> str:
    original = Path(original_filename)
    return f"{original.stem}_resumerefine.pdf"


def _bullet_char_bounds(bullet: dict[str, Any]) -> tuple[int, int]:
    """Return (min_chars, max_chars) for a bullet rewrite.

    Single-line bullets get a small ±8 % window so rewrites can incorporate
    keywords without pushing content onto a second line.  Multi-line bullets
    get a ±12 % window.  The AI is also told to stay within these bounds.
    """
    original = bullet["char_count"]
    is_single_line = bullet.get("line_count", 1) == 1
    if is_single_line:
        min_chars = max(10, int(round(original * 0.88)))
        max_chars = max(min_chars + 4, int(round(original * 1.08)))
    else:
        min_chars = max(10, int(round(original * 0.85)))
        max_chars = max(min_chars + 4, int(round(original * 1.12)))
    return min_chars, max_chars


def build_bullet_rewrite_request(bullets: list[dict[str, Any]], strict: bool = False) -> str:
    intro = "Stay within the exact length bounds." if strict else "Stay as close as possible to the original length bounds."
    rows = [intro]
    for bullet in bullets:
        min_chars, max_chars = _bullet_char_bounds(bullet)
        rows.append(f"{bullet['id']}::min={min_chars}::max={max_chars}::bullet={bullet['original_text']}")
    return "\n".join(rows)


def parse_bullet_rewrite_response(response_text: str) -> dict[int, str]:
    rewrites: dict[int, str] = {}
    for raw_line in response_text.splitlines():
        line = raw_line.strip()
        match = re.match(r"^(\d+)::(.*)$", line)
        if not match:
            continue
        bullet_id = int(match.group(1))
        bullet_text = normalize_bullet_text(match.group(2))
        if bullet_text:
            rewrites[bullet_id] = bullet_text
    return rewrites


def is_valid_bullet_rewrite(original_bullet: dict[str, Any], rewritten_text: str) -> bool:
    if not rewritten_text or not rewritten_text.startswith("• "):
        return False
    min_chars, max_chars = _bullet_char_bounds(original_bullet)
    return min_chars <= len(rewritten_text) <= max_chars


def rewrite_bullet_batch(client: OpenAI, bullets: list[dict[str, Any]], job_description: str, strict: bool = False, suggestions: list[str] | None = None) -> dict[int, str]:
    if not bullets:
        return {}

    suggestions_block = ""
    if suggestions:
        suggestions_block = "\n\nKey improvements to apply where relevant:\n" + "\n".join(f"- {s}" for s in suggestions)

    response = client.responses.create(
        model="gpt-4.1-mini",
        input=[
            {"role": "system", "content": BULLET_REWRITE_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Job Description:\n{job_description}"
                    f"{suggestions_block}\n\n"
                    f"Rewrite these bullets in order:\n{build_bullet_rewrite_request(bullets, strict=strict)}"
                ),
            },
        ],
    )
    parsed = parse_bullet_rewrite_response(response.output_text)
    return {bullet["id"]: parsed[bullet["id"]] for bullet in bullets if bullet["id"] in parsed}


def rewrite_pdf_bullets(client: OpenAI, bullets: list[dict[str, Any]], job_description: str, suggestions: list[str] | None = None) -> dict[int, str]:
    rewritten: dict[int, str] = {}

    for start in range(0, len(bullets), MAX_BATCH_BULLETS):
        batch = bullets[start:start + MAX_BATCH_BULLETS]
        first_pass = rewrite_bullet_batch(client, batch, job_description, strict=False, suggestions=suggestions)
        invalid = [
            bullet for bullet in batch
            if bullet["id"] not in first_pass or not is_valid_bullet_rewrite(bullet, first_pass[bullet["id"]])
        ]
        for bullet in batch:
            candidate = first_pass.get(bullet["id"])
            if candidate and bullet not in invalid:
                rewritten[bullet["id"]] = candidate

        if invalid:
            second_pass = rewrite_bullet_batch(client, invalid, job_description, strict=True, suggestions=suggestions)
            for bullet in invalid:
                candidate = second_pass.get(bullet["id"])
                rewritten[bullet["id"]] = candidate if candidate and is_valid_bullet_rewrite(bullet, candidate) else bullet["original_text"]

    for bullet in bullets:
        rewritten.setdefault(bullet["id"], bullet["original_text"])
    return rewritten


def build_refined_resume_text(pages_data: list[dict[str, Any]], bullet_rewrites: dict[int, str]) -> str:
    ordered_blocks: list[str] = []
    for page_data in pages_data:
        for block in page_data.get("blocks", []):
            if block.get("is_structural"):
                continue
            if block.get("classification") == "BULLET_POINT" and "bullet_id" in block:
                ordered_blocks.append(bullet_rewrites.get(block["bullet_id"], block["text"]))
            else:
                ordered_blocks.append(block.get("text", ""))
    return collapse_blank_lines("\n\n".join(block for block in ordered_blocks if block.strip()))


def try_insert_textbox(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    font_name: str,
    font_size: float,
    color: tuple[float, float, float],
    line_height: float,
) -> bool:
    shape = page.new_shape()
    try:
        remaining = shape.insert_textbox(
            rect,
            text,
            fontname=font_name,
            fontsize=font_size,
            color=color,
            align=fitz.TEXT_ALIGN_LEFT,
            lineheight=line_height,
        )
    except Exception:
        return False
    if remaining < 0:
        return False
    shape.commit(overlay=True)
    return True


def _test_text_fits(rect: fitz.Rect, text: str, font_name: str, font_size: float, line_height: float) -> bool:
    """Test if text fits in a rect WITHOUT modifying any real page (uses a throwaway doc)."""
    try:
        tmp = fitz.open()
        p = tmp.new_page(width=max(rect.width + 20, 100), height=max(rect.height * 4, 100))
        shape = p.new_shape()
        remaining = shape.insert_textbox(
            fitz.Rect(0, 0, rect.width, rect.height * 3),
            text,
            fontname=font_name,
            fontsize=font_size,
            align=fitz.TEXT_ALIGN_LEFT,
            lineheight=line_height,
        )
        tmp.close()
        return remaining >= 0
    except Exception:
        return False


def _register_page_fonts(document: fitz.Document, page: fitz.Page) -> None:
    """Register fonts embedded in this PDF page so insert_textbox can reuse the original font."""
    try:
        for font_info in page.get_fonts(full=True):
            xref = font_info[0]
            basefont = font_info[3]  # PostScript / basefont name
            if xref == 0 or not basefont:
                continue
            font_data = document.extract_font(xref)
            # extract_font → (basename, ext, subtype, buffer, referencer)
            if not font_data or not font_data[3]:
                continue
            try:
                page.insert_font(fontname=basefont, fontbuffer=font_data[3])
            except Exception:
                pass
    except Exception:
        pass


def fit_bullet_text_to_block(page: fitz.Page, block: dict[str, Any], text: str) -> None:
    replacement_text = normalize_bullet_text(text) or block.get("text", "")
    original_text = normalize_bullet_text(block.get("text", "")) or block.get("text", "")
    rect = fitz.Rect(block["rect"])
    color = pdf_color_tuple(block.get("color", 0))
    base_font_size = min(float(block.get("size", 10.0)), MAX_FONT_SIZE)
    minimum_font_size = MIN_FONT_SIZE
    line_height = float(block.get("line_height", 1.05))
    font_candidates: list[str] = []
    for candidate in [block.get("font", ""), safe_pdf_font_name(block.get("font", ""))]:
        if candidate and candidate not in font_candidates:
            font_candidates.append(candidate)

    for candidate_text in [replacement_text, original_text]:
        for font_name in font_candidates:
            font_size = base_font_size
            while font_size >= minimum_font_size - 0.001:
                if try_insert_textbox(page, rect, candidate_text, font_name, font_size, color, line_height):
                    return
                font_size -= 0.25


def _safe_redact_and_insert(
    page: fitz.Page,
    block: dict[str, Any],
    rewritten_text: str,
) -> None:
    """
    Redact a single bullet block and insert replacement text.

    The previous approach used a Helvetica-based fit pre-check which was too
    conservative: Helvetica is ~15 % wider than the common serif/narrow fonts
    used in resumes, so the check rejected valid rewrites and left blocks
    untouched (0 changes) or, for two-block bullets, left white gaps after the
    glyph block was already erased.

    New approach: always proceed.  fit_bullet_text_to_block cascades through
    the registered original font → Helvetica fallback and shrinks the font size
    down to MIN_FONT_SIZE, so it almost never fails to produce output.  The only
    safety net we keep is a degenerate-case guard using MIN_FONT_SIZE + wide
    rect so we still skip if the text is genuinely unrenderable.
    """
    rect = fitz.Rect(block["rect"])
    font_size = min(float(block.get("size", 10.0)), MAX_FONT_SIZE)
    line_height = float(block.get("line_height", 1.05))
    original = normalize_bullet_text(block.get("text", "")) or block.get("text", "")

    # Degenerate guard only: test at MIN_FONT_SIZE with a very generous rect
    # (3× width, 5× height).  If even that fails, skip to avoid a blank area.
    generous = fitz.Rect(0, 0, rect.width * 3, rect.height * 5)
    if not _test_text_fits(generous, original, SAFE_FONT_REGULAR, MIN_FONT_SIZE, line_height):
        return

    # Redact without inset — the 1 pt shrink was masking the leftmost pixel of
    # the bullet glyph on narrow rects.
    page.add_redact_annot(rect, fill=(1, 1, 1))
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
    fit_bullet_text_to_block(page, block, rewritten_text)


def build_refined_pdf(file_bytes: bytes, pages_data: list[dict[str, Any]], bullet_rewrites: dict[int, str]) -> bytes:
    document = fitz.open(stream=file_bytes, filetype="pdf")

    for page_data in pages_data:
        page = document[page_data["page_index"]]

        # Register embedded fonts so insert_textbox can use the original typeface.
        _register_page_fonts(document, page)

        # Step 1: Remove ONLY stray lone-glyph blocks that are NOT paired with a
        # bullet content block (Case C in extract_resume_data).  Paired glyph
        # blocks (Cases A/B, marked glyph_paired=True) are handled atomically in
        # Step 2 via the expanded rect, so we must NOT erase them here — doing so
        # would leave the content block without its bullet marker if Step 2 later
        # fails to reinsert.
        for block in page_data.get("blocks", []):
            if block.get("needs_redact") and not block.get("glyph_paired"):
                glyph_rect = fitz.Rect(block["rect"])
                page.add_redact_annot(glyph_rect, fill=(1, 1, 1))
                page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

        # Step 2: Rewrite every detected bullet block.
        bullet_blocks = [
            block for block in page_data.get("blocks", [])
            if block.get("classification") == "BULLET_POINT" and not block.get("is_structural")
        ]

        for block in bullet_blocks:
            bullet_id = block.get("bullet_id")
            rewritten_text = bullet_rewrites.get(bullet_id, block.get("text", ""))

            # For two-block bullets the content rect starts to the right of the
            # glyph block.  Expand it leftward so the • sits at the correct
            # horizontal position.
            if block.get("bullet_glyph_rect"):
                glyph_r = fitz.Rect(block["bullet_glyph_rect"])
                content_r = fitz.Rect(block["rect"])
                expanded = fitz.Rect(
                    min(glyph_r.x0, content_r.x0),
                    content_r.y0,
                    content_r.x1,
                    content_r.y1,
                )
                block_copy = dict(block)
                block_copy["rect"] = list(expanded)
                _safe_redact_and_insert(page, block_copy, rewritten_text)
            else:
                _safe_redact_and_insert(page, block, rewritten_text)

    buffer = BytesIO()
    document.save(buffer, garbage=4, deflate=True)
    document.close()
    buffer.seek(0)
    return buffer.getvalue()


def initialize_state() -> None:
    if "results" not in st.session_state:
        st.session_state.results = None


def process_resume_request(uploaded_resume: Any, job_description: str) -> dict[str, Any]:
    file_bytes = uploaded_resume.getvalue()
    file_extension = uploaded_resume.name.lower().split(".")[-1]
    resume_data = extract_resume_data(file_bytes, file_extension)
    resume_text = resume_data["text"]
    if not resume_text:
        raise ValueError("We could not extract readable text from that file. Try another PDF or DOCX version.")

    keywords = extract_keywords(job_description)
    score, _, missing_keywords = calculate_ats_score(resume_text, keywords)
    client = create_openai_client()
    suggestions = generate_improvement_suggestions(client, resume_text, job_description)

    refined_pdf_bytes = None
    download_filename = "refined_resume.pdf"

    if file_extension == "pdf" and resume_data.get("bullets"):
        bullet_rewrites = rewrite_pdf_bullets(client, resume_data["bullets"], job_description, suggestions)
        refined_resume = build_refined_resume_text(resume_data["pages"], bullet_rewrites)
        refined_pdf_bytes = build_refined_pdf(file_bytes, resume_data["pages"], bullet_rewrites)
        download_filename = generate_download_filename(uploaded_resume.name)
    else:
        refined_resume = refine_resume(client, resume_text, job_description)
        if file_extension == "pdf":
            fallback_bullets = {
                block["bullet_id"]: block["text"]
                for page in resume_data["pages"]
                for block in page.get("blocks", [])
                if block.get("classification") == "BULLET_POINT" and "bullet_id" in block
            }
            refined_pdf_bytes = build_refined_pdf(file_bytes, resume_data["pages"], fallback_bullets)
            download_filename = generate_download_filename(uploaded_resume.name)

    return {
        "score": score,
        "missing_keywords": missing_keywords,
        "suggestions": suggestions,
        "refined_resume": refined_resume,
        "download_bytes": refined_pdf_bytes,
        "download_filename": download_filename,
        "file_extension": file_extension,
    }


def main() -> None:
    from ui_shell import render_app

    st.set_page_config(page_title="ResumeRefine", page_icon=":page_facing_up:", layout="wide")
    initialize_state()
    render_app(process_resume_request)


if __name__ == "__main__":
    main()
