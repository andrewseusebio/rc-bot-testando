import os
from telegram import *
from telegram.ext import *
from database import usuarios, banidos, ADMINS
from estoque import *
from fila import *
from asaas import criar_pix
from logs import log
from webhook import app as flask_app

TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK = os.getenv("WEBHOOK_URL")

PRODUTOS = {
    "mix": ("MIX PEDIDOS FÍSICOS", 125),
    "digitais": ("PEDIDOS DIGITAIS", 75),
    "mais10": ("+10 PEDIDOS FÍSICOS", 155),
}

def admin(id): return id in ADMINS

def init(user):
    if user.id not in usuarios:
        usuarios[user.id] = {"saldo":0,"compras":[]}

async def start(u,c):
    init(u.effective_user)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Loja",callback_data="loja")],
        [InlineKeyboardButton("💰 Saldo",callback_data="saldo")],
        [InlineKeyboardButton("💸 PIX",callback_data="pix")],
        [InlineKeyboardButton("📦 Reservar",callback_data="reservar")]
    ])
    await u.message.reply_text("🤖 RC STORE",reply_markup=kb)

async def cb(u,c):
    q=u.callback_query; await q.answer()
    user=q.from_user; init(user)

    if q.data=="loja":
        kb=[]
        for k,v in PRODUTOS.items():
            kb.append([InlineKeyboardButton(
                f"{v[0]} ({contar(k)})",
                callback_data=f"buy_{k}"
            )])
        await q.edit_message_text("🛒 Loja",reply_markup=InlineKeyboardMarkup(kb))

    if q.data.startswith("buy_"):
        p=q.data.split("_")[1]
        nome,preco=PRODUTOS[p]
        if usuarios[user.id]["saldo"]<preco:
            return await q.edit_message_text("❌ Saldo insuficiente")
        item=retirar(p)
        if not item:
            return await q.edit_message_text("❌ Estoque vazio")
        usuarios[user.id]["saldo"]-=preco
        usuarios[user.id]["compras"].append(nome)
        log(f"COMPRA {user.id} {nome}")
        await q.edit_message_text(f"✅ {nome}\n\n{item}")

    if q.data=="saldo":
        await q.edit_message_text(f"💰 R$ {usuarios[user.id]['saldo']:.2f}")

    if q.data=="pix":
        qr,cp=criar_pix(user.id,50)
        await q.message.reply_photo(qr,caption=f"`{cp}`",parse_mode="Markdown")

    if q.data=="reservar":
        entrar(user.id)
        await q.edit_message_text("📦 Entrou na fila")

application = Application.builder().token(TOKEN).build()
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(cb))

async def startup(app):
    await app.bot.set_webhook(WEBHOOK+"/webhook")

application.post_init = startup

if __name__=="__main__":
    flask_app.run(host="0.0.0.0",port=int(os.getenv("PORT",8080)))
