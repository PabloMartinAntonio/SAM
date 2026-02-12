from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

ej = 5

cur.execute("""
SELECT
  SUM(CASE WHEN p.monto IS NOT NULL AND (p.moneda IS NULL OR p.moneda='') THEN 1 ELSE 0 END) AS con_monto_sin_moneda,
  SUM(CASE WHEN p.monto IS NOT NULL AND p.moneda IS NOT NULL AND p.moneda<>'' THEN 1 ELSE 0 END) AS con_monto_con_moneda
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
a,b = cur.fetchone()
print("con_monto_sin_moneda=", a, "con_monto_con_moneda=", b)

cur.execute("""
SELECT p.conversacion_pk, p.turno_idx, p.monto, p.moneda, LEFT(p.evidence_text,140)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s AND p.monto IS NOT NULL AND (p.moneda IS NULL OR p.moneda='')
ORDER BY p.promesa_pk DESC
LIMIT 10
""",(ej,))
print("\nMUESTRA 10 con monto sin moneda:")
for r in cur.fetchall():
    print(r)

cur.close(); conn.close()
