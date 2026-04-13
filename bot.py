import telebot
import requests
import json
import os

# БЕЗОПАСНО: токены из переменных окружения
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

if not TELEGRAM_TOKEN or not CRYPTO_PAY_TOKEN:
    print("❌ Токены не найдены!")
    print("Установите: TELEGRAM_TOKEN и CRYPTO_PAY_TOKEN")
    exit(1)

CRYPTO_PAY_API_URL = "https://testnet-pay.crypt.bot/api"
RATE_USDT_TO_RUB = 77.43

bot = telebot.TeleBot(TELEGRAM_TOKEN)
active_invoices = {}

def rub_to_usdt(rub_amount):
    return round(rub_amount / RATE_USDT_TO_RUB, 2)

def create_invoice(amount_usdt, telegram_id, rub_amount):
    headers = {
        "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
        "Content-Type": "application/json"
    }
    
    payload = {
        "asset": "USDT",
        "amount": str(amount_usdt),
        "description": f"Оплата {rub_amount} RUB",
        "payload": json.dumps({
            "telegram_id": telegram_id,
            "amount_rub": rub_amount
        }),
        "expires_in": 3600
    }
    
    try:
        response = requests.post(
            f"{CRYPTO_PAY_API_URL}/createInvoice",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                return {
                    "success": True,
                    "invoice_id": data["result"]["invoice_id"],
                    "pay_url": data["result"]["pay_url"]
                }
        return {"success": False, "error": "Ошибка API"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def check_invoice(invoice_id):
    headers = {"Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN}
    params = {"invoice_ids": invoice_id}
    
    try:
        response = requests.get(
            f"{CRYPTO_PAY_API_URL}/getInvoices",
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok") and data["result"]["items"]:
                return data["result"]["items"][0]
        return None
    except Exception as e:
        print(f"Ошибка: {e}")
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = telebot.types.InlineKeyboardMarkup()
    keyboard.add(telebot.types.InlineKeyboardButton("💸 Оплатить", callback_data="pay"))
    
    bot.send_message(
        message.chat.id,
        f"🤖 Крипто-бот\nКурс: 1 USDT = {RATE_USDT_TO_RUB} ₽\n\nНажмите «Оплатить»",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "pay":
        msg = bot.send_message(call.message.chat.id, "💸 Введите сумму в рублях:")
        bot.register_next_step_handler(msg, process_payment)

def process_payment(message):
    try:
        rub_amount = float(message.text.replace(',', '.'))
        
        if rub_amount < 10:
            bot.reply_to(message, "❌ Минимум 10 ₽")
            return
        
        usdt_amount = rub_to_usdt(rub_amount)
        
        result = create_invoice(usdt_amount, message.chat.id, rub_amount)
        
        if result["success"]:
            active_invoices[message.chat.id] = {
                "invoice_id": result["invoice_id"],
                "amount_rub": rub_amount,
                "pay_url": result["pay_url"]
            }
            
            keyboard = telebot.types.InlineKeyboardMarkup()
            keyboard.add(telebot.types.InlineKeyboardButton("💳 Оплатить", url=result["pay_url"]))
            keyboard.add(telebot.types.InlineKeyboardButton("✅ Проверить", callback_data=f"check_{result['invoice_id']}"))
            
            bot.reply_to(
                message,
                f"🧾 Счёт: {rub_amount} ₽ = {usdt_amount} USDT\n\nНажмите «Оплатить»",
                reply_markup=keyboard
            )
        else:
            bot.reply_to(message, f"❌ Ошибка: {result['error']}")
            
    except ValueError:
        bot.reply_to(message, "❌ Введите число")

@bot.callback_query_handler(func=lambda call: call.data.startswith("check_"))
def check_payment(call):
    invoice_id = int(call.data.split("_")[1])
    invoice = check_invoice(invoice_id)
    
    if invoice and invoice["status"] == "paid":
        bot.answer_callback_query(call.id, "✅ Оплачено!", show_alert=True)
        bot.edit_message_text(
            "✅ Платёж подтверждён! Спасибо!",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
    else:
        bot.answer_callback_query(call.id, "⏳ Ещё не оплачено", show_alert=True)

if __name__ == "__main__":
    print("✅ Бот запущен!")
    bot.infinity_polling()
