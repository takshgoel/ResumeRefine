import math
from html import escape
from typing import Any, Callable

import streamlit as st
import streamlit.components.v1 as components
from openai import APIError, AuthenticationError

Results = dict[str, Any]
ProcessResume = Callable[[Any, str], Results]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def score_color(score: int) -> str:
    if score < 50:
        return "#EF4444"
    if score <= 74:
        return "#F59E0B"
    return "#22C55E"


# ---------------------------------------------------------------------------
# Styles  — all card styling is applied via CSS to Streamlit's own DOM
# elements so we never inject orphaned <div> wrappers.
# ---------------------------------------------------------------------------

def render_global_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

        :root {
            --bg:            #0A0A0F;
            --surface:       #111118;
            --border:        #1E1E2E;
            --border-hover:  #2D2D45;
            --accent:        #7C6FF7;
            --accent-hover:  #9B96F9;
            --success:       #22C55E;
            --warning:       #F59E0B;
            --danger:        #EF4444;
            --text-primary:  #F1F0FF;
            --text-secondary:#8B8BA7;
            --text-muted:    #4A4A65;
            --input-bg:      #0D0D14;
        }

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
        }

        .stApp {
            background: var(--bg) !important;
            color: var(--text-primary);
        }

        /* ── NUKE all Streamlit chrome ── */
        header[data-testid="stHeader"],
        [data-testid="stToolbar"],
        [data-testid="stDecoration"],
        [data-testid="stStatusWidget"],
        .stDeployButton,
        #MainMenu,
        footer,
        [data-testid="stHeader"] {
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            visibility: hidden !important;
            overflow: hidden !important;
            position: fixed !important;
            top: -999px !important;
        }

        .block-container {
            max-width: 1200px !important;
            padding: 0 32px 40px !important;
            margin: 0 auto;
        }

        /* ── NAV ── */
        .nav-bar {
            background: var(--bg);
            border-bottom: 1px solid var(--border);
            padding: 0 32px;
            margin: 0 -32px 0;
        }
        .nav-bar-inner {
            display: flex;
            align-items: center;
            justify-content: space-between;
            max-width: 1200px;
            margin: 0 auto;
            height: 56px;
        }
        .logo {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 20px;
            font-weight: 700;
            color: var(--text-primary);
            text-decoration: none !important;
            display: flex;
            align-items: center;
            gap: 10px;
            letter-spacing: -0.02em;
        }
        .logo-icon {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            background: linear-gradient(135deg, #7C6FF7, #a78bfa);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            color: white;
            flex-shrink: 0;
        }
        .nav-tagline {
            font-size: 13px;
            color: var(--text-muted);
            font-weight: 400;
        }

        /* ── HERO ── */
        .hero-header {
            text-align: center;
            padding: 48px 0 12px;
        }
        .hero-header h1 {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 40px;
            font-weight: 700;
            color: var(--text-primary);
            margin: 0 0 14px;
            line-height: 1.15;
            letter-spacing: -0.03em;
        }
        .hero-header h1 em {
            font-style: normal;
            background: linear-gradient(135deg, #9B96F9, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .hero-header p {
            font-size: 16px;
            color: var(--text-secondary);
            margin: 0 auto;
            line-height: 1.65;
            max-width: 600px;
        }
        .hero-chips {
            display: flex;
            justify-content: center;
            gap: 10px;
            margin-top: 20px;
            flex-wrap: wrap;
        }
        .hero-chip {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 6px 14px;
            border-radius: 999px;
            background: rgba(124, 111, 247, 0.08);
            border: 1px solid rgba(124, 111, 247, 0.18);
            color: #c4b5fd;
            font-size: 12px;
            font-weight: 500;
        }
        .hero-chip .dot {
            width: 6px;
            height: 6px;
            border-radius: 999px;
            background: var(--accent);
        }

        /* ── COLUMN CARD STYLING ──
           Style Streamlit's column containers as cards rather than
           injecting orphaned <div> wrappers. */
        [data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px !important;
            transition: border-color 0.2s;
        }
        [data-testid="stColumn"] > div[data-testid="stVerticalBlockBorderWrapper"] > div:hover {
            border-color: var(--border-hover);
        }

        /* ── SECTION LABELS ── */
        .section-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.12em;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 4px;
        }
        .subsection-title {
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
            margin: 20px 0 10px;
        }

        /* ── STREAMLIT BUTTONS ── */
        .stButton > button, .stFormSubmitButton > button {
            background: linear-gradient(135deg, #7C6FF7, #9B96F9) !important;
            color: #fff !important;
            border: none !important;
            border-radius: 10px !important;
            height: 46px !important;
            font-size: 14px !important;
            font-weight: 600 !important;
            font-family: 'Inter', sans-serif !important;
            transition: all 0.2s !important;
            box-shadow: 0 4px 16px rgba(124, 111, 247, 0.25) !important;
            letter-spacing: 0.01em !important;
        }
        .stButton > button:hover, .stFormSubmitButton > button:hover {
            background: linear-gradient(135deg, #9B96F9, #b4aefb) !important;
            box-shadow: 0 6px 24px rgba(124, 111, 247, 0.35) !important;
            transform: translateY(-1px) !important;
        }
        .stButton > button:active {
            transform: translateY(0) !important;
        }

        /* ── TEXTAREA ── */
        .stTextArea textarea {
            background: var(--input-bg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            color: var(--text-primary) !important;
            font-size: 14px !important;
            font-family: 'Inter', sans-serif !important;
            resize: vertical !important;
            padding: 14px 16px !important;
            line-height: 1.6 !important;
            transition: border-color 0.2s, box-shadow 0.2s !important;
        }
        .stTextArea textarea:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(124,111,247,0.12) !important;
            outline: none !important;
        }
        .stTextArea label {
            color: var(--text-secondary) !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: 0.1em !important;
            text-transform: uppercase !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* ── TEXT INPUT ── */
        .stTextInput input {
            background: var(--input-bg) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
            color: var(--text-primary) !important;
            font-size: 14px !important;
            font-family: 'Inter', sans-serif !important;
            padding: 10px 14px !important;
        }
        .stTextInput input:focus {
            border-color: var(--accent) !important;
            box-shadow: 0 0 0 3px rgba(124,111,247,0.12) !important;
        }
        .stTextInput label {
            color: var(--text-secondary) !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: 0.1em !important;
            text-transform: uppercase !important;
            font-family: 'Inter', sans-serif !important;
        }

        /* ── FILE UPLOADER ── */
        .stFileUploader section {
            background: var(--input-bg) !important;
            border: 1px dashed var(--border-hover) !important;
            border-radius: 10px !important;
            padding: 24px 20px !important;
            transition: border-color 0.2s !important;
        }
        .stFileUploader section:hover { border-color: var(--accent) !important; }
        .stFileUploader label {
            color: var(--text-secondary) !important;
            font-size: 11px !important;
            font-weight: 600 !important;
            letter-spacing: 0.1em !important;
            text-transform: uppercase !important;
            font-family: 'Inter', sans-serif !important;
        }
        .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] p,
        .stFileUploader [data-testid="stFileUploaderDropzoneInstructions"] span {
            color: var(--text-secondary) !important;
            font-size: 13px !important;
        }
        .stFileUploader small { color: var(--text-muted) !important; }
        .stFileUploader [data-testid="stFileUploaderFile"] {
            background: rgba(124, 111, 247, 0.06) !important;
            border-radius: 8px !important;
        }

        /* ── TABS ── */
        [data-testid="stTabs"] [role="tablist"] {
            border-bottom: 1px solid var(--border) !important;
            gap: 0 !important;
            background: transparent !important;
        }
        [data-testid="stTabs"] button[role="tab"] {
            color: var(--text-muted) !important;
            background: transparent !important;
            border: none !important;
            border-bottom: 2px solid transparent !important;
            padding: 12px 22px !important;
            font-size: 13px !important;
            font-weight: 600 !important;
            font-family: 'Inter', sans-serif !important;
            text-transform: uppercase !important;
            letter-spacing: 0.06em !important;
            transition: color 0.15s, border-color 0.15s !important;
        }
        [data-testid="stTabs"] button[role="tab"]:hover {
            color: var(--text-secondary) !important;
        }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
            color: var(--text-primary) !important;
            border-bottom: 2px solid var(--accent) !important;
            background: transparent !important;
        }
        [data-testid="stTabs"] [role="tabpanel"] { padding-top: 20px !important; }

        /* ── SCORE RING ── */
        .score-wrap {
            text-align: center;
            margin-bottom: 24px;
        }
        .score-ring-wrap {
            position: relative;
            width: 140px;
            height: 140px;
            margin: 0 auto 10px;
        }
        .score-overlay {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            text-align: center;
            line-height: 1;
            pointer-events: none;
        }
        .score-num {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 36px;
            font-weight: 700;
            line-height: 1;
        }
        .score-desc-sm {
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 4px;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            font-weight: 600;
        }
        .score-descriptor {
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
        }

        /* ── STAT GRID ── */
        .stat-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: var(--input-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            transition: border-color 0.2s;
        }
        .stat-card:hover { border-color: var(--border-hover); }
        .stat-value {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 22px;
            font-weight: 700;
            color: var(--text-primary);
            line-height: 1;
            margin-bottom: 6px;
        }
        .stat-label {
            font-size: 10px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.08em;
            font-weight: 500;
        }

        /* ── KEYWORD PILLS ── */
        .keywords-wrap {
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-bottom: 4px;
        }
        .keyword-pill {
            background: rgba(124, 111, 247, 0.06);
            border: 1px solid rgba(124, 111, 247, 0.15);
            color: #c4b5fd;
            border-radius: 999px;
            padding: 5px 12px;
            font-size: 12px;
            font-weight: 500;
            font-family: 'Inter', sans-serif;
            transition: background 0.2s, border-color 0.2s;
        }
        .keyword-pill:hover {
            background: rgba(124, 111, 247, 0.12);
            border-color: rgba(124, 111, 247, 0.3);
        }

        /* ── SUGGESTION CARDS ── */
        .suggestion-card {
            display: flex;
            gap: 12px;
            align-items: flex-start;
            background: var(--input-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 14px 16px;
            margin-bottom: 8px;
            transition: border-color 0.2s;
        }
        .suggestion-card:hover { border-color: var(--border-hover); }
        .suggestion-num {
            width: 24px;
            height: 24px;
            min-width: 24px;
            border-radius: 999px;
            background: var(--accent);
            color: #fff;
            font-size: 11px;
            font-weight: 700;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .suggestion-text {
            font-size: 13px;
            color: var(--text-secondary);
            line-height: 1.65;
        }

        /* ── OUTPUT AREA ── */
        .output-content {
            background: var(--input-bg);
            border: 1px solid var(--border);
            border-radius: 10px;
            padding: 20px;
            max-height: 480px;
            overflow-y: auto;
        }
        .output-pre {
            white-space: pre-wrap;
            word-break: break-word;
            margin: 0;
            font-family: 'Inter', sans-serif;
            font-size: 13px;
            line-height: 1.8;
            color: var(--text-primary);
        }

        /* ── EMPTY STATE ── */
        .empty-state {
            color: var(--text-muted);
            font-size: 14px;
            line-height: 1.65;
            margin-top: 8px;
        }
        .empty-icon {
            font-size: 40px;
            margin-bottom: 12px;
            opacity: 0.4;
        }

        /* ── AUTH / LEGAL ── */
        .auth-shell {
            max-width: 480px;
            margin: 0 auto;
            padding: 2rem 0 4rem;
        }
        .glass-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 14px;
            padding: 28px;
            margin-bottom: 16px;
        }
        .legal-shell {
            max-width: 860px;
            margin: 0 auto;
            padding: 2rem 0 4rem;
        }
        .legal-shell h1, .auth-shell h1 {
            font-family: 'Space Grotesk', sans-serif;
            font-size: 26px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: 8px;
            letter-spacing: -0.02em;
        }
        .tiny-label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.12em;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 10px;
        }
        .legal-copy { color: var(--text-secondary); line-height: 1.75; }

        /* ── ALERTS ── */
        [data-testid="stAlert"] {
            background: var(--surface) !important;
            border: 1px solid var(--border) !important;
            border-radius: 10px !important;
        }

        /* ── SPINNER ── */
        [data-testid="stSpinner"] {
            color: var(--text-secondary) !important;
        }

        /* ── RESPONSIVE ── */
        @media (max-width: 768px) {
            .block-container { padding: 0 16px 24px !important; }
            .nav-bar { margin: 0 -16px; padding: 0 16px; }
            .hero-header { padding: 32px 0 8px; }
            .hero-header h1 { font-size: 28px; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

def render_navbar() -> None:
    st.markdown(
        """
        <div class="nav-bar">
            <div class="nav-bar-inner">
                <a class="logo" href="?page=home">
                    <div class="logo-icon">R</div>
                    ResumeRefine
                </a>
                <span class="nav-tagline">AI-powered resume optimization</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

def render_page_header() -> None:
    st.markdown(
        """
        <div class="hero-header">
            <h1>See How Your Resume Scores<br>for Your <em>Dream Job</em></h1>
            <p>Upload your resume, paste the job post, and instantly get your ATS match score, missing keywords, tailored suggestions, and a ready-to-send cover letter.</p>
            <div class="hero-chips">
                <span class="hero-chip"><span class="dot"></span> ATS Score Analysis</span>
                <span class="hero-chip"><span class="dot"></span> Keyword Gap Detection</span>
                <span class="hero-chip"><span class="dot"></span> AI Cover Letter</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Cover letter generator  (OpenAI API)
# ---------------------------------------------------------------------------

COVER_LETTER_SYSTEM = (
    "You are a professional cover letter writer. Write a compelling, well-structured "
    "cover letter of approximately 500 words tailored to the job description provided. "
    "Paragraph 1: strong opening that names the role, the company, and shows genuine "
    "enthusiasm for the opportunity. "
    "Paragraph 2: highlight 2-3 specific achievements from the resume that directly "
    "match the most critical job requirements — use numbers and outcomes where possible. "
    "Paragraph 3: connect additional skills, tools, or experiences that demonstrate "
    "broader value and cultural fit for the team. "
    "Paragraph 4: address any unique qualifications or differentiators that set this "
    "candidate apart from others. "
    "Paragraph 5: confident closing with a clear call to action and availability. "
    "Do not use generic filler phrases. Aim for approximately 500 words. "
    "Return only the cover letter text, no labels or headers."
)


def generate_cover_letter(refined_resume: str, job_description: str) -> str:
    from openai import OpenAI

    client = OpenAI()  # uses OPENAI_API_KEY from env
    response = client.responses.create(
        model="gpt-4.1-mini",
        instructions=COVER_LETTER_SYSTEM,
        input=f"Resume:\n{refined_resume}\n\nJob Description:\n{job_description}",
    )
    return response.output_text


# ---------------------------------------------------------------------------
# Analysis panel components
# ---------------------------------------------------------------------------

def render_score_ring(score: int) -> None:
    color = score_color(score)
    descriptor = (
        "You're in great shape!" if score >= 75
        else "Getting there — a few tweaks will help" if score >= 50
        else "Needs some work — check the suggestions below"
    )
    r = 52
    circumference = 2 * math.pi * r
    dash = (score / 100) * circumference
    gap = circumference - dash
    st.markdown(
        f"""
        <div class="score-wrap">
            <div class="score-ring-wrap">
                <svg width="140" height="140" viewBox="0 0 140 140">
                    <circle cx="70" cy="70" r="{r}" fill="none"
                        stroke="#1E1E2E" stroke-width="7"/>
                    <circle cx="70" cy="70" r="{r}" fill="none"
                        stroke="{color}" stroke-width="7"
                        stroke-dasharray="{dash:.2f} {gap:.2f}"
                        stroke-linecap="round"
                        transform="rotate(-90 70 70)"
                        style="transition: stroke-dasharray 0.6s ease;"/>
                </svg>
                <div class="score-overlay">
                    <div class="score-num" style="color:{color};">{score}%</div>
                    <div class="score-desc-sm">ATS Match</div>
                </div>
            </div>
            <div class="score-descriptor">{descriptor}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_grid(results: Results) -> None:
    score = results.get("score", 0)
    ext = results.get("file_extension", "")
    export_val = "PDF" if ext == "pdf" else "DOCX" if ext else "—"
    alignment = "High" if score >= 75 else "Mid" if score >= 50 else "Low"
    keywords_count = len(results.get("missing_keywords", []))

    stats = [
        ("Keyword Gaps", str(keywords_count)),
        ("Bullets Refined", "✓"),
        ("Role Alignment", alignment),
        ("Export Ready", export_val),
    ]
    cards_html = "".join(
        f"""<div class="stat-card">
                <div class="stat-value">{escape(val)}</div>
                <div class="stat-label">{escape(label)}</div>
            </div>"""
        for label, val in stats
    )
    st.markdown(f'<div class="stat-grid">{cards_html}</div>', unsafe_allow_html=True)


def render_keyword_badges(missing_keywords: list[str]) -> None:
    if not missing_keywords:
        st.markdown(
            "<p class='empty-state' style='font-size:13px;color:var(--success);'>"
            "Nice — your resume already covers the top keywords.</p>",
            unsafe_allow_html=True,
        )
        return
    badges = "".join(
        f"<span class='keyword-pill'>{escape(kw)}</span>" for kw in missing_keywords
    )
    st.markdown(f"<div class='keywords-wrap'>{badges}</div>", unsafe_allow_html=True)


def render_suggestions(suggestions: list[str]) -> None:
    for i, s in enumerate(suggestions, 1):
        st.markdown(
            f"""<div class="suggestion-card">
                    <div class="suggestion-num">{i}</div>
                    <div class="suggestion-text">{escape(s)}</div>
                </div>""",
            unsafe_allow_html=True,
        )


def render_analysis_panel(
    score: int,
    missing_keywords: list[str],
    suggestions: list[str],
    results: Results,
) -> None:
    st.markdown("<div class='section-label'>YOUR RESULTS</div>", unsafe_allow_html=True)
    render_score_ring(score)
    render_stat_grid(results)
    st.markdown("<div class='subsection-title'>Keywords You're Missing</div>", unsafe_allow_html=True)
    render_keyword_badges(missing_keywords)
    st.markdown("<div class='subsection-title'>How to Improve</div>", unsafe_allow_html=True)
    if suggestions:
        render_suggestions(suggestions)
    else:
        st.markdown(
            "<p class='empty-state'>Suggestions will appear after analysis.</p>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Output section — tabbed (Refined Resume | Cover Letter)
# ---------------------------------------------------------------------------

def render_output_section(results: Results) -> None:
    tab_resume, tab_cover = st.tabs(["Refined Resume", "Cover Letter"])

    with tab_resume:
        st.markdown(
            f"""<div class="output-content">
                    <pre class="output-pre">{escape(results["refined_resume"])}</pre>
                </div>""",
            unsafe_allow_html=True,
        )

        # ----------------------------------------------------------------
        # DOWNLOAD FEATURE — TEMPORARILY DISABLED
        # Re-enable when PDF export is ready.
        #
        # if results.get('file_extension') == 'pdf' and results.get('download_bytes'):
        #     st.download_button(
        #         'Download Optimized Resume',
        #         data=results['download_bytes'],
        #         file_name=results['download_filename'],
        #         mime='application/pdf',
        #         use_container_width=True,
        #     )
        # else:
        #     st.info(
        #         'PDF-preserving download is currently available only when the '
        #         'uploaded resume is a PDF.'
        #     )
        # ----------------------------------------------------------------

    with tab_cover:
        if "cover_letter" not in st.session_state:
            st.session_state.cover_letter = ""

        if st.button("Write My Cover Letter", key="gen_cl_btn", use_container_width=True):
            job_desc = st.session_state.get("job_description", "")
            if not job_desc:
                st.error("Job description not found. Please re-run the analysis first.")
            else:
                try:
                    with st.spinner("Writing your cover letter…"):
                        st.session_state.cover_letter = generate_cover_letter(
                            results["refined_resume"], job_desc
                        )
                except Exception as exc:
                    st.error(str(exc))

        if st.session_state.cover_letter:
            st.text_area(
                "Generated Cover Letter",
                value=st.session_state.cover_letter,
                height=340,
                key="cl_display",
                label_visibility="collapsed",
            )
            _render_copy_button(st.session_state.cover_letter)


def _render_copy_button(text: str) -> None:
    """Render a styled Copy-to-Clipboard button via a JS component."""
    safe = text.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    components.html(
        f"""
        <style>
            body {{ margin: 0; padding: 4px 0 0; background: transparent; }}
            .copy-btn {{
                background: #1A1A2E;
                border: 1px solid #2D2D45;
                border-radius: 8px;
                color: #8B8BA7;
                font-size: 13px;
                font-weight: 500;
                font-family: 'Inter', sans-serif;
                padding: 8px 18px;
                cursor: pointer;
                transition: all 0.2s;
                float: right;
            }}
            .copy-btn:hover {{ border-color: #7C6FF7; color: #F1F0FF; background: rgba(124,111,247,0.06); }}
            .copy-btn.copied {{ border-color: #22C55E; color: #22C55E; }}
        </style>
        <button class="copy-btn" id="copyBtn" onclick="
            const text = `{safe}`;
            navigator.clipboard.writeText(text).catch(() => {{
                const el = document.createElement('textarea');
                el.value = text;
                el.style.position = 'fixed';
                el.style.opacity = '0';
                document.body.appendChild(el);
                el.select();
                document.execCommand('copy');
                document.body.removeChild(el);
            }});
            const btn = document.getElementById('copyBtn');
            btn.textContent = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {{
                btn.textContent = 'Copy to Clipboard';
                btn.classList.remove('copied');
            }}, 2000);
        ">Copy to Clipboard</button>
        """,
        height=44,
    )


# ---------------------------------------------------------------------------
# Main tool
# ---------------------------------------------------------------------------

def render_resume_tool(process_resume: ProcessResume) -> None:
    if "results" not in st.session_state:
        st.session_state.results = None
    if "cover_letter" not in st.session_state:
        st.session_state.cover_letter = ""
    if "job_description" not in st.session_state:
        st.session_state.job_description = ""

    left_col, right_col = st.columns([0.55, 0.45], gap="large")

    with left_col:
        st.markdown("<div class='section-label'>UPLOAD & ANALYZE</div>", unsafe_allow_html=True)
        uploaded_resume = st.file_uploader(
            "Resume",
            type=["pdf", "docx"],
        )
        job_description = st.text_area(
            "Job Description",
            height=200,
            placeholder="Paste the target job description here…",
        )
        refine_clicked = st.button("Refine My Resume", type="primary", use_container_width=True)

        if refine_clicked:
            if uploaded_resume is None:
                st.error("Please upload a resume in PDF or DOCX format.")
                return
            if not job_description.strip():
                st.error("Please paste a job description first.")
                return
            try:
                with st.spinner("Analyzing your resume — this takes a few seconds…"):
                    st.session_state.results = process_resume(
                        uploaded_resume, job_description.strip()
                    )
                    st.session_state.job_description = job_description.strip()
                    st.session_state.cover_letter = ""
            except ValueError as exc:
                st.error(str(exc))
                return
            except AuthenticationError:
                st.error(
                    "Your OpenAI API key appears to be invalid. "
                    "Update OPENAI_API_KEY in your .env file and restart."
                )
                return
            except APIError as exc:
                st.error(f"OpenAI API error: {exc}")
                return
            except Exception as exc:
                st.error(f"Something went wrong: {exc}")
                return

        # Output tabs directly below the input — no scrolling needed
        if st.session_state.results:
            render_output_section(st.session_state.results)

    with right_col:
        if st.session_state.results:
            render_analysis_panel(
                st.session_state.results["score"],
                st.session_state.results["missing_keywords"],
                st.session_state.results["suggestions"],
                st.session_state.results,
            )
        else:
            st.markdown(
                """<div class='section-label'>OPTIMIZATION INSIGHTS</div>
                <div style="text-align:center; padding: 32px 0;">
                    <div class="empty-icon">📊</div>
                    <div class="empty-state">
                        Your ATS score, missing keywords, and tailored improvement
                        tips will appear here after you hit <strong style="color:var(--text-primary);">Refine My Resume</strong>.
                    </div>
                </div>""",
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Auth / Legal pages
# ---------------------------------------------------------------------------

def render_auth_page(mode: str) -> None:
    is_login = mode == "login"
    title = "Welcome back" if is_login else "Create your ResumeRefine account"
    subtitle = (
        "Access your optimisation workspace and saved resume insights."
        if is_login
        else "Start tailoring resumes with AI-powered ATS guidance."
    )
    st.markdown("<div class='auth-shell'><div class='glass-card'>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='tiny-label'>{'Log In' if is_login else 'Sign Up'}</div>"
        f"<h1>{escape(title)}</h1>"
        f"<div class='legal-copy' style='margin-bottom:1.5rem;'>{escape(subtitle)}</div>",
        unsafe_allow_html=True,
    )
    with st.form("login_form" if is_login else "signup_form"):
        if not is_login:
            st.text_input("Name", placeholder="Taylor Morgan")
        st.text_input("Email", placeholder="you@example.com")
        st.text_input("Password", type="password", placeholder="Enter your password")
        if st.form_submit_button("Log In" if is_login else "Create Account"):
            st.success("Auth UI is ready for backend integration.")
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_legal_page(page: str) -> None:
    title = "Privacy Policy" if page == "privacy" else "Terms and Conditions"
    st.markdown(
        f"<div class='legal-shell'><div class='glass-card'>"
        f"<div class='tiny-label'>Legal</div>"
        f"<h1>{escape(title)}</h1>"
        f"<div class='legal-copy'>Placeholder legal content for the ResumeRefine platform.</div>"
        f"</div></div>",
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# App router
# ---------------------------------------------------------------------------

def render_app(process_resume: ProcessResume) -> None:
    render_global_styles()
    render_navbar()
    page = st.query_params.get("page", "home")
    if page == "login":
        render_auth_page("login")
    elif page == "signup":
        render_auth_page("signup")
    elif page == "privacy":
        render_legal_page("privacy")
    elif page == "terms":
        render_legal_page("terms")
    else:
        render_page_header()
        render_resume_tool(process_resume)
