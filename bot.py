import telebot
import requests
import json
import os
import time

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CRYPTO_PAY_TOKEN = os.environ.get("CRYPTO_PAY_TOKEN")

if not TELEGRAM_TOKEN or not CRYPTO_PAY_TOKEN:
    print("❌ Ошибка: Токены не установлены!")
    exit(1)

print("✅ Токены загружены")

CRYPTO_PAY_API_URL = "https://testnet-pay.crypt.bot/api"
RATE_USDT_TO_RUB = 77.43

bot = telebot.TeleBot(TELEGRAM_TOKEN)

# ===== ПРИНУДИТЕЛЬНЫЙ СБРОС =====
print("🔄 Сбрасываю вебхук...")
try:
    # Удаляем вебхук
    bot.remove_webhook()
    print("✅ Вебхук удалён")
    
    # Останавливаем polling
    bot.stop_polling()
    print("✅ Polling остановлен")
except:
    pass

time.sleep(3)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message,
        f"🤖 *Бот готов!*\n\n"
        f"💰 Курс: 1 USDT = {RATE_USDT_TO_RUB} ₽\n\n"
        f"📝 Отправьте сумму в рублях (например: 100)",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_amount(message):
    try:
        rub_amount = float(message.text.replace(',', '.'))
        
        if rub_amount < 10:
            bot.reply_to(message, "❌ Минимум 10 ₽")
            return
        
        usdt_amount = round(rub_amount / RATE_USDT_TO_RUB, 2)
        
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
                
                keyboard = telebot.types.InlineKeyboardMarkup()
                keyboard.add(telebot.types.InlineKeyboardButton("💳 ОПЛАТИТЬ", url=pay_url))
                
                bot.reply_to(
                    message,
                    f"🧾 *Счёт: {rub_amount} ₽ = {usdt_amount} USDT*\n\nНажмите кнопку",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            else:
                bot.reply_to(message, f"❌ Ошибка API")
        else:
            bot.reply_to(message, f"❌ Ошибка")
            
    except ValueError:
        pass
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка")

if __name__ == "__main__":
    print("🚀 Запуск...")
    
    # Бесконечные попытки подключения
    while True:
        try:
            print("🔄 Подключаюсь к Telegram...")
            bot.infinity_polling(timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Переподключение через 5 секунд...")
            time.sleep(5)
