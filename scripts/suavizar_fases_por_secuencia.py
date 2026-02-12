import argparse
from typing import Dict, List, Tuple

from sa_core.config import load_config
from sa_core.db import get_conn


ALLOWED_TRANSITIONS: Dict[str, set] = {
    "APERTURA": {"APERTURA", "IDENTIFICACION"},
    "IDENTIFICACION": {"IDENTIFICACION", "INFORMACION_DEUDA"},
    "INFORMACION_DEUDA": {"INFORMACION_DEUDA", "NEGOCIACION", "ADVERTENCIAS"},
    "NEGOCIACION": {"NEGOCIACION", "CONSULTA_ACEPTACION", "INFORMACION_DEUDA"},
    "CONSULTA_ACEPTACION": {"CONSULTA_ACEPTACION", "FORMALIZACION_PAGO", "NEGOCIACION"},
    "FORMALIZACION_PAGO": {"FORMALIZACION_PAGO", "CIERRE"},
    "ADVERTENCIAS": {"ADVERTENCIAS", "CIERRE", "NEGOCIACION", "INFORMACION_DEUDA"},
    "CIERRE": {"CIERRE"},
}


def is_allowed(a: str, b: str) -> bool:
    if not a or not b:
        return True
    a = a.strip().upper()
    b = b.strip().upper()
    return b in ALLOWED_TRANSITIONS.get(a, {a}) or a == b


def _intermediate_for(a: str, b: str) -> str | None:
    a = (a or "").strip().upper()
    b = (b or "").strip().upper()
    if a == "APERTURA" and b == "NEGOCIACION":
        return "IDENTIFICACION"
    if a == "NEGOCIACION" and b == "IDENTIFICACION":
        return "INFORMACION_DEUDA"
    return None


def suavizar_fases_por_secuencia(conn, ejecucion_id: int, conf_min: float = 0.40, write: bool = False, verbose: bool = False) -> Dict:
    cur = conn.cursor()
    # Obtener conversaciones
    cur.execute("SELECT conversacion_pk FROM sa_conversaciones WHERE ejecucion_id=%s ORDER BY conversacion_pk", (ejecucion_id,))
    convs = [int(r[0]) for r in cur.fetchall()]

    total_violations_before = 0
    total_violations_after = 0
    total_changes = 0
    changes_log: List[Tuple[int, int, str, str]] = []  # (conv_pk, turno_pk, old_fase, new_fase)

    for conv_pk in convs:
        cur.execute(
            """
            SELECT turno_pk, turno_idx, fase, fase_conf, fase_source, text
            FROM sa_turnos
            WHERE conversacion_pk=%s
            ORDER BY turno_idx
            """,
            (conv_pk,)
        )
        rows = cur.fetchall()
        if not rows:
            continue

        # Local copies to simulate changes before writing
        local = [
            {
                "turno_pk": int(r[0]),
                "turno_idx": int(r[1]),
                "fase": (r[2] or "").strip().upper(),
                "fase_conf": float(r[3]) if r[3] is not None else None,
                "fase_source": (r[4] or ""),
                "text": (r[5] or ""),
            }
            for r in rows
        ]

        # Count violations before
        violations = 0
        for i in range(len(local) - 1):
            a = local[i]["fase"]
            b = local[i + 1]["fase"]
            if a and b and not is_allowed(a, b):
                violations += 1
        total_violations_before += violations

        # Smooth pass
        for i in range(len(local) - 1):
            a = local[i]["fase"]
            b = local[i + 1]["fase"]
            if not a or not b:
                continue
            if is_allowed(a, b):
                continue

            # Protection: don't touch strong DeepSeek
            prot_a = (local[i]["fase_source"] == "DEEPSEEK" and (local[i]["fase_conf"] or 0) >= 0.70)
            prot_b = (local[i + 1]["fase_source"] == "DEEPSEEK" and (local[i + 1]["fase_conf"] or 0) >= 0.70)

            conf_a = (local[i]["fase_conf"] or 0.0)
            conf_b = (local[i + 1]["fase_conf"] or 0.0)

            new_phase = None
            target_idx = None

            # Prefer modify the lower confidence turn
            if (not prot_b) and (conf_b < conf_a or conf_b < conf_min):
                # change B to A
                new_phase = a
                target_idx = i + 1
            elif (not prot_a) and (conf_a < conf_min):
                # change A to B
                new_phase = b
                target_idx = i
            else:
                mid = _intermediate_for(a, b)
                if mid:
                    if not prot_b and (conf_b <= conf_a):
                        new_phase = mid
                        target_idx = i + 1
                    elif not prot_a:
                        new_phase = mid
                        target_idx = i

            if new_phase and target_idx is not None:
                old_phase = local[target_idx]["fase"]
                if old_phase == new_phase:
                    continue
                local[target_idx]["fase"] = new_phase
                local[target_idx]["fase_conf"] = 0.55  # set to standard smoothed confidence
                local[target_idx]["fase_source"] = "SMOOTH"
                total_changes += 1
                changes_log.append((conv_pk, local[target_idx]["turno_pk"], old_phase, new_phase))

        # Count violations after
        violations_after = 0
        for i in range(len(local) - 1):
            a = local[i]["fase"]
            b = local[i + 1]["fase"]
            if a and b and not is_allowed(a, b):
                violations_after += 1
        total_violations_after += violations_after

        # Apply changes if write
        if write and changes_log:
            for (conv, turno_pk, old_f, new_f) in [c for c in changes_log if c[0] == conv_pk]:
                cur.execute(
                    "UPDATE sa_turnos SET fase=%s, fase_conf=%s, fase_source=%s WHERE turno_pk=%s",
                    (new_f, 0.55, "SMOOTH", turno_pk),
                )

    if write and total_changes:
        conn.commit()

    print("--- Suavizado Fases ---")
    print(f"Ejecución: {ejecucion_id}")
    print(f"Violaciones antes: {total_violations_before}")
    print(f"Violaciones después: {total_violations_after}")
    print(f"Cambios aplicados: {total_changes}")
    return {
        "violations_before": total_violations_before,
        "violations_after": total_violations_after,
        "changes": total_changes,
    }


def main():
    ap = argparse.ArgumentParser(description="Suaviza fases por secuencia para reducir transiciones ilegales")
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--conf_min", type=float, default=0.40)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--config", default="config.ini")
    args = ap.parse_args()

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    try:
        suavizar_fases_por_secuencia(conn, args.ejecucion_id, conf_min=args.conf_min, write=args.write, verbose=args.verbose)
    finally:
        if conn and conn.is_connected():
            conn.close()


if __name__ == "__main__":
    main()
