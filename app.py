# -*- coding: utf-8 -*-
import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

# 🔑 برگشت به کلید Groq (رایگان و کارآمد)
GROQ_API_KEY = "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"
MODEL = "llama-3.1-8b-instant" 
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

SYSTEM = "تو یک دستیار هوش مصنوعی فارسی‌زبان، دقیق و خوش‌برخورد هستی. کوتاه و مفید جواب بده."

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
        "Authorization": "Bearer " + GROQ_API_KEY,
        "Content-Type": "application/json",
    }

    try:
        r = requests.post(GROQ_URL, headers=headers, json=payload, timeout=60)
    except Exception as e:
        return jsonify({"error": "خطای شبکه: " + str(e)}), 502

    if r.status_code != 200:
        return jsonify({"error": f"Groq {r.status_code}: {r.text[:300]}"}), r.status_code

    try:
        reply = r.json()["choices"][0]["message"]["content"]
    except Exception:
        return jsonify({"error": "پاسخ قابل تجزیه نیست"}), 500

    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
