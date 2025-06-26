from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telethon import TelegramClient
from apscheduler.schedulers.background import BackgroundScheduler
import json
import os
import time
import random
import asyncio
import sqlite3
import pytz

# === Конфиги ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

DB_FILE = 'data.db'
timezone = pytz.timezone("Europe/Moscow")

ADD_GROUP, REMOVE_GROUP, ADD_CASE_NAME, ADD_CASE_URL, SELECT_CASE_TO_SEND, SELECT_CASE_TO_DELETE = range(6)


# === Работа с БД ===
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS groups (chat_id TEXT PRIMARY KEY)")
        c.execute("CREATE TABLE IF NOT EXISTS cases (name TEXT PRIMARY KEY, url TEXT)")
        conn.commit()


def get_groups():
    with sqlite3.connect(DB_FILE) as conn:
        return [row[0] for row in conn.execute("SELECT chat_id FROM groups")]


def add_group_db(chat_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR IGNORE INTO groups (chat_id) VALUES (?)", (chat_id,))
        conn.commit()


def remove_group_db(chat_id):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
        conn.commit()


def get_cases():
    with sqlite3.connect(DB_FILE) as conn:
        return {row[0]: row[1] for row in conn.execute("SELECT name, url FROM cases")}


def add_case_db(name, url):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("INSERT OR REPLACE INTO cases (name, url) VALUES (?, ?)", (name, url))
        conn.commit()


def remove_case_db(name):
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute("DELETE FROM cases WHERE name = ?", (name,))
        conn.commit()


# === Интерфейс ===
def start(update: Update, context: CallbackContext):
    buttons = [
        [KeyboardButton("📁 Кейсы"), KeyboardButton("👥 Группы")],
        [KeyboardButton("➕ Добавить группу"), KeyboardButton("➖ Удалить группу")],
        [KeyboardButton("➕ Добавить кейс"), KeyboardButton("❌ Удалить кейс")],
        [KeyboardButton("🚀 Буст кейса")]
    ]
    update.message.reply_text("Выбери действие:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
    return ConversationHandler.END


def handle_menu(update: Update, context: CallbackContext):
    text = update.message.text
    if text == "📁 Кейсы":
        cases = get_cases()
        if cases:
            msg = "\n".join([f"— {name}: {url}" for name, url in cases.items()])
            update.message.reply_text(msg)
        else:
            update.message.reply_text("Нет загруженных кейсов.")
    elif text == "👥 Группы":
        chats = get_groups()
        if chats:
            update.message.reply_text("Список групп:\n" + "\n".join(chats))
        else:
            update.message.reply_text("Нет добавленных групп.")
    elif text == "➕ Добавить группу":
        update.message.reply_text("Введи chat_id или @username для добавления:", reply_markup=ReplyKeyboardRemove())
        return ADD_GROUP
    elif text == "➖ Удалить группу":
        chats = get_groups()
        if not chats:
            update.message.reply_text("Список пуст.")
            return ConversationHandler.END
        buttons = [[KeyboardButton(chat)] for chat in chats]
        update.message.reply_text("Выбери группу для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return REMOVE_GROUP
    elif text == "➕ Добавить кейс":
        update.message.reply_text("Введи название кейса:", reply_markup=ReplyKeyboardRemove())
        return ADD_CASE_NAME
    elif text == "❌ Удалить кейс":
        cases = get_cases()
        if not cases:
            update.message.reply_text("Нет кейсов для удаления.")
            return ConversationHandler.END
        buttons = [[KeyboardButton(name)] for name in cases.keys()]
        update.message.reply_text("Выбери кейс для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return SELECT_CASE_TO_DELETE
    elif text == "🚀 Буст кейса":
        cases = get_cases()
        if not cases:
            update.message.reply_text("Нет кейсов для отправки.")
            return ConversationHandler.END
        buttons = [[KeyboardButton(name)] for name in cases.keys()]
        update.message.reply_text("Выбери кейс для рассылки:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return SELECT_CASE_TO_SEND
    else:
        update.message.reply_text("Не понял команду. Нажми /menu")
    return ConversationHandler.END


# === CRUD ===
def add_group(update: Update, context: CallbackContext):
    chat_id = update.message.text.strip()
    add_group_db(chat_id)
    update.message.reply_text(f"✅ Группа {chat_id} добавлена.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)


def remove_group(update: Update, context: CallbackContext):
    chat_id = update.message.text.strip()
    remove_group_db(chat_id)
    update.message.reply_text(f"❌ Группа {chat_id} удалена.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)


def add_case_name(update: Update, context: CallbackContext):
    context.user_data['new_case_name'] = update.message.text.strip()
    update.message.reply_text("Теперь введи ссылку на кейс:")
    return ADD_CASE_URL


def add_case_url(update: Update, context: CallbackContext):
    name = context.user_data['new_case_name']
    url = update.message.text.strip()
    add_case_db(name, url)
    update.message.reply_text(f"✅ Кейс «{name}» добавлен.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)


def delete_case(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    remove_case_db(name)
    update.message.reply_text(f"❌ Кейс «{name}» удалён.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)


def send_selected_case(update: Update, context: CallbackContext):
    case_name = update.message.text.strip()
    cases = get_cases()
    if case_name not in cases:
        update.message.reply_text("Такой кейс не найден.")
        return start(update, context)
    url = cases[case_name]
    update.message.reply_text(f"🚀 Рассылка: {case_name}", reply_markup=ReplyKeyboardRemove())
    asyncio.run(send_to_groups(url))
    return start(update, context)


async def send_to_groups(url):
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()
    for chat_id in get_groups():
        try:
            await client.send_message(chat_id, f"🔥 Новый кейс: {url}")
            await asyncio.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            print(f"Ошибка в {chat_id}: {e}")
    await client.disconnect()


# === Автопостинг ===
def schedule_rotation():
    cases = list(get_cases().values())
    if not cases:
        return
    selected = random.choice(cases)
    print(f"🚀 Автопостинг: {selected}")
    asyncio.run(send_to_groups(selected))


# === Бот ===
def main():
    init_db()

    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    scheduler = BackgroundScheduler(timezone=timezone)
    scheduler.add_job(schedule_rotation, 'cron', hour=12)
    scheduler.add_job(schedule_rotation, 'cron', hour=18)
    scheduler.start()

    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(Filters.text & ~Filters.command, handle_menu)],
        states={
            ADD_GROUP: [MessageHandler(Filters.text & ~Filters.command, add_group)],
            REMOVE_GROUP: [MessageHandler(Filters.text & ~Filters.command, remove_group)],
            ADD_CASE_NAME: [MessageHandler(Filters.text & ~Filters.command, add_case_name)],
            ADD_CASE_URL: [MessageHandler(Filters.text & ~Filters.command, add_case_url)],
            SELECT_CASE_TO_SEND: [MessageHandler(Filters.text & ~Filters.command, send_selected_case)],
            SELECT_CASE_TO_DELETE: [MessageHandler(Filters.text & ~Filters.command, delete_case)],
        },
        fallbacks=[CommandHandler('cancel', lambda u, c: u.message.reply_text("Отменено."))]
    )

    dp.add_handler(CommandHandler("menu", start))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()


if __name__ == "__main__":
    main()



from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telethon.tl.types import Channel
from telethon.errors import FloodWaitError

PARSE_KEYWORDS = ['behance', 'dribbble', 'like4like', 'design']
EXCLUDE_KEYWORDS = ['портфолио', 'кейсы']
NEW_CHAT_IDS = set()

async def search_and_send_chats(context: CallbackContext):
    user_id = context.job.context
    async with TelegramClient("session_name", API_ID, API_HASH) as client:
        found_chats = []
        async for dialog in client.iter_dialogs():
            entity = dialog.entity
            if isinstance(entity, Channel) and entity.megagroup:
                title = (entity.title or "").lower()
                about = (getattr(entity, 'about', '') or "").lower()
                if any(k in title or k in about for k in PARSE_KEYWORDS) and not any(bad in title or bad in about for bad in EXCLUDE_KEYWORDS):
                    found_chats.append((entity.id, entity.username or f"https://t.me/c/{entity.id}", entity.title))

        for chat_id, link, title in found_chats:
            if chat_id in get_groups():
                continue
            if chat_id in NEW_CHAT_IDS:
                continue
            NEW_CHAT_IDS.add(chat_id)

            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Добавить", callback_data=f"add_{chat_id}"),
                 InlineKeyboardButton("❌ Пропустить", callback_data=f"skip_{chat_id}")]
            ])
            chat_title = chat.title or "Без названия"
            context.bot.send_message(chat_id=user_id, text=f"Найден чат:\n{chat.title}\nID: {chat.id}\n{link}", parse_mode="HTML", reply_markup=keyboard)

def parse_chats_command(update: Update, context: CallbackContext):
    context.bot.send_message(chat_id=update.effective_chat.id, text="🔍 Начинаю искать группы…")
    context.job_queue.run_once(search_and_send_chats, 0, context=update.effective_chat.id)

def handle_chat_parse_decision(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    if data.startswith("add_"):
        chat_id = data.replace("add_", "")
        add_group_db(chat_id)
        query.edit_message_text(f"✅ Добавлен: {chat_id}")
        
    elif data.startswith("skip_"):
        query.edit_message_text("⏭ Пропущено")
