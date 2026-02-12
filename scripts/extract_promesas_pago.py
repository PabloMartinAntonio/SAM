import re
import argparse
from datetime import date, datetime, timedelta

from sa_core.config import load_config
from sa_core.db import get_conn

# -----------------------------
# Helpers: normalización números/moneda
# -----------------------------
MONEY_RE = re.compile(
    r"""
    (?P<curr>S\/\.|S\/|PEN|SOLES?|USD|\$)\s*
    (?P<num>(?:\d{1,3}(?:[.,]\d{3})+|\d+)(?:[.,]\d{1,2})?)
    """,
    re.IGNORECASE | re.VERBOSE
)

NUM_RE = re.compile(r"(?<!\d)(\d{1,5})(?!\d)")

CUOTAS_RE = re.compile(r"(?:(\d{1,2})\s*(?:cuotas?|meses?))", re.IGNORECASE)

# Fechas: 10 de mayo / 10/05 / 10-05 / el 10
MONTHS = {
    "enero":1,"ene":1,
    "febrero":2,"feb":2,
    "marzo":3,"mar":3,
    "abril":4,"abr":4,
    "mayo":5,"may":5,
    "junio":6,"jun":6,
    "julio":7,"jul":7,
    "agosto":8,"ago":8,
    "septiembre":9,"setiembre":9,"sep":9,"set":9,
    "octubre":10,"oct":10,
    "noviembre":11,"nov":11,
    "diciembre":12,"dic":12,
}

DATE_SLASH_RE = re.compile(r"(?<!\d)(\d{1,2})[\/\-](\d{1,2})(?:[\/\-](\d{2,4}))?(?!\d)")
DATE_TEXT_RE  = re.compile(r"(?<!\d)(\d{1,2})\s+de\s+([a-záéíóú]+)(?:\s+de\s+(\d{2,4}))?", re.IGNORECASE)

REL_RE = re.compile(r"\b(hoy|mañana|pasado\s+mañana)\b", re.IGNORECASE)

def parse_money(s: str):
    m = MONEY_RE.search(s or "")
    if not m:
        return None, None
    curr = (m.group("curr") or "").upper()
    num = m.group("num")
    # normalizar separadores: si hay ambos, asumir miles con ',' o '.' y decimal con el último
    n = num.replace(" ", "")
    if n.count(",") and n.count("."):
        # decimal = último separador
        if n.rfind(",") > n.rfind("."):
            n = n.replace(".", "").replace(",", ".")
        else:
            n = n.replace(",", "")
    else:
        # si solo coma: puede ser decimal o miles. si hay 1 coma y 2 dígitos después => decimal
        if n.count(",") == 1 and len(n.split(",")[1]) in (1,2):
            n = n.replace(",", ".")
        else:
            n = n.replace(",", "")
        # si solo punto y 3 dígitos después repetido => miles
        # ya queda ok si es decimal con 2 dígitos
    try:
        val = float(n)
    except:
        return None, None

    moneda = None
    if "USD" in curr or curr == "$":
        moneda = "USD"
    elif "PEN" in curr or "S/" in curr or "SOL" in curr:
        moneda = "PEN"
    else:
        moneda = curr[:8] if curr else None

    return round(val, 2), moneda

