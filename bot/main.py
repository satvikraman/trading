# bot/main.py
from flask import Flask, request, jsonify
from bot.telegram_handler import handle_telegram_webhook
from cal.config import is_local

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    payload = request.get_json()
    result = handle_telegram_webhook(payload)
    return jsonify(result)

# Cloud Function entrypoint (only used in GCP deployment)
def cloud_function_handler(request):
    return telegram_webhook()

if __name__ == "__main__" and is_local():
    app.run(port=5001, debug=True)
