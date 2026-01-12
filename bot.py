import os
from flask import Flask, request
from telegram import *
from telegram.ext import *
from database import usuarios, banidos, ADMINS
from estoque import *
from fila import *
from asaas import criar_pix

# ================= CONFIG =================

TOKEN = os.getenv("BOT_TOKEN", "").strip()

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
PORT = int(os.getenv("PORT", 8080))

# ================= FLASK =================

flask_app = Flask(__name__)

# ================= TELEGRAM =================

application = Application.builder().token(TOKEN).build()

# ================= PRODUTOS =================

PRODUTOS = {
    "mix": {"nome": "MIX PEDIDOS FÍSICOS", "preco": 125},
    "digitais": {"nome": "PEDIDOS DIGITAIS", "preco": 75},
    "mais10": {"nome": "+10 PEDIDOS FÍSICOS", "preco": 155},
}

def is_admin(uid): 
    return uid in ADMINS

def init_user(user):
    if user.id not in usuarios:
        usuarios[user.id] = {"saldo": 0.0, "compras": []}

# ================= COMANDOS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    init_user(update.effective_user)

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Loja", callback_data="loja")],
        [InlineKeyboardButton("💰 Saldo", callback_data="saldo")],
        [InlineKeyboardButton("💸 PIX", callback_data="pix")],
        [InlineKeyboardButton("📦 Reservar", callback_data="reservar")]
    ])

    await update.message.reply_text("🤖 RC STORE", reply_markup=teclado)

async def callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    user = q.from_user
    init_user(user)

    if q.data == "loja":
        teclado = []
        for p in PRODUTOS:
            teclado.append([
                InlineKeyboardButton(
                    f"{PRODUTOS[p]['nome']} ({contar(p)})",
                    callback_data=f"comprar_{p}"
                )
            ])
        await q.edit_message_text("🛒 Loja", reply_markup=InlineKeyboardMarkup(teclado))

    elif q.data.startswith("comprar_"):
        p = q.data.split("_")[1]
        preco = PRODUTOS[p]["preco"]
        u = usuarios[user.id]

        if u["saldo"] < preco:
            await q.edit_message_text("❌ Saldo insuficiente")
            return

        item = retirar(p)
        if not item:
            await q.edit_message_text("❌ Estoque vazio")
            return

        u["saldo"] -= preco
        u["compras"].append(PRODUTOS[p]["nome"])
        await q.edit_message_text(f"✅ Compra realizada\n\n{item}")

    elif q.data == "saldo":
        await q.edit_message_text(f"💰 Saldo: R$ {usuarios[user.id]['saldo']:.2f}")

    elif q.data == "pix":
        qr, copia = criar_pix(user.id, 50)
        await q.message.reply_photo(qr, caption=f"`{copia}`", parse_mode="Markdown")

    elif q.data == "reservar":
        entrar(user.id)
        await q.edit_message_text("📦 Você entrou na fila de reserva")

# ================= ADMIN =================

async def add_estoque_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    produto = context.args[0]
    item = " ".join(context.args[1:])
    adicionar(produto, item)
    await update.message.reply_text("✅ Item adicionado")

async def ver_estoque_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    produto = context.args[0]
    itens = listar(produto)
    texto = "\n".join([f"{i+1} - {x}" for i, x in enumerate(itens)])
    await update.message.reply_text(texto or "Estoque vazio")

async def remover_estoque_cmd(update, context):
    if not is_admin(update.effective_user.id):
        return
    produto = context.args[0]
    pos = int(context.args[1]) - 1
    remover_posicao(produto, pos)
    await update.message.reply_text("✅ Removido")

# ================= HANDLERS =================

application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(callbacks))
application.add_handler(CommandHandler("add_estoque", add_estoque_cmd))
application.add_handler(CommandHandler("ver_estoque", ver_estoque_cmd))
application.add_handler(CommandHandler("remover_estoque", remover_estoque_cmd))

# ================= WEBHOOK =================

@flask_app.route("/webhook", methods=["POST"])
async def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    await application.process_update(update)
    return "ok"

@flask_app.route("/asaas", methods=["POST"])
def asaas_webhook():
    data = request.json
    if data.get("event") == "PAYMENT_RECEIVED":
        user_id = int(data["payment"]["description"].split()[-1])
        valor = float(data["payment"]["value"])
        if user_id in usuarios:
            usuarios[user_id]["saldo"] += valor
    return "ok"

# ================= START =================

async def startup(app):
    await app.bot.set_webhook(WEBHOOK_URL + "/webhook")

application.post_init = startup

if __name__ == "__main__":
    flask_app.run(host="0.0.0.0", port=PORT)



