
import argparse
import sys
from contextlib import contextmanager

from sa_core.config import load_config
from sa_core.db import get_conn

# Constantes para fase_source
NOISE_IMPUTE_SOURCE = 'NO_IMP'
APERTURA_IMPUTE_SOURCE = 'AP_IMP'
APERTURA_BACKFILL_SOURCE = 'AP_BK'
CIERRE_IMPUTE_SOURCE = 'CI_IMP'
CIERRE_BACKFILL_SOURCE = 'CI_BK'
CIERRE_FIX1_SOURCE = 'CI_FIX1'

@contextmanager
def transaction(conn, do_write=False):
    """Manejador de contexto para transacciones con commit/rollback opcional."""
    cur = conn.cursor()
    try:
        yield cur
        if do_write:
            print("\n[DB] Committing changes...")
            conn.commit()
            print("[DB] Commit successful.")
        else:
            print("\n[DB] DRY RUN: Rolling back changes...")
            conn.rollback()
            print("[DB] Rollback successful.")
    except Exception as e:
        print(f"\n[DB] ERROR: An error occurred: {e}", file=sys.stderr)
        conn.rollback()
        print("[DB] Rollback successful due to error.", file=sys.stderr)
        raise
    finally:
        cur.close()

def noise_impute_prev_next(cur, ejecucion_id, do_write, verbose):
    """Imputa fases para turnos 'NOISE' desde el turno previo o siguiente."""
    print("\n1) Imputing NOISE from previous/next turn...")
    
    # Imputar desde el turno previo
    sql_prev = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_prev ON t.conversacion_pk = t_prev.conversacion_pk AND t.turno_idx = t_prev.turno_idx + 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase = t_prev.fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase_source = 'NOISE' AND (t.fase IS NULL OR TRIM(t.fase) = '')
      AND t_prev.fase IS NOT NULL AND TRIM(t_prev.fase) <> ''
    """
    params = (NOISE_IMPUTE_SOURCE, ejecucion_id)
    cur.execute(sql_prev, params)
    count_prev = cur.rowcount or 0
    print(f"  - Imputed from previous turn: {count_prev} rows")

    # Imputar desde el turno siguiente
    sql_next = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_next ON t.conversacion_pk = t_next.conversacion_pk AND t.turno_idx = t_next.turno_idx - 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase = t_next.fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase_source = 'NOISE' AND (t.fase IS NULL OR TRIM(t.fase) = '')
      AND t_next.fase IS NOT NULL AND TRIM(t_next.fase) <> ''
    """
    params = (NOISE_IMPUTE_SOURCE, ejecucion_id)
    cur.execute(sql_next, params)
    count_next = cur.rowcount or 0
    print(f"  - Imputed from next turn: {count_next} rows")
    return count_prev + count_next

def apertura_midcall_impute_prev(cur, ejecucion_id, do_write, verbose):
    """Corrige 'APERTURA' en mitad de llamada copiando la fase previa."""
    print("\n2) Correcting mid-call APERTURA from previous turn...")
    sql = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_prev ON t.conversacion_pk = t_prev.conversacion_pk AND t.turno_idx = t_prev.turno_idx + 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase = t_prev.fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase = 'APERTURA' AND t.turno_idx > 2
      AND t_prev.fase IS NOT NULL AND TRIM(t_prev.fase) <> '' AND t_prev.fase <> 'APERTURA'
    """
    params = (APERTURA_IMPUTE_SOURCE, ejecucion_id)
    cur.execute(sql, params)
    count = cur.rowcount or 0
    print(f"  - Corrected mid-call APERTURA: {count} rows")
    return count

def apertura_midcall_backfill_when_has_next(cur, ejecucion_id, do_write, verbose):
    """Busca hacia atrás una fase válida para 'APERTURA' en mitad de llamada."""
    print("\n3) Backfilling mid-call APERTURA from nearest valid past turn...")
    sql = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_next ON t.conversacion_pk = t_next.conversacion_pk AND t.turno_idx = t_next.turno_idx - 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    JOIN (
        SELECT t_sub.turno_pk, 
               (SELECT t_past.fase 
                FROM sa_turnos t_past
                WHERE t_past.conversacion_pk = t_sub.conversacion_pk AND t_past.turno_idx < t_sub.turno_idx
                  AND t_past.fase IS NOT NULL AND TRIM(t_past.fase) <> '' AND t_past.fase <> 'APERTURA'
                ORDER BY t_past.turno_idx DESC 
                LIMIT 1) as prev_fase
        FROM sa_turnos t_sub
    ) as prev_data ON t.turno_pk = prev_data.turno_pk
    SET t.fase = prev_data.prev_fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase = 'APERTURA'
      AND prev_data.prev_fase IS NOT NULL
    """
    params = (APERTURA_BACKFILL_SOURCE, ejecucion_id)
    cur.execute(sql, params)
    count = cur.rowcount or 0
    print(f"  - Backfilled mid-call APERTURA: {count} rows")
    return count

