from sa_core.config import load_config
from sa_core.db import get_conn

mapeo_version = "v12a8_ej2_2026-02-09"

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# Allowed phases (11)
cur.execute("SELECT fase_id, orden_fase FROM fases_conversacion ORDER BY orden_fase")
allowed = cur.fetchall()
print("allowed_phases=", len(allowed))
for fase_id, orden in allowed:
    print(f"  {orden:>2}. {fase_id}")

# Mapping rows for version
cur.execute("""
SELECT COUNT(*) 
FROM fase_mapeo_oficial
WHERE version=%s AND activo=1
""", (mapeo_version,))
n_map = cur.fetchone()[0]
print(f"\nmapeo_version={mapeo_version} rows_activos={n_map}")

cur.execute("""
SELECT fase_vieja_id, fase_nueva_id, criterio, prioridad
FROM fase_mapeo_oficial
WHERE version=%s AND activo=1
ORDER BY prioridad ASC, fase_vieja_id ASC
""", (mapeo_version,))
rows = cur.fetchall()
print("\nfirst_rows:")
for r in rows[:30]:
    print(" ", r)

cur.close()
conn.close()
