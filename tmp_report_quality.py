from sa_core.config import load_config
from sa_core.db import get_conn

ej = 2
cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 1) Distribución por fase_source y fase
cur.execute("""
SELECT IFNULL(fase_source,'(NULL)') AS src, IFNULL(fase,'(NULL)') AS fase, COUNT(*) n
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
GROUP BY src, fase
ORDER BY src, n DESC
""", (ej,))
print("\n=== dist (source,fase) ===")
for r in cur.fetchall()[:60]:
    print(r)

# 2) Pendientes (lo mismo que export)
conf_threshold = 0.55
cur.execute("""
SELECT COUNT(*)
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND (t.fase IS NULL OR TRIM(t.fase)='' OR IFNULL(t.fase_conf,0) < %s)
  AND (t.fase_source IS NULL OR t.fase_source <> 'DEEPSEEK')
""", (ej, conf_threshold))
print("\npendientes_export=", cur.fetchone()[0])

# 3) Violaciones de transición (muy útil)
allowed = {
 "APERTURA": {"APERTURA","IDENTIFICACION","INFORMACION_DEUDA","CIERRE"},
 "IDENTIFICACION": {"IDENTIFICACION","INFORMACION_DEUDA","NEGOCIACION","CIERRE"},
 "INFORMACION_DEUDA": {"INFORMACION_DEUDA","NEGOCIACION","ADVERTENCIAS","CIERRE"},
 "NEGOCIACION": {"NEGOCIACION","CONSULTA_ACEPTACION","FORMALIZACION_PAGO","ADVERTENCIAS","CIERRE","INFORMACION_DEUDA"},
 "CONSULTA_ACEPTACION": {"CONSULTA_ACEPTACION","FORMALIZACION_PAGO","NEGOCIACION","ADVERTENCIAS","CIERRE"},
 "FORMALIZACION_PAGO": {"FORMALIZACION_PAGO","NEGOCIACION","ADVERTENCIAS","CIERRE","CONSULTA_ACEPTACION"},
 "ADVERTENCIAS": {"ADVERTENCIAS","NEGOCIACION","CONSULTA_ACEPTACION","FORMALIZACION_PAGO","CIERRE","INFORMACION_DEUDA"},
 "CIERRE": {"CIERRE"}
}

cur.execute("""
SELECT t.conversacion_pk, t.turno_idx, t.fase, t2.fase
FROM sa_turnos t
JOIN sa_turnos t2 ON t2.conversacion_pk=t.conversacion_pk AND t2.turno_idx=t.turno_idx+1
JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
WHERE c.ejecucion_id=%s
  AND t.fase IS NOT NULL AND TRIM(t.fase)<>'' 
  AND t2.fase IS NOT NULL AND TRIM(t2.fase)<>''
ORDER BY t.conversacion_pk, t.turno_idx
""", (ej,))

viol = {}
for conv_pk, idx, a, b in cur.fetchall():
    if b not in allowed.get(a, set()):
        key = (a,b)
        viol[key] = viol.get(key,0) + 1

print("\n=== top transition violations ===")
for (a,b),n in sorted(viol.items(), key=lambda x: x[1], reverse=True)[:25]:
    print(n, a, "->", b)

cur.close()
conn.close()
