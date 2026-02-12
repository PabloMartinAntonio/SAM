from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

ej = 5

cur.execute("""
SELECT
  SUM(CASE WHEN p.monto IS NOT NULL THEN 1 ELSE 0 END) AS con_monto,
  SUM(CASE WHEN p.monto IS NULL THEN 1 ELSE 0 END) AS sin_monto,
  COUNT(*) AS total
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
con_monto, sin_monto, total = cur.fetchone()
print("total=", total, "con_monto=", con_monto, "sin_monto=", sin_monto)

cur.execute("""
SELECT estado_promesa, COUNT(*)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY estado_promesa
ORDER BY COUNT(*) DESC
""",(ej,))
print("\nby_estado:")
for estado, cnt in cur.fetchall():
    print(f"  {cnt:5d}  {estado}")

cur.execute("""
SELECT p.conversacion_pk, p.turno_idx, p.monto, p.moneda, p.numero_cuotas, p.fecha_pago, LEFT(p.evidence_text,120)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s AND p.monto IS NULL
ORDER BY p.promesa_pk DESC
LIMIT 10
""",(ej,))
rows = cur.fetchall()
print("\nMUESTRA 10 sin monto:")
for r in rows:
    print(r)

cur.close()
conn.close()