def parse_amount_and_currency(text: str):
    """
    Extrae monto y moneda de texto flexible.
    Detecta patrones como: "1246 soles", "150.", "S/ 1.500", "USD 200.00"
    Retorna: (float|None, str|None)
    """
    if not text:
        return None, None
    
    txt = text.lower()
    
    # Filtrar texto para quitar fechas obvias y otros patrones antes de buscar
    filtered_txt = txt
    # Ignorar: YYYY-MM-DD, DD/MM/YYYY, DD/MM, días de la semana
    filtered_txt = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b", " ", filtered_txt)
    filtered_txt = re.sub(r"\b\d{1,2}[/-]\d{1,2}(?:[/-](?:\d{2}|\d{4}))?\b", " ", filtered_txt)
    filtered_txt = re.sub(r"\b(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)\b", " ", filtered_txt)
    # Ignorar referencias a días del mes "el 5", "día 10"
    filtered_txt = re.sub(r"\b(?:el|d[ií]a)\s+\d{1,2}\b", " ", filtered_txt)
    filtered_txt = re.sub(r"\b\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", " ", filtered_txt)
    # Ignorar DNI y teléfonos largos (8+ dígitos sin separadores)
    filtered_txt = re.sub(r"\bdni\s+\d{8,}\b", " ", filtered_txt)
    filtered_txt = re.sub(r"\b\d{8,}\b", " ", filtered_txt)
    # Ignorar porcentajes
    filtered_txt = re.sub(r"\d+\s*%", " ", filtered_txt)
    
    # Detectar moneda por palabras clave en el texto filtrado
    moneda = None
    # Buscar en texto original (no filtrado) para no perder S/. con puntos
    # Patrón mejorado para S/, S/., soles, etc.
    if re.search(r"(?:\bsol(?:es)?\b|s\s*/\s*\.?|\bpen\b)", txt, re.IGNORECASE):
        moneda = "PEN"
    elif re.search(r"\b(?:d[oó]lar(?:es)?|usd)\b", txt, re.IGNORECASE):
        moneda = "USD"
    
    # Patrón mejorado para capturar números
    # Captura números de 1 a 7 dígitos con separadores opcionales de miles y decimales
    amount_pattern = r"""
        (?:S/\.?\s*|USD\s+|[$]\s*)?              # Prefijo moneda opcional
        (\d{1,3}(?:[\s.,]\d{3})*(?:[.,]\d{1,2})?|\d{1,7})  # Número: 1-3 dígitos iniciales + grupos de 3, o 1-7 dígitos
        \.?                                       # Punto final opcional "150."
        (?=\s|$|[^\d])                           # Seguido por espacio, fin, o no-dígito
    """
    
    # Buscar montos en el texto ORIGINAL (para capturar S/, USD prefijos correctamente)
    matches = list(re.finditer(amount_pattern, txt, re.IGNORECASE | re.VERBOSE))
    
    best_amount = None
    best_context_score = -1
    best_pos = -1  # Posición del mejor match (para preferir el último en empates)
    
    for m in matches:
        num_str = m.group(1)
        if not num_str or not num_str.strip():
            continue
        
        # Usar posiciones del grupo capturado (solo el número)
        match_start = m.start(1)
        match_end = m.end(1)
        match_context = txt[max(0, match_start - 15):min(len(txt), match_end + 15)]
        
        # Validar que el match no esté en contexto de fecha/DNI que debería filtrarse
        
        # Filtrar si está en fecha YYYY-MM-DD, DD/MM/YYYY, DD/MM
        if re.search(r"\d{4}[-/]\d{1,2}[-/]\d{1,2}", match_context):
            continue
        if re.search(r"\d{1,2}[/-]\d{1,2}(?:[/-](?:\d{2}|\d{4}))?", match_context):
            continue
        # Filtrar "el 5", "día 10"
        if re.search(r"\b(?:el|d[ií]a)\s+\d{1,2}\b", match_context):
            continue
        # Filtrar meses "5 de mayo"
        if re.search(r"\d{1,2}\s+de\s+(?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\b", match_context, re.IGNORECASE):
            continue
        # Filtrar DNI
        if re.search(r"\bdni\s+\d{8,}\b", match_context, re.IGNORECASE):
            continue
        # Filtrar teléfonos (8+ dígitos consecutivos)
        if re.search(r"\b\d{8,}\b", match_context):
            continue
        # Filtrar porcentajes
        if re.search(r"\d+\s*%", match_context):
            continue
        
        # Obtener contexto cercano (±25 caracteres) para detectar cuotas
        context_window_start = max(0, match_start - 25)
        context_window_end = min(len(txt), match_end + 25)
        context_window = txt[context_window_start:context_window_end]
        
        # Detectar si está asociado a "cuota(s)"
        if re.search(r"\bcuota[s]?\b", context_window):
            # Verificar si hay moneda explícita pegada al número
            # Prefijo: S/, USD pegado antes del número
            prefix_window = txt[max(0, match_start - 10):match_start]
            # Sufijo: soles, dólares, usd pegado después del número
            suffix_window = txt[match_end:min(len(txt), match_end + 15)]
            
            has_currency_prefix = re.search(r"s\s*/\s*\.?\s*$|usd\s+$", prefix_window, re.IGNORECASE)
            has_currency_suffix = re.search(r"^\s*(?:sol(?:es)?|d[oó]lar(?:es)?|usd|pen)\b", suffix_window, re.IGNORECASE)
            
            # Si NO hay moneda explícita cerca del número, descartar (es número de cuotas)
            if not (has_currency_prefix or has_currency_suffix):
                continue
        
        # Descartar números pequeños (<=24) sin moneda explícita (probablemente cuotas o días)
        try:
            temp_num = float(num_str.replace(" ", "").replace(",", "").replace(".", "").rstrip("."))
            if temp_num <= 24:
                # Verificar moneda pegada
                prefix_window = txt[max(0, match_start - 10):match_start]
                suffix_window = txt[match_end:min(len(txt), match_end + 15)]
                
                has_currency_prefix = re.search(r"s\s*/\s*\.?\s*$|usd\s+$", prefix_window, re.IGNORECASE)
                has_currency_suffix = re.search(r"^\s*(?:sol(?:es)?|d[oó]lar(?:es)?|usd|pen)\b", suffix_window, re.IGNORECASE)
                
                if not (has_currency_prefix or has_currency_suffix):
                    continue
        except (ValueError, OverflowError):
            pass
        
        # Obtener contexto alrededor del match (±40 caracteres) para scoring
        context_start = max(0, match_start - 40)
        context_end = min(len(txt), match_end + 40)
        context = txt[context_start:context_end]
        
        # Scoring del contexto para elegir el mejor match
        context_score = 0
        
        # Bonus si hay palabras clave de pago/deuda cerca
        if re.search(r"\b(?:pag[oaáó]|deud[a]|cancel[aáoó]|abon[o]|deposit[oó]|total|saldo|debe[sn]?|monto)\b", context):
            context_score += 10
        
        # Bonus si hay moneda cerca
        if re.search(r"\b(?:sol(?:es)?|s/\.?|pen|d[oó]lar(?:es)?|usd)\b", context):
            context_score += 5
        
        # Penalizar si está cerca de palabras temporales residuales
        if re.search(r"\b(?:mes(?:es)?|a[ñn]o[s]?|hora[s]?|minuto[s]?)\b", context):
            context_score -= 5
        
        # Ignorar si score es negativo
        if context_score < 0:
            continue
        
        # Normalizar el número
        normalized = num_str.replace(" ", "")
        
        # Determinar si usa coma o punto como decimal
        has_comma = "," in normalized
        has_dot = "." in normalized
        
        if has_comma and has_dot:
            # Ambos: determinar cuál es decimal (el último)
            last_comma_pos = normalized.rfind(",")
            last_dot_pos = normalized.rfind(".")
            if last_comma_pos > last_dot_pos:
                # Coma es decimal: "1.500,50"
                normalized = normalized.replace(".", "").replace(",", ".")
            else:
                # Punto es decimal: "1,500.50"
                normalized = normalized.replace(",", "")
        elif has_comma:
            # Solo coma: puede ser decimal o miles
            parts = normalized.split(",")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                # Decimal: "150,50"
                normalized = normalized.replace(",", ".")
            else:
                # Miles: "1,500" o "1,500,000"
                normalized = normalized.replace(",", "")
        elif has_dot:
            # Solo punto: puede ser decimal o miles
            parts = normalized.split(".")
            if len(parts) == 2 and len(parts[1]) in (1, 2):
                # Decimal: "150.50"
                pass  # ya está OK
            elif len(parts) == 2 and len(parts[1]) == 3:
                # Probablemente miles: "1.500"
                normalized = normalized.replace(".", "")
            else:
                # Múltiples puntos: miles "1.500.000"
                normalized = normalized.replace(".", "")
        
        # Remover punto final si existe "150."
        normalized = normalized.rstrip(".")
        
        try:
            amount = float(normalized)
            # Validar rango razonable para pagos (1 a 1 millón)
            if 1 <= amount <= 1000000:
                # Detectar si este match tiene moneda explícita pegada
                prefix_window = txt[max(0, match_start - 10):match_start]
                suffix_window = txt[match_end:min(len(txt), match_end + 15)]
                has_currency_prefix = re.search(r"s\s*/\s*\.?\s*$|usd\s+$", prefix_window, re.IGNORECASE)
                has_currency_suffix = re.search(r"^\s*(?:sol(?:es)?|d[oó]lar(?:es)?|usd|pen)\b", suffix_window, re.IGNORECASE)
                has_explicit_currency = bool(has_currency_prefix or has_currency_suffix)
                
                # Decidir si reemplazar el mejor candidato
                should_replace = False
                
                if context_score > best_context_score:
                    # Score claramente mejor
                    should_replace = True
                elif abs(context_score - best_context_score) <= 1 and not has_explicit_currency:
                    # Empate (exacto o suave) sin moneda explícita: preferir el más a la derecha
                    if match_start > best_pos:
                        should_replace = True
                
                if should_replace:
                    best_amount = round(amount, 2)
                    best_context_score = context_score
                    best_pos = match_start
        except (ValueError, OverflowError):
            continue
    
    # Si encontramos monto pero no moneda, intentar detectar moneda en el texto completo
    if best_amount is not None and moneda is None:
        # Buscar palabras clave de moneda de forma conservadora
        if re.search(r"\b(?:sol(?:es)?|pen)\b|s\s*/\s*\.?", txt, re.IGNORECASE):
            moneda = "PEN"
        elif re.search(r"\b(?:usd|d[oó]lar(?:es)?)\b", txt, re.IGNORECASE):
            moneda = "USD"
        # Si no encuentra nada, moneda queda None (no inferir)
    
    return best_amount, moneda

