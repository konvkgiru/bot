import telebot
import requests
import json
import os
import time

# ===== НАСТРОЙКИ (берём из переменных окружения) =====
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

if not TELEGRAM_TOKEN or not CRYPTO_PAY_TOKEN:
    print("❌ Ошибка: Не установлены переменные окружения!")
    print("Установите TELEGRAM_TOKEN и CRYPTO_PAY_TOKEN")
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
        return {"success": False, "error": "Ошибка создания счёта"}
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
        print(f"Ошибка проверки: {e}")
        return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
    keyboard.add(telebot.types.InlineKeyboardButton("💰 Ввести сумму для оплаты", callback_data="enter_amount"))
    keyboard.add(telebot.types.InlineKeyboardButton("💰 Получить тестовые USDT", url="https://t.me/CryptoTestnetBot?start=faucet"))
    keyboard.add(telebot.types.InlineKeyboardButton("📊 Текущий курс", callback_data="rate"))
    
    bot.send_message(
        message.chat.id,
        f"🤖 *Крипто-платёжный бот*\n\n"
        f"💵 Я принимаю оплату в *USDT* (тестовая сеть)\n"
        f"📊 Курс: *1 USDT = {RATE_USDT_TO_RUB} ₽*\n\n"
        f"👇 Нажмите кнопку ниже, чтобы ввести сумму в рублях",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    if call.data == "enter_amount":
        bot.answer_callback_query(call.id)
        msg = bot.send_message(
            call.message.chat.id,
            f"💸 *Введите сумму в рублях*\n\n"
            f"Пример: `500` или `1250.50`\n\n"
            f"💰 Минимальная сумма: *10 ₽*\n"
            f"📊 Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, process_rub_amount)
    
    elif call.data == "rate":
        bot.answer_callback_query(call.id, f"1 USDT = {RATE_USDT_TO_RUB} ₽", show_alert=True)
    
    elif call.data.startswith("check_"):
        invoice_id = int(call.data.split("_")[1])
        rub_amount = active_invoices.get(call.from_user.id, {}).get("amount_rub", 0)
        
        bot.answer_callback_query(call.id, "🔄 Проверяю статус...")
        invoice = check_invoice(invoice_id)
        
        if invoice:
            if invoice["status"] == "paid":
                paid_usdt = float(invoice.get("amount", "0"))
                paid_rub = round(paid_usdt * RATE_USDT_TO_RUB, 2)
                
                bot.answer_callback_query(call.id, "✅ Оплачено!", show_alert=True)
                bot.edit_message_text(
                    f"✅ *Платёж подтверждён!*\n\n"
                    f"💸 Сумма: *{rub_amount} ₽*\n"
                    f"💵 Оплачено: {paid_usdt} USDT (~{paid_rub} ₽)\n"
                    f"🆔 ID: `{invoice_id}`\n\n"
                    f"🎉 Спасибо за оплату!",
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    parse_mode="Markdown"
                )
                if call.from_user.id in active_invoices:
                    del active_invoices[call.from_user.id]
                    
            elif invoice["status"] == "active":
                pay_url = active_invoices.get(call.from_user.id, {}).get("pay_url", "")
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(telebot.types.InlineKeyboardButton("💳 Оплатить", url=pay_url))
                keyboard.add(telebot.types.InlineKeyboardButton("✅ Проверить снова", callback_data=f"check_{invoice_id}"))
                
                bot.answer_callback_query(call.id, f"⏳ Ещё не оплачено. Сумма: {invoice['amount']} USDT", show_alert=True)
            else:
                bot.answer_callback_query(call.id, "⏰ Счёт просрочен. Начните заново: /start", show_alert=True)
        else:
            bot.answer_callback_query(call.id, "❌ Счёт не найден", show_alert=True)

def process_rub_amount(message):
    try:
        rub_amount = float(message.text.replace(',', '.'))
        
        if rub_amount < 10:
            bot.reply_to(message, "❌ Минимальная сумма — *10 ₽*", parse_mode="Markdown")
            return
        
        if rub_amount > 100000:
            bot.reply_to(message, "❌ Максимальная сумма — *100 000 ₽*", parse_mode="Markdown")
            return
        
        usdt_amount = rub_to_usdt(rub_amount)
        
        if usdt_amount < 0.01:
            bot.reply_to(message, f"❌ Сумма {rub_amount} ₽ слишком маленькая.", parse_mode="Markdown")
            return
        
        status_msg = bot.reply_to(message, "🔄 Создаю платёжный счёт...")
        result = create_invoice(usdt_amount, message.chat.id, rub_amount)
        
        if result["success"]:
            active_invoices[message.chat.id] = {
                "invoice_id": result["invoice_id"],
                "amount_rub": rub_amount,
                "amount_usdt": usdt_amount,
                "pay_url": result["pay_url"]
            }
            
            keyboard = telebot.types.InlineKeyboardMarkup(row_width=1)
            keyboard.add(telebot.types.InlineKeyboardButton("💳 Оплатить через Crypto Bot", url=result["pay_url"]))
            keyboard.add(telebot.types.InlineKeyboardButton("✅ Проверить оплату", callback_data=f"check_{result['invoice_id']}"))
            keyboard.add(telebot.types.InlineKeyboardButton("💰 Получить тестовые USDT", url="https://t.me/CryptoTestnetBot?start=faucet"))
            
            bot.edit_message_text(
                f"🧾 *Счёт на оплату*\n\n"
                f"💸 Сумма: *{rub_amount} ₽*\n"
                f"💵 К оплате: *{usdt_amount} USDT*\n"
                f"📊 Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽\n"
                f"🆔 ID счёта: `{result['invoice_id']}`\n\n"
                f"1️⃣ Нажмите «Оплатить»\n"
                f"2️⃣ Подтвердите платеж в @CryptoTestnetBot\n"
                f"3️⃣ Нажмите «Проверить оплату»\n\n"
                f"⏰ Счёт действителен *1 час*",
                chat_id=message.chat.id,
                message_id=status_msg.message_id,
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        else:
            bot.edit_message_text(
                f"❌ Ошибка: {result['error']}",
                chat_id=message.chat.id,
                message_id=status_msg.message_id
            )
            
    except ValueError:
        bot.reply_to(message, "❌ *Неверный формат*\nВведите число, например: `500`", parse_mode="Markdown")

if __name__ == "__main__":
    print("🤖 Бот запущен на Railway!")
    print(f"📊 Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽")
    bot.infinity_polling(timeout=60, long_polling_timeout=30)
