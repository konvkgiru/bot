import telebot
import requests
import json
import os
import time

# Токены из переменных окружения Railway
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

# Проверка токенов
if not TELEGRAM_TOKEN:
    print("❌ Ошибка: TELEGRAM_TOKEN не установлен!")
    exit(1)

if not CRYPTO_PAY_TOKEN:
    print("❌ Ошибка: CRYPTO_PAY_TOKEN не установлен!")
    exit(1)

print("✅ Токены загружены успешно!")

CRYPTO_PAY_API_URL = "https://testnet-pay.crypt.bot/api"
RATE_USDT_TO_RUB = 77.43

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# Простой обработчик
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        f"🤖 Бот работает!\n\n"
        f"Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽\n\n"
        f"Отправьте сумму в рублях, например: 100"
    )

@bot.message_handler(func=lambda message: True)
def handle_amount(message):
    try:
        # Пробуем преобразовать текст в число
        rub_amount = float(message.text.replace(',', '.'))
        
        if rub_amount < 10:
            bot.reply_to(message, "❌ Минимальная сумма: 10 ₽")
            return
        
        usdt_amount = round(rub_amount / RATE_USDT_TO_RUB, 2)
        
        # Создаём счёт
        headers = {
            "Crypto-Pay-API-Token": CRYPTO_PAY_TOKEN,
            "Content-Type": "application/json"
        }
        
        payload = {
            "asset": "USDT",
            "amount": str(usdt_amount),
            "description": f"Оплата {rub_amount} RUB"
        }
        
        response = requests.post(
            f"{CRYPTO_PAY_API_URL}/createInvoice",
            headers=headers,
            json=payload,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                pay_url = data["result"]["pay_url"]
                invoice_id = data["result"]["invoice_id"]
                
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(telebot.types.InlineKeyboardButton("💳 ОПЛАТИТЬ", url=pay_url))
                
                bot.reply_to(
                    message,
                    f"🧾 *Счёт на оплату*\n\n"
                    f"Сумма: {rub_amount} ₽\n"
                    f"К оплате: {usdt_amount} USDT\n\n"
                    f"Нажмите кнопку ниже для оплаты",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                bot.reply_to(message, f"❌ Ошибка: {data.get('error')}")
        else:
            bot.reply_to(message, f"❌ Ошибка HTTP: {response.status_code}")
            
    except ValueError:
        # Если это не число, игнорируем
        pass
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

if __name__ == "__main__":
    print("🚀 Бот запущен!")
    print(f"📊 Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽")
    print("🤖 Начинаем polling...")
    
    try:
        bot.infinity_polling(timeout=60)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
