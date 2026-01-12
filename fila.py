import json, os
PATH = "reservas/fila_fisicos.json"

def carregar():
    if not os.path.exists(PATH): return []
    return json.load(open(PATH))

def salvar(fila):
    json.dump(fila, open(PATH,"w"), indent=4)

def entrar(user):
    fila = carregar()
    fila.append(user)
    salvar(fila)

def remover(pos):
    fila = carregar()
    fila.pop(pos)
    salvar(fila)
