import concurrent.futures
import os
import queue
import re
import time
import requests
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI

load_dotenv()

def _single_rdap_check(domain_name: str) -> str:
    clean_domain = re.sub(r"[^a-zA-Z0-9.-]", "", domain_name).strip().lower()
    url = f"https://rdap.org/domain/{clean_domain}"
    try:
        response = requests.get(
            url,
            timeout=4,
            headers={"User-Agent": "DomainCheckerAgent/1.0 (https://rdap.org)"},
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
        return "No valid domains provided. Please pass comma-separated domains with TLDs (e.g. name1.in, name2.com)."

    start_time = time.perf_counter()

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


class QueueLogHandler(BaseCallbackHandler):
    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self.llm_start_time = None
        self.tool_start_time = None

    def on_llm_start(self, serialized, prompts, **kwargs):
        self.llm_start_time = time.perf_counter()
        self.log_queue.put("🧠 **Ollama Cloud:** Brainstorming budget-friendly domain candidates...")

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
            self.log_queue.put(f"  ↳ **Batch Results Received** *({elapsed_ms:.1f}ms)*")


def get_agent():
    ollama_api_key = os.getenv("OLLAMA_API_KEY")
    ollama_base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
    ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

    if not ollama_api_key:
        raise ValueError("OLLAMA_API_KEY is missing from your environment or .env file!")

    llm = ChatOpenAI(
        model=ollama_model,
        api_key=ollama_api_key,
        base_url=ollama_base_url,
        temperature=0.85,
        max_retries=3,
    )

    system_prompt = """You are an autonomous Domain Naming Agent focused on finding the CHEAPEST, highest-value available domain names. Your mandate is to return EXACTLY 10 AVAILABLE domain names.

STRATEGY FOR BUDGET EXECUTION:
1. Prioritize low-cost, high-value extensions like .in, .co.in, and .com. Avoid expensive extensions unless explicitly requested.
2. Brainstorm 15-20 candidate domains at once combining creative root words with these budget TLDs.
3. Call `check_domain_batch` ONCE with all candidates formatted as a single comma-separated string.
4. If you have at least 10 AVAILABLE domains, stop checking and present them.
5. In your final response, list ONLY the verified AVAILABLE domains along with a brief 1-sentence brand explanation for each."""

    return create_agent(model=llm, tools=tools, system_prompt=system_prompt)


initialize_agent = get_agent