from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telethon import TelegramClient
import json
import os
import time
import random
import asyncio

# === Конфиги ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

CHATS_FILE = 'chats.json'
CASES_FILE = 'cases.json'

ADD_GROUP, REMOVE_GROUP, ADD_CASE_NAME, ADD_CASE_URL, SELECT_CASE_TO_SEND, SELECT_CASE_TO_DELETE = range(6)

def load_json(file):
    if os.path.exists(file):
        with open(file, 'r') as f:
            return json.load(f)
    return {} if "cases" in file else []

def save_json(file, data):
    with open(file, 'w') as f:
        json.dump(data, f)

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
        cases = load_json(CASES_FILE)
        if cases:
            msg = "\n".join([f"— {name}: {url}" for name, url in cases.items()])
            update.message.reply_text(msg)
        else:
            update.message.reply_text("Нет загруженных кейсов.")
    elif text == "👥 Группы":
        chats = load_json(CHATS_FILE)
        if chats:
            update.message.reply_text("Список групп:\n" + "\n".join(chats))
        else:
            update.message.reply_text("Нет добавленных групп.")
    elif text == "➕ Добавить группу":
        update.message.reply_text("Введи chat_id или @username для добавления:", reply_markup=ReplyKeyboardRemove())
        return ADD_GROUP
    elif text == "➖ Удалить группу":
        chats = load_json(CHATS_FILE)
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
        cases = load_json(CASES_FILE)
        if not cases:
            update.message.reply_text("Нет кейсов для удаления.")
            return ConversationHandler.END
        buttons = [[KeyboardButton(name)] for name in cases.keys()]
        update.message.reply_text("Выбери кейс для удаления:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return SELECT_CASE_TO_DELETE
    elif text == "🚀 Буст кейса":
        cases = load_json(CASES_FILE)
        if not cases:
            update.message.reply_text("Нет кейсов для отправки.")
            return ConversationHandler.END
        buttons = [[KeyboardButton(name)] for name in cases.keys()]
        update.message.reply_text("Выбери кейс для рассылки:", reply_markup=ReplyKeyboardMarkup(buttons, resize_keyboard=True))
        return SELECT_CASE_TO_SEND
    else:
        update.message.reply_text("Не понял команду. Нажми /menu")
    return ConversationHandler.END

def add_group(update: Update, context: CallbackContext):
    chat_id = update.message.text.strip()
    chats = load_json(CHATS_FILE)
    if chat_id not in chats:
        chats.append(chat_id)
        save_json(CHATS_FILE, chats)
        update.message.reply_text(f"✅ Группа {chat_id} добавлена.", reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text("Группа уже в списке.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

def remove_group(update: Update, context: CallbackContext):
    chat_id = update.message.text.strip()
    chats = load_json(CHATS_FILE)
    if chat_id in chats:
        chats.remove(chat_id)
        save_json(CHATS_FILE, chats)
        update.message.reply_text(f"❌ Группа {chat_id} удалена.", reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text("Такой группы нет в списке.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

def add_case_name(update: Update, context: CallbackContext):
    context.user_data['new_case_name'] = update.message.text.strip()
    update.message.reply_text("Теперь введи ссылку на кейс:")
    return ADD_CASE_URL

def add_case_url(update: Update, context: CallbackContext):
    case_url = update.message.text.strip()
    case_name = context.user_data['new_case_name']
    cases = load_json(CASES_FILE)
    cases[case_name] = case_url
    save_json(CASES_FILE, cases)
    update.message.reply_text(f"✅ Кейс «{case_name}» добавлен.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

def delete_case(update: Update, context: CallbackContext):
    case_name = update.message.text.strip()
    cases = load_json(CASES_FILE)
    if case_name in cases:
        del cases[case_name]
        save_json(CASES_FILE, cases)
        update.message.reply_text(f"❌ Кейс «{case_name}» удалён.", reply_markup=ReplyKeyboardRemove())
    else:
        update.message.reply_text("Такой кейс не найден.", reply_markup=ReplyKeyboardRemove())
    return start(update, context)

def send_selected_case(update: Update, context: CallbackContext):
    case_name = update.message.text.strip()
    cases = load_json(CASES_FILE)
    if case_name not in cases:
        update.message.reply_text("Такой кейс не найден.")
        return start(update, context)
    url = cases[case_name]
    update.message.reply_text(f"🚀 Начинаю рассылку кейса: {case_name}", reply_markup=ReplyKeyboardRemove())
    asyncio.run(send_with_telethon(url))
    return start(update, context)


async def send_with_telethon(url):
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()
    chats = load_json(CHATS_FILE)
    for chat_id in chats:
        try:
            await client.send_message(chat_id, f"🔥 Новый кейс: {url}")
            await asyncio.sleep(random.uniform(1.5, 3.0))
        except Exception as e:
            print(f"Ошибка при отправке в {chat_id}: {e}")
    await client.disconnect()

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

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
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(CommandHandler("menu", start))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
