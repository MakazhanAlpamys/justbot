import json
import logging
import os
import asyncio
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants for ConversationHandler
CHOOSING, TYPING_TEXT, WAITING_MEDIA, BROADCAST = range(4)

# Store users who have started the bot
users = set()

def load_admins() -> List[int]:
    try:
        with open("admins.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("Admin file not found or corrupted. Creating a new one.")
        with open("admins.json", "w") as f:
            json.dump([], f)
        return []

# Load admin IDs
ADMIN_IDS = load_admins()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    users.add(user_id)

    welcome_text = (
        "🌟 *QamQor — сіздің қаржылық көмекшіңіз*\n\n"
        "Қаржылық сауаттылықты арттыруға, алаяқтардан қорғануға және "
        "ақшаңызды дұрыс басқаруға көмектеседі. Күн сайын кеңестер мен "
        "мотивация алыңыз, сұрақтарыңызды қойып, сенімді жауаптар табыңыз."
    )

    await update.message.reply_text(welcome_text, parse_mode="Markdown")

    if user_id in ADMIN_IDS:
        await send_admin_menu(update, context)

async def send_admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("📢 Барлық қолданушыларға хабарлау", callback_data="broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👨‍💻 *Әкімші панелі*\n\nҚолжетімді әрекеттер:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "broadcast":
        await query.message.reply_text(
            "📢 *Барлық қолданушыларға хабарлау*\n\n"
            "Жіберілетін хабарлама мәтінін енгізіңіз.\n"
            "Болдырмау үшін /cancel командасын жіберіңіз.",
            parse_mode="Markdown"
        )
        return TYPING_TEXT

    return ConversationHandler.END

async def text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["broadcast_text"] = update.message.text

    keyboard = [
        [InlineKeyboardButton("🖼 Сурет қосу", callback_data="add_photo")],
        [InlineKeyboardButton("🎬 Видео қосу", callback_data="add_video")],
        [InlineKeyboardButton("▶️ Хабарламаны жіберу", callback_data="send_now")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "✅ *Мәтін сақталды*\n\n"
        f"Мәтін: {update.message.text}\n\n"
        "Енді не істейміз?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return WAITING_MEDIA

async def media_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "add_photo":
        await query.message.reply_text(
            "🖼 Хабарламаға қосатын суретті жіберіңіз.",
            parse_mode="Markdown"
        )
        context.user_data["media_type"] = "photo"
        return BROADCAST

    elif query.data == "add_video":
        await query.message.reply_text(
            "🎬 Хабарламаға қосатын видеоны жіберіңіз.",
            parse_mode="Markdown"
        )
        context.user_data["media_type"] = "video"
        return BROADCAST

    elif query.data == "send_now":
        await broadcast_message(update, context)
        return ConversationHandler.END

    return WAITING_MEDIA

async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.photo:
        context.user_data["media"] = update.message.photo[-1].file_id
        media_type = "photo"
    elif update.message.video:
        context.user_data["media"] = update.message.video.file_id
        media_type = "video"
    else:
        await update.message.reply_text(
            "❌ Қате формат. Сурет немесе видео жіберіңіз.",
            parse_mode="Markdown"
        )
        return BROADCAST

    context.user_data["media_type"] = media_type

    keyboard = [
        [InlineKeyboardButton("▶️ Хабарламаны жіберу", callback_data="send_now")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"✅ {media_type.capitalize()} сақталды!\n\n"
        "Хабарламаны жіберуге дайынсыз ба?",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    return WAITING_MEDIA

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query if hasattr(update, "callback_query") else None

    text = context.user_data.get("broadcast_text", "")
    media_type = context.user_data.get("media_type", None)
    media = context.user_data.get("media", None)

    successful = 0
    failed = 0

    message_text = "📢 *Хабарлама тарату басталды*\n\nКүте тұрыңыз..."
    if query:
        await query.edit_message_text(message_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(message_text, parse_mode="Markdown")

    for user_id in users:
        try:
            if media_type == "photo":
                await context.bot.send_photo(user_id, photo=media, caption=text)
            elif media_type == "video":
                await context.bot.send_video(user_id, video=media, caption=text)
            else:
                await context.bot.send_message(user_id, text)
            successful += 1
        except Exception as e:
            logger.error(f"Failed to send message to user {user_id}: {e}")
            failed += 1

    result_text = (
        "✅ *Хабарлама тарату аяқталды*\n\n"
        f"Жіберілген: {successful}\n"
        f"Жіберілмеген: {failed}"
    )

    if query:
        await query.message.reply_text(result_text, parse_mode="Markdown")
    else:
        await update.message.reply_text(result_text, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "❌ Операция жойылды.",
        parse_mode="Markdown"
    )
    context.user_data.clear()
    return ConversationHandler.END

async def main():
    token = os.environ.get("TELEGRAM_TOKEN", "7932888925:AAFzrOM2MdGNkq8CsMmNx6kApMtFLN4M4sw")
    if not token:
        logger.error("Telegram token not found. Set the TELEGRAM_TOKEN environment variable.")
        return

    application = Application.builder().token(token).build()

    application.add_handler(CommandHandler("start", start))

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button_callback, pattern="^broadcast$")],
        states={
            TYPING_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, text_input)],
            WAITING_MEDIA: [CallbackQueryHandler(media_choice)],
            BROADCAST: [
                MessageHandler(filters.PHOTO | filters.VIDEO, receive_media),
                CallbackQueryHandler(broadcast_message, pattern="^send_now$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(conv_handler)

    logger.info("Bot started")
    await application.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
