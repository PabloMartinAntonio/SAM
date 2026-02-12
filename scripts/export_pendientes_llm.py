import os
import csv
import argparse
from typing import Dict

from sa_core.config import load_config
from sa_core.db import get_conn


def export_pendientes_llm(conn, ejecucion_id: int, conf_threshold: float, limit: int = 0, out_dir: str = "out_reports") -> Dict:
    """
    Exporta a CSV los turnos pendientes de clasificación por LLM para una ejecución.
    - Pendientes: (t.fase IS NULL OR TRIM(t.fase)='' OR IFNULL(t.fase_conf,0) < conf_threshold)
    - Excluye los con t.fase_source='DEEPSEEK'
    - Incluye prev_fase y next_fase via self-joins
    CSV columnas EXACTAS: turno_pk, conv_pk, turno_idx, conversacion_id, text, fase, fase_conf, fase_source, prev_fase, next_fase
    Retorna dict con path y rows
    """
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"run_{ejecucion_id}_pendientes_llm.csv")

    cur = conn.cursor()
    sql = (
        """
        SELECT
          t.turno_pk,
          t.conversacion_pk AS conv_pk,
          t.turno_idx,
          c.conversacion_id,
          t.text,
          t.fase,
          t.fase_conf,
          t.fase_source,
          t_prev.fase AS prev_fase,
          t_next.fase AS next_fase
        FROM sa_turnos t
        JOIN sa_conversaciones c ON c.conversacion_pk=t.conversacion_pk
        LEFT JOIN sa_turnos t_prev ON t_prev.conversacion_pk=t.conversacion_pk AND t_prev.turno_idx=t.turno_idx-1
        LEFT JOIN sa_turnos t_next ON t_next.conversacion_pk=t.conversacion_pk AND t_next.turno_idx=t.turno_idx+1
                WHERE c.ejecucion_id=%s
                    AND t.fase_source = 'NO_IMP'  -- Solo imputados desde NOISE, candidatos para LLM
                    AND t.fase_source <> 'IMPUTE_SHORT'  -- Exclusión explícita para evitar regresiones
        ORDER BY t.conversacion_pk, t.turno_idx
        """
    )

    params = [ejecucion_id]
    if limit and limit > 0:
        sql += " LIMIT %s"
        params.append(limit)

    cur.execute(sql, tuple(params))
    rows = cur.fetchall()
    cur.close()

    total_rows = 0
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        wr = csv.writer(f)
        wr.writerow([
            "turno_pk",
            "conv_pk",
            "turno_idx",
            "conversacion_id",
            "text",
            "fase",
            "fase_conf",
            "fase_source",
            "prev_fase",
            "next_fase",
        ])
        for r in rows:
            wr.writerow([
                int(r[0]),  # turno_pk
                int(r[1]),  # conv_pk
                int(r[2]),  # turno_idx
                r[3],       # conversacion_id
                r[4] or "",
                (r[5] or ""),
                r[6] if r[6] is not None else "",
                (r[7] or ""),
                (r[8] or ""),
                (r[9] or ""),
            ])
            total_rows += 1

    print(f"[OK] wrote: {out_path} rows={total_rows} ejecucion_id={ejecucion_id} conf_threshold={conf_threshold}")
    return {"path": out_path, "rows": total_rows}


def main():
    ap = argparse.ArgumentParser(description="Exporta pendientes LLM a CSV")
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--conf_threshold", type=float, default=0.55)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out_dir", default="out_reports")
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    try:
        export_pendientes_llm(conn, args.ejecucion_id, args.conf_threshold, args.limit, args.out_dir)
    finally:
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
