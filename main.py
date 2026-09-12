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

# 2. Voice Presets Configuration (Microsoft Natural Burmese Voices)
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
    
    await update.message.reply_text(
        f"မင်္ဂလာပါ အစ်ကိုအောင်! SORA TTS Voice Bot မှ ကြိုဆိုပါတယ်။\n\n"
        f"လက်ရှိ အသံ: **{preset_label}**\n\n"
        f"စာသား ပို့ပေးပါ၊ ချက်ချင်း MP3 အသံဖိုင် ပြောင်းပေးပါမယ်ဗျာ။",
        reply_markup=reply_markup,
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
                f"✅ Voice Style ကို **{preset_label}** သို့ ပြောင်းလိုက်ပါပြီ။ စာသား ပို့ပေးနိုင်ပါပြီ။", 
                parse_mode="Markdown"
            )

async def generate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    current_style_key = context.user_data.get("style", "female")
    preset = VOICE_PRESETS[current_style_key]

    status_msg = await update.message.reply_text(f"🎙️ {preset['label']} ဖြင့် ဖတ်ပြနေပါတယ်... ခဏစောင့်ပါ...")

    try:
        # Edge TTS Stream ပြုလုပ်ခြင်း
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
                performer="SORA Audio Studio"
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

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_voice))

    print("Telegram Bot application starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
