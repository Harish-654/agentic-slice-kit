# RUN

Run from the repository root (the folder that contains `.git`). Set your OpenRouter key, then start the server:

    export OPENROUTER_API_KEY=your-key
    python -m uvicorn web.student:app --port 8001

For Codespaces 

    python -m uvicorn web.student:app --host 0.0.0.0 --port 8000

Then open <http://127.0.0.1:8001> in a browser and choose **Create account** (any name, a password of 8 or more characters).

- PowerShell instead of bash: `$env:OPENROUTER_API_KEY = "your-key"`.
- First time on a machine only: `pip install -r requirements.txt`.
- To let the code sandbox run programs (Python, JavaScript, Java, C++), start Docker and run `python scripts/pull_runtimes.py` once.
  Everything else works without it; program questions then fall back to multiple choice and say why.
