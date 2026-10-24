"""A beginner-friendly, command-line AI study assistant powered by Gemma 4."""

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from typing import Any


MODEL = "gemma-4-26b-a4b-it"
API_KEY_FILE = Path(__file__).with_name("api_key.json")
MAX_CONTINUATION_REQUESTS = 3
STUDY_INSTRUCTIONS = (
    "You are a clear, direct study assistant. Answer the student's exact "
    "question directly and stay on topic. Give only the concise answer, "
    "usually one or two sentences. Do not include a draft, preamble, extra "
    "explanation, worked steps, summary, or follow-up question unless the "
    "student explicitly asks for them. Use plain language. Make the answer "
    "complete and end with a finished sentence; never cut off mid-sentence."
)


class GoogleApiError(RuntimeError):
    """A request was rejected by Google's API."""


def ask_study_assistant(client: Any, question: str) -> str:
    """Send one study question to Google's Gemma model and return its answer."""
    response = client.generate_content(model=MODEL, question=question)
    return response


class GeminiApiClient:
    """Tiny Google API client built with Python's standard library."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def generate_content(self, model: str, question: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        contents = [{"role": "user", "parts": [{"text": question}]}]
        answer_parts: list[str] = []

        for attempt in range(MAX_CONTINUATION_REQUESTS + 1):
            payload = {
                "systemInstruction": {"parts": [{"text": STUDY_INSTRUCTIONS}]},
                "contents": contents,
                "generationConfig": {"temperature": 0.3},
            }
            request = Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key,
                },
                method="POST",
            )
            # The key is sent in a header, never placed in the URL or printed.
            try:
                with urlopen(request, timeout=60) as response:
                    data = json.loads(response.read().decode("utf-8"))
            except HTTPError as error:
                detail = ""
                try:
                    error_data = json.loads(error.read().decode("utf-8"))
                    error_info = error_data.get("error", {})
                    if isinstance(error_info, dict):
                        message = error_info.get("message")
                        status = error_info.get("status")
                        if isinstance(message, str):
                            detail = message.replace(self.api_key, "[redacted]")[:500]
                        if isinstance(status, str):
                            detail = f"{status}: {detail}" if detail else status
                except (UnicodeDecodeError, json.JSONDecodeError):
                    pass
                reason = f"Google API returned HTTP {error.code}"
                if detail:
                    reason = f"{reason} ({detail})"
                raise GoogleApiError(reason) from error

            candidates = data.get("candidates", [])
            if not candidates or not isinstance(candidates[0], dict):
                raise GoogleApiError(
                    "Google returned no answer. Try rephrasing the question."
                )
            candidate = candidates[0]
            content = candidate.get("content", {})
            parts = content.get("parts", []) if isinstance(content, dict) else []
            if not isinstance(parts, list):
                raise GoogleApiError("Google returned an unreadable answer.")
            text_parts = [
                part["text"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            ]
            answer_parts.extend(text_parts)

            if candidate.get("finishReason") != "MAX_TOKENS":
                return "\n".join(answer_parts)
            if attempt == MAX_CONTINUATION_REQUESTS:
                raise GoogleApiError(
                    "Google repeatedly stopped before finishing the answer. "
                    "Please ask a shorter question or split it into parts."
                )

            contents.append({"role": "model", "parts": parts})
            contents.append(
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": "Continue exactly where your previous response "
                            "stopped. Do not repeat any completed text. Finish the "
                            "current explanation and answer the original question."
                        }
                    ],
                }
            )

        raise GoogleApiError("Google could not complete the answer.")


def make_client() -> Any:
    """Create the Google GenAI client without displaying the secret key."""
    api_key = load_api_key()
    if not api_key:
        raise RuntimeError(
            "API key is not set. Add GEMINI_API_KEY to api_key.json or set it in the environment."
        )

    return GeminiApiClient(api_key)


def load_api_key() -> str | None:
    """Read the key from the environment or the local JSON file."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if api_key and api_key.strip():
        return api_key.strip()

    try:
        with API_KEY_FILE.open(encoding="utf-8") as key_file:
            config = json.load(key_file)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as error:
        raise RuntimeError("api_key.json is not valid JSON.") from error
    except OSError as error:
        raise RuntimeError("Could not read api_key.json.") from error

    if not isinstance(config, dict):
        raise RuntimeError("api_key.json must contain a JSON object.")
    api_key = config.get("GEMINI_API_KEY")
    if not isinstance(api_key, str):
        raise RuntimeError("api_key.json must contain a string GEMINI_API_KEY value.")
    return api_key.strip() or None


def run_self_test() -> bool:
    """Exercise the assistant locally without any network request."""

    class FakeClient:
        def generate_content(self, **kwargs: Any) -> Any:
            assert kwargs["model"] == MODEL
            assert kwargs["question"] == "Explain fractions simply."
            return "A fraction is a part of a whole."

    fake_client = FakeClient()
    answer = ask_study_assistant(fake_client, "Explain fractions simply.")
    assert answer == "A fraction is a part of a whole."
    print("Self-test passed. No API key or network request was used.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Ask an AI assistant study questions.")
    parser.add_argument(
        "--self-test", action="store_true", help="Run a safe offline test and exit."
    )
    args = parser.parse_args()

    if args.self_test:
        return 0 if run_self_test() else 1

    print("Gemma 4 Study Assistant — type 'quit' to leave.\n")
    try:
        client = make_client()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    except ImportError:
        print("Python's standard library is missing a required module.", file=sys.stderr)
        return 1

    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            return 0

        if question.lower() in {"quit", "exit"}:
            print("Goodbye!")
            return 0
        if not question:
            continue

        try:
            answer = ask_study_assistant(client, question)
            print(f"\nGemma 4: {answer}\n")
        except GoogleApiError as error:
            print(f"\n{error}\n", file=sys.stderr)
        except RuntimeError as error:
            print(f"\n{error}\n", file=sys.stderr)
        except Exception as error:
            # Avoid printing request details that might contain credentials.
            print(f"The Google API request failed ({type(error).__name__}). Check your connection and setup.", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
