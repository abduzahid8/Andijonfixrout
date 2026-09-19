"""Telegram bot: answers /start with a Web App button, plus /points and /help.

Long-polling entrypoint is `python run_bot.py` (repo root).
Requires TELEGRAM_BOT_TOKEN in .env.
"""
import logging

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .ai_service import analyze_image
from .config import settings
from .database import Base, SessionLocal, engine, ensure_migrations
from .models import User
from .reports_service import finalize_report
from .storage import save_upload

log = logging.getLogger("roadpulse.bot")

WELCOME = (
    "🛣️ *RoadPulse* — report potholes, earn points, fix your city.\n\n"
    "Tap below to open the Mini App, *or just send a road photo here* — "
    "our AI verifies the defect in seconds. \\+10 ⭐️ per verified report."
)


def _keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚀 Open RoadPulse",
                    web_app=WebAppInfo(url=settings.MINI_APP_URL),
                )
            ],
            [InlineKeyboardButton("⭐️ My points", callback_data="points")],
        ]
    )


def _points_text(telegram_id: int) -> str:
    db = SessionLocal()
    try:
        user = db.get(User, telegram_id)
    finally:
        db.close()
    if user is None:
        return "No reports yet — open the app and file your first pothole!"
    return f"⭐️ You have *{user.points} points*."


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(WELCOME, reply_markup=_keyboard(), parse_mode="Markdown")


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "/start — open the Mini App\n"
        "/points — check your ⭐️ balance\n"
        "/myid — show your Telegram ID (needed for admin setup)\n"
        "/cancel — abort a pending photo report\n\n"
        "Or skip the app: send a road photo here, then share the location.",
        reply_markup=_keyboard(),
    )


async def points_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        _points_text(update.effective_user.id), parse_mode="Markdown"
    )


async def points_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(
        _points_text(query.from_user.id), parse_mode="Markdown"
    )


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"🆔 Your Telegram ID is `{update.effective_user.id}`\n"
        "Send it to the project owner to get admin rights.",
        parse_mode="Markdown",
    )


# ---- Direct photo reports: photo -> AI check -> request location -> save ----
PENDING: dict[int, dict] = {}  # user_id -> {"file_id": str, "verdict": dict}


def _location_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📍 Send my location", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    status_msg = await update.message.reply_text("🔍 AI is checking the road…")
    try:
        tg_file = await update.message.photo[-1].get_file()
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception as exc:
        log.warning("photo download failed: %s", exc)
        await status_msg.edit_text("❌ Could not download that photo. Please try again.")
        return
    verdict = await analyze_image(raw, "image/jpeg")
    if not verdict["is_road"] or not verdict["has_defect"]:
        await status_msg.edit_text(
            "❌ The AI did not detect a road defect in this photo. "
            "Send a clear picture of asphalt with a pothole or crack."
        )
        return
    PENDING[user.id] = {"file_id": update.message.photo[-1].file_id, "verdict": verdict}
    await status_msg.edit_text(
        f"✅ Defect spotted ({verdict['defect_type']}, {verdict['severity']}).\n"
        "Now tap the button below to attach the location:",
        reply_markup=_location_keyboard(),
    )


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    pending = PENDING.pop(user.id, None)
    if pending is None:
        await update.message.reply_text("Send a road photo first, then share the location.")
        return
    try:
        tg_file = await context.bot.get_file(pending["file_id"])
        raw = bytes(await tg_file.download_as_bytearray())
    except Exception as exc:
        log.warning("photo re-download failed: %s", exc)
        await update.message.reply_text(
            "❌ That photo expired. Please send it again.", reply_markup=ReplyKeyboardRemove()
        )
        return
    image_url = save_upload(raw, "image/jpeg")
    loc = update.message.location
    db = SessionLocal()
    try:
        out = finalize_report(
            db,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            image_url=image_url,
            latitude=loc.latitude,
            longitude=loc.longitude,
            verdict=pending["verdict"],
        )
    finally:
        db.close()
    report = out["report"]
    await update.message.reply_text(
        f"✅ Recorded: *{report.defect_type}* ({report.severity}, +{out['points']} ⭐️).\n"
        "Thanks — it is now on the city map.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


async def cancel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    PENDING.pop(update.effective_user.id, None)
    await update.message.reply_text("Cancelled.", reply_markup=ReplyKeyboardRemove())


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    log.exception("handler error: %s", context.error)


def build_app() -> Application:
    if not settings.TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is empty — add your BotFather token to .env")
    app = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("points", points_cmd))
    app.add_handler(CommandHandler("myid", myid_cmd))
    app.add_handler(CommandHandler("cancel", cancel_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_error_handler(on_error)
    return app
    app.add_handler(CallbackQueryHandler(points_callback, pattern="^points$"))
    return app


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    Base.metadata.create_all(bind=engine)  # bot may boot before the API server
    ensure_migrations()
    log.info("Starting bot polling, mini_app_url=%s", settings.MINI_APP_URL)
    build_app().run_polling(allowed_updates=Update.ALL_TYPES)
