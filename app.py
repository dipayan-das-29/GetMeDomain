import queue
import re
import threading
import time
import streamlit as st
from agent import QueueLogHandler, get_agent

# Page Config - Wide Layout Enabled
st.set_page_config(
    page_title="GetMeDomain — AI Domain Finder",
    page_icon="🐶",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Custom Full-Width Layout & Typography CSS
st.markdown(
    """
    <style>
    /* Import Modern Web Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    /* Global Typography Reset */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        -webkit-font-smoothing: antialiased;
    }

    /* Hide default Streamlit overhead */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Utilize Full Screen Width */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
        padding-left: 3rem !important;
        padding-right: 3rem !important;
        max-width: 100% !important;
    }

    /* Top Navigation Bar */
    .nav-bar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 1.5rem;
        border-bottom: 1px solid #22272e;
        margin-bottom: 2.5rem;
    }
    .brand-logo-group {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .brand-icon {
        font-size: 1.8rem;
    }
    .brand-name {
        font-size: 1.4rem;
        font-weight: 800;
        color: #ffffff;
        letter-spacing: -0.5px;
    }
    .brand-badge {
        font-size: 0.75rem;
        background: rgba(0, 212, 178, 0.12);
        color: #00D4B2;
        border: 1px solid rgba(0, 212, 178, 0.3);
        padding: 4px 12px;
        border-radius: 20px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }

    /* Full-Width Hero Section */
    .hero-container {
        text-align: center;
        margin-bottom: 2.5rem;
    }
    .hero-title {
        font-size: 3.2rem;
        font-weight: 800;
        letter-spacing: -1.2px;
        color: #ffffff;
        margin-bottom: 0.8rem;
        line-height: 1.1;
    }
    .hero-subtitle {
        font-size: 1.25rem;
        color: #8b949e;
        font-weight: 400;
        max-width: 800px;
        margin: 0 auto;
        line-height: 1.5;
    }

    /* Streamlit Text Area Customization */
    .stTextArea textarea {
        font-family: 'Inter', sans-serif !important;
        font-size: 1.05rem !important;
        border-radius: 10px !important;
        background-color: #0d1117 !important;
        border: 1px solid #30363d !important;
    }
    .stTextArea textarea:focus {
        border-color: #00D4B2 !important;
        box-shadow: 0 0 0 1px #00D4B2 !important;
    }

    /* Cards Styling */
    .domain-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #00D4B2;
        margin-bottom: 6px;
        letter-spacing: -0.4px;
        font-family: 'Inter', monospace;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# State Management
if "run_count" not in st.session_state:
    st.session_state.run_count = 1
if "last_results" not in st.session_state:
    st.session_state.last_results = None

# 1. Full-Width Top Navigation Header
st.markdown(
    """
    <div class="nav-bar">
        <div class="brand-logo-group">
            <span class="brand-icon">🐶</span>
            <span class="brand-name">GoSonny</span>
            <span class="brand-badge">Pro</span>
        </div>
        <div style="font-size: 0.9rem; color: #8b949e; font-weight: 500;">Powered by Ollama Cloud LLM</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 2. Hero Header
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title">Find your next brandable domain</div>
        <div class="hero-subtitle">Describe your product or business. We perform parallel RDAP lookups in real-time to find 10 verified available domains.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 3. Search Input Section Across Full Width
user_idea = st.text_area(
    label="Business Concept",
    placeholder="e.g. An AI platform that converts technical documentation into interactive video guides...",
    height=100,
    label_visibility="collapsed",
)

col_ext, col_btn = st.columns([3, 1])

with col_ext:
    selected_tlds_list = st.multiselect(
        "Extensions",
        [".com", ".ai", ".io", ".app", ".dev", ".org"],
        default=[".com", ".ai"],
        label_visibility="collapsed",
    )

with col_btn:
    search_clicked = st.button("🐶 Search Domains", type="primary", use_container_width=True)

# 4. Agent Execution Flow
if search_clicked:
    if not user_idea.strip():
        st.warning("Please describe your business concept first.")
    else:
        st.session_state.run_count += 1
        selected_tlds = ", ".join(selected_tlds_list) if selected_tlds_list else ".com, .ai"

        with st.status("Searching available domains across parallel threads...", expanded=True) as status:
            try:
                agent = get_agent()
                prompt_input = (
                    f"Business Idea: '{user_idea}'. "
                    f"Target Extensions: {selected_tlds}. "
                    f"Attempt #{st.session_state.run_count}. "
                    f"Brainstorm 20 candidates and use check_domain_batch to verify them. Ensure you reach AT LEAST 10 AVAILABLE domains."
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
                    label=f"Verified 10 available domains in {total_elapsed:.2f}s!",
                    state="complete",
                    expanded=False,
                )

                final_content = agent_result["response"]["messages"][-1].content
                st.session_state.last_results = final_content

            except Exception as e:
                status.update(label="Search failed", state="error")
                st.error(f"Error: {str(e)}")

# 5. Wide Grid Output (5 Cards per Row on Large Screens)
if st.session_state.last_results:
    st.markdown("---")
    content = st.session_state.last_results

    found_domains = re.findall(
        r"\b[a-zA-Z0-9-]+\.(?:com|ai|io|app|dev|org)\b", content, re.IGNORECASE
    )
    unique_domains = list(dict.fromkeys([d.lower() for d in found_domains]))

    st.subheader("10 Verified Available Domains")

    if unique_domains:
        # Utilizing full width with a 5-column wide grid layout
        cols = st.columns(5)
        for idx, domain in enumerate(unique_domains[:10]):
            with cols[idx % 5]:
                with st.container(border=True):
                    st.markdown(f"<div class='domain-title'>🟢 {domain}</div>", unsafe_allow_html=True)
                    st.caption("Available Now")
                    
                    godaddy_url = f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"
                    namecheap_url = f"https://www.namecheap.com/domains/registration/results/?domain={domain}"

                    btn_c1, btn_c2 = st.columns(2)
                    with btn_c1:
                        st.link_button("GoDaddy", godaddy_url, use_container_width=True)
                    with btn_c2:
                        st.link_button("Namecheap", namecheap_url, use_container_width=True)
    else:
        st.warning("Could not automatically structure domain list. Check full output below.")

    with st.expander("Show AI Reasoning & Descriptions", expanded=False):
        st.markdown(content)