from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Si existe la tabla de saltos/violaciones, contamos pendientes.
# Si no existe, va a fallar: en ese caso pegá el error y ajustamos.
cur.execute("""
SELECT COUNT(*) AS violaciones
FROM sa_saltos_fase s
JOIN sa_conversaciones c ON c.conversacion_pk=s.conversacion_pk
WHERE c.ejecucion_id=%s AND (s.resuelto=0 OR s.resuelto IS NULL)
""", (ej,))
v = cur.fetchone()[0]

print(f"ejecucion_id={ej} violaciones_pendientes={v}")

cur.close()
conn.close()
