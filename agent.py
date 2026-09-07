import logging
import os
import re
import time
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
import requests
from rich.logging import RichHandler

# =====================================================================
# 1. SETUP LOGGING & CONFIGURATION
# =====================================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)],
)
logger = logging.getLogger("domain_agent")

load_dotenv()

ollama_api_key = os.getenv("OLLAMA_API_KEY")
ollama_base_url = os.getenv("OLLAMA_BASE_URL", "https://ollama.com/v1")
ollama_model = os.getenv("OLLAMA_MODEL", "gpt-oss:120b")

if not ollama_api_key:
    logger.error("OLLAMA_API_KEY is missing from the .env file.")
    raise ValueError("OLLAMA_API_KEY is missing from the .env file.")

# =====================================================================
# 2. DEFINE KEYLESS RDAP DOMAIN CHECKING TOOLS
# =====================================================================


@tool
def check_domain_availability(domain_name: str) -> str:
    """Checks real-time domain availability via the open RDAP protocol (Registration Data Access Protocol).

    No API keys or credentials required.
    """
    clean_domain = domain_name.strip().lower()
    url = f"https://rdap.org/domain/{clean_domain}"

    logger.debug(f"Querying RDAP for: {clean_domain}")

    try:
        response = requests.get(
            url,
            timeout=5,
            headers={
                "User-Agent": "DomainCheckerAgent/1.0 (https://rdap.org)"
            },
        )

        # RDAP Standard: 404 means domain is NOT registered (AVAILABLE)
        if response.status_code == 404:
            logger.info(f"[bold green]AVAILABLE[/bold green] -> {clean_domain}")
            return f"{clean_domain} is AVAILABLE for registration."

        # RDAP Standard: 200 means domain IS registered (TAKEN)
        elif response.status_code == 200:
            logger.info(f"[bold red]TAKEN[/bold red] -> {clean_domain}")
            return f"{clean_domain} is TAKEN."

        else:
            logger.warning(
                f"RDAP returned status {response.status_code} for {clean_domain}"
            )
            return f"Unable to verify status for {clean_domain} (HTTP {response.status_code})."

    except requests.RequestException as e:
        logger.error(f"Network error querying RDAP for {clean_domain}: {e}")
        return f"Error checking {clean_domain}: {str(e)}"


@tool
def clean_domain_string(raw_name: str) -> str:
    """Cleans text into a valid alphanumeric domain root string (lowercased, no spaces/special characters)."""
    cleaned = re.sub(r"[^a-zA-Z0-9-]", "", raw_name).lower()
    logger.debug(f"Cleaned '{raw_name}' -> '{cleaned}'")
    return cleaned


tools = [check_domain_availability, clean_domain_string]

# =====================================================================
# 3. INITIALIZE OLLAMA CLOUD LLM VIA CHATOPENAI & CREATE AGENT
# =====================================================================

logger.info(
    f"Connecting to Ollama Cloud API ({ollama_base_url}) using model '{ollama_model}'..."
)

llm = ChatOpenAI(
    model=ollama_model,
    api_key=ollama_api_key,
    base_url=ollama_base_url,
    temperature=0.1,
    max_retries=3,
)

system_prompt = """You are an autonomous Domain Naming Agent. Your goal is to deliver verified AVAILABLE domains for a given concept.

Execution Steps:
1. Brainstorm 8 creative candidate root names for the user's idea.
2. Pass each candidate root name through `clean_domain_string`.
3. Check availability for each using `check_domain_availability` with both `.com` and `.ai` extensions.
4. If fewer than 3 options are AVAILABLE, generate 5 more candidates and repeat the check.
5. Provide a final list displaying ONLY the available domains along with a 1-sentence brand reasoning for each."""

agent_executor = create_agent(
    model=llm, tools=tools, system_prompt=system_prompt
)

# =====================================================================
# 4. RUN AGENT
# =====================================================================

if __name__ == "__main__":
    user_idea = (
        "An AI system that converts technical books into interactive voice lessons"
    )
    logger.info(f"Starting domain agent execution for prompt: '{user_idea}'")

    for attempt in range(1, 4):
        try:
            logger.info(f"Attempt {attempt}/3 running...")
            response = agent_executor.invoke(
                {
                    "messages": [
                        ("user", f"Find available domains for: {user_idea}")
                    ]
                }
            )
            logger.info(
                "[bold green]Agent completed execution successfully![/bold green]"
            )

            final_output = response["messages"][-1].content
            logger.info("\n" + "=" * 50 + "\n" + final_output + "\n" + "=" * 50)
            break
        except Exception as e:
            logger.error(
                f"Attempt {attempt} failed with error: {e}", exc_info=True
            )
            if attempt < 3:
                logger.info("Retrying in 3 seconds...")
                time.sleep(3)