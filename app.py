import os
import hmac
import hashlib
import json

from flask import Flask, request, jsonify

app = Flask(__name__)

IPN_SECRET = os.environ.get("IPN_SECRET", "")


@app.get("/")
def home():
    return "Telegram payment backend is running"


@app.post("/nowpayments/ipn")
def nowpayments_ipn():
    signature = request.headers.get("x-nowpayments-sig", "")

    try:
        payload = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "Invalid JSON"}), 400

    if not IPN_SECRET:
        return jsonify({"error": "IPN secret is not configured"}), 500

    # NOWPayments signs the sorted JSON payload with HMAC-SHA512.
    sorted_payload = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True
    )

    expected_signature = hmac.new(
        IPN_SECRET.encode(),
        sorted_payload.encode(),
        hashlib.sha512
    ).hexdigest()

    if not hmac.compare_digest(signature, expected_signature):
        return jsonify({"error": "Invalid signature"}), 401

    print("Valid NOWPayments IPN:", payload)

    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
