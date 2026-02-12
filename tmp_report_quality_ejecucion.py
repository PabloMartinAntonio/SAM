import argparse
from sa_core.config import load_config
from sa_core.db import get_conn

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    cur = conn.cursor()

    ej = args.ejecucion_id

    print(f"\n=== COUNTS ejecucion_id={ej} ===")
    cur.execute("""
        SELECT COUNT(*)
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        WHERE c.ejecucion_id=%s
    """, (ej,))
    total = cur.fetchone()[0]
    print("total_turnos=", total)

    cur.execute("""
        SELECT COUNT(*)
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        WHERE c.ejecucion_id=%s AND (t.fase IS NULL OR TRIM(t.fase)='')
    """, (ej,))
    fase_null = cur.fetchone()[0]
    print("fase_null=", fase_null)

    cur.execute("""
        SELECT COUNT(*)
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        WHERE c.ejecucion_id=%s AND (t.fase_source='NOISE')
    """, (ej,))
    noise = cur.fetchone()[0]
    print("noise_marcados=", noise)

    cur.execute("""
        SELECT COUNT(*)
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        WHERE c.ejecucion_id=%s
          AND (t.fase IS NULL OR TRIM(t.fase)='')
          AND (t.fase_source IS NULL OR TRIM(t.fase_source)='')
    """, (ej,))
    fase_null_y_source_null = cur.fetchone()[0]
    print("fase_null_y_source_null=", fase_null_y_source_null)

    print(f"\n=== DIST (source,fase) ejecucion_id={ej} ===")
    cur.execute("""
        SELECT
          COALESCE(NULLIF(TRIM(t.fase_source),''),'(NULL)') AS source,
          COALESCE(NULLIF(TRIM(t.fase),''),'(NULL)') AS fase,
          COUNT(*) AS cnt
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        WHERE c.ejecucion_id=%s
        GROUP BY source, fase
        ORDER BY cnt DESC
    """, (ej,))
    for r in cur.fetchall():
        print(r)

    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
