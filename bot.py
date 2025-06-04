import os
import json
import openai
import logging
import tempfile
import subprocess
from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    filters, ContextTypes
)

# Настройка
OWNER_ID = int(os.getenv("OWNER_ID"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY
HISTORY_FILE = "history.json"

# Логирование
logging.basicConfig(level=logging.INFO)

# Загрузка истории из файла
if os.path.exists(HISTORY_FILE):
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
else:
    history = []

def save_history():
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    await update.message.reply_text("Привет! Я готов слушать чат и помогать тебе по команде.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    user = update.effective_user.first_name
    chat_id = update.effective_chat.id

    # Записываем всё (из группы или лички)
    history.append({"user": user, "text": text, "chat_id": chat_id})
    save_history()

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    if not voice:
        return
    file = await context.bot.get_file(voice.file_id)

    with tempfile.NamedTemporaryFile(suffix=".oga") as f:
        await file.download_to_drive(f.name)
        mp3_path = f.name.replace(".oga", ".mp3")
        subprocess.run(["ffmpeg", "-i", f.name, mp3_path])
        with open(mp3_path, "rb") as audio_file:
            transcript = openai.Audio.transcribe("whisper-1", audio_file)
            text = transcript['text']
            history.append({
                "user": update.effective_user.first_name,
                "text": text,
                "chat_id": update.effective_chat.id,
                "source": "voice"
            })
            save_history()
            if update.effective_user.id == OWNER_ID:
                await update.message.reply_text(f"Голосовое расшифровано:\n{text}")

async def summarize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    messages = [h["text"] for h in history[-50:]]
    prompt = "\n".join(messages)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Ты анализируешь беседу и делаешь краткое резюме."},
            {"role": "user", "content": f"Сделай краткое резюме:\n{prompt}"}
        ]
    )
    await update.message.reply_text(response['choices'][0]['message']['content'])

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    query = " ".join(context.args)
    if not query:
        await update.message.reply_text("Напиши что искать, например:\n/поиск дедлайн")
        return
    matches = [h for h in history if query.lower() in h["text"].lower()]
    if not matches:
        await update.message.reply_text("Ничего не найдено.")
        return
    response = "\n\n".join([f"{m['user']}: {m['text']}" for m in matches[-10:]])
    await update.message.reply_text(f"Нашёл:\n\n{response}")

async def extract_todo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return
    messages = [h["text"] for h in history[-100:]]
    prompt = "\n".join(messages)
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "Ты извлекаешь задачи (TODO) из переписки."},
            {"role": "user", "content": f"Найди и перечисли задачи:\n{prompt}"}
        ]
    )
    await update.message.reply_text(response['choices'][0]['message']['content'])

# Запуск
if __name__ == "__main__":
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("резюме", summarize))
    app.add_handler(CommandHandler("поиск", search))
    app.add_handler(CommandHandler("todo", extract_todo))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice))
    app.run_polling()
