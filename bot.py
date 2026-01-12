# bot.py

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import os
import asyncio
import asyncpg
from datetime import datetime

# ================= VARIÁVEIS DE AMBIENTE =================

TOKEN = os.getenv("TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x]
GRUPO_TELEGRAM = int(os.getenv("GRUPO_TELEGRAM", 0))

STATE_DEPOSITAR = "depositar_valor"

# ================= VARIÁVEIS GLOBAIS =================
bonus_ativo = False
bonus_percentual = 0
bonus_valor_minimo = 0

# ================= UTIL =================
def is_admin(user_id):
    return user_id in ADMINS

async def criar_tabelas(conn):
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS usuarios(
        id BIGINT PRIMARY KEY,
        nome TEXT,
        username TEXT,
        saldo NUMERIC DEFAULT 0,
        registro TIMESTAMP
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS compras(
        id SERIAL PRIMARY KEY,
        usuario_id BIGINT REFERENCES usuarios(id),
        produto TEXT,
        preco NUMERIC,
        login TEXT,
        senha TEXT,
        data TIMESTAMP
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS estoque(
        id SERIAL PRIMARY KEY,
        produto TEXT,
        login TEXT,
        senha TEXT,
        imagens TEXT[]
    );
    """)
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS bonus(
        id SERIAL PRIMARY KEY,
        ativo BOOLEAN,
        percentual NUMERIC,
        valor_minimo NUMERIC
    );
    """)

# ================= SAFE EDIT =================
async def safe_edit_message(query, texto, teclado=None, parse_mode="Markdown"):
    try:
        await query.edit_message_text(texto, reply_markup=teclado, parse_mode=parse_mode)
    except:
        await query.message.reply_text(texto, reply_markup=teclado, parse_mode=parse_mode)

# ================= BOT MENUS =================
async def start_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    conn: asyncpg.Connection = context.bot_data["db"]

    usuario = await conn.fetchrow("SELECT * FROM usuarios WHERE id=$1", user.id)
    if not usuario:
        await conn.execute(
            "INSERT INTO usuarios(id,nome,username,saldo,registro) VALUES($1,$2,$3,$4,$5)",
            user.id, user.full_name, user.username or "", 0, datetime.now()
        )

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Loja", callback_data="menu_loja")],
        [InlineKeyboardButton("💰 Saldo", callback_data="menu_saldo")],
        [
            InlineKeyboardButton("📦 Meus pedidos", callback_data="menu_pedidos"),
            InlineKeyboardButton("👤 Perfil", callback_data="menu_perfil")
        ],
        [InlineKeyboardButton("🆘 Suporte", callback_data="menu_suporte")]
    ])

    texto = (
        f"👋 Olá, *{user.full_name}*\n\n"
        "💻🔥 ®RC STORE – BOT OFICIAL ®🔥💻\n\n"
        "Bem-vindo à maior plataforma de produtos digitais!"
    )

    img = "https://i.postimg.cc/Gt47J7p0/Screenshot-1.png"

    if update.message:
        await update.message.reply_photo(
            photo=img,
            caption=texto,
            reply_markup=teclado,
            parse_mode="Markdown"
        )
    else:
        query = update.callback_query
        await query.edit_message_media(
            InputMediaPhoto(media=img, caption=texto, parse_mode="Markdown"),
            reply_markup=teclado
        )

