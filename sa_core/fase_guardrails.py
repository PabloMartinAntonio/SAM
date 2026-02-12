from typing import Tuple, List
import re

FILLER_RE = re.compile(r"^(si|sí|ok|okay|ya|aj[aá]|mm+|eh+|gracias|dale|listo|perfecto)\W*$", re.I)
DEUDA_KW = re.compile(r"\b(deuda|monto|saldo|importe|venc|interes|cuota|pag[oar]|cbu|alias|transfer|deposit)\b", re.I)
NEGOCIO_KW = re.compile(r"\b(negoci|acord|propuest|plan|opcion|pued[e]?|pod[e]?mos|oferta)\b", re.I)

# Whitelist de retrocesos tolerables (prev_fase, curr_fase)
TOLERABLE_RETROCESOS = {
    ("OBJECIONES_CLIENTE", "OFERTA_PAGO"),
    ("VALIDACION_IDENTIDAD", "PRESENTACION_AGENTE"),
    ("CONSULTA_ACEPTACION", "OFERTA_PAGO"),
    ("CONSULTA_ACEPTACION", "OBJECIONES_CLIENTE"),
}


def has_meaningful_text(s: str) -> bool:
    if not s:
        return False
    t = (s or "").strip()
    if not t:
        return False
    if FILLER_RE.match(t.lower()):
        return False
    return len(t.replace(" ", "")) >= 3


def is_retroceso_tolerable(prev_fase: str, curr_fase: str) -> bool:
    """
    Verifica si el retroceso de prev_fase a curr_fase está en la whitelist de retrocesos tolerables.
    """
    prev = (prev_fase or "").strip().upper()
    curr = (curr_fase or "").strip().upper()
    return (prev, curr) in TOLERABLE_RETROCESOS


def apply_guardrails(pred_fase: str, pred_conf: float, is_noise: int,
                     last_phase: str | None, has_next_meaningful_text: bool,
                     curr_text: str, prev_texts: List[str]) -> Tuple[str | None, float, str, str]:
    """
    Returns: (final_fase, final_conf, final_source, reason)
    - If noise: mark NOISE and no phase
    - CIERRE guard: if next has meaningful text, change to INFORMACION_DEUDA or NEGOCIACION
    - APERTURA late: if last_phase exists and not APERTURA, change to IDENTIFICACION unless strong start evidence
    """
    reason = ""

    # Noise handling
    if is_noise:
        return None, 0.0, "NOISE", "Detected noise/out-of-domain"

    fase = (pred_fase or "").strip().upper()
    conf = float(pred_conf or 0.0)

    # CIERRE guard
    if fase == "CIERRE" and has_next_meaningful_text:
        txt_block = " ".join([curr_text] + (prev_texts or []))
        if DEUDA_KW.search(txt_block):
            return "INFORMACION_DEUDA", max(conf, 0.55), "GUARDRAILS", "Prevented premature CIERRE -> info deuda"
        else:
            return "NEGOCIACION", max(conf, 0.55), "GUARDRAILS", "Prevented premature CIERRE -> negociacion"

    # APERTURA late guard
    lp = (last_phase or "").strip().upper()
    if fase == "APERTURA" and lp and lp != "APERTURA":
        strong_start = re.search(r"me\s+comunico\s+con\s+usted|de\s+parte\s+de|somos\s+", (curr_text or ""), re.I)
        if not strong_start:
            return "IDENTIFICACION", max(conf, 0.50), "GUARDRAILS", "Adjusted late APERTURA -> IDENTIFICACION"

    return fase, conf, "DEEPSEEK", reason
