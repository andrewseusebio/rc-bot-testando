usuarios = {}
banidos = set()
ADMINS = [8276989322]

def init_user(user):
    if user.id not in usuarios:
        usuarios[user.id] = {
            "nome": user.full_name,
            "saldo": 0.0,
            "compras": []
        }
