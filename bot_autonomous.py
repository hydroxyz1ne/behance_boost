from telegram.ext import Updater, CommandHandler
import json
import asyncio
import random
from telethon import TelegramClient

# === Настройки ===
import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
CHATS_FILE = 'chats.json'
TASK_FILE = 'boost_task.json'

def load_chats():
    try:
        with open(CHATS_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_chats(chats):
    with open(CHATS_FILE, 'w') as f:
        json.dump(chats, f)

def addchat(update, context):
    chat_id = update.message.text.split()[-1]
    chats = load_chats()
    if chat_id not in chats:
        chats.append(chat_id)
        save_chats(chats)
        update.message.reply_text(f'Чат {chat_id} добавлен.')
    else:
        update.message.reply_text(f'Чат уже в списке.')

def listchats(update, context):
    chats = load_chats()
    update.message.reply_text("Список чатов:\n" + "\n".join(chats))

def boost(update, context):
    try:
        url = context.args[0]
    except:
        update.message.reply_text('❌ Укажи ссылку: /boost https://behance.net/...')
        return
    with open(TASK_FILE, 'w') as f:
        json.dump({'url': url}, f)
    update.message.reply_text('🚀 Начинаю рассылку...')
    asyncio.run(run_sender())

async def run_sender():
    client = TelegramClient('session_name', API_ID, API_HASH)
    await client.start()
    with open(CHATS_FILE, 'r') as f:
        chats = json.load(f)
    with open(TASK_FILE, 'r') as f:
        task = json.load(f)
    for chat_id in chats:
        try:
            await client.send_message(chat_id, f'🔥 Новый кейс: {task["url"]}')
            print(f"✅ Отправлено в {chat_id}")
            delay = random.uniform(2, 4)
            await asyncio.sleep(delay)
        except Exception as e:
            print(f"⚠️ Ошибка {chat_id}: {e}")
    await client.disconnect()

updater = Updater(BOT_TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler('addchat', addchat))
dp.add_handler(CommandHandler('listchats', listchats))
dp.add_handler(CommandHandler('boost', boost))
updater.start_polling()
updater.idle()

