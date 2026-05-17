# scripts/send_test_message.py
import sys
from bot.telegram_api import send_message
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route("/test_callback", methods=["POST"])
def test_callback():
    data = request.json
    print("\n✅ OTP callback received!")
    print(f"OTP: {data.get('otp')}")
    print(f"Source: {data.get('source')}")
    return jsonify({"status": "received"}), 200

if __name__ == "__main__":
    chat_id = int(sys.argv[1])  # e.g., your own chat_id
    text = " ".join(sys.argv[2:])
    context = "test_otp"
    target_url = "http://localhost:8000/test_callback"

    send_message(chat_id, text, context, target_url)    
    app.run(port=8000)

