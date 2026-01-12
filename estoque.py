import os
BASE = "estoque"

MAPA = {
    "mix": "mix_fisicos.txt",
    "digitais": "pedidos_digitais.txt",
    "mais10": "mais_10_fisicos.txt"
}

def path(p): return os.path.join(BASE, MAPA[p])

def listar(p):
    if not os.path.exists(path(p)): return []
    return [l.strip() for l in open(path(p), encoding="utf-8") if l.strip()]

def contar(p): return len(listar(p))

def adicionar(p, item):
    open(path(p), "a", encoding="utf-8").write(item + "\n")

def retirar(p):
    itens = listar(p)
    if not itens: return None
    item = itens.pop(0)
    open(path(p), "w", encoding="utf-8").write("\n".join(itens) + "\n")
    return item

def remover_posicao(p, pos):
    itens = listar(p)
    if pos < 0 or pos >= len(itens): return False
    itens.pop(pos)
    open(path(p), "w", encoding="utf-8").write("\n".join(itens) + "\n")
    return True