def cierre_midcall_impute_prev_when_has_next(cur, ejecucion_id, do_write, verbose):
    """Corrige 'CIERRE' en mitad de llamada si tiene turno siguiente."""
    print("\n4) Correcting mid-call CIERRE from previous turn...")
    sql = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_prev ON t.conversacion_pk = t_prev.conversacion_pk AND t.turno_idx = t_prev.turno_idx + 1
    JOIN sa_turnos t_next ON t.conversacion_pk = t_next.conversacion_pk AND t.turno_idx = t_next.turno_idx - 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase = t_prev.fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase = 'CIERRE'
      AND t_prev.fase IS NOT NULL AND TRIM(t_prev.fase) <> '' AND t_prev.fase <> 'CIERRE'
    """
    params = (CIERRE_IMPUTE_SOURCE, ejecucion_id)
    cur.execute(sql, params)
    count = cur.rowcount or 0
    print(f"  - Corrected mid-call CIERRE: {count} rows")
    return count

def cierre_backfill_when_has_next(cur, ejecucion_id, do_write, verbose):
    """Busca hacia atrás una fase válida para 'CIERRE' en mitad de llamada."""
    print("\n5) Backfilling mid-call CIERRE from nearest valid past turn...")
    sql = """
    UPDATE sa_turnos t
    JOIN sa_turnos t_next ON t.conversacion_pk = t_next.conversacion_pk AND t.turno_idx = t_next.turno_idx - 1
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    JOIN (
        SELECT t_sub.turno_pk, 
               (SELECT t_past.fase 
                FROM sa_turnos t_past
                WHERE t_past.conversacion_pk = t_sub.conversacion_pk AND t_past.turno_idx < t_sub.turno_idx
                  AND t_past.fase IS NOT NULL AND TRIM(t_past.fase) <> '' AND t_past.fase <> 'CIERRE'
                ORDER BY t_past.turno_idx DESC 
                LIMIT 1) as prev_fase
        FROM sa_turnos t_sub
    ) as prev_data ON t.turno_pk = prev_data.turno_pk
    SET t.fase = prev_data.prev_fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.fase = 'CIERRE'
      AND prev_data.prev_fase IS NOT NULL
    """
    params = (CIERRE_BACKFILL_SOURCE, ejecucion_id)
    cur.execute(sql, params)
    count = cur.rowcount or 0
    print(f"  - Backfilled mid-call CIERRE: {count} rows")
    return count

def fix_turno1_cierre(cur, ejecucion_id, do_write, verbose):
    """Corrige 'CIERRE' en turno 1 si el turno 2 tiene fase válida."""
    print("\n6) Fixing CIERRE at turn 1...")
    sql = """
    UPDATE sa_turnos t
    JOIN sa_turnos t2 ON t.conversacion_pk = t2.conversacion_pk AND t2.turno_idx = 2
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase = t2.fase, t.fase_source = %s
    WHERE c.ejecucion_id = %s
      AND t.turno_idx = 1 AND t.fase = 'CIERRE'
      AND t2.fase IS NOT NULL AND TRIM(t2.fase) <> ''
    """
    params = (CIERRE_FIX1_SOURCE, ejecucion_id)
    cur.execute(sql, params)
    count = cur.rowcount or 0
    print(f"  - Fixed CIERRE at turn 1: {count} rows")
    return count

def ensure_and_update_fase_8(cur, ejecucion_id, mapeo_version, do_write, verbose):
    """Asegura que la columna fase_8 exista y la actualiza."""
    print("\n7) Updating fase_8...")
    
    # Verificar si la columna existe
    cur.execute("SHOW COLUMNS FROM sa_turnos LIKE 'fase_8'")
    column_exists = cur.fetchone() is not None
    
    if not column_exists:
        if not do_write:
            print("  - WARNING: Column 'fase_8' does not exist and --write not specified. Skipping fase_8 update.")
            return 0
        # Crear columna solo en modo write
        cur.execute("ALTER TABLE sa_turnos ADD COLUMN fase_8 VARCHAR(64) NULL AFTER fase")
        print("  - Column 'fase_8' created.")
    elif verbose:
        print("  - Column 'fase_8' already exists.")
    
    # Actualizar fase_8 usando el mapeo
    sql_map = """
    UPDATE sa_turnos t
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    LEFT JOIN fase_mapeo_oficial m ON t.fase = m.fase_vieja_id AND m.version = %s AND m.activo = 1
    SET t.fase_8 = m.fase_nueva_id
    WHERE c.ejecucion_id = %s
    """
    params = (mapeo_version, ejecucion_id)
    cur.execute(sql_map, params)
    count_map = cur.rowcount or 0
    print(f"  - Mapped fase_8 from fase_mapeo_oficial: {count_map} rows")

    # Setear 'NOISE' en los nulos restantes
    sql_noise = """
    UPDATE sa_turnos t
    JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
    SET t.fase_8 = 'NOISE'
    WHERE c.ejecucion_id = %s
      AND (t.fase_8 IS NULL OR TRIM(t.fase_8) = '')
    """
    params_noise = (ejecucion_id,)
    cur.execute(sql_noise, params_noise)
    count_noise = cur.rowcount or 0
    print(f"  - Set remaining fase_8 to NOISE: {count_noise} rows")
    return count_map + count_noise

def show_metrics(cur, ejecucion_id):
    """Imprime métricas de calidad y estado final."""
    print("\n8) Final Metrics:")

    # Conteo por fase_source
    print("\n  - Counts by fase_source:")
    cur.execute("""
        SELECT fase_source, COUNT(*) as n, SUM(CASE WHEN fase IS NULL OR TRIM(fase) = '' THEN 1 ELSE 0 END) as fase_null
        FROM sa_turnos t
        JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
        WHERE c.ejecucion_id = %s
        GROUP BY fase_source
        ORDER BY fase_source
    """, (ejecucion_id,))
    for row in cur.fetchall():
        print(f"    - {row[0] or 'NULL':<20}: n={row[1]:<6}, fase_null={row[2]}")

    # NOISE y fase nulos (separados)
    cur.execute("""
        SELECT COUNT(*) FROM sa_turnos t
        JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
        WHERE c.ejecucion_id = %s AND t.fase_source = 'NOISE'
    """, (ejecucion_id,))
    noise_turns = cur.fetchone()[0]
    
    cur.execute("""
        SELECT COUNT(*) FROM sa_turnos t
        JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
        WHERE c.ejecucion_id = %s AND (t.fase IS NULL OR TRIM(t.fase) = '')
    """, (ejecucion_id,))
    fase_null_turns = cur.fetchone()[0]
    
    print(f"\n  - Turns with fase_source='NOISE': {noise_turns}")
    print(f"  - Turns with NULL or empty fase: {fase_null_turns}")

    # fase_8 nulos
    cur.execute("""
        SELECT COUNT(*) FROM sa_turnos t
        JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
        WHERE c.ejecucion_id = %s AND (t.fase_8 IS NULL OR TRIM(t.fase_8) = '')
    """, (ejecucion_id,))
    print(f"  - Null/empty fase_8 turns: {cur.fetchone()[0]}")

    # Violaciones de secuencia
    print("\n  - Final sequence violations:")
    sql_violations = """
    WITH fase_orden AS (
        SELECT 'APERTURA' as fase, 1 as orden UNION ALL
        SELECT 'IDENTIFICACIÓN', 2 UNION ALL
        SELECT 'IDENTIFICACION', 2 UNION ALL
        SELECT 'INFORMACIÓN_DEUDA', 3 UNION ALL
        SELECT 'INFORMACION_DEUDA', 3 UNION ALL
        SELECT 'NEGOCIACIÓN', 4 UNION ALL
        SELECT 'NEGOCIACION', 4 UNION ALL
        SELECT 'CONSULTA_ACEPTACIÓN', 5 UNION ALL
        SELECT 'CONSULTA_ACEPTACION', 5 UNION ALL
        SELECT 'FORMALIZACIÓN_PAGO', 6 UNION ALL
        SELECT 'FORMALIZACION_PAGO', 6 UNION ALL
        SELECT 'ADVERTENCIAS', 7 UNION ALL
        SELECT 'CIERRE', 8
    ),
    turnos_con_orden AS (
        SELECT 
            t.conversacion_pk, t.turno_idx, t.fase, fo.orden,
            LAG(t.fase, 1) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) as prev_fase,
            LAG(fo.orden, 1) OVER (PARTITION BY t.conversacion_pk ORDER BY t.turno_idx) as prev_orden
        FROM sa_turnos t
        JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
        LEFT JOIN fase_orden fo ON t.fase = fo.fase
        WHERE c.ejecucion_id = %s AND t.fase IS NOT NULL AND TRIM(t.fase) <> ''
    )
    SELECT prev_fase, fase, COUNT(*) as violations
    FROM turnos_con_orden
    WHERE prev_orden IS NOT NULL AND orden IS NOT NULL AND orden < prev_orden
      -- Excepciones permitidas (con variantes acentuadas)
      AND NOT (prev_fase IN ('FORMALIZACION_PAGO', 'FORMALIZACIÓN_PAGO') AND fase IN ('CONSULTA_ACEPTACION', 'CONSULTA_ACEPTACIÓN'))
      AND NOT (prev_fase = 'ADVERTENCIAS' AND fase IN ('CONSULTA_ACEPTACION', 'CONSULTA_ACEPTACIÓN'))
      AND NOT (prev_fase = 'ADVERTENCIAS' AND fase IN ('FORMALIZACION_PAGO', 'FORMALIZACIÓN_PAGO'))
    GROUP BY prev_fase, fase
    ORDER BY violations DESC
    """
    cur.execute(sql_violations, (ejecucion_id,))
    violations = cur.fetchall()
    if not violations:
        print("    - No violations found.")
    for prev_fase, fase, count in violations:
        print(f"    - {prev_fase} -> {fase}: {count} times")

def main():
    ap = argparse.ArgumentParser(description="Post-procesa una ejecución con operaciones SQL idempotentes.")
    ap.add_argument("--config", default="config.ini", help="Ruta al archivo de configuración.")
    ap.add_argument("--ejecucion_id", type=int, required=True, help="ID de la ejecución a procesar.")
    ap.add_argument("--mapeo_version", required=True, help="Versión del mapeo en fase_mapeo_oficial.")
    ap.add_argument("--write", action="store_true", help="Si se especifica, realiza los cambios en la DB.")
    ap.add_argument("--verbose", action="store_true", help="Muestra más detalles en el modo dry-run.")
    args = ap.parse_args()

    print(f"Starting post-processing for ejecucion_id={args.ejecucion_id}")
    if not args.write:
        print("--- RUNNING IN DRY-RUN MODE (no updates will be committed) ---")

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    
    total_updated = 0

    try:
        with transaction(conn, args.write) as cur:
            total_updated += noise_impute_prev_next(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += apertura_midcall_impute_prev(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += apertura_midcall_backfill_when_has_next(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += cierre_midcall_impute_prev_when_has_next(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += cierre_backfill_when_has_next(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += fix_turno1_cierre(cur, args.ejecucion_id, args.write, args.verbose)
            total_updated += ensure_and_update_fase_8(cur, args.ejecucion_id, args.mapeo_version, args.write, args.verbose)
            
            # Las métricas se muestran siempre, incluso en dry-run, sobre el estado potencial
            show_metrics(cur, args.ejecucion_id)

    finally:
        conn.close()

    print(f"\nProcess finished. Total rows affected (in {('write' if args.write else 'dry-run')} mode): {total_updated}")

if __name__ == "__main__":
    main()