def infer_currency_from_text(text: str):
    """
    Intenta inferir la moneda de un texto buscando keywords conservadoras.
    Incluye: normalización, detección de typos, y heurísticas para señales de Perú.
    Retorna: "PEN", "USD", o None si no encuentra nada.
    """
    if not text:
        return None
    
    # Normalización: lowercase, colapsar espacios múltiples
    txt = text.lower()
    txt = re.sub(r"\s+", " ", txt)
    
    # Quitar tildes (opcional pero útil para typos)
    tildes_map = str.maketrans("áéíóúü", "aeiouu")
    txt_norm = txt.translate(tildes_map)
    
    # PRIORIDAD 1: Detectar USD (más específico, detectar primero)
    # Buscar: usd, dolar, dólar, dolares, dólares
    if re.search(r"\b(?:usd|d[oó]lar(?:es)?)", txt, re.IGNORECASE):
        return "USD"
    
    # PRIORIDAD 2: Keywords directas de PEN (incluye typos comunes)
    # sol, soles, pen, s/, s/., s /, soldes, soless
    pen_keywords = [
        r"\b(?:sol(?:es)?|pen)\b",  # sol, soles, pen
        r"s\s*/\s*\.?",              # s/, s/., s / (con espacios)
        r"\bsoldes\b",               # typo OCR: soldes
        r"\bsoless\b",               # typo: soless
    ]
    
    for pattern in pen_keywords:
        if re.search(pattern, txt_norm, re.IGNORECASE):
            return "PEN"
    
    # PRIORIDAD 3: Heurística conservadora "Perú cues"
    # Solo aplicar si NO encontramos USD ni keywords PEN directas
    # Señales: interbank, plaza vea, plazavea, tarjeta oh, financiera oh
    peru_cues = [
        r"\binterbank\b",
        r"\bplaza\s*vea\b",
        r"\bplazavea\b",
        r"\btarjeta\s+oh\b",
        r"\bfinanciera\s+oh\b",
    ]
    
    for pattern in peru_cues:
        if re.search(pattern, txt_norm, re.IGNORECASE):
            return "PEN"
    
    # Si no encuentra nada, retornar None (no inventar)
    return None

