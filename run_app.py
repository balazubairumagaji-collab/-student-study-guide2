"""Start the local browser app and prompt privately for a Gemini API key."""

import getpass
import os
import sys

from main import load_api_key
from web_app import main


def run() -> int:
    try:
        configured_key = load_api_key()
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1

    if not configured_key:
        try:
            api_key = getpass.getpass(
                "Paste your Gemini API key here (input is hidden): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nNo key entered. The assistant was not started.")
            return 1

        if not api_key:
            print("No key entered. The assistant was not started.")
            return 1

        # Keep the key only in this process; never write it to a file or print it.
        os.environ["GEMINI_API_KEY"] = api_key

    try:
        main(open_browser=True)
    except OSError as error:
        if getattr(error, "winerror", None) == 10048:
            print("Port 8000 is already in use. Stop the other Study Assistant window with Ctrl+C, then try again.")
        else:
            print(f"Could not start the local app ({type(error).__name__}).")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
