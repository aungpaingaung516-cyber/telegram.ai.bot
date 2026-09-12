import io
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from google import genai
from google.genai import types

# ----------------- CONFIGURATION -----------------
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"  # @BotFather မှ ရရှိသော Token ထည့်ပါ
GEMINI_API_KEY = "YOUR_GEMINI_API_KEY"          # AI Studio မှ API Key ထည့်ပါ
# -------------------------------------------------

# Gemini Client ဖွင့်ခြင်း
client = genai.Client(api_key=GEMINI_API_KEY)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# မြန်မာလို ပိပိသသ အသံထွက်စေမည့် Voice Presets များ
VOICE_PRESETS = {
    "normal": {
        "label": "😊 Normal / သာမန် စကားပြော",
        "voice": "Kore",
        "instruction": (
            "You are a native Burmese speaker. Read the provided Burmese text out loud "
            "with crystal clear, highly accurate Burmese pronunciation, natural native rhythm, "
            "and fluent voice intonation. Avoid robotic tone."
        )
    },
    "story": {
        "label": "📖 Story / ပုံပြင်ပြော",
        "voice": "Puck",
        "instruction": (
            "You are a native Burmese storyteller. Read the Burmese text with captivating emotion, "
            "expressive tone, correct sentence pauses, and clear native pronunciation."
        )
    },
    "news": {
        "label": "🎙️ News / သတင်းဖတ်",
        "voice": "Fenrir",
        "instruction": (
            "You are a professional Burmese news broadcaster. Read the Burmese text with "
            "formal, articulate, precise, and crisp native Burmese pronunciation."
        )
    },
    "horror": {
        "label": "👻 Horror / ခြောက်ခြားဖွယ်",
        "voice": "Charon",
        "instruction": (
            "You are a terrifying Burmese horror narrator. Read the Burmese text in a dark, "
            "slow, eerie whisper with chilling pauses, while maintaining clear Burmese articulation."
        )
    }
}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Default Style အဖြစ် Normal ကို သတ်မှတ်ထားမည်
    if "style" not in context.user_data:
        context.user_data["style"] = "normal"

    keyboard = [
        [InlineKeyboardButton(data["label"], callback_data=key)]
        for key, data in VOICE_PRESETS.items()
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "မင်္ဂလာပါ အစ်ကိုအောင်! AI Voice Generator Bot မှ ကြိုဆိုပါတယ် 🎙️\n\n"
        "လိုချင်သည့် **Voice Style** ကို အောက်ပါ ခလုတ်များတွင် ရွေးချယ်ပြီး မြန်မာစာသား ပို့ပေးပါ-",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_click(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    selected_style = query.data
    context.user_data["style"] = selected_style
    preset_name = VOICE_PRESETS[selected_style]["label"]

    await query.edit_message_text(
        f"✅ **{preset_name}** စတိုင်ကို ရွေးချယ်ထားပါသည်။ အသံထုတ်ချင်သည့် စာသား ပို့ပေးပါဗျ။",
        parse_mode="Markdown"
    )

async def generate_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    current_style_key = context.user_data.get("style", "normal")
    preset = VOICE_PRESETS[current_style_key]

    status_msg = await update.message.reply_text(f"🎙️ {preset['label']} အသံဖိုင် ဖန်တီးနေပါတယ်... ခဏစောင့်ပါ...")

    try:
        # Gemini 2.0 Flash ဖြင့် Audio Output တောင်းဆိုခြင်း
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=user_text,
            config=types.GenerateContentConfig(
                system_instruction=preset["instruction"],
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=preset["voice"]
                        )
                    )
                )
            )
        )

        audio_bytes = None
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                audio_bytes = part.inline_data.data
                break

        if audio_bytes:
            # Memory ထဲမှ Audio Data ကို Telegram Voice Message အဖြစ် ပြောင်းလဲခြင်း
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = "voice_output.wav"

            await update.message.reply_voice(
                voice=audio_file,
                caption=f"🎙️ Style: {preset['label']}"
            )
            await status_msg.delete()
        else:
            await status_msg.edit_text("❌ Audio ဖိုင် ထွက်မလာပါဗျာ၊ စာသားကို ပြန်စစ်ပေးပါ။")

    except Exception as e:
        await status_msg.edit_text(f"❌ Error ဖြစ်သွားပါသည်: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_click))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, generate_voice))

    print("Bot စတင်ပွင့်နေပါပြီ...")
    app.run_polling()