def parse_cuotas(s: str):
    m = CUOTAS_RE.search(s or "")
    if m:
        try:
            return int(m.group(1))
        except:
            return None
    return None

def _safe_year(y: int):
    if y < 100:
        return 2000 + y
    return y

def parse_fecha(s: str, base_date: date):
    txt = (s or "").strip()
    if not txt:
        return None, None

    m = DATE_SLASH_RE.search(txt)
    if m:
        d = int(m.group(1)); mo = int(m.group(2)); y = m.group(3)
        y = _safe_year(int(y)) if y else base_date.year
        try:
            return date(y, mo, d), m.group(0)
        except:
            pass

    m = DATE_TEXT_RE.search(txt)
    if m:
        d = int(m.group(1))
        mon = m.group(2).lower().strip()
        mon = mon.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u")
        mo = MONTHS.get(mon)
        y = m.group(3)
        y = _safe_year(int(y)) if y else base_date.year
        if mo:
            try:
                return date(y, mo, d), m.group(0)
            except:
                pass

    m = REL_RE.search(txt.lower())
    if m:
        key = m.group(1).lower()
        if key == "hoy":
            return base_date, m.group(0)
        if key == "mañana":
            return base_date + timedelta(days=1), m.group(0)
        if "pasado" in key:
            return base_date + timedelta(days=2), m.group(0)

    # "el 10" sin mes: tomar mes actual (heurístico)
    m = re.search(r"\bel\s+(\d{1,2})\b", txt.lower())
    if m:
        d = int(m.group(1))
        try:
            return date(base_date.year, base_date.month, d), m.group(0)
        except:
            pass

    return None, None

