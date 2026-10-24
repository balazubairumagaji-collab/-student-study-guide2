# AI Study Assistant

A small Python project for asking Google's Gemma 4 model study questions from a local browser page or the command line. It is designed for beginners and includes safe offline checks.

## 1. Open the project

Open this folder in VS Code. In VS Code, open **Terminal → New Terminal** for the commands below.

## 2. Check Python

```powershell
python --version
```

Python 3.10 or newer is recommended. This project was checked with Python 3.14.7.

## 3. Dependencies

This project uses Python's built-in HTTPS and JSON tools, so it has no package to install.

## 4. Run the offline checks

The checks use a fake response. They do not need an API key, access the network, or use API credits:

```powershell
python -m unittest -v
python main.py --self-test
```

## 5. Save your Google API key when you are ready

Create a new Gemini API key in Google AI Studio. If you previously shared a key in chat, revoke it and use a replacement. Open `api_key.json` in the project folder and paste the replacement into the value below:

```json
{
  "GEMINI_API_KEY": "paste-your-new-key-here"
}
```

Do not put the key in `main.py`, share it, or commit `api_key.json`. The app reads this local file when it starts. Alternatively, `GEMINI_API_KEY` in the environment takes precedence.

## 6. Open the browser app

For the simplest startup, stop any earlier copy with **Ctrl+C** in its terminal, then run this from the project folder in VS Code:

```powershell
python run_app.py
```

If port 8000 is occupied, the app automatically uses another available local port and opens that address.

If the key is present in `api_key.json` or `GEMINI_API_KEY` is already set, the app opens its local browser address without prompting for a key. Otherwise, the terminal privately prompts for one. The key is never sent to the browser. Keep the terminal open while you use the page; press **Ctrl+C** there to stop the app. It listens only on your own computer. Each submitted study question is sent to Google's Gemini API and may use API quota or incur charges depending on your account.

## 7. Start the command-line assistant

```powershell
python main.py
```

Type a question and press Enter. Type `quit` to exit. Each question makes a real request to Google's Gemini API. The offline checks above never make those requests.

## How the program works

- `make_client()` reads `GEMINI_API_KEY` from the environment or `api_key.json`; it never prints the key.
- `GeminiApiClient` calls Google's documented REST endpoint, sending the API key in a request header rather than in the URL.
- If Google marks a response as stopped at its token limit, the app requests a continuation; if it still cannot finish after several attempts, it reports that instead of presenting a known-truncated answer as complete.
- `ask_study_assistant()` sends the question to `gemma-4-26b-a4b-it` and returns its text response.
- `--self-test` and `test_main.py` use fake responses, so they are safe to run without a key.
