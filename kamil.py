import telebot
from telebot import types
import os
import time
from pymongo import MongoClient
from flask import Flask
from threading import Thread
import google.generativeai as genai

# --- 1. Gemini AI ማዋቀር ---
GEMINI_KEY = os.getenv('GEMINI_KEY')
genai.configure(api_key=GEMINI_KEY)

# ለጂሚኒ የተሰጠ መመሪያ (Personality)
instructions = """
አንተ በጣም ብልህ እና ሰፊ እውቀት ያለህ ረዳት ነህ። 
1. ማንኛውንም የሰው ልጅ ጥያቄ (ሳይንስ፣ ቴክኖሎጂ፣ ጤና፣ ታሪክ ወዘተ) በትክክል እና በዝርዝር መልስ።
2. ስለ Ezuhd (ኢዙ) ከተጠየቅክ እርሱ የዚህ ቦት ባለቤት፣ ጎበዝ የቴክኖሎጂ ባለሙያ እና የፕሮግራም አድራጊ መሆኑን ንገራቸው።
3. መልሶችህን በተቻለ መጠን ግልጽ በሆነ አማርኛ አቅርብ።
"""
model = genai.GenerativeModel('gemini-pro')

# --- 2. Render እንዳያጠፋው የውሸት ሰርቨር (Flask) ---
app = Flask('')
@app.route('/')
def home():
    return "Bot is alive!"

def run_flask():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

# --- 3. ማዋቀሪያ (ሚስጥራዊ መረጃዎች) ---
TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID_STR = os.getenv('ADMIN_ID')
MONGO_URI = os.getenv('MONGO_URI')
MY_GROUP_LINK = "https://t.me/ezuhd"

if not TOKEN or not ADMIN_ID_STR or not MONGO_URI:
    print("❌ ስህተት: መረጃዎች አልተሟሉም!")
    exit(1)

ADMIN_ID = int(ADMIN_ID_STR)
bot = telebot.TeleBot(TOKEN)

# --- 4. MongoDB መዝገብ ማገናኛ ---
client = MongoClient(MONGO_URI)
db = client['telegram_bot']
msg_collection = db['messages']

def save_msg(admin_msg_id, user_id):
    try:
        msg_collection.update_one({"admin_msg_id": str(admin_msg_id)}, {"$set": {"user_id": user_id}}, upsert=True)
    except: pass

def get_user(admin_msg_id):
    try:
        res = msg_collection.find_one({"admin_msg_id": str(admin_msg_id)})
        return res['user_id'] if res else None
    except: return None

# --- 5. በተኖች (Buttons) ---
def main_menu():
    m = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("📞 አድሚን አናግር", callback_data="get_admin")
    btn2 = types.InlineKeyboardButton("🔙 ግሩፕ", url=MY_GROUP_LINK)
    m.row(btn1, btn2)
    return m

# --- 6. የቦቱ ስራዎች ---

@bot.message_handler(commands=['start'])
def welcome(message):
    bot.reply_to(message, "ሰላም! እኔ Gemini AI ነኝ። ማንኛውንም ጥያቄ መጠየቅ ይችላሉ። አድሚን ለማግኘት ግን 'አድሚን አናግር' የሚለውን ይጫኑ።", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda c: c.data == "get_admin")
def contact_admin(call):
    bot.send_message(call.message.chat.id, "እባክዎን መልዕክትዎን እዚህ ይላኩ፤ በቀጥታ ለአድሚን ይደርሳል።")

@bot.message_handler(content_types=['text', 'photo', 'video', 'voice', 'document', 'audio'])
def handle_all_msg(message):
    is_admin = (message.from_user.id == ADMIN_ID)

    # አድሚኑ ለሰው ምላሽ ሲሰጥ
    if is_admin and message.reply_to_message:
        uid = get_user(message.reply_to_message.message_id)
        if uid:
            try:
                if message.content_type == 'text':
                    bot.send_message(uid, f"👤 **ከአድሚን ምላሽ:**\n\n{message.text}", reply_markup=main_menu())
                else:
                    bot.copy_message(uid, ADMIN_ID, message.message_id, reply_markup=main_menu())
                bot.send_message(ADMIN_ID, "✅ ምላሽዎ ተልኳል።")
                return 
            except: pass

    # AI ምላሽ የሚሰጥበት ሁኔታ
    # አድሚን ከሆነ 'ai ' ብሎ መጀመር አለበት፣ ሌሎች ግን ዝም ብለው ይጠይቃሉ
    text = message.text if message.text else ""
    should_respond = not is_admin or (is_admin and text.lower().startswith('ai '))

    if should_respond and message.content_type == 'text':
        query = text[3:].strip() if (is_admin and text.lower().startswith('ai ')) else text
        if query:
            try:
                bot.send_chat_action(message.chat.id, 'typing')
                full_prompt = f"{instructions}\n\nጥያቄ: {query}"
                response = model.generate_content(full_prompt)
                bot.reply_to(message, response.text)
                
                if not is_admin:
                    bot.send_message(ADMIN_ID, f"🤖 **Gemini ለመልካም ሰው የመለሰው:**\n\n{response.text}")
            except Exception as e:
                print(f"AI Error: {e}")
                bot.reply_to(message, "ይቅርታ፣ አሁን መልስ መስጠት አልቻልኩም።")

    # ተራ ሰው መልዕክት ሲልክ ለአድሚን ይላካል (Forward)
    if not is_admin:
        try:
            fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            save_msg(fwd.message_id, message.from_user.id)
        except: pass

# --- ማስጀመሪያ ---
if __name__ == "__main__":
    print("--- 🚀 ቦቱ በ Gemini እና Flask እየተነሳ ነው... ---")
    # Flaskን በThread ማስነሳት
    t = Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # ቦቱን ማስነሳት
    bot.infinity_polling(none_stop=True)
