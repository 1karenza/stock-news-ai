"""Private Google Sheet key catalog and Gemini text generation."""

from dataclasses import dataclass
import re
from urllib.parse import quote

import requests


DEFAULT_MODELS = ("gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro")
SHEET_RANGE = "'API Keys'!A2:C"
RECOVERABLE_STATUSES = {400, 404, 408, 429, 500, 502, 503, 504}


@dataclass(frozen=True)
class ApiKeyEntry:
    label: str
    value: str


@dataclass(frozen=True)
class GeminiResult:
    text: str | None
    model: str | None
    error: str | None


def parse_key_rows(rows):
    """Read Label | API key | Enabled; blank Enabled means active."""
    entries = []
    labels = set()
    for row in rows:
        if len(row) < 2:
            continue
        label, value = str(row[0]).strip(), str(row[1]).strip()
        enabled = str(row[2]).strip().lower() if len(row) > 2 else ""
        if not label or not value or enabled in {"no", "false", "0", "off", "không"}:
            continue
        if label in labels:
            raise ValueError("Tên API key trong Google Sheet phải là duy nhất.")
        labels.add(label)
        entries.append(ApiKeyEntry(label, value))
    return entries


def load_sheet_keys(spreadsheet_id, service_account_info):
    """Read a private sheet using a service account shared with the workbook."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials

    credentials = Credentials.from_service_account_info(
        service_account_info,
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    session = AuthorizedSession(credentials)
    response = session.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{quote(spreadsheet_id, safe='')}/values/"
        f"{quote(SHEET_RANGE, safe='')}",
        timeout=(5, 20),
    )
    response.raise_for_status()
    return parse_key_rows(response.json().get("values", []))


def list_text_models(api_key):
    """List the key's models that support generateContent."""
    models = []
    page_token = None
    while True:
        params = {"pageSize": 1000}
        if page_token:
            params["pageToken"] = page_token
        response = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            headers={"x-goog-api-key": api_key},
            params=params,
            timeout=(5, 20),
        )
        response.raise_for_status()
        payload = response.json()
        for entry in payload.get("models", []):
            name = entry.get("name", "")
            non_text = ("image", "audio", "tts", "live", "embedding")
            if (name.startswith("models/gemini-")
                    and not any(kind in name.lower() for kind in non_text)
                    and "generateContent" in entry.get("supportedGenerationMethods", [])):
                models.append(name.removeprefix("models/"))
        page_token = payload.get("nextPageToken")
        if not page_token:
            break
    return tuple(dict.fromkeys(models))


def generate_with_fallback(api_key, models, instructions, content, auto_switch=False):
    """Try selected models in order; only temporary/model errors trigger fallback."""
    choices = tuple(models if auto_switch else models[:1])
    if not api_key or not choices:
        return GeminiResult(None, None, "Chưa chọn API key và mô hình Gemini.")

    body = {
        "systemInstruction": {"parts": [{"text": instructions}]},
        "contents": [{"role": "user", "parts": [{"text": content}]}],
    }
    for index, model in enumerate(choices):
        if not re.fullmatch(r"gemini-[A-Za-z0-9_.-]+", model):
            return GeminiResult(None, None, "Tên mô hình Gemini không hợp lệ.")
        try:
            response = requests.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": api_key},
                json=body,
                timeout=(5, 90),
            )
        except requests.RequestException:
            if index + 1 < len(choices):
                continue
            return GeminiResult(None, None, "Không kết nối được Gemini. Hãy thử quét lại.")

        if response.status_code != 200:
            if response.status_code in RECOVERABLE_STATUSES and index + 1 < len(choices):
                continue
            if response.status_code in {401, 403}:
                return GeminiResult(None, None, "API key không được Gemini chấp nhận hoặc không có quyền sử dụng.")
            return GeminiResult(None, None, f"Gemini chưa xử lý được yêu cầu (HTTP {response.status_code}).")

        try:
            candidate = response.json().get("candidates", [{}])[0]
            if candidate.get("finishReason") == "SAFETY":
                return GeminiResult(None, None, "Gemini không thể xử lý nội dung bài viết này.")
            parts = candidate.get("content", {}).get("parts", [])
            text = "\n".join(part.get("text", "") for part in parts if part.get("text")).strip()
        except (ValueError, IndexError, AttributeError, TypeError):
            text = ""
        if text:
            return GeminiResult(text, model, None)
        if index + 1 == len(choices):
            return GeminiResult(None, None, "Gemini không trả về nội dung tóm tắt.")

    return GeminiResult(None, None, "Các mô hình đã chọn đều chưa xử lý được bài viết.")