# ================= CALLBACK =================
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    conn: asyncpg.Connection = context.bot_data["db"]
    data = query.data

    if data == "menu_loja":
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📁 Produtos", callback_data="cat_produtos")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")]
        ])
        await safe_edit_message(query, "Escolha uma categoria:", teclado)

    elif data == "cat_produtos":
        produtos = await conn.fetch("SELECT DISTINCT produto FROM estoque")
        teclado = []
        for p in produtos:
            qtd = await conn.fetchval("SELECT COUNT(*) FROM estoque WHERE produto=$1", p["produto"])
            teclado.append([InlineKeyboardButton(f"{p['produto']} ({qtd})", callback_data=f"comprar_{p['produto']}")])
        teclado.append([InlineKeyboardButton("🔙 Voltar", callback_data="menu_loja")])
        await safe_edit_message(query, "📦 Produtos disponíveis:", InlineKeyboardMarkup(teclado))

    elif data.startswith("comprar_"):
        produto = data.split("_", 1)[1]
        u = await conn.fetchrow("SELECT * FROM usuarios WHERE id=$1", user.id)
        item = await conn.fetchrow("SELECT * FROM estoque WHERE produto=$1 LIMIT 1", produto)

        if not item:
            await safe_edit_message(query, "❌ Estoque insuficiente.")
            return

        preco = 100
        if u["saldo"] < preco:
            await safe_edit_message(query, "❌ Saldo insuficiente.")
            return

        await conn.execute("DELETE FROM estoque WHERE id=$1", item["id"])
        await conn.execute("UPDATE usuarios SET saldo=saldo-$1 WHERE id=$2", preco, user.id)
        await conn.execute(
            "INSERT INTO compras(usuario_id,produto,preco,login,senha,data) VALUES($1,$2,$3,$4,$5,$6)",
            user.id, produto, preco, item["login"], item["senha"], datetime.now()
        )

        await safe_edit_message(query, f"✅ Compra realizada!\nProduto: {produto}\nPreço: R$ {preco:.2f}")

    elif data == "menu_saldo":
        u = await conn.fetchrow("SELECT saldo FROM usuarios WHERE id=$1", user.id)
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Adicionar saldo", callback_data="adicionar_saldo")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="voltar_inicio")]
        ])
        await safe_edit_message(query, f"💰 Saldo: R$ {u['saldo']:.2f}", teclado)

    elif data == "adicionar_saldo":
        context.user_data[STATE_DEPOSITAR] = True
        await query.message.reply_text("Digite o valor:")

    elif data == "menu_pedidos":
        compras = await conn.fetch("SELECT * FROM compras WHERE usuario_id=$1", user.id)
        texto = "📦 Seus pedidos:\n\n"
        for c in compras:
            texto += f"{c['produto']} - R$ {c['preco']:.2f}\nLogin: {c['login']} | Senha: {c['senha']}\n\n"
        await safe_edit_message(query, texto or "Nenhuma compra.")

    elif data == "voltar_inicio":
        await start_menu(update, context)

# ================= TEXTO =================
async def receber_valor(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if STATE_DEPOSITAR in context.user_data:
        conn: asyncpg.Connection = context.bot_data["db"]
        valor = float(update.message.text)
        await conn.execute(
            "UPDATE usuarios SET saldo=saldo+$1 WHERE id=$2",
            valor, update.effective_user.id
        )
        context.user_data.pop(STATE_DEPOSITAR)
        await update.message.reply_text(f"✅ Depósito de R$ {valor:.2f} realizado.")

# ================= ADMIN =================
async def bonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bonus_ativo, bonus_percentual, bonus_valor_minimo
    bonus_percentual = float(context.args[0])
    bonus_valor_minimo = float(context.args[1])
    bonus_ativo = True
    await update.message.reply_text("🎁 Bônus ativado.")

async def desativar_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    global bonus_ativo
    bonus_ativo = False
    await update.message.reply_text("❌ Bônus desativado.")

async def add_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    produto, login_senha, *imgs = context.args
    login, senha = login_senha.split(":")
    conn = context.bot_data["db"]
    await conn.execute(
        "INSERT INTO estoque(produto,login,senha,imagens) VALUES($1,$2,$3,$4)",
        produto, login, senha, imgs
    )
    await update.message.reply_text("✅ Item adicionado.")

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conn = await asyncpg.connect(DATABASE_URL)
    await criar_tabelas(conn)
    app.bot_data["db"] = conn

    app.add_handler(CommandHandler("start", start_menu))
    app.add_handler(CommandHandler("bonus", bonus_cmd))
    app.add_handler(CommandHandler("desativar_bonus", desativar_bonus))
    app.add_handler(CommandHandler("add_estoque", add_estoque))

    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, receber_valor))

    print("🤖 Bot rodando...")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
