import os
import json
import requests
import asyncpg
import aiohttp
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from flask import Flask, request

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

# ================= COMANDO: /pix =================
ASSAS_API_KEY = "sua_api_key"  # Coloque sua chave da API Assas aqui
ASSAS_API_URL = "https://api.assas.com.br/v2/cobrar/pix"

def gerar_pix(valor, cliente_id):
    url = ASSAS_API_URL
    headers = {
        'Authorization': f'Bearer {ASSAS_API_KEY}',
        'Content-Type': 'application/json'
    }
    data = {
        "valor": valor,
        "cliente_id": cliente_id,
        "descricao": "Recarga de saldo",
        "expiracao": 3600  # Tempo de expiração em segundos (1 hora)
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        data = response.json()
        qr_code_url = data["pix"]["qrcode"]
        payment_url = data["pix"]["url"]
        return qr_code_url, payment_url
    return None, None

async def enviar_pix(update, context):
    user_id = update.effective_user.id
    valor = 50  # Valor de exemplo
    qr_code_url, payment_url = gerar_pix(valor, user_id)

    if qr_code_url:
        texto = f"💰 Para adicionar R$ {valor} ao seu saldo, pague via Pix:\n{payment_url}"
        await update.message.reply_text(texto)
        await update.message.reply_photo(photo=qr_code_url)
    else:
        await update.message.reply_text("❌ Não foi possível gerar o Pix. Tente novamente mais tarde.")

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

        preco = 100  # Valor do produto
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

# ================= COMANDOS ADMIN =================
async def add_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        produto = context.args[0]
        login_senha = context.args[1]
        imagens = context.args[2:]
        login, senha = login_senha.split(":")
        conn: asyncpg.Connection = context.bot_data["db"]
        await conn.execute(
            "INSERT INTO estoque(produto,login,senha,imagens) VALUES($1,$2,$3,$4)",
            produto, login, senha, imagens
        )
        await update.message.reply_text(f"✅ Item adicionado: {produto}")
    except:
        await update.message.reply_text("❌ Uso: /add_estoque produto login:senha url1 url2 ...")

async def ver_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    conn: asyncpg.Connection = context.bot_data["db"]
    estoque = await conn.fetch("SELECT * FROM estoque")
    if not estoque:
        await update.message.reply_text("❌ Estoque vazio.")
        return
    texto = "📦 Estoque:\n"
    for e in estoque:
        texto += f"ID: {e['id']} | Produto: {e['produto']} | Login: {e['login']}\n"
    await update.message.reply_text(texto)

# ================= MAIN =================
async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conn = await asyncpg.connect(DATABASE_URL)
    await criar_tabelas(conn)
    app.bot_data["db"] = conn

    # Comandos de usuário
    app.add_handler(CommandHandler("start", start_menu))
    app.add_handler(CommandHandler("pix", enviar_pix))

    # Comandos de administrador
    app.add_handler(CommandHandler("add_estoque", add_estoque))
    app.add_handler(CommandHandler("ver_estoque", ver_estoque))

    # Manipuladores de callback
    app.add_handler(CallbackQueryHandler(callback_handler))

    # Rodando o bot
    print("🤖 Bot rodando...")
    await app.run_polling()

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    import asyncio
    asyncio.run(main())
