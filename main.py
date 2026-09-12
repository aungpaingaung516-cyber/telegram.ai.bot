import os
import io
import asyncio
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import edge_tts

# 1. Flask Web Server Setup (Render Health Check)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is live and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Voice Presets Configuration
VOICE_PRESETS = {
    "female": {
        "label": "👩 မနိလာ (အမျိုးသမီး အသံ)",
        "voice": "my-MM-NilarNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "male": {
        "label": "👨 မောင်သီဟ (အမျိုးသား အသံ)",
        "voice": "my-MM-ThihaNeural",
        "rate": "+0%",
        "pitch": "+0Hz"
    },
    "story": {
        "label": "📖 ဇာတ်လမ်းပြော အသံ (အေးဆေး)",
        "voice": "my-MM-NilarNeural",
        "rate": "-10%",
        "pitch": "-5Hz"
    },
    "news": {
        "label": "📰 သတင်းဖတ် အသံ (မြန်မြန်)",
        "voice": "my-MM-ThihaNeural",
        "rate": "+10%",
        "pitch": "+0Hz"
    }
}

# 3. Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bot ကို ပြန်ဖွင့်ပေးခြင်း
    context.chat_data["disabled"] = False
    
    keyboard = [
        [
            InlineKeyboardButton("👩 မနိလာ", callback_data="style_female"),
            InlineKeyboardButton("👨 မောင်သီဟ", callback_data="style_male"),
        ],
        [
            InlineKeyboardButton("📖 ဇာတ်လမ်းပြော", callback_data="style_story"),
            InlineKeyboardButton("📰 သတင်းဖတ်", callback_data="style_news"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current = context.user_data.get("style", "female")
    preset_label = VOICE_PRESETS[current]["label"]
    
    msg = (
        f"မင်္ဂလာပါ အစ်ကိုအောင်! SORA Voice Bot ကို ဖွင့်လိုက်ပါပြီ။ ✨\n\n"
        f"လက်ရှိ အသံ: **{preset_label}**\n\n"
        f"💡 **Group ထဲတွင် သုံးနည်း:**\n"
        f"Bot ရဲ့ စာသား သို့မဟုတ် အသံဖိုင်ကို **Reply** ပြန်ပြီး စာရေးမှသာ အသံထွက်ပေးပါမည်။\n\n"
        f"🛑 Bot ကို ခေတ္တ ပိတ်ထားချင်ပါက `/stop` လို့ ပို့ပါ၊ ပြန်ဖွင့်ချင်ပါက `/start` လို့ ပို့ပါ။"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bot ကို ခေတ္တ ပိတ်ထားခြင်း
    context.chat_data["disabled"] = True
    await update.message.reply_text(
        "🛑 Bot အလုပ်လုပ်ခြင်းကို ခေတ္တ ရပ်ဆိုင်းလိုက်ပါပြီ။\n"
        "ပြန်ဖွင့်လိုပါက `/start` ဟု ပို့ပေးပါ အစ်ကိုအောင်။", 
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith("style_"):
        style_key = data.replace("style_", "")
        if style_key in VOICE_PRESETS:
            context.user_data["style"] = style_key
            preset_label = VOICE_PRESETS[style_key]["label"]
            await query.edit_message_text(
                f"✅ Voice Style ကို **{preset_label}** သို့ ပြောင်းလိုက်ပါပြီ။", 
                parse_mode="Markdown"
            )

async def generate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Bot ကို /stop လုပ်ထားလျှင် ဘာမှ မလုပ်ပါ
    if context.chat_data.get("disabled", False):
        return

    chat_type = update.effective_chat.type

    # Group / Supergroup ထဲမှာဆိုရင် Bot ကို Reply ပြန်ထားတဲ့ စာများကိုပဲ အသံပြောင်းပေးမည်
    if chat_type in ["group", "supergroup"]:
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        if not is_reply_to_bot:
            return  # Bot ထံ Reply မဟုတ်ပါက လစ်လျူရှုမည်

    user_text = update.message.text
    if not user_text:
        return

    current_style_key = context.user_data.get("style", "female")
    preset = VOICE_PRESETS[current_style_key]

    status_msg = await update.message.reply_text(
        f"🎙️ {preset['label']} ဖြင့် ဖတ်ပြနေပါတယ်... ခဏစောင့်ပါ...",
        reply_to_message_id=update.message.message_id
    )

    try:
        communicate = edge_tts.Communicate(
            text=user_text,
            voice=preset["voice"],
            rate=preset["rate"],
            pitch=preset["pitch"]
        )

        audio_bytes = bytearray()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_bytes.extend(chunk["data"])

        if audio_bytes:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice_output.mp3"

            await update.message.reply_audio(
                audio=audio_file,
                filename="voice_output.mp3",
                caption=f"🎙️ Voice: {preset['label']}",
                title=f"{preset['label']}",
                performer="SORA Audio Studio",
                reply_to_message_id=update.message.message_id
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Audio ဖိုင် ထွက်မလာပါဗျာ၊ စာသား ပြန်စစ်ပေးပါ။")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်သွားပါသည်: {str(e)}")

# 4. Main Execution
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(bot_token).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_voice))

    print("Telegram Bot application starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