def is_promesa_text(s: str):
    s2 = (s or "").lower()
    # indica intención/compromiso
    prom = any(k in s2 for k in [
        "me comprometo", "compromiso de pago", "promesa de pago",
        "voy a pagar", "pago el", "pago mañana", "pago hoy",
        "lo cancelo", "cancelaré", "cancelar",
        "abono", "deposito", "depósito", "pagaré"
    ])
    # señales de formalización por envío de info (whatsapp, documento)
    formal = any(k in s2 for k in [
        "le envío", "te envío", "por whatsapp", "documentación", "documento",
        "carta de liquidación", "carta de no adeudo", "carta de liquidacion"
    ])
    return prom or formal

def estado_from_fields(monto, fecha, cuotas, txt: str):
    # estado simple (ajustable)
    if monto and fecha:
        return "COMPROMETIDA_CON_FECHA"
    if monto and (cuotas and cuotas > 1):
        return "COMPROMETIDA_EN_CUOTAS_SIN_FECHA"
    if monto:
        return "COMPROMETIDA_SIN_FECHA"
    # si no hay monto pero hay señales de promesa
    if is_promesa_text(txt):
        if fecha:
            return "PENDIENTE_MONTO_CON_FECHA"
        return "PENDIENTE_MONTO"
    return None

def ensure_table(conn):
    # ya existe, pero por las dudas
    cur = conn.cursor()
    cur.execute("SHOW TABLES LIKE 'sa_promesas_pago'")
    ok = cur.fetchone() is not None
    cur.close()
    if not ok:
        raise RuntimeError("No existe sa_promesas_pago")

