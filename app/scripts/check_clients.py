from app.repositories.db import get_conn

conn = get_conn()
rows = conn.execute("SELECT id, client_key, name, created_at FROM clients ORDER BY id DESC LIMIT 10").fetchall()
for r in rows:
    print(dict(r))
conn.close()
