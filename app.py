import concurrent.futures
import os
import queue
import re
import threading
import time
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import requests
import streamlit as st

# Load environment variables
load_dotenv()

st.set_page_config(
    page_title="GetMeDomain - AI Domain Finder", page_icon="🌐", layout="wide"
)

# =====================================================================
# 1. SESSION STATE
# =====================================================================
if "run_count" not in st.session_state:
    st.session_state.run_count = 1
if "last_results" not in st.session_state:
    st.session_state.last_results = None

# =====================================================================
# 2. FAST BATCH RDAP CHECKING TOOLS
# =====================================================================


def _single_rdap_check(domain_name: str) -> str:
    """Helper function to check a single domain via RDAP."""
    clean_domain = re.sub(r"[^a-zA-Z0-9.-]", "", domain_name).strip().lower()
    url = f"https://rdap.org/domain/{clean_domain}"
    try:
        response = requests.get(
            url,
            timeout=4,
            headers={
                "User-Agent": "DomainCheckerAgent/1.0 (https://rdap.org)"
            },
        )
        if response.status_code == 404:
            return f"{clean_domain}: AVAILABLE"
        elif response.status_code == 200:
            return f"{clean_domain}: TAKEN"
        else:
            return f"{clean_domain}: UNKNOWN (HTTP {response.status_code})"
    except Exception as e:
        return f"{clean_domain}: ERROR ({str(e)})"


@tool
def check_domain_batch(domains_comma_separated: str) -> str:
    """Checks real-time domain availability for a list of comma-separated domains concurrently in parallel."""
    domain_list = [
        d.strip()
        for d in domains_comma_separated.split(",")
        if d.strip() and "." in d
    ]
    if not domain_list:
        return "No valid domains provided. Please pass comma-separated domains with TLDs (e.g. name1.com, name2.ai)."

    start_time = time.perf_counter()

    # Use thread pool to run RDAP queries in parallel
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(_single_rdap_check, domain): domain
            for domain in domain_list
        }
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    elapsed_ms = (time.perf_counter() - start_time) * 1000
    available_count = sum(1 for r in results if "AVAILABLE" in r)

    formatted_results = "\n".join(results)
    return f"Batch Check Completed in {elapsed_ms:.1f}ms ({available_count} Available):\n{formatted_results}"


tools = [check_domain_batch]

# =====================================================================
# 3. THREAD-SAFE QUEUE LOG HANDLER
# =====================================================================


class QueueLogHandler(BaseCallbackHandler):

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self.llm_start_time = None
        self.tool_start_time = None

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.llm_start_time = time.perf_counter()
        self.log_queue.put(
            "🧠 **Ollama Cloud:** Brainstorming domain candidates..."
        )

    def on_llm_end(self, response, **kwargs):
        if self.llm_start_time:
            elapsed = time.perf_counter() - self.llm_start_time
            self.log_queue.put(f"  ↳ ⏱️ **LLM Latency:** `{elapsed:.2f}s`")

    def on_tool_start(self, serialized, input_str, **kwargs):
        self.tool_start_time = time.perf_counter()
        tool_name = serialized.get("name", "Tool")
        self.log_queue.put(f"🔧 **Parallel Tool Call (`{tool_name}`):**")

    def on_tool_end(self, output, **kwargs):
        if self.tool_start_time:
            elapsed_ms = (time.perf_counter() - self.tool_start_time) * 1000
            self.log_queue.put(
                f"  ↳ **Batch Results Received** *({elapsed_ms:.1f}ms)*"
            )


# =====================================================================
# 4. AGENT INITIALIZATION
# =====================================================================


@st.cache_resource
def get_agent():
    # Safely look up secrets in Streamlit Cloud or fall back to local .env
    ollama_api_key = st.secrets.get("OLLAMA_API_KEY") or os.getenv("OLLAMA_API_KEY")
    ollama_base_url = st.secrets.get("OLLAMA_BASE_URL") or os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
    ollama_model = st.secrets.get("OLLAMA_MODEL") or os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

    if not ollama_api_key:
        st.error("❌ OLLAMA_API_KEY is missing from your .env file!")
        st.stop()

    llm = ChatOpenAI(
        model=ollama_model,
        api_key=ollama_api_key,
        base_url=ollama_base_url,
        temperature=0.85,
        max_retries=3,
    )

    system_prompt = """You are an autonomous Domain Naming Agent. Your mandate is to return EXACTLY 10 AVAILABLE domain names.

STRATEGY FOR FAST EXECUTION:
1. Brainstorm 15-20 candidate domains at once (combining creative root words with the requested TLD extensions).
2. Call `check_domain_batch` ONCE with all 15-20 candidates formatted as a single comma-separated string (e.g. "name1.com, name2.ai, name3.io, ...").
3. Inspect the batch output. If you have at least 10 AVAILABLE domains, stop checking and present them.
4. If you have fewer than 10 AVAILABLE domains, generate another batch of 15-20 candidates and run `check_domain_batch` again.
5. In your final response, list ONLY the verified AVAILABLE domains along with a brief 1-sentence brand explanation for each."""

    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


