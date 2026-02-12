from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

ej = 5

cur.execute("""
SELECT COUNT(*)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
""",(ej,))
print("promesas_en_bd_ej=", cur.fetchone()[0])

cur.execute("""
SELECT estado_promesa, COUNT(*)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY estado_promesa
ORDER BY COUNT(*) DESC
""",(ej,))
print("by_estado:")
for estado, cnt in cur.fetchall():
    print(f"  {cnt:5d}  {estado}")

cur.execute("""
SELECT
  p.conversacion_pk, p.turno_idx, p.monto, p.moneda, p.numero_cuotas, p.fecha_pago,
  LEFT(p.evidence_text,120)
FROM sa_promesas_pago p
JOIN sa_conversaciones c ON c.conversacion_pk=p.conversacion_pk
WHERE c.ejecucion_id=%s
ORDER BY p.promesa_pk DESC
LIMIT 10
""",(ej,))
print("\nMUESTRA 10 (bd):")
for r in cur.fetchall():
    print(r)

cur.close()
conn.close()
