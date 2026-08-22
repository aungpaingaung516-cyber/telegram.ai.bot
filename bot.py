import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters
import google.generativeai as genai

# အကိုအောင် ပေးထားတဲ့ Token နဲ့ API Key တွေ ထည့်ပြီးသား
TELEGRAM_BOT_TOKEN = "8903870807:AAHs_ovC4nvT0elYHbbNX-D7j-yc5PujCbs"
GEMINI_API_KEY = "AQ.Ab8RN6LXpFbFcoqbJRpGqSbMusj-m58_upYcAZ4COhzjdgWl_g"

# Gemini ကို Setup လုပ်ခြင်း
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
    print("🤖 Bot အလုပ်လုပ်နေပါပြီ အကိုအောင်...")
    app.run_polling()
