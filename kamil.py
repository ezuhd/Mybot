import telebot
from telebot import types
import os
from pymongo import MongoClient
from flask import Flask
from threading import Thread
import google.generativeai as genai

# --- 1. ቁልፎችን ማጽዳት ---
TOKEN = os.getenv('BOT_TOKEN', '').strip()
ADMIN_ID_STR = os.getenv('ADMIN_ID', '').strip()
MONGO_URI = os.getenv('MONGO_URI', '').strip()
GEMINI_KEY = os.getenv('GEMINI_KEY', '').strip()
MY_GROUP_LINK = "https://t.me/ezuhd"

ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else 0
bot = telebot.TeleBot(TOKEN)

# --- 2. Gemini AI ማዋቀር (Personality) ---
instructions = """
አንተ በጣም ብልህ እና ሰፊ እውቀት ያለህ ረዳት ነህ። 
1. ማንኛውንም የሰው ልጅ ጥያቄ በትክክል እና በዝርዝር መልስ።
2. ስለ Ezuhd (ኢዙ) ከተጠየቅክ እርሱ የዚህ ቦት ባለቤት፣ ጎበዝ የቴክኖሎጂ ባለሙያ እና የፕሮግራም አድራጊ መሆኑን ንገራቸው።
3. መልሶችህን በተቻለ መጠን ግልጽ በሆነ አማርኛ አቅርብ።
"""

if GEMINI_KEY:
    genai.configure(api_key=GEMINI_KEY)
    # ፈጣኑን ሞዴል እንጠቀማለን
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    model = None

# --- 3. Flask ሰርቨር (Render) ---
app = Flask('')
@app.route('/')
def home(): return "Bot is alive!"

def run_server():
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))

# --- 4. ዳታቤዝ (MongoDB) ---
try:
    client = MongoClient(MONGO_URI)
    msg_collection = client['telegram_bot']['messages']
except:
    msg_collection = None

def save_msg(admin_msg_id, user_id):
    if msg_collection is not None:
        try:
            msg_collection.update_one({"admin_msg_id": str(admin_msg_id)}, {"\$set": {"user_id": user_id}}, upsert=True)
        except: pass

def get_user(admin_msg_id):
    if msg_collection is not None:
        try:
            res = msg_collection.find_one({"admin_msg_id": str(admin_msg_id)})
            return res['user_id'] if res else None
        except: return None
    return None

# --- 5. በተኖች (Inline Keyboard) ---
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
def handle_all(message):
    user_id = message.from_user.id
    is_admin = (user_id == ADMIN_ID)
    text = message.text if message.text else ""

    # ሀ. አድሚኑ ሪፕሌይ ሲያደርግ (AI ጣልቃ አይገባም)
    if is_admin and message.reply_to_message:
        uid = get_user(message.reply_to_message.message_id)
        if uid:
            try:
                if message.content_type == 'text':
                    bot.send_message(uid, f"👤 **ከአድሚን ምላሽ:**\n\n{text}")
                else:
                    bot.copy_message(uid, ADMIN_ID, message.message_id)
                bot.send_message(ADMIN_ID, "✅ ምላሽዎ ተልኳል።")
                return 
            except: pass

    # ለ. AI የሚያስብበት ክፍል
    should_ai = False
    query = ""

    if is_admin:
        if text.lower().startswith('ai '):
            should_ai = True
            query = text[3:].strip()
    else:
        if text:
            should_ai = True
            query = text

    if should_ai and query:
        if model is None:
            bot.reply_to(message, "❌ የ Gemini API Key አልተገኘም።")
        else:
            try:
                bot.send_chat_action(message.chat.id, 'typing')
                full_prompt = f"{instructions}\n\nጥያቄ: {query}"
                response = model.generate_content(full_prompt)
                
                # መልሱን ለጠያቂው መላክ
                bot.reply_to(message, response.text)
                
                # AI የመለሰውን ለአድሚኑ ማሳወቅ
                if not is_admin:
                    bot.send_message(ADMIN_ID, f"🤖 **Gemini ለመልካም ሰው የመለሰው:**\n\n{response.text}")
            except Exception as e:
                bot.reply_to(message, f"❌ ይቅርታ፣ አሁን መልስ መስጠት አልቻልኩም። ስህተት: {e}")

    # ሐ. መልዕክቱን ለአድሚን Forward ማድረግ (AI ለሚመልሰውም ጭምር)
    if not is_admin:
        try:
            fwd = bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
            save_msg(fwd.message_id, user_id)
        except: pass

if __name__ == "__main__":
    Thread(target=run_server).start()
    print("🚀 ቦቱ በ Gemini እና Flask እየተነሳ ነው...")
    bot.infinity_polling(skip_pending=True)
