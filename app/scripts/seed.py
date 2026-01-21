from app.repositories.db import init_db, get_conn

BARBERS = ["Barbeiro 1", "Barbeiro 2"]

SERVICES = [
    # name, duration_minutes, price_cents (opcional)
    ("Corte", 30, None),
    ("Barba", 30, None),
    ("Cabelo + Barba", 60, None),
    ("Cabelo + Barba + Limpeza de Pele", 90, None),
]

def run():
    init_db()
    conn = get_conn()
    try:
        for b in BARBERS:
            conn.execute(
                "INSERT OR IGNORE INTO barbers(name,is_active) VALUES(?,1)",
                (b,),
            )
        for name, dur, price in SERVICES:
            conn.execute(
                "INSERT OR IGNORE INTO services(name,duration_minutes,price_cents,is_active) VALUES(?,?,?,1)",
                (name, dur, price),
            )
        conn.commit()
    finally:
        conn.close()

if __name__ == "__main__":
    run()
