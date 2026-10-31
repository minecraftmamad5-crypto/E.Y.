# -*- coding: utf-8 -*-
import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 🔑 تنظیمات گوگل جمنای (Google AI Studio)
GOOGLE_API_KEY = "AQ.Ab8RN6KJypJqgCm3GtYMZC93dbBo725m_mq_ZkZtenFRnKFMIQ" 
MODEL = "gemini-1.5-flash"  # مدل پیشنهادی گوگل برای کارهای سریع و روزمره
# آدرس سازگار با OpenAI در گوگل
GOOGLE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"

SYSTEM = "تو EXPERA هستی؛ یک دستیار هوشمند، مهربان و خوش‌برخورد متخصص آزمایش‌های علمی و عناصر شیمیایی.در زمینه‌های طراحی و توضیح آزمایش‌ها، عناصر شیمیایی، جدول تناوبی، ویژگی‌های عناصر، ابزارهای آزمایشگاهی و آزمایش‌های فیزیک، شیمی و زیست‌شناسی تخصص داری.مانند یک معلم حرفه‌ای، هر آزمایشی را که دانش‌آموز نام می‌برد، از هدف و وسایل موردنیاز تا مراحل انجام، توضیح علمی، نتایج مورد انتظار و نکات ایمنی به‌صورت کامل، دقیق و مرحله‌به‌مرحله آموزش بده."

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
        "Authorization": "Bearer " + GOOGLE_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        # ارسال درخواست به آدرس گوگل
        r = requests.post(GOOGLE_URL, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return jsonify({"error": "خطای شبکه: " + str(e)}), 502

    if r.status_code != 200:
        return jsonify({"error": f"Google API {r.status_code}: {r.text[:300]}"}), r.status_code

    try:
        reply = r.json()["choices"][0]["message"]["content"]
    except Exception:
        return jsonify({"error": "پاسخ قابل تجزیه نیست"}), 500

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
