import os
import asyncio
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN", "").strip()
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").strip()
PORT = int(os.getenv("PORT", 8080))

assert TOKEN and ":" in TOKEN, "BOT_TOKEN inválido"

# ================= FLASK =================

app = Flask(__name__)

# ================= TELEGRAM =================

asyncio.get_event_loop()

application = (
    Application.builder()
    .token(TOKEN)
    .concurrent_updates(True)
    .build()
)

# ================= DADOS SIMPLES =================

usuarios = {}

def init_user(user):
    if user.id not in usuarios:
        usuarios[user.id] = {"saldo": 0}

# ================= COMANDOS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_user(update.effective_user)

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
    ])

    await update.message.reply_text(
        "🤖 Bot iniciado com sucesso!",
        reply_markup=teclado
    )

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user
    init_user(user)

    if query.data == "saldo":
        await query.edit_message_text(
            f"💰 Saldo: R$ {usuarios[user.id]['saldo']:.2f}"
        )

# ================= HANDLERS =================

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callbacks))

# ================= WEBHOOK =================

@app.route("/webhook", methods=["POST"])
def telegram_webhook():
    update = Update.de_json(
        request.get_json(force=True),
        application.bot
    )
    application.create_task(application.process_update(update))
    return "ok", 200

# ================= START =================

async def on_startup(app_: Application):
    await app_.bot.set_webhook(f"{WEBHOOK_URL}/webhook")

application.post_init = on_startup

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
