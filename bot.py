import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai
from flask import Flask

# Flask server တစ်ခု တည်ဆောက်ခြင်း (Render ရဲ့ Web Service အတွက် လိုအပ်လို့ပါ)
server = Flask(__name__)

@server.route('/')
def home():
    return "🤖 Bot is running 24/7!"

TELEGRAM_BOT_TOKEN = "8903870807:AAHs_ovC4nvT0elYHbbNX-D7j-yc5PujCbs"
GEMINI_API_KEY = "AQ.Ab8RN6LXpFbFcoqbJRpGqSbMusj-m58_upYcAZ4COhzjdgWl_g"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    try:
        response = model.generate_content(user_message)
        bot_reply = response.text
    except Exception as e:
        bot_reply = "ဗျာ... ခဏလေးနော်၊ စနစ်မှာ အနည်းငယ် ချို့ယွင်းသွားလို့ပါ 😅"
    
    await update.message.reply_text(bot_reply)

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    # Render ပေးမယ့် Port ကို ယူသုံးရန်
    port = int(os.environ.get("PORT", 5000))
    
    print("🤖 Bot စတင်အလုပ်လုပ်နေပါပြီ...")
    
    # Polling နဲ့ Bot ကို Run မယ်
    # (မှတ်ချက်။ Free Web Service အိပ်မသွားအောင် UptimeRobot လိုမျိုးနဲ့ ဝင်နှိုးဖို့ လိုပါမယ်)
    app.run_polling()
