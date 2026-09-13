import os
import io
import struct
import mimetypes
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from google import genai
from google.genai import types

# 1. Flask Web Server Setup (Render Health Check)
app = Flask(__name__)

@app.route('/')
def health_check():
    return "Bot is live and running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# 2. Gemini API Client Setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_API_KEY)

# 3. Voice Presets Configuration
VOICE_PRESETS = {
    "zephyr": {"label": "✨ Zephyr", "voice": "Zephyr"},
    "puck": {"label": "😊 Puck", "voice": "Puck"},
    "charon": {"label": "📖 Charon", "voice": "Charon"},
    "kore": {"label": "📰 Kore", "voice": "Kore"},
    "fenrir": {"label": "👻 Fenrir", "voice": "Fenrir"}
}

# 4. Helper Functions for WAV Header & PCM Conversion
def parse_audio_mime_type(mime_type: str) -> dict[str, int]:
    bits_per_sample = 16
    rate = 24000
    if mime_type:
        parts = mime_type.split(";")
        for param in parts:
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate = int(param.split("=", 1)[1])
                except (ValueError, IndexError):
                    pass
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except (ValueError, IndexError):
                    pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}

def convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    parameters = parse_audio_mime_type(mime_type)
    bits_per_sample = parameters["bits_per_sample"]
    sample_rate = parameters["rate"]
    num_channels = 1
    data_size = len(audio_data)
    bytes_per_sample = bits_per_sample // 8
    block_align = num_channels * bytes_per_sample
    byte_rate = sample_rate * block_align
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", chunk_size, b"WAVE", b"fmt ",
        16, 1, num_channels, sample_rate, byte_rate, block_align, bits_per_sample,
        b"data", data_size
    )
    return header + audio_data

# 5. Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["disabled"] = False
    
    keyboard = [
        [InlineKeyboardButton("✨ Zephyr", callback_data="style_zephyr"), InlineKeyboardButton("😊 Puck", callback_data="style_puck")],
        [InlineKeyboardButton("📖 Charon", callback_data="style_charon"), InlineKeyboardButton("📰 Kore", callback_data="style_kore")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current = context.user_data.get("style", "zephyr")
    preset_label = VOICE_PRESETS[current]["label"]
    
    msg = (
        f"မင်္ဂလာပါ အစ်ကိုအောင်! Gemini 3.1 Flash TTS Bot မှ ကြိုဆိုပါတယ်။ ✨\n\n"
        f"လက်ရှိ အသံ: **{preset_label}**\n\n"
        f"💡 **Group ထဲတွင် သုံးနည်း:**\n"
        f"Bot ရဲ့ စာကို **Reply** ပြန်ပြီး စာရေးမှသာ အသံထွက်ပေးပါမည်။\n\n"
        f"🛑 ရပ်လိုပါက `/stop`၊ ပြန်ဖွင့်လိုပါက `/start` ဟု ပို့ပါ။"
    )
    await update.message.reply_text(msg, reply_markup=reply_markup, parse_mode="Markdown")

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.chat_data["disabled"] = True
    await update.message.reply_text("🛑 Bot အလုပ်လုပ်ခြင်းကို ခေတ္တ ရပ်ဆိုင်းလိုက်ပါပြီ။\nပြန်ဖွင့်လိုပါက `/start` ဟု ပို့ပေးပါ အစ်ကိုအောင်။", parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data.startswith("style_"):
        style_key = data.replace("style_", "")
        if style_key in VOICE_PRESETS:
            context.user_data["style"] = style_key
            await query.edit_message_text(f"✅ Voice Style ကို **{VOICE_PRESETS[style_key]['label']}** သို့ ပြောင်းလိုက်ပါပြီ။", parse_mode="Markdown")

async def generate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.chat_data.get("disabled", False):
        return

    chat_type = update.effective_chat.type
    if chat_type in ["group", "supergroup"]:
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )
        if not is_reply_to_bot:
            return

    user_text = update.message.text
    if not user_text:
        return

    current_style_key = context.user_data.get("style", "zephyr")
    preset = VOICE_PRESETS[current_style_key]

    status_msg = await update.message.reply_text(
        f"🎙️ Gemini Flash TTS ({preset['label']}) ဖြင့် အသံပြောင်းနေပါတယ်... ခဏစောင့်ပါ...",
        reply_to_message_id=update.message.message_id
    )

    try:
        model = "gemini-3.1-flash-tts-preview"
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=user_text)],
            ),
        ]
        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            response_modalities=["audio"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=preset["voice"]
                    )
                )
            ),
        )

        audio_data = bytearray()
        mime_type = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.parts is None:
                continue
            if chunk.parts[0].inline_data and chunk.parts[0].inline_data.data:
                inline_data = chunk.parts[0].inline_data
                audio_data.extend(inline_data.data)
                mime_type = inline_data.mime_type

        if audio_data:
            wav_bytes = convert_to_wav(bytes(audio_data), mime_type)
            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = "voice_output.wav"

            await update.message.reply_audio(
                audio=audio_file,
                filename="voice_output.wav",
                caption=f"🎙️ Voice: {preset['label']}",
                title=f"{preset['label']}",
                performer="Gemini TTS Studio",
                reply_to_message_id=update.message.message_id
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Audio ဖိုင် ထွက်မလာပါဗျာ၊ စာသား ပြန်စစ်ပေးပါ။")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်သွားပါသည်: {str(e)}")

# 6. Main Execution
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_voice))

    print("Telegram Bot application starting...")
    application.run_polling()

if __name__ == '__main__':
    main()
