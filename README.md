# GetMeDomain

A lightweight Python project for working with domain-related tasks.

## Project Structure

- `app.py` – main application entry point
- `agent.py` – agent logic
- `requirements.txt` – Python dependency list
- `.env` – local environment variables (not committed)

## Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure environment variables in a `.env` file if needed.

## Run

```bash
 streamlit run app.py
```

## Notes

- Keep secrets out of source control.
- Use `.env` locally and make sure it is ignored by Git.

required keys in .env
- OLLAMA_API_KEY= Generated API Key
- OLLAMA_BASE_URL=https://ollama.com/v1
- OLLAMA_MODEL=gpt-oss:120b