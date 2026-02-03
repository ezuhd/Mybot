
import telebot

TOKEN = '8477512625:AAGwlVcuVrnOxpHeVSfrDT4hBehDAqrC3sE'
bot = telebot.TeleBot(TOKEN)

try:
    me = bot.get_me()
    print(f"✅ ግንኙነት ተሳክቷል! የቦቱ ስም: {me.first_name}")
except Exception as e:
    print(f"❌ ስህተት ተፈጥሯል: {e}")

