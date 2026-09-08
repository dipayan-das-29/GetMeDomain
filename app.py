import base64
import os
import queue
import re
import threading
import time
import urllib.parse
import streamlit as st
from backend import QueueLogHandler, get_agent

# 1. Page Configuration
st.set_page_config(
    page_title="GetMeDomain - AI Domain Intelligence",
    page_icon="🦊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_image_base64_with_fallbacks(filename_list):
    for name in filename_list:
        file_path = os.path.join(BASE_DIR, name)
        if os.path.exists(file_path):
            with open(file_path, "rb") as img_file:
                ext = name.split(".")[-1].lower()
                mime_type = "image/png" if ext == "png" else "image/jpeg"
                encoded = base64.b64encode(img_file.read()).decode("utf-8")
                return f"data:{mime_type};base64,{encoded}"
    return None

icon_src = get_image_base64_with_fallbacks(["image (2).jpg", "image (2).png", "image (2).jpeg", "image(2).jpg"])
logo_src = get_image_base64_with_fallbacks(["image (3).png", "image (3).jpg", "image (3).jpeg", "image(3).png"])

DEFAULT_FOX_SVG = """data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><polygon points='50,15 90,85 10,85' fill='%2300f5d4'/><circle cx='50' cy='50' r='20' fill='%2300363e'/></svg>"""
if not icon_src:
    icon_src = DEFAULT_FOX_SVG

if "run_count" not in st.session_state:
    st.session_state.run_count = 1
if "last_results" not in st.session_state:
    st.session_state.last_results = None

st.markdown("""
    <style>
    @import url('https://api.fontshare.com/v2/css?f[]=clash-display@700,600&display=swap');
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=Space+Mono:wght@700&display=swap');

    .stApp, div[data-testid="stAppViewContainer"], div[data-testid="stHeader"] {
        background: transparent !important;
    }
    body { background-color: #021317 !important; }

    [data-testid="collapsedControl"] { display: none !important; }
    section[data-testid="stSidebar"] { display: none !important; }

    @keyframes orbRotate {
        0% { transform: rotate(0deg) scale(1); }
        50% { transform: rotate(180deg) scale(1.15); }
        100% { transform: rotate(360deg) scale(1); }
    }
    @keyframes pulseGlow {
        0%, 100% { opacity: 0.65; }
        50% { opacity: 0.95; }
    }
    .stApp::before {
        content: ""; position: fixed; top: -20%; left: -20%; width: 140vw; height: 140vh; z-index: -2;
        background: radial-gradient(circle at 20% 20%, rgba(0, 245, 212, 0.18) 0%, transparent 40%),
                    radial-gradient(circle at 80% 30%, rgba(0, 168, 232, 0.22) 0%, transparent 45%),
                    radial-gradient(circle at 50% 80%, rgba(0, 82, 104, 0.35) 0%, transparent 50%);
        filter: blur(60px); animation: orbRotate 22s ease-in-out infinite, pulseGlow 10s ease-in-out infinite; pointer-events: none;
    }
    html, body, p, span, div, label, .stMarkdown, h1, h2, h3 {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif !important;
        color: #ffffff !important;
    }
    #MainMenu, footer, header { visibility: hidden; }
    .block-container { padding-top: 1.8rem !important; padding-bottom: 2.5rem !important; max-width: 1200px !important; margin: 0 auto !important; }
    
    .nav-bar { display: flex; align-items: center; justify-content: space-between; width: 100%; padding-bottom: 1.2rem; border-bottom: 1px solid rgba(255, 255, 255, 0.12); margin-bottom: 2.5rem; }
    .brand-logo-group { display: flex; align-items: center; gap: 16px; }
    .brand-icon-img { height: 52px; width: 52px; object-fit: cover; border-radius: 10px; border: 1px solid rgba(0, 245, 212, 0.35); }
    .brand-name-img { height: 42px; width: auto; object-fit: contain; }
    .brand-badge { font-size: 0.72rem; font-weight: 700; text-transform: uppercase; background: rgba(0, 245, 212, 0.15); color: #00f5d4 !important; border: 1px solid rgba(0, 245, 212, 0.4); padding: 3px 10px; border-radius: 20px; }
    .brand-subtext { font-size: 0.88rem; font-weight: 600; color: #8be0d0 !important; text-align: right; }
    
    .hero-container { text-align: center; margin-bottom: 2.5rem; width: 100%; }
    .hero-title { font-size: 3.1rem !important; font-weight: 800 !important; color: #ffffff !important; margin-bottom: 0.8rem !important; }
    .hero-subtitle { font-size: 1.05rem !important; font-weight: 500 !important; color: #a7f3d0 !important; max-width: 800px !important; margin: 0 auto !important; }
    
    .stTextArea textarea { border-radius: 12px !important; background-color: rgba(1, 22, 27, 0.9) !important; color: #ffffff !important; border: 1px solid rgba(0, 245, 212, 0.3) !important; padding: 12px !important; }
    
    /* Multiselect Main Field & Popup Dropdown Styling */
    div[data-testid="stMultiSelect"] div[data-baseweb="select"] { background-color: rgba(1, 22, 27, 0.9) !important; border-radius: 10px !important; border: 1px solid rgba(0, 245, 212, 0.3) !important; }
    div[data-baseweb="popover"], div[data-baseweb="menu"], ul[role="listbox"] {
        background-color: #01161b !important;
        border: 1px solid rgba(0, 245, 212, 0.35) !important;
        border-radius: 10px !important;
    }
    li[role="option"] {
        background-color: #01161b !important;
        color: #ffffff !important;
    }
    li[role="option"]:hover, li[role="option"][aria-selected="true"] {
        background-color: rgba(0, 245, 212, 0.2) !important;
        color: #00f5d4 !important;
    }

    /* Crisp Custom Domain Card & Buttons */
    .domain-card {
        background-color: rgba(2, 28, 38, 0.95);
        border: 1px solid rgba(0, 245, 212, 0.35);
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 6px 20px rgba(0, 0, 0, 0.45);
    }
    .domain-title { font-size: 1.15rem; font-weight: 700; color: #00f5d4 !important; margin-bottom: 6px; font-family: 'Space Mono', monospace !important; }
    .status-badge { display: inline-block; font-size: 0.7rem; font-weight: 700; color: #00f5d4; background: rgba(0, 245, 212, 0.15); border: 1px solid rgba(0, 245, 212, 0.4); padding: 3px 8px; border-radius: 12px; margin-bottom: 14px; }
    
    .btn-row { display: flex; gap: 10px; width: 100%; }
    .reg-btn {
        flex: 1; text-align: center; background-color: rgba(0, 245, 212, 0.1); color: #00f5d4 !important;
        border: 1px solid rgba(0, 245, 212, 0.35); padding: 8px 12px; border-radius: 8px; font-size: 0.82rem;
        font-weight: 600; text-decoration: none; transition: all 0.2s ease;
    }
    .reg-btn:hover { background-color: rgba(0, 245, 212, 0.25); border-color: #00f5d4; color: #ffffff !important; }
    </style>
""", unsafe_allow_html=True)

logo_html = f'<img src="{logo_src}" class="brand-name-img" alt="Logo">' if logo_src else '<span style="font-size:2rem; font-weight:700; color:#fff;">GetMeDomain</span>'
st.markdown(f"""
    <div class="nav-bar">
        <div class="brand-logo-group">
            <img src="{icon_src}" class="brand-icon-img" alt="Icon">
            {logo_html}
            <span class="brand-badge">Budget AI</span>
        </div>
        <div class="brand-subtext">CHEAP RDAP ENGINE<br><span style="font-size: 0.75rem; opacity: 0.8;">Live Availability Check</span></div>
    </div>
""", unsafe_allow_html=True)

st.markdown("""
    <div class="hero-container">
        <div class="hero-title">Find budget-friendly domains</div>
        <div class="hero-subtitle">Autonomous AI agent prioritizing low-cost extensions like .in, .co.in, and .com via real-time RDAP registries.</div>
    </div>
""", unsafe_allow_html=True)

user_idea = st.text_area(
    "Describe your product or business concept:",
    placeholder="e.g. An AI platform that converts technical documentation into interactive audio lessons...",
    height=110,
)

st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

tld_options = st.multiselect(
    "Target Budget Extensions (TLDs):",
    [".in", ".co.in", ".com", ".org", ".net", ".ai"],
    default=[".in", ".com"],
)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    search_clicked = st.button(
        "Find 10 Cheap Available Domains", type="primary", use_container_width=True
    )
with btn_col2:
    rerun_clicked = st.button(
        "Don't Like These? Rerun for 10 New Names", use_container_width=True
    )

if search_clicked or rerun_clicked:
    if not user_idea.strip():
        st.warning("Please enter a business concept first!")
    elif not tld_options:
        st.warning("Please select at least one TLD extension below your prompt!")
    else:
        if rerun_clicked:
            st.session_state.run_count += 1
        else:
            st.session_state.run_count = 1

        selected_tlds = ", ".join(tld_options)

        with st.status(
            f"🤖 Batch-checking cheap domain candidates (Attempt #{st.session_state.run_count})...",
            expanded=True,
        ) as status:
            try:
                agent = get_agent()

                prompt_input = (
                    f"Business Idea: '{user_idea}'. "
                    f"Target Extensions: {selected_tlds}. "
                    f"Attempt #{st.session_state.run_count}. "
                    f"Brainstorm 20 domain candidates using ONLY the specified target extensions and use check_domain_batch to verify them. Ensure you reach AT LEAST 10 AVAILABLE domains."
                )

                log_queue = queue.Queue()
                log_handler = QueueLogHandler(log_queue)

                agent_result = {}
                agent_exception = []

                def run_agent():
                    try:
                        res = agent.invoke(
                            {"messages": [("user", prompt_input)]},
                            config={"callbacks": [log_handler]},
                        )
                        agent_result["response"] = res
                    except Exception as ex:
                        agent_exception.append(ex)

                total_start_time = time.perf_counter()

                thread = threading.Thread(target=run_agent, daemon=True)
                thread.start()

                while thread.is_alive() or not log_queue.empty():
                    while not log_queue.empty():
                        msg = log_queue.get()
                        status.write(msg)
                    time.sleep(0.1)

                total_elapsed = time.perf_counter() - total_start_time

                if agent_exception:
                    raise agent_exception[0]

                status.update(
                    label=f"Verified 10 Cheap Domains in {total_elapsed:.2f}s!",
                    state="complete",
                    expanded=False,
                )

                final_content = agent_result["response"]["messages"][-1].content
                st.session_state.last_results = final_content
                st.rerun()

            except Exception as e:
                status.update(label="❌ Search failed!", state="error")
                st.error(f"Execution error: {str(e)}")

if st.session_state.last_results:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.divider()

    content = st.session_state.last_results

    found_domains = re.findall(
        r"\b[a-zA-Z0-9-]+\.(?:in|co\.in|com|org|net|ai)\b",
        content,
        re.IGNORECASE,
    )
    unique_domains = list(
        dict.fromkeys([d.lower() for d in found_domains])
    )

    st.subheader(
        f"10 Verified Budget-Friendly Domains (Attempt #{st.session_state.run_count})"
    )

    if unique_domains:
        formatted_tags = " &nbsp;&nbsp;•&nbsp;&nbsp; ".join(
            [f"**`{d}`**" for d in unique_domains]
        )
        st.success(f"**Available Now:** {formatted_tags}")
        st.caption(
            "Click a domain card below to proceed with quick registration check:"
        )
        
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

        display_list = unique_domains[:10]
        for i in range(0, len(display_list), 3):
            row_domains = display_list[i:i+3]
            cols = st.columns(3)
            
            for idx, domain in enumerate(row_domains):
                godaddy_url = f"https://www.godaddy.com/domainsearch/find?domainToCheck={urllib.parse.quote(domain)}"
                namecheap_url = f"https://www.namecheap.com/domains/registration/results/?domain={urllib.parse.quote(domain)}"

                with cols[idx]:
                    st.markdown(f"""
                        <div class="domain-card">
                            <div class="domain-title">{domain}</div>
                            <span class="status-badge">🟢 VERIFIED AVAILABLE</span>
                            <div class="btn-row">
                                <a href="{godaddy_url}" target="_blank" class="reg-btn">GoDaddy ↗</a>
                                <a href="{namecheap_url}" target="_blank" class="reg-btn">Namecheap ↗</a>
                            </div>
                        </div>
                    """, unsafe_allow_html=True)
    else:
        st.warning("See agent detailed output below.")

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    with st.expander(
        "📄 View Detailed Agent Reasoning & Full Output", expanded=False
    ):
        st.markdown(content)