from sa_core.config import load_config
from sa_core.db import get_conn

src_ej = 2
limit_convs = 20

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

# 1) Crear nueva ejecucion_id (si tenés tabla sa_ejecuciones; si no, usamos max+1 de sa_conversaciones)
cur.execute("SELECT COALESCE(MAX(ejecucion_id),0)+1 FROM sa_conversaciones")
new_ej = int(cur.fetchone()[0])

# 2) Tomar conversacion_pk de origen
cur.execute("""
SELECT conversacion_pk
FROM sa_conversaciones
WHERE ejecucion_id=%s
ORDER BY conversacion_pk
LIMIT %s
""", (src_ej, limit_convs))
conv_pks = [int(r[0]) for r in cur.fetchall()]
if not conv_pks:
    raise SystemExit("No hay conversaciones en src_ej")

# 3) Duplicar conversaciones a nueva ejecucion_id
# (copiamos filas de sa_conversaciones cambiando ejecucion_id; conservamos conversacion_pk? NO, debe ser nuevo)
# Estrategia: insertar nuevas filas con conversacion_id modificado y luego copiar turnos apuntando a nuevas PKs.
# Requiere conocer columnas de sa_conversaciones.
cur.execute("SHOW COLUMNS FROM sa_conversaciones")
cols = [r[0] for r in cur.fetchall()]
# asumimos PK autoincrement conversacion_pk existe
if "conversacion_pk" not in cols or "ejecucion_id" not in cols:
    raise SystemExit("Esquema sa_conversaciones inesperado")

insert_cols = [c for c in cols if c != "conversacion_pk"]
sel_cols = ", ".join(insert_cols)
ins_cols = ", ".join(insert_cols)

# Traer filas origen
ph = ",".join(["%s"]*len(conv_pks))
cur.execute(f"SELECT {sel_cols} FROM sa_conversaciones WHERE conversacion_pk IN ({ph})", tuple(conv_pks))
src_rows = cur.fetchall()

# Insertar y mapear old_pk -> new_pk
pk_map = {}
for row in src_rows:
    row = list(row)
    # set ejecucion_id = new_ej
    ej_idx = insert_cols.index("ejecucion_id")
    row[ej_idx] = new_ej
    # opcional: marcar conversacion_id para identificar sandbox si existe
    if "conversacion_id" in insert_cols:
        cid_idx = insert_cols.index("conversacion_id")
        row[cid_idx] = f"SANDBOX_EJ{new_ej}__" + (row[cid_idx] or "")
    cur.execute(f"INSERT INTO sa_conversaciones ({ins_cols}) VALUES ({', '.join(['%s']*len(insert_cols))})", tuple(row))
    new_pk = cur.lastrowid
    # recuperar old_pk para map: necesitamos leerlo de vuelta con conversacion_id único
    # más simple: reconsultar por conversacion_id recién insertado
    pk_map_key = row[insert_cols.index("conversacion_id")] if "conversacion_id" in insert_cols else None
    pk_map[pk_map_key] = new_pk

# reconstruir map old_pk -> new_pk usando conversacion_id
cur.execute(f"SELECT conversacion_pk, conversacion_id FROM sa_conversaciones WHERE ejecucion_id=%s", (new_ej,))
new_rows = cur.fetchall()
new_by_cid = {r[1]: int(r[0]) for r in new_rows}

cur.execute(f"SELECT conversacion_pk, conversacion_id FROM sa_conversaciones WHERE conversacion_pk IN ({ph})", tuple(conv_pks))
old_rows = cur.fetchall()
old_by_cid = {r[1]: int(r[0]) for r in old_rows}

old_to_new = {}
for cid, oldpk in old_by_cid.items():
    newcid = f"SANDBOX_EJ{new_ej}__" + (cid or "")
    newpk = new_by_cid.get(newcid)
    if newpk:
        old_to_new[oldpk] = newpk

# 4) Copiar turnos
cur.execute("SHOW COLUMNS FROM sa_turnos")
tcols = [r[0] for r in cur.fetchall()]
t_insert_cols = [c for c in tcols if c != "turno_pk"]
t_sel = ", ".join(t_insert_cols)
t_ins = ", ".join(t_insert_cols)

copied = 0
for oldpk, newpk in old_to_new.items():
    cur.execute(f"SELECT {t_sel} FROM sa_turnos WHERE conversacion_pk=%s ORDER BY turno_idx", (oldpk,))
    turns = cur.fetchall()
    for tr in turns:
        tr = list(tr)
        # set conversacion_pk to newpk
        cp_idx = t_insert_cols.index("conversacion_pk")
        tr[cp_idx] = newpk
        # limpiar fase para dejar pendientes (fase, fase_conf, fase_source, fase_8 si existe)
        if "fase" in t_insert_cols:
            tr[t_insert_cols.index("fase")] = None
        if "fase_conf" in t_insert_cols:
            tr[t_insert_cols.index("fase_conf")] = None
        if "fase_source" in t_insert_cols:
            tr[t_insert_cols.index("fase_source")] = None
        if "fase_8" in t_insert_cols:
            tr[t_insert_cols.index("fase_8")] = None
        cur.execute(f"INSERT INTO sa_turnos ({t_ins}) VALUES ({', '.join(['%s']*len(t_insert_cols))})", tuple(tr))
        copied += 1

conn.commit()
print(f"[OK] SANDBOX created new_ej={new_ej} copied_convs={len(old_to_new)} copied_turnos={copied}")

cur.close()
conn.close()
