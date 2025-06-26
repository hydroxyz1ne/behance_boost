from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, ConversationHandler
from telethon import TelegramClient
from apscheduler.schedulers.background import BackgroundScheduler
import json, os, time, random, asyncio

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")

CHATS_FILE = 'chats.json'
CASES_FILE = 'cases.json'
BLACKLIST_FILE = 'blacklist.json'

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
        update.message.reply_text("".join([f"— {k}: {v}" for k, v in cases.items()]) or "Нет кейсов.")
    elif text == "👥 Группы":
        chats = load_json(CHATS_FILE)
        update.message.reply_text("".join(chats) or "Нет групп.")
    elif text == "➕ Добавить группу":
        update.message.reply_text("Введи @username или chat_id:", reply_markup=ReplyKeyboardRemove())
        return ADD_GROUP
    elif text == "➖ Удалить группу":
        chats = load_json(CHATS_FILE)
        update.message.reply_text("Выбери группу для удаления:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(c)] for c in chats], resize_keyboard=True))
        return REMOVE_GROUP
    elif text == "➕ Добавить кейс":
        update.message.reply_text("Введи название кейса:", reply_markup=ReplyKeyboardRemove())
        return ADD_CASE_NAME
    elif text == "❌ Удалить кейс":
        cases = load_json(CASES_FILE)
        update.message.reply_text("Выбери кейс для удаления:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(k)] for k in cases], resize_keyboard=True))
        return SELECT_CASE_TO_DELETE
    elif text == "🚀 Буст кейса":
        cases = load_json(CASES_FILE)
        update.message.reply_text("Выбери кейс:",
            reply_markup=ReplyKeyboardMarkup([[KeyboardButton(k)] for k in cases], resize_keyboard=True))
        return SELECT_CASE_TO_SEND
    else:
        update.message.reply_text("Нажми /menu")
    return ConversationHandler.END

def add_group(update: Update, context: CallbackContext):
    chat = update.message.text.strip()
    chats = load_json(CHATS_FILE)
    if chat not in chats:
        chats.append(chat)
        save_json(CHATS_FILE, chats)
        update.message.reply_text("✅ Добавлено")
    else:
        update.message.reply_text("Уже есть.")
    return start(update, context)

def remove_group(update: Update, context: CallbackContext):
    chat = update.message.text.strip()
    chats = load_json(CHATS_FILE)
    if chat in chats:
        chats.remove(chat)
        save_json(CHATS_FILE, chats)
        update.message.reply_text("❌ Удалено")
    else:
        update.message.reply_text("Нет в списке.")
    return start(update, context)

def add_case_name(update: Update, context: CallbackContext):
    context.user_data["new_case_name"] = update.message.text.strip()
    update.message.reply_text("Введи ссылку на кейс:")
    return ADD_CASE_URL

def add_case_url(update: Update, context: CallbackContext):
    name = context.user_data["new_case_name"]
    url = update.message.text.strip()
    cases = load_json(CASES_FILE)
    cases[name] = url
    save_json(CASES_FILE, cases)
    update.message.reply_text("✅ Кейс добавлен")
    return start(update, context)

def delete_case(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    cases = load_json(CASES_FILE)
    if name in cases:
        del cases[name]
        save_json(CASES_FILE, cases)
        update.message.reply_text("❌ Удалено")
    else:
        update.message.reply_text("Нет такого кейса.")
    return start(update, context)

def send_selected_case(update: Update, context: CallbackContext):
    name = update.message.text.strip()
    cases = load_json(CASES_FILE)
    if name not in cases:
        update.message.reply_text("Нет такого кейса.")
        return start(update, context)
    url = cases[name]
    asyncio.run(send_with_telethon(url))
    update.message.reply_text("📤 Рассылка завершена.")
    return start(update, context)

async def send_with_telethon(url):
    client = TelegramClient("session_user", API_ID, API_HASH)
    await client.start()
    chats = load_json(CHATS_FILE)
    blacklist = set(load_json(BLACKLIST_FILE))
    for chat_id in chats:
        if chat_id in blacklist:
            continue
        try:
            await client.send_message(chat_id, f"🔥 Новый кейс: {url}")
            await asyncio.sleep(random.uniform(2, 4))
        except Exception as e:
            print(f"[⚠️] {chat_id} исключён: {e}")
            blacklist.add(chat_id)
            save_json(BLACKLIST_FILE, list(blacklist))
    await client.disconnect()

def schedule_rotation():
    cases = load_json(CASES_FILE)
    if not cases: return
    last = int(os.getenv("LAST_CASE_INDEX", "0"))
    names = list(cases.keys())
    case_name = names[last % len(names)]
    print(f"[📅] Плановая рассылка: {case_name}")
    asyncio.run(send_with_telethon(cases[case_name]))
    os.environ["LAST_CASE_INDEX"] = str((last + 1) % len(names))

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text("Отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    scheduler = BackgroundScheduler()
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
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dp.add_handler(CommandHandler("menu", start))
    dp.add_handler(conv_handler)

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
