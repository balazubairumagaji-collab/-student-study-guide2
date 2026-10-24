"""Offline tests; these never call Google's API."""

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

from main import (
    GeminiApiClient,
    MODEL,
    ask_study_assistant,
    load_api_key,
    make_client,
    run_self_test,
)


class StudyAssistantTests(unittest.TestCase):
    def test_offline_self_test_passes(self):
        self.assertTrue(run_self_test())

    def test_missing_key_is_reported_without_showing_a_secret(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("main.API_KEY_FILE", Path("missing-api-key.json")):
                with self.assertRaisesRegex(RuntimeError, "API key is not set"):
                    make_client()

    def test_api_key_is_loaded_from_json_file(self):
        with tempfile.TemporaryDirectory() as directory:
            key_file = Path(directory) / "api_key.json"
            key_file.write_text(
                json.dumps({"GEMINI_API_KEY": "local-test-key"}), encoding="utf-8"
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("main.API_KEY_FILE", key_file):
                    self.assertEqual(load_api_key(), "local-test-key")
                    self.assertEqual(make_client().api_key, "local-test-key")

    def test_answer_comes_from_gemma_response(self):
        class FakeClient:
            def generate_content(self, **kwargs):
                self.kwargs = kwargs
                return "Try a smaller example."

        client = FakeClient()
        answer = ask_study_assistant(client, "Help me study")

        self.assertEqual(answer, "Try a smaller example.")
        self.assertEqual(client.kwargs["model"], MODEL)
        self.assertEqual(client.kwargs["question"], "Help me study")

    @patch("main.urlopen")
    def test_api_client_uses_google_endpoint_and_key_header(self, mock_urlopen):
        fake_response = mock_urlopen.return_value.__enter__.return_value
        fake_response.read.return_value = json.dumps(
            {"candidates": [{"content": {"parts": [{"text": "Study step one."}]}}]}
        ).encode("utf-8")

        answer = GeminiApiClient("test-key-only").generate_content(
            MODEL, "Help me study"
        )

        self.assertEqual(answer, "Study step one.")
        request = mock_urlopen.call_args.args[0]
        self.assertIn("generativelanguage.googleapis.com", request.full_url)
        self.assertNotIn("test-key-only", request.full_url)
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key-only")
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["contents"][0]["parts"][0]["text"], "Help me study")
        self.assertNotIn("maxOutputTokens", payload["generationConfig"])
        instructions = payload["systemInstruction"]["parts"][0]["text"]
        self.assertIn("Answer the student's exact question directly", instructions)
        self.assertIn("Give only the concise answer", instructions)
        self.assertIn("never cut off mid-sentence", instructions)

    @patch("main.urlopen")
    def test_api_error_includes_google_reason_without_exposing_key(self, mock_urlopen):
        secret = "local-secret-key"
        error_body = json.dumps(
            {
                "error": {
                    "code": 400,
                    "status": "INVALID_ARGUMENT",
                    "message": f"Invalid API key: {secret}",
                }
            }
        ).encode("utf-8")
        mock_urlopen.side_effect = HTTPError(
            "https://generativelanguage.googleapis.com/",
            400,
            "Bad Request",
            {},
            io.BytesIO(error_body),
        )

        with self.assertRaises(RuntimeError) as raised:
            GeminiApiClient(secret).generate_content(MODEL, "Help me study")

        self.assertIn("HTTP 400", str(raised.exception))
        self.assertIn("INVALID_ARGUMENT", str(raised.exception))
        self.assertNotIn(secret, str(raised.exception))

    @patch("main.urlopen")
    def test_api_continues_when_google_stops_at_token_limit(self, mock_urlopen):
        first_response = mock_urlopen.return_value.__enter__.return_value
        first_response.read.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": "The answer begins"}],
                        },
                        "finishReason": "MAX_TOKENS",
                    }
                ]
            }
        ).encode("utf-8")
        second_response = unittest.mock.MagicMock()
        second_response.__enter__.return_value.read.return_value = json.dumps(
            {
                "candidates": [
                    {
                        "content": {"parts": [{"text": " and ends completely."}]},
                        "finishReason": "STOP",
                    }
                ]
            }
        ).encode("utf-8")
        mock_urlopen.side_effect = [
            contextlib.nullcontext(first_response),
            contextlib.nullcontext(second_response.__enter__.return_value),
        ]

        answer = GeminiApiClient("test-key").generate_content(MODEL, "Explain this")

        self.assertEqual(answer, "The answer begins\n and ends completely.")
        self.assertEqual(mock_urlopen.call_count, 2)
        continuation_payload = json.loads(mock_urlopen.call_args_list[1].args[0].data)
        self.assertEqual(continuation_payload["contents"][1]["role"], "model")
        self.assertIn("The answer begins", continuation_payload["contents"][1]["parts"][0]["text"])
        self.assertEqual(continuation_payload["contents"][2]["role"], "user")


if __name__ == "__main__":
    unittest.main()
