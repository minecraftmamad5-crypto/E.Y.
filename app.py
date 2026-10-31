# -*- coding: utf-8 -*-
"""
EXPERA AI - Flask website backend
Python 3.8+
Install: pip install Flask requests
"""

import os
import uuid
import json
import sqlite3
import threading
from typing import Any, Dict, List, Optional, Tuple

import requests
from flask import Flask, render_template, request, jsonify, session

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET")

# ---------------------------------------------------------------------
# EXPERA configuration
# ---------------------------------------------------------------------

SYSTEM_PROMPT = (
    "تو EXPERA هستی؛ یک دستیار هوشمند، مهربان و خوش‌برخورد متخصص آزمایش‌های "
    "علمی و عناصر شیمیایی. در زمینه‌های طراحی و توضیح آزمایش‌ها، عناصر شیمیایی، "
    "جدول تناوبی، ویژگی‌های عناصر، ابزارهای آزمایشگاهی و آزمایش‌های فیزیک، "
    "شیمی و زیست‌شناسی تخصص داری. مانند یک معلم حرفه‌ای، هر آزمایشی را که "
    "دانش‌آموز نام می‌برد، از هدف و وسایل موردنیاز تا مراحل انجام، توضیح علمی، "
    "نتایج مورد انتظار و نکات ایمنی به‌صورت کامل، دقیق و مرحله‌به‌مرحله آموزش بده."
)

CONNECT_TIMEOUT = 8
AI_READ_TIMEOUT = 45
MAX_OUTPUT_TOKENS = 650
MAX_HISTORY_MESSAGES = 12
MAX_INPUT_CHARACTERS = 10000
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "expera_history.sqlite3")

# ---------------------------------------------------------------------
# کلیدهای پیش‌فرض (اگر متغیرهای محیطی تنظیم نشوند، از اینها استفاده می‌شود)
# ---------------------------------------------------------------------

DEFAULT_OPENAI_KEYS = "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"
DEFAULT_GEMINI_KEYS = "AQ.Ab8RN6KJypJqgCm3GtYMZC93dbBo725m_mq_ZkZtenFRnKFMIQ,AQ.Ab8RN6IJJyiyF0jkg5fYkEN-_kODYt83N4ITpJJcnSggHn8T_g"
DEFAULT_DEEPSEEK_KEYS = "sk-8f19e917cc67474b984f0a787a9c9890,sk-10eb1a3b9afc44e281a2ef79a1c5d041,sk-03efbb0bbaf04e62adb31093fafadbf3"
DEFAULT_GROQ_KEYS = "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"
DEFAULT_POLLINATIONS_KEYS = "sk_n4XyE1lrKefs6nOoZ8iAJLeJukcJ1PqT,sk_Jg9NXZNON3etsZRiULoYJiyQtMjCbo6A,sk_d15ho5s4GEpfwtLTeKLFBm8yoRmntOda"

# خواندن از محیط، و در صورت نبود، استفاده از مقادیر پیش‌فرض بالا
def _keys(env_name: str, default_val: str = "") -> List[str]:
    raw = os.getenv(env_name, default_val)
    return list(dict.fromkeys(k.strip() for k in raw.split(",") if k.strip()))

PROVIDERS = [
    {
        "name": "OpenAI",
        "url": "https://api.openai.com/v1/responses",
        "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"), # مدل تصحیح شد
        "kind": "responses",
        "keys": _keys("OPENAI_API_KEYS", DEFAULT_OPENAI_KEYS),
    },
    {
        "name": "Google Gemini",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
        "model": os.getenv("GEMINI_MODEL", "gemini-1.5-flash"), # مدل تصحیح شد
        "kind": "chat",
        "keys": _keys("GEMINI_API_KEYS", DEFAULT_GEMINI_KEYS),
        "extra_payload": {"reasoning_effort": "low"},
    },
    {
        "name": "DeepSeek",
        "url": "https://api.deepseek.com/chat/completions",
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"), # مدل تصحیح شد
        "kind": "chat",
        "keys": _keys("DEEPSEEK_API_KEYS", DEFAULT_DEEPSEEK_KEYS),
        "extra_payload": {"thinking": {"type": "disabled"}},
    },
    {
        "name": "Groq",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "model": os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"), # مدل تصحیح شد
        "kind": "chat",
        "keys": _keys("GROQ_API_KEYS", DEFAULT_GROQ_KEYS),
        "token_param": "max_completion_tokens",
    },
    {
        "name": "Pollinations",
        "url": "https://gen.pollinations.ai/v1/chat/completions",
        "model": os.getenv("POLLINATIONS_MODEL", "openai"),
        "kind": "chat",
        "keys": _keys("POLLINATIONS_API_KEYS", DEFAULT_POLLINATIONS_KEYS),
    },
]

