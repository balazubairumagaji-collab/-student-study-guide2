"""Local browser interface for the Gemma 4 AI Study Assistant."""

import errno
import json
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from main import GoogleApiError, ask_study_assistant, make_client


PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Study Assistant</title>
  <style>
    :root { color-scheme: light; --ink:#17213a; --muted:#68728a; --blue:#4f63e8; --line:#e3e7f0; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; background:linear-gradient(135deg,#f4f6ff,#edf8f8); color:var(--ink); font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
    main { width:min(760px,calc(100% - 32px)); margin:7vh auto; }
    .card { background:white; border:1px solid var(--line); border-radius:24px; padding:clamp(24px,5vw,48px); box-shadow:0 20px 60px #26336b12; }
    .tag { display:inline-flex; align-items:center; gap:8px; color:#4353c9; background:#eef0ff; border-radius:999px; padding:6px 12px; font-size:13px; font-weight:650; }
    h1 { margin:18px 0 8px; font-size:clamp(30px,6vw,42px); line-height:1.15; letter-spacing:-.03em; }
    .intro { margin:0 0 28px; color:var(--muted); }
    label { display:block; font-weight:650; margin:0 0 9px; }
    textarea { display:block; width:100%; min-height:145px; resize:vertical; border:1px solid #cfd5e3; border-radius:14px; padding:15px; color:var(--ink); font:inherit; outline:none; }
    textarea:focus { border-color:var(--blue); box-shadow:0 0 0 3px #4f63e822; }
    .row { display:flex; align-items:center; justify-content:space-between; gap:14px; margin-top:14px; }
    .hint { color:var(--muted); font-size:13px; }
    button { border:0; border-radius:12px; padding:12px 20px; background:var(--blue); color:white; font:inherit; font-weight:650; cursor:pointer; }
    button:hover { background:#3e50d4; }
    button:disabled { opacity:.65; cursor:wait; }
    .answer { margin-top:28px; border:1px solid var(--line); background:#fbfcff; border-radius:16px; padding:20px; white-space:pre-wrap; overflow-wrap:anywhere; }
    .answer h2 { margin:0 0 10px; font-size:18px; }
    .answer[hidden] { display:none; }
    .status { color:var(--muted); min-height:24px; margin-top:12px; }
    .status.error { color:#a52828; }
    footer { color:var(--muted); font-size:13px; margin:18px 4px; text-align:center; }
    @media(max-width:520px) { .row { align-items:stretch; flex-direction:column; } button { width:100%; } }
  </style>
</head>
<body>
  <main>
    <section class="card" aria-labelledby="title">
      <span class="tag">✦ Powered by Google Gemma 4</span>
      <h1 id="title">Your AI Study Assistant</h1>
      <p class="intro">Ask a question about something you’re learning. Get a clear explanation, one step at a time.</p>
      <form id="ask-form">
        <label for="question">What are you studying?</label>
        <textarea id="question" name="question" maxlength="2000" placeholder="For example: Explain fractions with a simple example." required></textarea>
        <div class="row">
          <span class="hint">Your question is sent to Google when you press Ask.</span>
          <button id="ask-button" type="submit">Ask Gemma</button>
        </div>
      </form>
      <p id="status" class="status" role="status" aria-live="polite"></p>
      <article id="answer-box" class="answer" hidden>
        <h2>Gemma’s explanation</h2>
        <div id="answer"></div>
      </article>
    </section>
    <footer>Your API key stays in this local Python app and is never placed in the webpage.</footer>
  </main>
  <script>
    const form = document.querySelector('#ask-form');
    const question = document.querySelector('#question');
    const button = document.querySelector('#ask-button');
    const status = document.querySelector('#status');
    const answerBox = document.querySelector('#answer-box');
    const answer = document.querySelector('#answer');
    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const text = question.value.trim();
      if (!text) return;
      button.disabled = true;
      status.className = 'status';
      status.textContent = 'Thinking…';
      answerBox.hidden = true;
      try {
        const response = await fetch('/ask', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ question: text })
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
        answer.textContent = data.answer;
        answerBox.hidden = false;
        status.textContent = '';
      } catch (error) {
        status.className = 'status error';
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    });
  </script>
</body>
</html>"""


class StudyAssistantHandler(BaseHTTPRequestHandler):
    """Serve the page and handle study questions on localhost."""

    server_version = "StudyAssistant/1.0"

    def send_json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path != "/":
            self.send_error(404, "Page not found")
            return
        body = PAGE.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/ask":
            self.send_json(404, {"error": "Page not found."})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid request."})
            return
        if length < 1 or length > 10_000:
            self.send_json(400, {"error": "Please enter a shorter study question."})
            return

        try:
            data = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self.send_json(400, {"error": "The question could not be read."})
            return

        question = data.get("question") if isinstance(data, dict) else None
        if not isinstance(question, str) or not question.strip() or len(question) > 2_000:
            self.send_json(400, {"error": "Enter a question up to 2,000 characters long."})
            return

        try:
            response = ask_study_assistant(make_client(), question.strip())
        except GoogleApiError as error:
            self.send_json(502, {"error": str(error)})
            return
        except RuntimeError as error:
            self.send_json(
                503,
                {"error": str(error)},
            )
            return
        except Exception as error:
            self.send_json(
                502,
                {"error": f"Google’s request failed ({type(error).__name__}). Check the connection and API setup."},
            )
            return

        self.send_json(200, {"answer": response})

    def log_message(self, format: str, *args: Any) -> None:
        # Do not log request bodies or study questions.
        super().log_message(format, *args)


def main(open_browser: bool = False) -> None:
    host = "127.0.0.1"
    address = (host, 8000)
    with socket.socket() as probe:
        port_is_occupied = probe.connect_ex(address) == 0

    if port_is_occupied:
        server = ThreadingHTTPServer(("127.0.0.1", 0), StudyAssistantHandler)
    else:
        try:
            server = ThreadingHTTPServer(address, StudyAssistantHandler)
        except OSError as error:
            if error.errno != errno.EADDRINUSE and getattr(error, "winerror", None) != 10048:
                raise
            server = ThreadingHTTPServer(("127.0.0.1", 0), StudyAssistantHandler)

    host, port = server.server_address[:2]
    url = f"http://{host}:{port}"
    print(f"AI Study Assistant is ready at {url}")
    print("Keep this terminal open. Press Ctrl+C to stop the local app.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStudy Assistant stopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
