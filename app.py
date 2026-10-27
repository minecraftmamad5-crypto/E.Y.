# -*- coding: utf-8 -*-
"""وب‌سایت چت — همان مکانیزم ربات Bale بدون هیچ تغییری در کلید/مدل/Endpoint."""
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 🔑 همان کلید و همان مدل فایل ربات Bale — دست‌نخورده
OPENAI_API_KEY = "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"
MODEL = "gpt-6-luna"

OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"

SYSTEM_INSTRUCTIONS = (
    "تو یک دستیار هوش مصنوعی فارسی‌زبان، دقیق و خوش‌برخورد هستی. "
    "معمولاً به زبان خود کاربر پاسخ بده. جواب‌ها را روشن و مفید بنویس و "
    "اگر از چیزی مطمئن نیستی، صادقانه بگو."
)

MAX_HISTORY_MESSAGES = 10


def ask_openai(messages):
    """همان تابع ask_openai ربات Bale، فقط به‌جای CHAT_HISTORY آرگومان می‌گیرد."""
    input_messages = messages[-MAX_HISTORY_MESSAGES:]

    payload = {
        "model": MODEL,
        "instructions": SYSTEM_INSTRUCTIONS,
        "input": input_messages,
        "max_output_tokens": 700,
    }
    headers = {
        "Authorization": "Bearer " + OPENAI_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            OPENAI_RESPONSES_URL, headers=headers, json=payload, timeout=90
        )
    except requests.exceptions.Timeout:
        return None, "پاسخ‌گویی طول کشید؛ لطفاً دوباره پیام بده.", 504
    except requests.exceptions.RequestException:
        return None, "اتصال به سرویس هوش مصنوعی برقرار نشد. اینترنت و دسترسی به API را بررسی کن.", 502

    if response.status_code == 401:
        print("OpenAI API error: 401 - API key is invalid or unauthorized.")
        return None, "کلید OpenAI معتبر نیست یا اجازه دسترسی ندارد؛ تنظیمات کلید را بررسی کن.", 401
    if response.status_code == 429:
        print("OpenAI API error: 429 - rate limit or quota problem.")
        return None, "محدودیت درخواست یا اعتبار API به پایان رسیده است؛ وضعیت حساب API را بررسی کن.", 429
    if not response.ok:
        print("OpenAI API error {}: {}".format(response.status_code, response.text[:500]))
        return None, "سرویس هوش مصنوعی خطا داد. چند لحظه بعد دوباره امتحان کن.", response.status_code

    try:
        data = response.json()
    except ValueError:
        print("OpenAI returned invalid JSON.")
        return None, "پاسخ سرویس قابل خواندن نبود؛ دوباره امتحان کن.", 500

    # استخراج متن دقیقاً مثل ربات Bale
    answer_parts = []
    for item in data.get("output", []):
        if item.get("type") == "message":
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    text_part = content.get("text", "")
                    if text_part:
                        answer_parts.append(text_part)

    answer = "\n".join(answer_parts).strip()
    if not answer:
        print("No output text in API response: {}".format(str(data)[:500]))
        return None, "این بار جواب متنی دریافت نکردم؛ دوباره امتحان کن.", 500

    return answer, None, 200


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "پیام خالی است"}), 400

    clean = []
    for m in messages:
        if (isinstance(m, dict)
                and m.get("role") in ("user", "assistant")
                and isinstance(m.get("content"), str)):
            clean.append({"role": m["role"], "content": m["content"]})

    if not clean or clean[-1]["role"] != "user":
        return jsonify({"error": "آخرین پیام باید از کاربر باشد"}), 400

    answer, error, status = ask_openai(clean)
    if error:
        return jsonify({"error": error}), status

    return jsonify({"reply": answer})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
