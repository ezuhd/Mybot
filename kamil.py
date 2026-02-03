import telebot
from telebot import types
import os, time
from pymongo import MongoClient

# --- ማዋቀሪያ (ሚስጥራዊ መረጃዎች እዚህ ኮድ ውስጥ የሉም!) ---
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID_STR = os.getenv('ADMIN_ID')
MONGO_URI = os.getenv('MONGO_URI')
MY_GROUP_LINK = "https://t.me/ezuhd"

# መረጃዎቹ መኖራቸውን ማረጋገጫ
if not TOKEN or not ADMIN_ID_STR or not MONGO_URI:
    print("❌ ስህተት: BOT_TOKEN, ADMIN_ID ወይም MONGO_URI በ Koyeb ላይ አልተሞሉም!")
    exit(1)

ADMIN_ID = int(ADMIN_ID_STR)
bot = telebot.TeleBot(TOKEN)

# --- MongoDB መዝገብ ማገናኛ ---
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
msg_collection = db['messages']

def save_msg(admin_msg_id, user_id):
    try:
        msg_collection.update_one(
            {"admin_msg_id": str(admin_msg_id)},
            {"$set": {"user_id": user_id}},
            upsert=True
        )
    except Exception as e:
        print(f"MongoDB ስህተት: {e}")

def get_user(admin_msg_id):
    try:
        res = msg_collection.find_one({"admin_msg_id": str(admin_msg_id)})
        return res['user_id'] if res else None
    except: return None

# --- በተኖች ---
def main_menu():
    m = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("📞 አድሚን", callback_data="get_admin")
    btn2 = types.InlineKeyboardButton("🔙 ግሩፕ", url=MY_GROUP_LINK)
    m.row(btn1, btn2)
    return m

# --- የቦቱ ስራዎች ---

@bot.message_handler(commands=['start'])
def welcome(message):
    u = message.from_user
    info = f"🚀 <b>አዲስ ሰው ጀምሯል</b>\n👤 ስም: {u.first_name}\n🔗 ዩዘር: @{u.username if u.username else 'የለውም'}"
    sent = bot.send_message(ADMIN_ID, info, parse_mode='HTML')
    save_msg(sent.message_id, u.id)
    bot.send_message(message.chat.id, "ሰላም! ፎቶ ወይም ሀሳብዎን እዚህ ይላኩ።", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "get_admin")
def contact_admin(call):
    kb = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    kb.add(types.KeyboardButton("📞 ስልክ ቁጥሬን ላክ", request_contact=True))
    bot.send_message(call.message.chat.id, "አድሚኑን ለማግኘት ስልክዎን ያጋሩ", reply_markup=kb)

@bot.message_handler(content_types=['contact'])
def get_phone(message):
    u = message.from_user
    info = f"<b>📞 ስልክ ተላከ</b>\n👤 ስም: {message.contact.first_name}\n📱 ቁጥር: +{message.contact.phone_number}"
    sent = bot.send_message(ADMIN_ID, info, parse_mode='HTML')
    save_msg(sent.message_id, u.id)
    bot.send_message(message.chat.id, "መልዕክትዎ ደርሷል!", reply_markup=main_menu())

@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'audio'])
def handle_msg(message):
    if message.from_user.id == ADMIN_ID and message.reply_to_message:
        uid = get_user(message.reply_to_message.message_id)
        if uid:
            try:
                if message.content_type == 'text':
                    bot.send_message(uid, f"👤 <b>ከአድሚን ምላሽ:</b>\n\n{message.text}", reply_markup=main_menu(), parse_mode='HTML')
                else:
                    bot.copy_message(uid, ADMIN_ID, message.message_id, reply_markup=main_menu())
                bot.send_message(ADMIN_ID, "✅ ምላሽዎ ተልኳል።")
                return 
            except Exception as e:
                bot.send_message(ADMIN_ID, f"❌ ስህተት: {e}")

    try:
        fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        save_msg(fwd.message_id, message.from_user.id)
        if message.from_user.id != ADMIN_ID:
            bot.send_message(message.chat.id, "መልዕክትዎ ደርሷል!", reply_markup=main_menu())
    except Exception as e:
        print(f"Forward ስህተት: {e}")

print("--- 🔄 ቦቱ በ MongoDB እየተነሳ ነው... ---")
bot.polling(none_stop=True)
