from sa_core.config import load_config
from sa_core.db import get_conn

src_ej = 2
limit_convs = 20

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

try:
    conn.start_transaction()

    # new ejecucion_id = max+1
    cur.execute("SELECT COALESCE(MAX(ejecucion_id),0)+1 FROM sa_ejecuciones")
    new_ej = int(cur.fetchone()[0])

    # crear sa_ejecuciones
    cur.execute(
        "INSERT INTO sa_ejecuciones (ejecucion_id, notas, input_dir) VALUES (%s, %s, %s)",
        (new_ej, f"SANDBOX copy from ejecucion_id={src_ej}", None)
    )

    # conversacion_pk origen
    cur.execute("""
        SELECT conversacion_pk
        FROM sa_conversaciones
        WHERE ejecucion_id=%s
        ORDER BY conversacion_pk
        LIMIT %s
    """, (src_ej, limit_convs))
    conv_pks = [int(r[0]) for r in cur.fetchall()]
    if not conv_pks:
        raise RuntimeError("No hay conversaciones en src_ej")

    # columnas sa_conversaciones
    cur.execute("SHOW COLUMNS FROM sa_conversaciones")
    cols = [r[0] for r in cur.fetchall()]
    if "conversacion_pk" not in cols or "ejecucion_id" not in cols:
        raise RuntimeError("Esquema sa_conversaciones inesperado")

    insert_cols = [c for c in cols if c != "conversacion_pk"]
    sel_cols = ", ".join(insert_cols)
    ins_cols = ", ".join(insert_cols)

    ph = ",".join(["%s"]*len(conv_pks))
    cur.execute(f"SELECT {sel_cols} FROM sa_conversaciones WHERE conversacion_pk IN ({ph})", tuple(conv_pks))
    src_rows = cur.fetchall()

    # necesitamos conversacion_id para mapear
    if "conversacion_id" not in insert_cols:
        raise RuntimeError("sa_conversaciones no tiene conversacion_id, no puedo mapear sandbox de forma segura")

    idx_ej = insert_cols.index("ejecucion_id")
    idx_cid = insert_cols.index("conversacion_id")

    # Insertar conversaciones sandbox y guardar mapping old_pk->new_pk por conversacion_id
    cur.execute(f"SELECT conversacion_pk, conversacion_id FROM sa_conversaciones WHERE conversacion_pk IN ({ph})", tuple(conv_pks))
    old_rows = cur.fetchall()
    old_by_cid = {r[1]: int(r[0]) for r in old_rows}

    old_to_new = {}
    for row in src_rows:
        row = list(row)
        row[idx_ej] = new_ej
        cid = row[idx_cid] or ""
        new_cid = f"SANDBOX_EJ{new_ej}__{cid}"
        row[idx_cid] = new_cid

        cur.execute(
            f"INSERT INTO sa_conversaciones ({ins_cols}) VALUES ({', '.join(['%s']*len(insert_cols))})",
            tuple(row)
        )
        new_pk = cur.lastrowid
        # mapear usando cid original
        old_pk = old_by_cid.get(cid)
        if old_pk:
            old_to_new[old_pk] = new_pk

    # copiar turnos
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
            tr[t_insert_cols.index("conversacion_pk")] = newpk
            # limpiar para pendientes
            for fld in ("fase", "fase_conf", "fase_source", "fase_8"):
                if fld in t_insert_cols:
                    tr[t_insert_cols.index(fld)] = None
            cur.execute(
                f"INSERT INTO sa_turnos ({t_ins}) VALUES ({', '.join(['%s']*len(t_insert_cols))})",
                tuple(tr)
            )
            copied += 1

    conn.commit()
    print(f"[OK] SANDBOX created new_ej={new_ej} copied_convs={len(old_to_new)} copied_turnos={copied}")

except Exception as e:
    conn.rollback()
    raise
finally:
    cur.close()
    conn.close()
