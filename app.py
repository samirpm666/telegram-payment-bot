import os
import hmac
import hashlib
import json
import time
import requests

from flask import Flask, request, jsonify

app = Flask(__name__)

# =========================
# SETTINGS
# =========================

NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY", "")
IPN_SECRET = os.environ.get("IPN_SECRET", "")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")

PUBLIC_URL = "https://telegram-payment-bot-xeez.onrender.com"

PRICE_USD = 10
PAY_CURRENCY = "usdtton"

NOWPAYMENTS_API = "https://api.nowpayments.io/v1"


# =========================
# TELEGRAM API
# =========================

def telegram_request(method, data=None):

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

    response = requests.post(
        url,
        json=data or {},
        timeout=30
    )

    return response.json()


def send_message(chat_id, text, reply_markup=None):

    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_markup:
        data["reply_markup"] = reply_markup

    return telegram_request("sendMessage", data)


# =========================
# NOWPAYMENTS INVOICE
# =========================

def create_invoice(chat_id):

    order_id = f"tg_{chat_id}_{int(time.time())}"

    payload = {
        "price_amount": PRICE_USD,
        "price_currency": "usd",
        "pay_currency": PAY_CURRENCY,
        "order_id": order_id,
        "order_description": "Telegram VIP subscription",
        "ipn_callback_url": f"{PUBLIC_URL}/nowpayments/ipn",
        "success_url": "https://t.me/",
        "cancel_url": "https://t.me/"
    }

    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json"
    }

    response = requests.post(
        f"{NOWPAYMENTS_API}/invoice",
        headers=headers,
        json=payload,
        timeout=30
    )

    return response.json()


# =========================
# TELEGRAM WEBHOOK
# =========================

@app.post("/telegram/webhook")
def telegram_webhook():

    update = request.get_json(silent=True) or {}

    # -------------------------
    # NORMAL MESSAGE
    # -------------------------

    message = update.get("message")

    if message:

        chat_id = message["chat"]["id"]
        text = message.get("text", "")

        if text == "/start":

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "💳 Купить VIP — $10",
                            "callback_data": "buy_vip"
                        }
                    ]
                ]
            }

            send_message(
                chat_id,
                "Добро пожаловать!\n\n"
                "VIP подписка — $10.\n"
                "Оплата: USDT через сеть TON.\n\n"
                "Нажмите кнопку ниже для оплаты.",
                keyboard
            )

    # -------------------------
    # BUTTON PRESS
    # -------------------------

    callback = update.get("callback_query")

    if callback:

        callback_id = callback["id"]
        data = callback.get("data")

        chat_id = callback["message"]["chat"]["id"]

        telegram_request(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_id
            }
        )

        if data == "buy_vip":

            invoice = create_invoice(chat_id)

            print("NOWPayments invoice response:")
            print(invoice)

            invoice_url = invoice.get("invoice_url")

            if not invoice_url:

                send_message(
                    chat_id,
                    "Ошибка при создании платежа.\n\n"
                    "Попробуйте ещё раз."
                )

                return jsonify({"ok": True})

            keyboard = {
                "inline_keyboard": [
                    [
                        {
                            "text": "💳 Оплатить $10 USDT",
                            "url": invoice_url
                        }
                    ]
                ]
            }

            send_message(
                chat_id,
                "Счёт создан.\n\n"
                "Нажмите кнопку ниже и оплатите $10 USDT "
                "через сеть TON.\n\n"
                "После подтверждения платежа бот автоматически "
                "подтвердит оплату.",
                keyboard
            )

    return jsonify({"ok": True})


# =========================
# NOWPAYMENTS IPN
# =========================

@app.post("/nowpayments/ipn")
def nowpayments_ipn():

    signature = request.headers.get(
        "x-nowpayments-sig",
        ""
    )

    try:
        payload = request.get_json(force=True)

    except Exception:

        return jsonify({
            "error": "Invalid JSON"
        }), 400

    if not IPN_SECRET:

        return jsonify({
            "error": "IPN secret is not configured"
        }), 500

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

    if not hmac.compare_digest(
        signature,
        expected_signature
    ):

        return jsonify({
            "error": "Invalid signature"
        }), 401

    print("VALID NOWPAYMENTS IPN:")
    print(payload)

    payment_status = payload.get("payment_status")
    order_id = payload.get("order_id", "")

    print("Payment status:", payment_status)
    print("Order ID:", order_id)

    # -------------------------
    # SUCCESSFUL PAYMENT
    # -------------------------

    if payment_status == "finished":

        print("PAYMENT FINISHED")

        if order_id.startswith("tg_"):

            parts = order_id.split("_")

            if len(parts) >= 2:

                chat_id = parts[1]

                send_message(
                    chat_id,
                    "Оплата получена.\n\n"
                    "Ваш платёж подтверждён.\n"
                    "VIP доступ будет выдан автоматически."
                )

    return jsonify({
        "status": "ok"
    }), 200


# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def home():

    return "Telegram payment backend is running"


# =========================
# START SERVER
# =========================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    app.run(
        host="0.0.0.0",
        port=port
    )