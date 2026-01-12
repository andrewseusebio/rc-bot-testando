from flask import Flask, request
from telegram import Update
from main import application
from database import usuarios

app = Flask(__name__)

@app.route("/webhook", methods=["POST"])
async def tg():
    update = Update.de_json(request.json, application.bot)
    await application.process_update(update)
    return "ok"

@app.route("/asaas", methods=["POST"])
def asaas():
    data = request.json
    if data.get("event") == "PAYMENT_RECEIVED":
        user = int(data["payment"]["description"].split()[-1])
        valor = float(data["payment"]["value"])
        if user in usuarios:
            usuarios[user]["saldo"] += valor
    return "ok"
