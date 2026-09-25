import unittest
from unittest.mock import Mock, patch

from gemini_runtime import generate_with_fallback, list_text_models, load_sheet_keys, parse_key_rows


def response(status, payload=None):
    result = Mock(status_code=status)
    result.json.return_value = payload or {}
    return result


class GeminiRuntimeTests(unittest.TestCase):
    @patch("google.auth.transport.requests.AuthorizedSession")
    @patch("google.oauth2.service_account.Credentials.from_service_account_info")
    def test_sheet_loader_uses_read_only_scope_and_expected_tab(self, credentials, session):
        session.return_value.get.return_value.json.return_value = {
            "values": [["Key A", "secret-a", "TRUE"]]
        }
        entries = load_sheet_keys("sheet-id", {"type": "service_account"})
        self.assertEqual([entry.label for entry in entries], ["Key A"])
        self.assertEqual(credentials.call_args.kwargs["scopes"],
                         ["https://www.googleapis.com/auth/spreadsheets.readonly"])
        request_url = session.return_value.get.call_args.args[0]
        self.assertIn("/spreadsheets/sheet-id/values/", request_url)
        self.assertIn("API%20Keys", request_url)

    def test_sheet_rows_keep_only_named_enabled_keys(self):
        rows = [
            ["Key A", "secret-a", "TRUE"],
            ["Key B", "secret-b", "FALSE"],
            ["Key C", "secret-c"],
            ["", "secret-d", "TRUE"],
        ]
        self.assertEqual([(key.label, key.value) for key in parse_key_rows(rows)],
                         [("Key A", "secret-a"), ("Key C", "secret-c")])
        with self.assertRaises(ValueError):
            parse_key_rows([["Key A", "secret-a"], ["Key A", "secret-b"]])

    @patch("gemini_runtime.requests.get")
    def test_model_list_only_includes_gemini_text_models(self, get):
        get.return_value = response(200, {"models": [
            {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent"]},
            {"name": "models/gemini-embedding-001", "supportedGenerationMethods": ["embedContent"]},
            {"name": "models/other", "supportedGenerationMethods": ["generateContent"]},
        ]})
        self.assertEqual(list_text_models("private-key"), ("gemini-2.5-flash",))
        self.assertEqual(get.call_args.kwargs["headers"], {"x-goog-api-key": "private-key"})

    @patch("gemini_runtime.requests.post")
    def test_quota_error_tries_next_selected_model(self, post):
        post.side_effect = [
            response(429),
            response(200, {"candidates": [{"content": {"parts": [{"text": "Kết quả"}]}}]}),
        ]
        result = generate_with_fallback("private-key", ("gemini-first", "gemini-second"),
                                        "rules", "article", auto_switch=True)
        self.assertEqual(result.text, "Kết quả")
        self.assertEqual(result.model, "gemini-second")
        self.assertEqual(post.call_count, 2)

    @patch("gemini_runtime.requests.post")
    def test_bad_key_does_not_retry_other_model(self, post):
        post.return_value = response(403)
        result = generate_with_fallback("bad-key", ("gemini-first", "gemini-second"),
                                        "rules", "article", auto_switch=True)
        self.assertIsNone(result.text)
        self.assertIn("API key", result.error)
        post.assert_called_once()

    @patch("gemini_runtime.requests.post")
    def test_invalid_model_request_tries_next_model(self, post):
        post.side_effect = [
            response(400),
            response(200, {"candidates": [{"content": {"parts": [{"text": "Tin chính"}]}}]}),
        ]
        result = generate_with_fallback("private-key", ("gemini-first", "gemini-second"),
                                        "rules", "article", auto_switch=True)
        self.assertEqual(result.model, "gemini-second")
        self.assertEqual(post.call_count, 2)

    @patch("gemini_runtime.requests.post")
    def test_safety_block_does_not_retry_other_model(self, post):
        post.return_value = response(200, {"candidates": [{"finishReason": "SAFETY"}]})
        result = generate_with_fallback("private-key", ("gemini-first", "gemini-second"),
                                        "rules", "article", auto_switch=True)
        self.assertIsNone(result.text)
        post.assert_called_once()

    @patch("gemini_runtime.requests.post")
    def test_manual_mode_only_calls_first_model(self, post):
        post.return_value = response(429)
        result = generate_with_fallback("private-key", ("gemini-first", "gemini-second"),
                                        "rules", "article", auto_switch=False)
        self.assertIsNone(result.text)
        post.assert_called_once()


if __name__ == "__main__":
    unittest.main()
