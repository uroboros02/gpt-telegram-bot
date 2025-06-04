import os
import openai
from telegram import Update, Audio
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)
import tempfile
import subprocess

OWNER_ID = int(os.getenv("OWNER_ID"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

chat_history = []

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("Привет! Жду твоих команд.")

async def log_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    chat_history.append(f"{update.effective_user.first_name}: {update.message.text}")

async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    prompt = "\n".join(chat_history[-50:])
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Ты — ассистент, делающий краткие резюме по истории чатов."},
            {"role": "user", "content": f"Сделай краткое резюме этого диалога:\n{prompt}"}
        ]
    )
    summary = response['choices'][0]['message']['content']
    await update.message.reply_text(summary)

async def transcribe_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    voice = update.message.voice or update.message.audio
    if not voice:
        await update.message.reply_text("Нет голосового сообщения.")
        return
    file = await context.bot.get_file(voice.file_id)
    with tempfile.NamedTemporaryFile(suffix=".oga") as f:
        await file.download_to_drive(f.name)
        mp3_path = f.name.replace(".oga", ".mp3")
        subprocess.run(["ffmpeg", "-i", f.name, mp3_path])
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
            await update.message.reply_text(f"Текст: {transcript['text']}")
            chat_history.append(f"[голосовое]: {transcript['text']}")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("резюме", summarize))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), log_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, transcribe_voice))
    app.run_polling()