def delete_existing_for_run(conn, ejecucion_id):
    cur = conn.cursor()
    cur.execute("""
      DELETE p FROM sa_promesas_pago p
      JOIN sa_conversaciones c ON c.conversacion_pk = p.conversacion_pk
      WHERE c.ejecucion_id = %s
    """, (ejecucion_id,))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.ini")
    ap.add_argument("--ejecucion_id", type=int, required=True)
    ap.add_argument("--limit_convs", type=int, default=0)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--dry_run", action="store_true")
    ap.add_argument("--base_date", default="2025-05-02")  # dataset SANDBOX
    ap.add_argument("--selftest", action="store_true", help="Run self-test for amount/currency extraction")
    ap.add_argument("--test_context", action="store_true", help="Run integration test for context-based amount detection")
    args = ap.parse_args()
    
    if args.selftest:
        print("[SELFTEST] Testing parse_amount_and_currency()")
        test_cases = [
            ("la deuda total asciende ya a 1246 soles", (1246.0, "PEN")),
            ("pago los 150.", (150.0, None)),
            ("S/ 1.500", (1500.0, "PEN")),
            ("USD 200.00", (200.0, "USD")),
            ("hasta el 5 de mayo", (None, None)),
            ("deuda de 1,234.50 dólares", (1234.5, "USD")),
            ("cancelaré S/. 2.500", (2500.0, "PEN")),
            ("DNI 12345678 fecha 05/03/2025", (None, None)),
            ("se le puede fraccionar en 2 cuotas", (None, None)),
            ("en 8 cuotas", (None, None)),
            ("S/ 2", (2.0, "PEN")),
            ("Estos 814, claro, 824, estimado", (824.0, None)),
            # Test de contexto (simula búsqueda en turnos vecinos)
            ("[t-1] pago 150 soles [t0] ¿puedo agendarlo?", (150.0, "PEN")),
            # Test de detección de moneda cuando monto existe
            ("pago los 150", (150.0, None)),
            ("pago los 150 soles", (150.0, "PEN")),
            ("pago los 150 USD", (150.0, "USD")),
        ]
        for test_input, expected in test_cases:
            result = parse_amount_and_currency(test_input)
            status = "✓" if result == expected else "✗"
            print(f"  {status} '{test_input[:50]}' => {result} (expected {expected})")
        
        # Test adicional para infer_currency_from_text
        print("\n[SELFTEST] Testing infer_currency_from_text()")
        currency_tests = [
            ("pago 150", None),
            ("[t-1] son 200 soles [t0] lo pagaré", "PEN"),
            ("[t-2] deuda de 300 USD", "USD"),
            ("conversación sin moneda", None),
            # Nuevos tests: typos y heurística Perú
            ("pago 150 soldes", "PEN"),  # typo OCR
            ("agente interbank llama por deuda de 150", "PEN"),  # heurística Perú
            ("pago 150 usd", "USD"),  # USD minúsculas
            ("deuda en Plaza Vea por 200", "PEN"),  # Plaza Vea -> Perú cue
            ("pago 300 dólares", "USD"),  # dólares con tilde
            ("tarjeta oh ... abonar 150", "PEN"),  # Tarjeta OH -> Perú cue
        ]
        for test_input, expected in currency_tests:
            result = infer_currency_from_text(test_input)
            status = "✓" if result == expected else "✗"
            print(f"  {status} '{test_input[:40]}' => {result} (expected {expected})")
        
        print("\n[SELFTEST] Complete\n")
        print("NOTA: El sistema también busca montos en turnos vecinos (±2 turnos)")
        print("      cuando el turno de la promesa no contiene números.")
        print("      Y busca moneda en el mismo contexto si monto existe pero moneda=None.\n")
        return
    
    if args.test_context:
        print("[TEST_CONTEXT] Testing context-based amount detection")
        # Simular conversación con turnos
        base_date_test = datetime.strptime("2025-05-02", "%Y-%m-%d").date()
        
        # Simular turnos donde t0 tiene promesa pero no monto, t-1 tiene monto
        turns_sim = [
            {"turno_idx": 1, "text": "Buenos días, le llamo por su deuda pendiente", "speaker": "AGENTE", "fase": None, "turno_pk": 1},
            {"turno_idx": 2, "text": "Sí, son 150 soles que debo", "speaker": "CLIENTE", "fase": None, "turno_pk": 2},
            {"turno_idx": 3, "text": "¿Cuándo puede pagarlo?", "speaker": "AGENTE", "fase": None, "turno_pk": 3},
            {"turno_idx": 4, "text": "Te puedo agendar para cancelarlo mañana", "speaker": "CLIENTE", "fase": "OFERTA_PAGO", "turno_pk": 4},
            {"turno_idx": 5, "text": "Perfecto, queda agendado", "speaker": "AGENTE", "fase": None, "turno_pk": 5},
        ]
        
        # Simular flush_conv
        candidates = []
        for row in turns_sim:
            txt = row["text"] or ""
            if row.get("fase") == "OFERTA_PAGO":
                candidates.append(row)
            elif is_promesa_text(txt):
                candidates.append(row)
        
        print(f"  Candidatos encontrados: {len(candidates)}")
        
        for row in candidates:
            txt = row["text"] or ""
            monto, moneda = parse_money(txt)
            if monto is None:
                monto, moneda = parse_amount_and_currency(txt)
            
            print(f"  - turno_idx={row['turno_idx']}: '{txt[:50]}' => monto={monto}")
            
            # Si no hay monto, buscar en contexto
            if monto is None:
                turno_idx_actual = row["turno_idx"]
                turns_by_idx = {t["turno_idx"]: t for t in turns_sim}
                
                context_parts = []
                for offset in [-2, -1, 0, 1, 2]:
                    idx = turno_idx_actual + offset
                    if idx in turns_by_idx:
                        t = turns_by_idx[idx]
                        txt_part = (t.get("text") or "").strip()
                        if txt_part:
                            label = f"[t{offset:+d}]" if offset != 0 else "[t0]"
                            context_parts.append(f"{label} {txt_part}")
                
                context_text = " ".join(context_parts)
                print(f"    Contexto: '{context_text[:100]}...'")
                
                context_monto, context_moneda = parse_amount_and_currency(context_text)
                print(f"    Monto en contexto: {context_monto} {context_moneda}")
                
                if context_monto is not None:
                    print(f"    ✓ ÉXITO: Detectado {context_monto} {context_moneda} desde contexto")
                else:
                    print(f"    ✗ No se detectó monto en contexto")
        
        print("\n[TEST_CONTEXT] Complete\n")
        return

    base_date = datetime.strptime(args.base_date, "%Y-%m-%d").date()

    cfg = load_config(args.config)
    conn = get_conn(cfg)
    ensure_table(conn)

    cur = conn.cursor(dictionary=True)

    q = """
    SELECT c.conversacion_pk, c.conversacion_id, t.turno_pk, t.turno_idx, t.speaker, t.text, t.fase, t.fase_source
    FROM sa_conversaciones c
    JOIN sa_turnos t ON t.conversacion_pk = c.conversacion_pk
    WHERE c.ejecucion_id = %s
    ORDER BY c.conversacion_pk, t.turno_idx
    """
    params = [args.ejecucion_id]
    if args.limit_convs > 0:
        # limitar conversacion_pk con subquery
        q = """
        SELECT c.conversacion_pk, c.conversacion_id, t.turno_pk, t.turno_idx, t.speaker, t.text, t.fase, t.fase_source
        FROM (
            SELECT conversacion_pk, conversacion_id
            FROM sa_conversaciones
            WHERE ejecucion_id=%s
            ORDER BY conversacion_pk
            LIMIT %s
        ) c
        JOIN sa_turnos t ON t.conversacion_pk = c.conversacion_pk
        ORDER BY c.conversacion_pk, t.turno_idx
        """
        params = [args.ejecucion_id, args.limit_convs]

    cur.execute(q, tuple(params))

    # agrupar por conversación, recolectar candidatos
    promesas = []
    last_conv = None
    turns_buf = []

    def flush_conv(conv_pk, conv_id, turns):
        if not turns:
            return
        # buscar en fases clave primero
        candidates = []
        for row in turns:
            txt = row["text"] or ""
            if not txt.strip():
                continue
            if row.get("fase") in ("OFERTA_PAGO", "FORMALIZACION_PAGO", "NEGOCIACION_ACUERDO", "CONSULTA_ACEPTACION"):
                candidates.append(row)
            elif is_promesa_text(txt):
                candidates.append(row)

        if not candidates:
            return

        # elegir el mejor candidato con scoring
        best = None
        best_score = -1

        for row in candidates:
            txt = row["text"] or ""
            monto, moneda = parse_money(txt)
            
            # Intentar extracción alternativa si parse_money no encontró nada
            if monto is None:
                monto, moneda = parse_amount_and_currency(txt)
            
            cuotas = parse_cuotas(txt)
            fecha, fecha_txt = parse_fecha(txt, base_date)
            st = estado_from_fields(monto, fecha, cuotas, txt)
            if not st:
                continue

            score = 0
            if monto: score += 5
            if fecha: score += 4
            if cuotas: score += 2
            if row.get("fase") == "FORMALIZACION_PAGO": score += 2
            if row.get("fase") == "NEGOCIACION_ACUERDO": score += 2
            if "promesa" in (txt.lower()): score += 2
            if "comprom" in (txt.lower()): score += 1

            if score > best_score:
                best_score = score
                best = (row, monto, moneda, cuotas, fecha, fecha_txt, st, score)

        if not best:
            return

        row, monto, moneda, cuotas, fecha, fecha_txt, st, score = best

        # Si no hay monto (PENDIENTE_MONTO*), buscar en contexto de turnos vecinos
        if monto is None and st in ("PENDIENTE_MONTO", "PENDIENTE_MONTO_CON_FECHA"):
            turno_idx_actual = row["turno_idx"]
            
            # Construir índice de turnos por turno_idx para acceso rápido
            turns_by_idx = {t["turno_idx"]: t for t in turns}
            
            # Recolectar hasta 2 turnos anteriores y 2 posteriores
            context_parts = []
            for offset in [-2, -1, 0, 1, 2]:
                idx = turno_idx_actual + offset
                if idx in turns_by_idx:
                    t = turns_by_idx[idx]
                    txt_part = (t.get("text") or "").strip()
                    if txt_part:
                        # Etiquetar con posición relativa
                        label = f"[t{offset:+d}]" if offset != 0 else "[t0]"
                        context_parts.append(f"{label} {txt_part}")
            
            # Concatenar contexto
            context_text = " ".join(context_parts)
            
            # Intentar extraer monto del contexto
            context_monto, context_moneda = parse_amount_and_currency(context_text)
            
            # Si encontramos monto en contexto, actualizar
            if context_monto is not None:
                monto = context_monto
                # Preservar moneda si ya existía (por palabras clave globales)
                if moneda is None:
                    moneda = context_moneda
                
                # Actualizar estado según nuevos campos
                st = estado_from_fields(monto, fecha, cuotas, row["text"])
        
        # Si hay monto pero no moneda, intentar inferir moneda del contexto de turnos
        if monto is not None and moneda is None:
            turno_idx_actual = row["turno_idx"]
            
            # Construir índice de turnos si no existe (puede ya existir del bloque anterior)
            if 'turns_by_idx' not in locals():
                turns_by_idx = {t["turno_idx"]: t for t in turns}
            
            # Recolectar contexto si no existe (puede ya existir del bloque anterior)
            if 'context_text' not in locals():
                context_parts = []
                for offset in [-2, -1, 0, 1, 2]:
                    idx = turno_idx_actual + offset
                    if idx in turns_by_idx:
                        t = turns_by_idx[idx]
                        txt_part = (t.get("text") or "").strip()
                        if txt_part:
                            label = f"[t{offset:+d}]" if offset != 0 else "[t0]"
                            context_parts.append(f"{label} {txt_part}")
                context_text = " ".join(context_parts)
            
            # Intentar inferir moneda del contexto
            inferred_currency = infer_currency_from_text(context_text)
            if inferred_currency is not None:
                moneda = inferred_currency

        # confidence heurística
        conf = 0.40
        if monto: conf += 0.20
        if fecha: conf += 0.20
        if cuotas: conf += 0.10
        if row.get("fase") in ("FORMALIZACION_PAGO", "NEGOCIACION_ACUERDO"): conf += 0.05
        conf = min(conf, 0.95)

        promesas.append({
            "conversacion_pk": conv_pk,
            "turno_pk": row["turno_pk"],
            "turno_idx": row["turno_idx"],
            "monto": monto,
            "moneda": moneda,
            "numero_cuotas": cuotas,
            "fecha_pago": fecha,
            "fecha_pago_texto": fecha_txt,
            "estado_promesa": st,
            "confidence": round(conf, 4),
            "source": "RULES",
            "evidence_text": (row["text"] or "")[:500],
            "conversacion_id": conv_id,
        })

    for r in cur:
        conv_pk = r["conversacion_pk"]
        conv_id = r["conversacion_id"]
        if last_conv is None:
            last_conv = conv_pk
        if conv_pk != last_conv:
            # flush
            flush_conv(last_conv, last_conv_id, turns_buf)
            turns_buf = []
            last_conv = conv_pk
        last_conv_id = conv_id
        turns_buf.append(r)

    # último
    if last_conv is not None:
        flush_conv(last_conv, last_conv_id, turns_buf)

    cur.close()

    if args.dry_run and args.write:
        raise RuntimeError("No uses --dry_run y --write juntos")

    if args.write:
        deleted = delete_existing_for_run(conn, args.ejecucion_id)
        print(f"[CLEAN] deleted_existing_for_run={deleted}")

        curw = conn.cursor()
        ins = """
        INSERT INTO sa_promesas_pago
        (conversacion_pk, turno_pk, turno_idx, monto, moneda, numero_cuotas, fecha_pago, fecha_pago_texto,
         estado_promesa, confidence, source, evidence_text)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """
        for p in promesas:
            curw.execute(ins, (
                p["conversacion_pk"], p["turno_pk"], p["turno_idx"],
                p["monto"], p["moneda"], p["numero_cuotas"], p["fecha_pago"], p["fecha_pago_texto"],
                p["estado_promesa"], p["confidence"], p["source"], p["evidence_text"]
            ))
        conn.commit()
        curw.close()

    # reporte
    total = len(promesas)
    print(f"[OK] ejecucion_id={args.ejecucion_id} promesas_detectadas={total}")
    by_estado = {}
    for p in promesas:
        by_estado[p["estado_promesa"]] = by_estado.get(p["estado_promesa"], 0) + 1
    print("by_estado:")
    for k in sorted(by_estado, key=lambda x: (-by_estado[x], x)):
        print(f"  {by_estado[k]:4d}  {k}")

    # mostrar 10 ejemplos
    print("\nMUESTRA 10:")
    for p in promesas[:10]:
        print(f"- conv_pk={p['conversacion_pk']} turno_idx={p['turno_idx']} estado={p['estado_promesa']} monto={p['monto']} {p['moneda']} cuotas={p['numero_cuotas']} fecha={p['fecha_pago']} ev='{p['evidence_text'][:120]}'")

    conn.close()

if __name__ == "__main__":
    main()
