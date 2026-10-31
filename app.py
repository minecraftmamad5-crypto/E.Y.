# -*- coding: utf-8 -*-
import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 🔑 تنظیمات Pollinations AI
POLLINATIONS_API_KEY = "sk_d15ho5s4GEpfwtLTeKLFBm8yoRmntOda"
MODEL = "openai"  # مدل پیش‌فرض Pollinations برای چت
# آدرس سازگار با OpenAI در Pollinations
POLLINATIONS_URL = "https://gen.pollinations.ai/v1/chat/completions"

SYSTEM = "تو خیام هستی؛ یک دستیار هوشمند، مهربان و خوش‌برخورد متخصص علوم تجربی.در زمینه‌های فیزیک، شیمی، زیست‌شناسی، زمین‌شناسی، نجوم، بدن انسان، مواد، انرژی، جانداران و پدیده‌های طبیعی تخصص داری.مفاهیم علمی را ساده، دقیق و جذاب آموزش بده، به سؤالات با صبر و حوصله پاسخ بده و مطالب را متناسب با سطح دانش‌آموز توضیح بده."

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json() or {}
    messages = data.get("messages", [])

    if not messages:
        return jsonify({"error": "پیام خالی است"}), 400

    payload = {
        "model": MODEL,
        "messages": [{"role": "system", "content": SYSTEM}] + messages,
        "temperature": 0.7,
        "max_tokens": 700,
    }
    
    headers = {
        "Authorization": "Bearer " + POLLINATIONS_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        # ارسال درخواست به آدرس Pollinations
        r = requests.post(POLLINATIONS_URL, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return jsonify({"error": "خطای شبکه: " + str(e)}), 502

    if r.status_code != 200:
        return jsonify({"error": f"Pollinations {r.status_code}: {r.text[:300]}"}), r.status_code

    try:
        reply = r.json()["choices"][0]["message"]["content"]
    except Exception:
        return jsonify({"error": "پاسخ قابل تجزیه نیست"}), 500

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
