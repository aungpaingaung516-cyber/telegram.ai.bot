import os
import io
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from google import genai
from google.genai import types

# 1. Flask Web Server Setup
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

# 3. Voice Presets
VOICE_PRESETS = {
    "normal": {"label": "😊 ရိုးရိုး အသံ", "voice": "Puck", "instruction": "Speak naturally in clear Burmese."},
    "story": {"label": "📖 ဇာတ်လမ်းပြော အသံ", "voice": "Charon", "instruction": "Speak like an engaging Burmese story narrator with dramatic tone."},
    "news": {"label": "📰 သတင်းဖတ် အသံ", "voice": "Kore", "instruction": "Speak like a professional Burmese news anchor."},
    "horror": {"label": "👻 ထိတ်လန့်/သရဲဇာတ်လမ်း အသံ", "voice": "Fenrir", "instruction": "Speak in a creepy, slow, horror narrative voice in Burmese."}
}

# 4. Telegram Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("😊 Normal", callback_data="style_normal"), InlineKeyboardButton("📖 Story", callback_data="style_story")],
        [InlineKeyboardButton("📰 News", callback_data="style_news"), InlineKeyboardButton("👻 Horror", callback_data="style_horror")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    current = context.user_data.get("style", "normal")
    await update.message.reply_text(
        f"မင်္ဂလာပါ အစ်ကိုအောင်! Gemini AI Voice Bot မှ ကြိုဆိုပါတယ်။\n\nလက်ရှိ အသံ: **{VOICE_PRESETS[current]['label']}**\n\nစာသား ပို့ပေးပါဗျ။",
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
            await query.edit_message_text(f"✅ Voice Style ကို **{VOICE_PRESETS[style_key]['label']}** သို့ ပြောင်းလိုက်ပါပြီ။", parse_mode="Markdown")

async def generate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    current_style_key = context.user_data.get("style", "normal")
    preset = VOICE_PRESETS[current_style_key]

    status_msg = await update.message.reply_text(f"🎙️ {preset['label']} ဖန်တီးနေပါတယ်... ခဏစောင့်ပါ...")

    try:
        clean_instruction = (
            f"{preset['instruction']} "
            "Read ONLY the spoken Burmese text. Ignore any brackets, SFX cues like (SFX: ...) or [Hook]."
        )

        # Safety Block မဖြစ်စေရန် လျှော့ပေးခြင်း
        safety_settings = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=clean_instruction,
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=preset["voice"])
                    )
                ),
                safety_settings=safety_settings
            )
        )

        audio_bytes = None
        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if part.inline_data:
                    audio_bytes = part.inline_data.data
                    break

        if audio_bytes:
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice_output.mp3"

            await update.message.reply_audio(
                audio=audio_file,
                filename="voice_output.mp3",
                caption=f"🎙️ Style: {preset['label']}",
                title=f"{preset['label']}",
                performer="Gemini AI Studio"
            )
            await status_msg.delete()
        else:
            # Block ဖြစ်သည့် အကြောင်းအရင်းကို အသေးစိတ် ပြသပေးခြင်း
            finish_reason = response.candidates[0].finish_reason if response.candidates else "UNKNOWN"
            await status_msg.edit_text(f"❌ စာသားကြောင့် Block ဖြစ်သွားပါသည် (Reason: {finish_reason})။ စာသားကို အနည်းငယ် တိုပြီး ပြင်ပို့ပေးပါ။")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်သွားပါသည်: {str(e)}")

# 5. Main Execution
def main():
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()

    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_voice))

    application.run_polling()

if __name__ == '__main__':
    main()