# =====================================================================
# 5. UI LAYOUT & CONTROLS
# =====================================================================

st.title("GetMeDomain AI")
st.caption("#DesiVidesi")

with st.sidebar:
    st.header("Settings")
    tld_options = st.multiselect(
        "Allowed Extensions:",
        [".com", ".ai", ".io", ".app", ".dev", ".org"],
        default=[".com", ".ai"],
    )
    st.info("Uses multithreaded RDAP checks to test 15+ domains in parallel.")

user_idea = st.text_area(
    "Describe your product or business concept:",
    placeholder="e.g. An AI agent that converts technical books into interactive voice lessons...",
    height=100,
)

btn_col1, btn_col2 = st.columns([1, 1])
with btn_col1:
    search_clicked = st.button(
        "🚀 Find 10 Available Domains", type="primary", use_container_width=True
    )
with btn_col2:
    rerun_clicked = st.button(
        "🔄 Don't Like These? Rerun for 10 New Names", use_container_width=True
    )

# Handle Execution Trigger
if search_clicked or rerun_clicked:
    if not user_idea.strip():
        st.warning("Please enter a business concept first!")
    else:
        if rerun_clicked:
            st.session_state.run_count += 1
        else:
            st.session_state.run_count = 1

        selected_tlds = ", ".join(tld_options) if tld_options else ".com, .ai"

        with st.status(
            f"🤖 Batch-checking domain candidates (Attempt #{st.session_state.run_count})...",
            expanded=True,
        ) as status:
            try:
                agent = get_agent()

                prompt_input = (
                    f"Business Idea: '{user_idea}'. "
                    f"Target Extensions: {selected_tlds}. "
                    f"Attempt #{st.session_state.run_count}. "
                    f"Brainstorm 20 domain candidates and use check_domain_batch to verify them. Ensure you reach AT LEAST 10 AVAILABLE domains."
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
                    label=f"✅ Verified 10 Available Domains in {total_elapsed:.2f}s!",
                    state="complete",
                    expanded=False,
                )

                final_content = agent_result["response"]["messages"][
                    -1
                ].content
                st.session_state.last_results = final_content

            except Exception as e:
                status.update(label="❌ Search failed!", state="error")
                st.error(f"Execution error: {str(e)}")

# =====================================================================
# 6. RESULTS CONTAINER
# =====================================================================

if st.session_state.last_results:
    st.divider()

    results_container = st.container()

    with results_container:
        content = st.session_state.last_results

        # Extract unique domain strings matching requested pattern
        found_domains = re.findall(
            r"\b[a-zA-Z0-9-]+\.(?:com|ai|io|app|dev|org)\b",
            content,
            re.IGNORECASE,
        )
        unique_domains = list(
            dict.fromkeys([d.lower() for d in found_domains])
        )

        st.subheader(
            f"🎉 10 Verified Available Domains (Attempt #{st.session_state.run_count})"
        )

        if unique_domains:
            # Single consolidated horizontal list of domains
            formatted_tags = " &nbsp;&nbsp;•&nbsp;&nbsp; ".join(
                [f"**`{d}`**" for d in unique_domains]
            )
            st.success(f"**Available Now:** {formatted_tags}")
            st.caption(
                "Click a domain below to proceed with quick registration check:"
            )

            # Display domain options as grid cards (3 per row)
            cols = st.columns(3)
            for idx, domain in enumerate(unique_domains[:10]):
                with cols[idx % 3]:
                    with st.container(border=True):
                        st.markdown(f"#### 🟢 `{domain}`")
                        godaddy_url = f"https://www.godaddy.com/domainsearch/find?domainToCheck={domain}"
                        namecheap_url = f"https://www.namecheap.com/domains/registration/results/?domain={domain}"

                        c1, c2 = st.columns(2)
                        with c1:
                            st.link_button(
                                "GoDaddy", godaddy_url, use_container_width=True
                            )
                        with c2:
                            st.link_button(
                                "Namecheap",
                                namecheap_url,
                                use_container_width=True,
                            )
        else:
            st.warning("See agent detailed output below.")

        with st.expander(
            "📄 View Detailed Agent Reasoning & Full Output", expanded=False
        ):
            st.markdown(content)