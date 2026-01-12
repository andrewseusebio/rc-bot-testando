#!/bin/bash

# Verifique se o Python 3 está instalado e crie um ambiente virtual
python3 -m venv venv

# Ative o ambiente virtual
source venv/bin/activate

# Instale as dependências do projeto
pip install -r requirements.txt

# Inicie o bot
python3 bot.py
