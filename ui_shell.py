from html import escape
from typing import Any, Callable

import streamlit as st
from openai import APIError, AuthenticationError

Results = dict[str, Any]
ProcessResume = Callable[[Any, str], Results]


def score_color(score: int) -> str:
    if score < 40:
        return "#ef4444"
    if score <= 70:
        return "#fbbf24"
    return "#22c55e"


def render_global_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');
        :root {
            --bg-card: rgba(15, 23, 42, 0.78);
            --bg-card-strong: rgba(10, 15, 32, 0.94);
            --border: rgba(255, 255, 255, 0.10);
            --text-primary: #f8fafc;
            --text-secondary: #cbd5e1;
            --text-muted: #94a3b8;
            --shadow-soft: 0 24px 80px rgba(7, 10, 22, 0.45);
            --shadow-card: 0 18px 48px rgba(5, 10, 25, 0.34);
        }
        html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(124, 92, 255, 0.28), transparent 30%),
                radial-gradient(circle at top right, rgba(168, 85, 247, 0.18), transparent 28%),
                linear-gradient(180deg, #0b1026 0%, #0f172a 40%, #090d1f 100%);
            color: var(--text-primary);
        }
        .stApp [data-testid="stHeader"] { background: transparent; }
        #MainMenu, footer { visibility: hidden; }
        .block-container { padding-top: 1.5rem; padding-bottom: 0; max-width: 1180px; }
        .nav-shell {
            position: sticky;
            top: 0;
            z-index: 999;
            width: 100%;
            margin: -1.5rem 0 0;
            background: rgba(11,16,38,0.6);
            backdrop-filter: blur(10px);
        }
        .nav-inner { display: flex; align-items: center; justify-content: space-between; gap: 24px; max-width: 1200px; margin: 0 auto; padding: 18px 32px; }
        .brand { font-family: 'Inter', sans-serif; font-size: 20px; font-weight: 600; color: white; text-decoration: none; letter-spacing: 0.01em; }
        .nav-links { display: flex; align-items: center; justify-content: center; gap: 32px; flex: 1; }
        .nav-actions { display: flex; align-items: center; gap: 12px; }
        .nav-link, .text-link { color: rgba(255,255,255,0.75); text-decoration: none; font-family: 'Inter', sans-serif; font-size: 15px; font-weight: 500; transition: color 0.2s ease; }
        .nav-link:hover, .text-link:hover { color: white; transform: none; text-shadow: none; }
        .ghost-btn, .gradient-btn { display: inline-flex; align-items: center; justify-content: center; text-decoration: none; font-family: 'Inter', sans-serif; font-size: 15px; font-weight: 500; transition: background 0.2s ease, border-color 0.2s ease, color 0.2s ease, transform 0.2s ease; }
        .ghost-btn { padding: 10px 16px; color: white; border: 1px solid rgba(255,255,255,0.15); border-radius: 8px; background: transparent; }
        .ghost-btn:hover { background: rgba(255,255,255,0.05); box-shadow: none; transform: translateY(-1px); }
        .gradient-btn { padding: 10px 18px; color: white; background: linear-gradient(135deg,#7C5CFF,#A855F7); border: none; border-radius: 10px; box-shadow: 0 12px 28px rgba(124, 92, 255, 0.28); }
        .gradient-btn:hover { box-shadow: 0 16px 32px rgba(124, 92, 255, 0.34); transform: translateY(-1px); }
        .hero { padding: 3.6rem 0 2.6rem; display: grid; grid-template-columns: 1.08fr 0.92fr; gap: 2.6rem; align-items: center; }
        .eyebrow { display: inline-flex; gap: 0.5rem; align-items: center; padding: 0.45rem 0.9rem; border-radius: 999px; background: rgba(124, 92, 255, 0.12); border: 1px solid rgba(124, 92, 255, 0.24); color: #d8ccff; font-size: 0.88rem; font-weight: 600; margin-bottom: 1.25rem; }
        .hero h1 { font-family: 'Space Grotesk', sans-serif; font-size: clamp(3.6rem, 7vw, 5.8rem); line-height: 0.95; letter-spacing: -0.07em; margin: 0; max-width: 9ch; font-weight: 700; }
        .hero p { color: var(--text-secondary); font-size: 1.02rem; line-height: 1.85; max-width: 40rem; margin: 1.55rem 0 0; font-weight: 400; }
        .hero-actions { display: flex; gap: 0.9rem; flex-wrap: wrap; margin-top: 1.75rem; }
        .fade-card { animation: fadeUp 0.75s ease both; }
        @keyframes fadeUp { from { opacity: 0; transform: translateY(16px); } to { opacity: 1; transform: translateY(0); } }
        .hero-visual { position: relative; border-radius: 34px; padding: 1.5rem; min-height: 500px; background: linear-gradient(160deg, rgba(124, 92, 255, 0.22), rgba(17, 24, 39, 0.94)), rgba(15, 23, 42, 0.96); border: 1px solid rgba(124, 92, 255, 0.24); box-shadow: 0 28px 80px rgba(0, 0, 0, 0.46); overflow: hidden; }
        .orb { position: absolute; border-radius: 999px; opacity: 0.9; }
        .orb-one { width: 180px; height: 180px; right: -40px; top: -30px; background: radial-gradient(circle, rgba(168, 85, 247, 0.95), rgba(168, 85, 247, 0)); }
        .orb-two { width: 220px; height: 220px; left: -70px; bottom: -90px; background: radial-gradient(circle, rgba(108, 99, 255, 0.95), rgba(108, 99, 255, 0)); }
        .visual-panel, .glass-card { position: relative; border-radius: 24px; padding: 1.2rem; background: rgba(8, 13, 29, 0.75); border: 1px solid rgba(255, 255, 255, 0.08); backdrop-filter: blur(12px); box-shadow: var(--shadow-card); transition: transform 0.25s ease, box-shadow 0.25s ease, border-color 0.25s ease; }
        .glass-card:hover { transform: translateY(-4px); border-color: rgba(124, 92, 255, 0.32); box-shadow: 0 26px 58px rgba(0, 0, 0, 0.36); }
        .visual-topline, .tiny-label { color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.72rem; }
        .visual-topline { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
        .score-ring { display: flex; align-items: center; justify-content: center; width: 132px; height: 132px; border-radius: 999px; background: conic-gradient(from 180deg, #22c55e 0 78%, rgba(255,255,255,0.08) 78% 100%); margin: 0 auto 1rem; }
        .score-ring-inner { width: 96px; height: 96px; border-radius: 999px; background: rgba(8, 13, 29, 0.95); display: flex; flex-direction: column; justify-content: center; align-items: center; }
        .metric-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.9rem; margin-top: 1rem; }
        .mini-metric { border-radius: 18px; padding: 1rem; background: rgba(255, 255, 255, 0.04); border: 1px solid rgba(255, 255, 255, 0.07); }
        .section-wrap { padding: 1rem 0 0.25rem; margin-top: 4rem; margin-bottom: 1.5rem; }
        .section-kicker { color: #c4b5fd; text-transform: uppercase; letter-spacing: 0.14em; font-size: 0.78rem; font-weight: 700; margin-bottom: 0.65rem; }
        .section-title { font-family: 'Space Grotesk', sans-serif; font-size: clamp(2.1rem, 4vw, 3rem); margin: 0; letter-spacing: -0.05em; font-weight: 700; }
        .section-copy, .card-copy, .legal-copy { color: var(--text-secondary); line-height: 1.75; }
        .section-copy { max-width: 44rem; margin-top: 0.9rem; margin-bottom: 1.4rem; }
        .pill-badge { display: inline-flex; align-items: center; margin: 0.25rem 0.45rem 0.25rem 0; padding: 0.46rem 0.85rem; border-radius: 999px; background: linear-gradient(var(--bg-card-strong), var(--bg-card-strong)) padding-box, linear-gradient(135deg, rgba(108, 99, 255, 0.9), rgba(168, 85, 247, 0.9)) border-box; border: 1px solid transparent; color: #ede9fe; font-size: 0.88rem; font-weight: 600; }
        .preview-card { border-radius: 22px; padding: 1rem; min-height: 520px; max-height: 520px; overflow-y: auto; background: rgba(5, 10, 24, 0.62); border: 1px solid rgba(255, 255, 255, 0.08); }
        .preview-card pre { white-space: pre-wrap; word-wrap: break-word; margin: 0; color: #e2e8f0; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; line-height: 1.6; font-size: 0.92rem; }
        .feature-grid, .pricing-grid, .steps-grid, .footer-grid { display: grid; gap: 1rem; }
        .feature-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); }
        .pricing-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .steps-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
        .footer-grid { grid-template-columns: 1.4fr 1fr 1fr 1fr; }
        .icon-badge, .step-number { display: inline-flex; align-items: center; justify-content: center; border-radius: 16px; margin-bottom: 1rem; }
        .icon-badge { width: 2.8rem; height: 2.8rem; background: linear-gradient(135deg, rgba(108, 99, 255, 0.22), rgba(168, 85, 247, 0.22)); border: 1px solid rgba(255, 255, 255, 0.08); font-size: 1rem; font-weight: 700; }
        .step-number { width: 2.2rem; height: 2.2rem; border-radius: 999px; background: linear-gradient(135deg, #6c63ff, #a855f7); color: white; font-size: 0.95rem; font-weight: 800; }
        .card-title, .footer-title { font-weight: 700; margin-bottom: 0.55rem; color: #ffffff; }
        .price { font-size: 2.5rem; font-weight: 800; letter-spacing: -0.04em; margin: 0.6rem 0 1rem; }
        .price-note, .footer-copy { color: var(--text-muted); }
        .auth-shell, .legal-shell { max-width: 860px; margin: 0 auto; padding: 2rem 0 4rem; }
        .auth-shell { max-width: 520px; }
        .legal-shell h1, .auth-shell h1 { font-family: 'Space Grotesk', sans-serif; letter-spacing: -0.04em; margin-bottom: 0.75rem; }
        .legal-shell h3 { margin-top: 1.5rem; margin-bottom: 0.55rem; font-size: 1.05rem; }
        .footer { margin-top: 3rem; padding: 1.75rem 0 3rem; border-top: 1px solid rgba(255, 255, 255, 0.08); }
        .section-anchor { position: relative; top: -110px; }
        .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button { width: 100%; border-radius: 16px; padding: 0.9rem 1rem; border: 1px solid rgba(255, 255, 255, 0.08); background: linear-gradient(135deg, #6c63ff, #a855f7); color: white; font-weight: 700; box-shadow: 0 14px 30px rgba(108, 99, 255, 0.28); transition: transform 0.2s ease, box-shadow 0.2s ease; }
        .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover { transform: translateY(-2px); box-shadow: 0 18px 34px rgba(108, 99, 255, 0.34); }
        .stTextArea textarea, .stTextInput input, .stFileUploader section { border-radius: 18px !important; border: 1px solid rgba(255, 255, 255, 0.12) !important; background: rgba(7, 12, 26, 0.8) !important; color: var(--text-primary) !important; }
        .stFileUploader label, .stTextArea label, .stTextInput label { color: var(--text-primary) !important; font-weight: 600 !important; }
        div[data-testid="stProgressBar"] > div > div { background-color: rgba(255, 255, 255, 0.08); border-radius: 999px; }
        div[data-testid="stProgressBar"] > div > div > div > div { border-radius: 999px; }
        @media (max-width: 980px) { .hero, .feature-grid, .pricing-grid, .steps-grid, .footer-grid { grid-template-columns: 1fr; } .nav-inner { flex-wrap: wrap; padding: 16px 20px; } .nav-links { width: 100%; justify-content: flex-start; gap: 20px; flex-wrap: wrap; } .nav-actions { margin-left: 0; } .block-container { padding-top: 1rem; } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_navbar() -> None:
    st.markdown(
        """
        <div class="nav-shell">
            <div class="nav-inner">
                <a class="brand" href="?page=home">ResumeRefine</a>
                <div class="nav-links">
                    <a class="nav-link" href="?page=home#platform">Platform</a>
                    <a class="nav-link" href="?page=home#features">Features</a>
                    <a class="nav-link" href="?page=home#how-it-works">How It Works</a>
                    <a class="nav-link" href="?page=home#pricing">Pricing</a>
                    <a class="nav-link" href="?page=home#resources">Resources</a>
                </div>
                <div class="nav-actions">
                    <a class="ghost-btn" href="?page=login">Log In</a>
                    <a class="gradient-btn" href="?page=signup">Start Free Trial</a>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_header(kicker: str, title: str, copy: str) -> None:
    st.markdown(f"<div class='section-wrap fade-card'><div class='section-kicker'>{escape(kicker)}</div><h2 class='section-title'>{escape(title)}</h2><p class='section-copy'>{escape(copy)}</p></div>", unsafe_allow_html=True)
def render_hero() -> None:
    st.markdown("<div class='section-anchor' id='platform'></div>", unsafe_allow_html=True)
    st.markdown("<section class='hero'><div class='fade-card'><div class='eyebrow'>AI Resume Platform | Trusted ATS Optimization</div><h1>Turn Your Resume<br>Into an Interview Magnet</h1><p>AI-powered resume optimization that improves ATS scores and tailors your resume to every job description.</p><div class='hero-actions'><a class='gradient-btn' href='?page=signup'>Start Free Trial</a><a class='ghost-btn' href='#resume-tool'>Try ResumeRefine</a></div></div><div class='hero-visual fade-card'><div class='orb orb-one'></div><div class='orb orb-two'></div><div class='visual-panel' style='margin-top:1rem;'><div class='visual-topline'><span>AI Career Studio</span><span>Live Optimization</span></div><div class='score-ring'><div class='score-ring-inner'><div style='font-size:2rem;font-weight:800;'>92%</div><div class='tiny-label'>ATS Match</div></div></div><div class='metric-grid'><div class='mini-metric'><div class='tiny-label'>Keywords Added</div><div style='font-size:1.4rem;font-weight:800;margin-top:0.35rem;'>18</div></div><div class='mini-metric'><div class='tiny-label'>Bullet Upgrades</div><div style='font-size:1.4rem;font-weight:800;margin-top:0.35rem;'>12</div></div><div class='mini-metric'><div class='tiny-label'>Role Alignment</div><div style='font-size:1.4rem;font-weight:800;margin-top:0.35rem;'>High</div></div><div class='mini-metric'><div class='tiny-label'>Export Ready</div><div style='font-size:1.4rem;font-weight:800;margin-top:0.35rem;'>PDF</div></div></div></div></div></section>", unsafe_allow_html=True)


def render_score_meter(score: int) -> None:
    color = score_color(score)
    descriptor = "Strong match" if score > 70 else "Moderate match" if score >= 40 else "Needs attention"
    st.markdown(f"<div class='glass-card' style='padding:1.25rem;margin-bottom:1rem;'><div class='tiny-label'>ATS Match Score</div><div style='font-size:3rem;font-weight:800;color:{color};line-height:1.05;margin:0.25rem 0 0.35rem;'>{score}%</div><div style='color:#cbd5e1;margin-bottom:0.75rem;'>{descriptor}. Increase your score by adding the missing keywords below.</div><style>div[data-testid=\"stProgressBar\"] > div > div > div > div {{ background: linear-gradient(90deg, {color}, #a855f7); }}</style></div>", unsafe_allow_html=True)
    st.progress(score)


def render_keyword_badges(missing_keywords: list[str]) -> None:
    if not missing_keywords:
        st.markdown("<div class='glass-card' style='padding:1rem;color:#bbf7d0;'>Your resume already covers the top detected keywords.</div>", unsafe_allow_html=True)
        return
    st.markdown("".join(f"<span class='pill-badge'>{escape(keyword)}</span>" for keyword in missing_keywords), unsafe_allow_html=True)


def render_refined_resume_preview(refined_resume: str) -> None:
    st.markdown(f"<div class='glass-card fade-card'><div class='tiny-label'>Output</div><div style='font-size:1.4rem;font-weight:800;margin:0.25rem 0 1rem;'>Refined Resume Preview</div><div class='preview-card'><pre>{escape(refined_resume)}</pre></div></div>", unsafe_allow_html=True)


def render_analysis_panel(score: int, missing_keywords: list[str], suggestions: list[str]) -> None:
    st.markdown("<div class='tiny-label'>Insights</div><div style='font-size:1.55rem;font-weight:800;margin-bottom:1rem;'>Optimization Insights</div>", unsafe_allow_html=True)
    render_score_meter(score)
    st.markdown("<div style='font-size:1rem;font-weight:700;margin:1rem 0 0.65rem;'>Missing Keywords</div>", unsafe_allow_html=True)
    render_keyword_badges(missing_keywords)
    st.markdown("<div style='font-size:1rem;font-weight:700;margin:1.2rem 0 0.65rem;'>Improvement Suggestions</div>", unsafe_allow_html=True)
    if suggestions:
        for index, suggestion in enumerate(suggestions, start=1):
            st.markdown(f"<div class='glass-card' style='padding:1rem;margin-bottom:0.75rem;'><div style='display:flex;gap:0.75rem;align-items:flex-start;'><div class='step-number' style='width:1.8rem;height:1.8rem;font-size:0.82rem;margin-bottom:0;'>{index}</div><div style='color:#e2e8f0;line-height:1.6;'>{escape(suggestion)}</div></div></div>", unsafe_allow_html=True)
    else:
        st.info("Suggestions will appear here after analysis.")


def render_resume_tool(process_resume: ProcessResume) -> None:
    st.markdown("<div class='section-anchor' id='resume-tool'></div>", unsafe_allow_html=True)
    render_section_header("Platform", "Optimize every application in one workspace", "Upload your existing resume, paste the target job description, and let ResumeRefine handle ATS analysis, keyword detection, rewriting, and PDF-ready export.")
    left_col, right_col = st.columns([1.06, 0.94], gap='large')
    with left_col:
        st.markdown("<div class='glass-card fade-card'><div class='tiny-label'>Resume Input</div><div style='font-size:1.45rem;font-weight:800;margin:0.25rem 0 1rem;'>Build a tailored, ATS-ready resume</div>", unsafe_allow_html=True)
        uploaded_resume = st.file_uploader('Upload Resume', type=['pdf', 'docx'])
        job_description = st.text_area('Job Description', height=320, placeholder='Paste the target job description here...')
        refine_clicked = st.button('Refine Resume', type='primary', use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        if refine_clicked:
            if uploaded_resume is None:
                st.error('Please upload a resume in PDF or DOCX format.')
                return
            if not job_description.strip():
                st.error('Please paste a job description before refining your resume.')
                return
            try:
                with st.spinner('Optimizing your resume...'):
                    st.session_state.results = process_resume(uploaded_resume, job_description.strip())
            except ValueError as exc:
                st.error(str(exc))
                return
            except AuthenticationError:
                st.error('Your OpenAI API key appears to be invalid. Update OPENAI_API_KEY in your .env file and restart the app.')
                return
            except APIError as exc:
                st.error(f'OpenAI API error: {exc}')
                return
            except Exception as exc:
                st.error(f'Something went wrong while optimizing the resume: {exc}')
                return
        if st.session_state.results:
            st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)
            render_refined_resume_preview(st.session_state.results['refined_resume'])
            if st.session_state.results['file_extension'] == 'pdf' and st.session_state.results['download_bytes']:
                st.download_button('Download Optimized Resume', data=st.session_state.results['download_bytes'], file_name=st.session_state.results['download_filename'], mime='application/pdf', use_container_width=True)
            else:
                st.info('PDF-preserving download is currently available only when the uploaded resume is a PDF.')
    with right_col:
        st.markdown("<div class='glass-card fade-card'>", unsafe_allow_html=True)
        if st.session_state.results:
            render_analysis_panel(st.session_state.results['score'], st.session_state.results['missing_keywords'], st.session_state.results['suggestions'])
        else:
            st.markdown("<div class='tiny-label'>Optimization Insights</div><div style='font-size:1.55rem;font-weight:800;margin:0.25rem 0 0.8rem;'>See your score, gaps, and next moves</div><div style='color:#cbd5e1;line-height:1.75;margin-bottom:1rem;'>Upload a resume and job description to unlock ATS scoring, missing keyword detection, and personalized improvement suggestions.</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)


def render_features() -> None:
    render_section_header('Features', 'Everything you need to sharpen every resume submission', 'ResumeRefine combines AI rewriting, ATS scoring, keyword intelligence, and recruiter-friendly export in a single polished workflow.')
    st.markdown(
        """
        <div class="feature-grid">
            <div class="glass-card"><div class="icon-badge">AI</div><div class="card-title">AI Resume Optimization</div><div class="card-copy">Rewrite and reorganize your resume to better match the role while preserving factual accuracy.</div></div>
            <div class="glass-card"><div class="icon-badge">ATS</div><div class="card-title">ATS Keyword Detection</div><div class="card-copy">Surface the exact high-signal keywords your target job description expects.</div></div>
            <div class="glass-card"><div class="icon-badge">PDF</div><div class="card-title">Professional Resume Export</div><div class="card-copy">Download an optimized PDF while preserving layout when your source resume is a PDF.</div></div>
            <div class="glass-card"><div class="icon-badge">BP</div><div class="card-title">Bullet Point Enhancement</div><div class="card-copy">Strengthen impact statements with clearer action verbs and stronger role alignment.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_how_it_works() -> None:
    render_section_header('How It Works', 'Three simple steps to a sharper application', 'The workflow is intentionally lightweight so you can adapt your resume quickly for every role without losing your formatting or momentum.')
    st.markdown(
        """
        <div class="steps-grid">
            <div class="glass-card"><div class="step-number">1</div><div class="card-title">Upload your resume</div><div class="card-copy">Drop in your PDF or DOCX resume to extract the current content and structure.</div></div>
            <div class="glass-card"><div class="step-number">2</div><div class="card-title">Paste the job description</div><div class="card-copy">Provide the target role so ResumeRefine can identify alignment, gaps, and relevant keywords.</div></div>
            <div class="glass-card"><div class="step-number">3</div><div class="card-title">Download your optimized resume</div><div class="card-copy">Review the refined version, check the insights, and export your optimized PDF.</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pricing() -> None:
    render_section_header('Pricing', 'Flexible plans for candidates, power users, and teams', 'Pricing is placeholder content for now, but the layout is ready for future billing integration and plan management.')
    st.markdown(
        """
        <div class="pricing-grid">
            <div class="glass-card"><div class="card-title">Free</div><div class="price">$0<span class="price-note">/mo</span></div><div class="card-copy">5 resume optimizations per month</div><div class="card-copy">ATS score</div><div class="card-copy">Keyword analysis</div></div>
            <div class="glass-card"><div class="card-title">Pro</div><div class="price">$19<span class="price-note">/mo</span></div><div class="card-copy">Unlimited optimizations</div><div class="card-copy">Resume bullet rewriting</div><div class="card-copy">Job match insights</div></div>
            <div class="glass-card"><div class="card-title">Team</div><div class="price">$79<span class="price-note">/mo</span></div><div class="card-copy">Team analytics</div><div class="card-copy">Resume version history</div><div class="card-copy">Recruiter insights</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_resources() -> None:
    render_section_header('Resources', 'Built to feel like a trusted AI career product', 'Explore secure account flows, legal pages, and a refined product shell that makes the optimization engine feel production-ready.')


def render_footer() -> None:
    st.markdown(
        """
        <footer class="footer">
            <div class="footer-grid">
                <div>
                    <div class="footer-title">ResumeRefine</div>
                    <div class="footer-copy">AI-powered resume optimization that helps candidates improve ATS alignment and export polished, job-ready resumes.</div>
                    <div class="footer-copy" style="margin-top:1rem;">ResumeRefine (c) 2026</div>
                </div>
                <div>
                    <div class="footer-title">Product</div>
                    <div><a class="text-link" href="?page=home#platform">Platform</a></div>
                    <div><a class="text-link" href="?page=home#features">Features</a></div>
                    <div><a class="text-link" href="?page=home#pricing">Pricing</a></div>
                </div>
                <div>
                    <div class="footer-title">Company</div>
                    <div><a class="text-link" href="?page=home#resources">About</a></div>
                    <div><a class="text-link" href="?page=home#resources">Careers</a></div>
                </div>
                <div>
                    <div class="footer-title">Legal</div>
                    <div><a class="text-link" href="?page=privacy">Privacy Policy</a></div>
                    <div><a class="text-link" href="?page=terms">Terms</a></div>
                </div>
            </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def render_auth_page(mode: str) -> None:
    is_login = mode == 'login'
    title = 'Welcome back' if is_login else 'Create your ResumeRefine account'
    subtitle = 'Access your optimization workspace and saved resume insights.' if is_login else 'Start tailoring resumes with AI-powered ATS guidance.'
    st.markdown("<div class='auth-shell'><div class='glass-card fade-card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='tiny-label'>{'Log In' if is_login else 'Sign Up'}</div><h1>{escape(title)}</h1><div class='legal-copy' style='margin-bottom:1.5rem;'>{escape(subtitle)}</div>", unsafe_allow_html=True)
    with st.form('login_form' if is_login else 'signup_form'):
        if not is_login:
            st.text_input('Name', placeholder='Taylor Morgan')
        st.text_input('Email', placeholder='you@example.com')
        st.text_input('Password', type='password', placeholder='Enter your password')
        if st.form_submit_button('Log In' if is_login else 'Create Account'):
            st.success('This is a polished placeholder flow. Auth UI is ready for backend integration.')
    st.markdown("</div></div>", unsafe_allow_html=True)


def render_legal_page(page: str) -> None:
    title = 'Privacy Policy' if page == 'privacy' else 'Terms and Conditions'
    st.markdown(f"<div class='legal-shell'><div class='glass-card fade-card'><div class='tiny-label'>Legal</div><h1>{escape(title)}</h1><div class='legal-copy'>Professional placeholder legal content for the ResumeRefine platform, including data use, account usage, user responsibilities, limitation of liability, and data security.</div></div></div>", unsafe_allow_html=True)


def render_app(process_resume: ProcessResume) -> None:
    render_global_styles()
    render_navbar()
    page = st.query_params.get('page', 'home')
    if page == 'login':
        render_auth_page('login')
    elif page == 'signup':
        render_auth_page('signup')
    elif page == 'privacy':
        render_legal_page('privacy')
    elif page == 'terms':
        render_legal_page('terms')
    else:
        render_hero()
        render_resume_tool(process_resume)
        render_features()
        render_how_it_works()
        render_pricing()
        render_resources()
    render_footer()
