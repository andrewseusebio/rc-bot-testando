from datetime import datetime

def log(texto):
    with open("logs.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now()}] {texto}\n")