_thread_local = threading.local()
_db_lock = threading.RLock()

# ---------------------------------------------------------------------
# Persistent per-browser conversation history (SQLite)
# ---------------------------------------------------------------------

def _db_connection():
    conn = sqlite3.connect(DATABASE_PATH, timeout=15)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY,
            history TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )"""
    )
    return conn

def _get_history(conversation_id: str) -> List[Dict[str, str]]:
    with _db_lock:
        conn = _db_connection()
        try:
            row = conn.execute(
                "SELECT history FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            ).fetchone()
            if not row:
                return []
            value = json.loads(row[0])
            return value if isinstance(value, list) else []
        finally:
            conn.close()

def _save_history(conversation_id: str, history: List[Dict[str, str]]) -> None:
    safe_history = history[-MAX_HISTORY_MESSAGES:]
    with _db_lock:
        conn = _db_connection()
        try:
            conn.execute(
                """INSERT INTO conversations (conversation_id, history, updated_at)
                   VALUES (?, ?, CURRENT_TIMESTAMP)
                   ON CONFLICT(conversation_id) DO UPDATE SET
                   history = excluded.history, updated_at = CURRENT_TIMESTAMP""",
                (conversation_id, json.dumps(safe_history, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

def _clear_history(conversation_id: str) -> None:
    with _db_lock:
        conn = _db_connection()
        try:
            conn.execute(
                "DELETE FROM conversations WHERE conversation_id = ?",
                (conversation_id,),
            )
            conn.commit()
        finally:
            conn.close()

def _conversation_id() -> str:
    value = session.get("expera_conversation_id")
    if not value:
        value = str(uuid.uuid4())
        session["expera_conversation_id"] = value
    return value

# ---------------------------------------------------------------------
# Provider API helpers and fallback mechanism
# ---------------------------------------------------------------------

def _session_requests() -> requests.Session:
    sess = getattr(_thread_local, "requests_session", None)
    if sess is None:
        sess = requests.Session()
        _thread_local.requests_session = sess
    return sess

def _safe_error_text(response: requests.Response) -> str:
    try:
        data = response.json()
        if isinstance(data, dict):
            error = data.get("error", data)
            if isinstance(error, dict):
                return str(error.get("message") or error.get("code") or "API error")[:250]
            if isinstance(error, str):
                return error[:250]
            if data.get("description"):
                return str(data["description"])[:250]
    except (ValueError, TypeError):
        pass
    return (response.text or "Unknown API error")[:250]

def _chat_messages(history: List[Dict[str, str]], user_text: str) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in history[-MAX_HISTORY_MESSAGES:]:
        role, content = item.get("role"), item.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            messages.append({"role": role, "content": content.strip()})
    messages.append({"role": "user", "content": user_text.strip()})
    return messages

def _extract_chat_answer(data: Dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    content = (choices[0].get("message") or {}).get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, str):
                parts.append(part)
            elif isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
        return "\n".join(parts).strip()
    return ""

def _extract_responses_answer(data: Dict[str, Any]) -> str:
    direct = data.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    parts = []
    for item in data.get("output", []) or []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for part in item.get("content", []) or []:
            if isinstance(part, dict) and part.get("type") in ("output_text", "text"):
                if isinstance(part.get("text"), str):
                    parts.append(part["text"])
    return "\n".join(parts).strip()

def _call_provider(
    provider: Dict[str, Any],
    api_key: str,
    history: List[Dict[str, str]],
    user_text: str,
) -> Tuple[Optional[str], str]:
    headers = {
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    messages = _chat_messages(history, user_text)

    if provider["kind"] == "responses":
        payload = {
            "model": provider["model"],
            "input": [
                {"role": item["role"], "content": item["content"]}
                for item in messages if item["role"] != "system"
            ],
            "instructions": SYSTEM_PROMPT,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
            "store": False,
        }
    else:
        payload = {
            "model": provider["model"],
            "messages": messages,
            "stream": False,
            provider.get("token_param", "max_tokens"): MAX_OUTPUT_TOKENS,
        }
        payload.update(provider.get("extra_payload", {}))

    try:
        response = _session_requests().post(
            provider["url"],
            headers=headers,
            json=payload,
            timeout=(CONNECT_TIMEOUT, AI_READ_TIMEOUT),
        )
    except requests.RequestException as exc:
        app.logger.warning("%s network error: %s", provider["name"], str(exc)[:180])
        return None, "network"

    if response.status_code != 200:
        app.logger.warning(
            "%s HTTP %s: %s",
            provider["name"], response.status_code, _safe_error_text(response),
        )
        if response.status_code in (401, 403):
            return None, "bad_key"
        if response.status_code in (402, 429):
            return None, "quota"
        if response.status_code >= 500:
            return None, "server"
        return None, "configuration"

    try:
        data = response.json()
    except ValueError:
        return None, "bad_json"

    answer = (
        _extract_responses_answer(data)
        if provider["kind"] == "responses"
        else _extract_chat_answer(data)
    )
    return (answer, "ok") if answer else (None, "empty")

def ask_ai(user_text: str, history: Optional[List[Dict[str, str]]] = None):
    """Try providers in order; only try another key for 401/403."""
    user_text = (user_text or "").strip()
    if not user_text:
        return "لطفاً یک پیام بنویس.", None

    user_text = user_text[:MAX_INPUT_CHARACTERS]
    history = history or []

    if not any(provider["keys"] for provider in PROVIDERS):
        return "هیچ کلید API تنظیم نشده است. متغیرهای محیطی سرویس‌ها را تنظیم کن.", None

    for provider in PROVIDERS:
        keys = provider["keys"]
        if not keys:
            continue

        for index, api_key in enumerate(keys):
            answer, reason = _call_provider(provider, api_key, history, user_text)
            if reason == "ok" and answer:
                app.logger.info("EXPERA answered using %s (%s)", provider["name"], provider["model"])
                return answer, provider["name"]

            if reason == "bad_key" and index + 1 < len(keys):
                continue
            break

    return (
        "متأسفانه هیچ‌کدام از سرویس‌های هوش مصنوعی در دسترس نیستند. "
        "اتصال اینترنت، کلیدهای API، سهمیه و دسترسی مدل‌ها را بررسی کن.",
        None,
    )

# ---------------------------------------------------------------------
# Website commands (equivalent to the Bale bot commands)
# ---------------------------------------------------------------------

def _help_text() -> str:
    return (
        "سلام! 👋 من EXPERA هستم؛ دستیار هوشمند آزمایش‌های علمی و عناصر شیمیایی.\n\n"
        "سؤالت را بنویس تا راهنمایی‌ات کنم.\n\n"
        "/start — شروع گفت‌وگو\n"
        "/help — راهنما\n"
        "/reset — پاک کردن حافظه همین گفت‌وگو\n"
        "/status — وضعیت سرویس‌های هوش مصنوعی"
    )

def _status_text() -> str:
    lines = ["وضعیت سرویس‌های هوش مصنوعی EXPERA:"]
    for index, provider in enumerate(PROVIDERS, start=1):
        count = len(provider["keys"])
        if count:
            lines.append(
                "{}. {} — مدل {} — {} کلید تنظیم‌شده".format(
                    index, provider["name"], provider["model"], count
                )
            )
        else:
            lines.append("{}. {} — کلیدی تنظیم نشده".format(index, provider["name"]))
    return "\n".join(lines)

def _extract_latest_user_message(data: Dict[str, Any]) -> str:
    messages = data.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user":
                content = item.get("content")
                if isinstance(content, str):
                    return content.strip()
    message = data.get("message")
    return message.strip() if isinstance(message, str) else ""

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_text = _extract_latest_user_message(data)

    if not user_text:
        return jsonify({"error": "پیام خالی است"}), 400
    if len(user_text) > MAX_INPUT_CHARACTERS:
        return jsonify({"error": "پیام بیش از حد طولانی است."}), 413

    conversation_id = _conversation_id()
    command = user_text.split()[0].split("@")[0].lower()

    if command == "/start":
        return jsonify({"reply": "ربات EXPERA فعال است. ✅\n\n" + _help_text()})
    if command == "/help":
        return jsonify({"reply": _help_text()})
    if command == "/status":
        return jsonify({"reply": _status_text()})
    if command == "/reset":
        _clear_history(conversation_id)
        return jsonify({"reply": "حافظه این گفت‌وگو پاک شد. ✅"})
    if user_text.startswith("/"):
        return jsonify({"reply": "دستور شناخته نشد. برای دیدن راهنما /help را بفرست."})

    history = _get_history(conversation_id)
    answer, provider_name = ask_ai(user_text, history)

    if provider_name:
        history.extend([
            {"role": "user", "content": user_text},
            {"role": "assistant", "content": answer},
        ])
        _save_history(conversation_id, history)

    return jsonify({"reply": answer, "provider": provider_name})

@app.route("/api/reset", methods=["POST"])
def reset():
    _clear_history(_conversation_id())
    return jsonify({"success": True, "reply": "حافظه این گفت‌وگو پاک شد. ✅"})

@app.route("/api/status", methods=["GET"])
def status():
    return jsonify({
        "providers": [
            {
                "name": p["name"],
                "model": p["model"],
                "configured": bool(p["keys"]),
                "key_count": len(p["keys"]),
            }
            for p in PROVIDERS
        ]
    })

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "app": "EXPERA AI"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
