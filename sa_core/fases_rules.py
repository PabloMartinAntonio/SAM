# sa_core/fases_rules.py
import re
import unicodedata
from collections import defaultdict

# -----------------------
# Normalización
# -----------------------
def normalize_text(s: str) -> str:
    """
    lower + remover tildes (diacríticos) + colapsar espacios.
    Importante: NO elimina símbolos como '/', '.', 'S/'.
    """
    if not s:
        return ""
    s = s.lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    # Eliminar símbolos comunes que pueden distorsionar tokens (mantener letras y números)
    s = re.sub(r"[\./:;,_-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# -----------------------
# Reglas por fase (Perú)
# -----------------------
FASE_SEQUENCE = [
    "APERTURA",
    "IDENTIFICACION",
    "INFORMACION_DEUDA",
    "NEGOCIACION",
    "CONSULTA_ACEPTACION",
    "FORMALIZACION_PAGO",
    "ADVERTENCIAS",
    "CIERRE",
]

FASE_RULES = {
    "APERTURA": {
        re.compile(r"\b(al[oó]|hola|buenos dias|buenas tardes|buenas noches)\b", re.I): 4,  # saludo fuerte
        re.compile(r"\balo\b|muy buenos dias|buen dia|buenas|estimado|senor|senorita|que tal|¿que tal\??|como esta|disculpe|disculpe la molestia|perm[ií]tame|un momentito|¿me escucha\??|le saluda la senorita|le saluda el senor|central de cobranzas|area de recuperos|gestion de cobranza|una consultita", re.I): 2,
        re.compile(r"le saluda|mi nombre es|habla|se comunica|me comunico|me comunico con|le llamo|lo contacto|llamo de|por encargo|cobranzas|area de cobran", re.I): 4,
        re.compile(r"\bdigame\b", re.I): 2,  # controlado por heurística contextual
    },
    "IDENTIFICACION": {
        re.compile(r"con quien tengo el gusto|hablo con|me confirma|me valida|verificar datos|es usted|titular|apoderado|se encuentra|puede atender|me regala su|me brinda su|me indica su|me confirma su nombre|titular de la linea|don|dona|¿me indica su dni\??|¿me brinda su documento\??|¿me confirma sus datos\??|¿usted es|¿se encuentra|verificacion de identidad|validacion de seguridad|¿me confirma su fecha de nacimiento\??|¿me confirma su direccion\??", re.I): 4,
        re.compile(r"\bdni\b|documento de identidad|numero de documento|\bce\b|carnet de extranjeria|fecha de nacimiento|direccion|correo|ruc", re.I): 5,
        re.compile(r"de parte de quien|quien habla|con quien hablo|de donde llama|de que empresa|de que entidad|de que area", re.I): 4,
    },
    "INFORMACION_DEUDA": {
        re.compile(r"deuda|saldo|saldo pendiente|monto pendiente|importe|adeuda|vencid|mora|cuota vencida|interes|moratorio|penalidad|cartera castig|monto total|importe total|saldo total|deuda asciende|a la fecha|tiene pendiente|presenta atraso|cuotas vencidas|monto adeudado|deuda registrada|obligacion|gastos de cobranza|intereses|mora|vencimiento|regularice su deuda", re.I): 5,
        re.compile(r"tarjeta|credito|prestamo|linea|financiera|banco|cuenta|contrato|operacion|tarjeta oh|financiera oh|plaza vea|ripley|falabella", re.I): 3,
        re.compile(r"\bs\d{2,}\b|\bs\s+\d{2,}\b|sol|soles|nuevo sol|lucas|mango|palo|palos", re.I): 2,
    },
    "NEGOCIACION": {
        re.compile(r"podemos|le puedo ofrecer|oferta|beneficio|descuento|campana|convenio|acuerdo|fraccion|cuotas|cronograma|reprogram|refinanc|pago unico|liquidacion|liquidar|rebaja|rebajita|condonacion|quita|fraccionamiento|podemos llegar a un acuerdo|alternativas de pago|facilidades|fraccionamiento|reprogramacion|refinanciacion|convenio|descuento por pronto pago|pagar una parte|abonar algo|¿cuanto podria pagar hoy\??|¿con cuanto cuenta\??|¿que monto se le haria posible\??|sin chamba|sin trabajo|estoy misio|no tengo saldo|no cuento con dinero|ahorita|en un ratito|mas tarde|estoy corto|estoy ajustado|no dispongo|no cuento con", re.I): 5,
        re.compile(r"cuanto podria abonar|cuanto podria pagar|con cuanto cuenta|monto minimo|cuota minima|abono inicial|pago parcial", re.I): 5,
        re.compile(r"\bs\d{2,}\b|\bs\s+\d{2,}\b", re.I): 1,  # baja, para no disparar falsos positivos
        re.compile(r"ahorita|en un ratito|mas tarde|no tengo|no hay plata|sin trabajo|estoy misio|no me alcanza|pucha|ya pe|pues|\bpe\b|chamba|me quede sin chamba|estoy corto|estoy ajustado|no dispongo|no cuento con", re.I): 2,
        re.compile(r"\b(no puedo|no cuento|no tengo|no dispongo|ahorita no|por ahora no|en este momento no|sin trabajo|desemplead(o|a)|no me alcanza|no alcanza|no tengo dinero|no tengo efectivo|no tengo saldo|estoy misio|m[aá]s adelante|otro d[ií]a|despu[eé]s|cuando cobre|cuando tenga)\b", re.I): 4,
        re.compile(r"\b(cuotas?|en\s+cuotas|a\s+cuotas|mes(es)?|\d+\s+mes(es)?|plazo|fraccion(ar|ado)|financi(ar|ado))\b", re.I): 4,
        re.compile(r"\b(voy a buscar|lo voy a buscar|ya lo busco|lo veo|yo lo veo|te digo|le digo|te aviso|le aviso|voy a ver|lo reviso|en efectivo)\b", re.I): 4,
        re.compile(r"puedo hacer el pago|donde puedo pagar|en donde puedo pagar|puedo pagar en|pagar en", re.I): 4,
        # NOTA: números NO suman solos (evita ruido). Se suma condicionalmente abajo.
    },
    "CONSULTA_ACEPTACION": {
        re.compile(r"\b(le parece|le parece bien|est[aá] de acuerdo|de acuerdo|conforme|acept(o|a)|confirm(o|a)|confirmamos|me confirma|me confirmas|queda conforme|queda de acuerdo|correcto|perfecto)\b", re.I): 5,
        re.compile(r"\b(ok|okay|okey|listo|dale)\b", re.I): 2,
        re.compile(r"\bya(,)?\s*(se[nñ]orita)?\b|\ba ver\b", re.I): 2,
        # 'sí' solo si viene con contexto fuerte (evita disparar por un "sí" cualquiera)
        re.compile(r"\b(s[ií])\b.*\b(de acuerdo|correcto|conforme|acept(o|a)|confirm(o|a)|perfecto)\b", re.I): 4,
    },
    "FORMALIZACION_PAGO": {
        re.compile(r"queda registrado|queda agendado|se agenda|promesa de pago|compromiso|se compromete|fecha de pago|dia de pago|queda pactado|queda confirmado|le envio el numero de cuenta|le envio el cci|le mando por whatsapp|le llega el link|codigo de operacion|numero de operacion|nro de operacion|voucher|constancia|captura|pantallazo|yape|plin|transferencia|deposito|agente|banca movil|banca por internet|bcp|interbank|bbva|scotiabank", re.I): 5,
        re.compile(r"tome nota|anote|anota|apunte|le doy el numero|le dejo el numero|por whatsapp|\bwhatsapp\b", re.I): 5,
        re.compile(r"tarjeta en fisico|tarjeta fisica|realizar la cancelacion|cancelacion", re.I): 4,
        re.compile(r"hoy|manana|pasado|quincena|fin de mes|\b\d{1,2}\s+de\s+\w+\b", re.I): 4,
        re.compile(r"\b\d{1,2}\s+\d{1,2}\b", re.I): 3,  # fechas normalizadas tipo 01 02
        re.compile(r"\b(en\s+)?\d+\s+d[ií]as?(?:\s+h[aá]biles)?\b", re.I): 4,
        re.compile(r"\b(en\s+)?\d+\s+horas?\b|\b(48|72)\s+horas?\b", re.I): 3,
    },
    "ADVERTENCIAS": {
        re.compile(r"pasa a pre-legal|pasa a legal|area legal|acciones legales|proceso legal|proceso judicial|demanda|embargo|medida cautelar|notificacion|carta notarial|cobranza judicial|se derivara a legal|central de riesgo|reporte a infocorp|bloqueo|juicio|historial crediticio|calificacion negativa|sbs", re.I): 6,
        re.compile(r"infocorp|centrales de riesgo|sbs|reporte negativo|calificacion|historial crediticio", re.I): 6,
        re.compile(r"si no paga|de lo contrario|caso contrario|procederemos|se derivara|se reportara", re.I): 4,
    },
    "CIERRE": {
        re.compile(r"gracias por su tiempo|muchas gracias|gracias|que tenga buen dia|que este bien|hasta luego|nos comunicamos|quedamos atentos|chau|buenas tardes|listo gracias|que le vaya bien", re.I): 2,
        re.compile(r"hasta luego|que tenga buen dia|que este bien|nos comunicamos|quedamos atentos|chau|buenas tardes|listo gracias|que le vaya bien", re.I): 4,
    },
}

NUM_RE = re.compile(r"\d{2,}|\d+[.,]\d+")
PAY_WORDS_RE = re.compile(r"pagar|abonar|pago|cuota|sol|soles|nuevo sol|lucas|mango|palo|palos", re.I)
DIGITS_CHUNK_RE = re.compile(r"^(?:\d[\s\-.]*){3,}$")
REPITO_RE = re.compile(r"\b(como le repito|se lo repito|le repito)\b", re.I)
WHEN_BRINDO_RE = re.compile(r"\b(cuando le brind[oa]?\b|cuando le brinde)\b", re.I)


def _phase_index(phase: str) -> int:
    try:
        return FASE_SEQUENCE.index(phase)
    except ValueError:
        return -1


def detect_fase_rules_based(text: str, turn_idx: int, total_turns: int, last_phase: str | None = None, is_last_turns: bool = False):
    """
    Returns: (fase_or_None, confidence_float_0_1, max_score_int)
    """
    t = normalize_text(text)
    scores = {fase: 0 for fase in FASE_SEQUENCE}

    # Scores base
    for fase, rules in FASE_RULES.items():
        for pattern, weight in rules.items():
            if pattern.search(t):
                scores[fase] += weight


    # --- Heurísticas contextuales adicionales y ajustes de pesos ---
    # 1) "Dígame." temprano solo si venimos de apertura
    if last_phase == "APERTURA" and turn_idx <= 5 and len(t) <= 25 and re.fullmatch(r"digame[.!]?", t):
        scores["APERTURA"] += 3

    # 2) "Sí" temprano como confirmación inicial (ahora suma a APERTURA y +4)
    if last_phase == "APERTURA" and turn_idx <= 5 and len(t) <= 20 and re.fullmatch(r"(si|si senorita|si señorita)[.!]?", t):
        scores["APERTURA"] += 4

    # 3) Ack "Ya" ultra corto (limitado por contexto, +4)
    if len(t) <= 5 and re.fullmatch(r"ya[.!]?", t) and last_phase in ("INFORMACION_DEUDA","NEGOCIACION","CONSULTA_ACEPTACION"):
        scores["CONSULTA_ACEPTACION"] += 4

    # 4) NEGOCIACION contextual extendida (+4, len>=20, context ampliado)
    context_neg_words = re.compile(r"\b(mi esposo|mi hijo|mis hijos|familiar|familia|gastos|trabaj|desemplead|no tengo|no puedo|ingreso|morosidad|coordinar|comunicar|no se ha podido|no han podido|unos dias|deme unos dias|minimo|mínimo|catalogo|catálogo|ventas|vendo|no vende|no se vende|no pide|no hay)\b", re.I)
    if last_phase in ("INFORMACION_DEUDA","NEGOCIACION","CONSULTA_ACEPTACION") and len(t) >= 20 and re.search(context_neg_words, t):
        scores["NEGOCIACION"] += 4

    # 5) Tiempo/antigüedad como parte de NEGOCIACION (años/meses) +4
    if last_phase in ("NEGOCIACION","CONSULTA_ACEPTACION") and re.search(r"\b\d+\s*(anos?|a[nñ]os?|mes(es)?)\b", t):
        scores["NEGOCIACION"] += 4

    # 5b) "buen tiempo" sin números
    if last_phase in ("NEGOCIACION","CONSULTA_ACEPTACION") and re.search(r"\b(buen tiempo|hace tiempo|ya tengo)\b", t):
        scores["NEGOCIACION"] += 4

    # 6) Montos en negociación aunque el score base de NEGOCIACION sea 0, pero SOLO con contexto
    if last_phase == "NEGOCIACION" and NUM_RE.search(t) and PAY_WORDS_RE.search(t):
        scores["NEGOCIACION"] += 3

    # 7) Turnos de dígitos con prefijo opcional "ya" dentro de formalización (+5)
    only_digits = (re.fullmatch(r"(ya[.,]?\s*)?[0-9\s\.,-]+", t) is not None) and (NUM_RE.search(t) is not None)
    if last_phase == "FORMALIZACION_PAGO" and only_digits and len(t) <= 30:
        scores["FORMALIZACION_PAGO"] += 5

    # 8) CIERRE por "gracias" muy al final
    if ("gracias" in t) and (turn_idx >= max(1, total_turns-2)):
        scores["CIERRE"] += 5

    # 9) "tarjeta" como aclaración en negociación
    if last_phase in ("NEGOCIACION","CONSULTA_ACEPTACION") and re.search(r"\btarjeta\b", t):
        scores["NEGOCIACION"] += 4

    # 10) "devolver la llamada / horario" (follow-up) - sin acentos porque normalize_text los elimina
    if last_phase in ("NEGOCIACION","FORMALIZACION_PAGO") and re.search(r"devolver la llamada|horario|a que hora|me podria llamar|podria llamar|manana", t):
        scores["NEGOCIACION"] += 4

    # 10b) Re-contacto/coordinar con condición doble (+6)
    if last_phase in ("NEGOCIACION", "FORMALIZACION_PAGO"):
        contact_match = re.search(r"\b(me podria llamar|podria llamar|me puede llamar|lo llamo|le llamo)\b", t)
        timing_match = re.search(r"\b(manana|horario|coordino|coordinar)\b", t)
        if contact_match and timing_match:
            scores["NEGOCIACION"] += 6

    # 10c) "con quien tengo el gusto" dentro de negociación/formalización (+4)
    if last_phase in ("NEGOCIACION", "FORMALIZACION_PAGO") and re.search(r"con quien tengo el gusto", t):
        scores["NEGOCIACION"] += 4

    # 11) "100 y tanto" como monto de deuda (solo si venimos de INFORMACION_DEUDA)
    if last_phase == "INFORMACION_DEUDA" and NUM_RE.search(t) and re.search(r"\b(deuda|saldo|monto|soles?|s/|tanto)\b", t):
        scores["INFORMACION_DEUDA"] += 4

    # 12) Chunks de dígitos en formalización (ej: "9 3 1.", "5 8 6.")
    if last_phase == "FORMALIZACION_PAGO" and DIGITS_CHUNK_RE.search(t):
        scores["FORMALIZACION_PAGO"] += 4

    # 13) "Le repito" como refuerzo de información de deuda
    if last_phase == "INFORMACION_DEUDA" and REPITO_RE.search(t):
        scores["INFORMACION_DEUDA"] += 3

    # 14) "Cuando le brindo" (turno truncado en negociación)
    if last_phase == "NEGOCIACION" and WHEN_BRINDO_RE.search(t):
        scores["NEGOCIACION"] += 3

    # 15) Secuencia de dígitos sueltos hereda formalización (+5)
    single_digits_seq_re = re.compile(r"(?:\b\d\b[\s\.\-]*){3,}")
    if last_phase == "FORMALIZACION_PAGO" and single_digits_seq_re.search(t):
        scores["FORMALIZACION_PAGO"] += 5

    # 16) "como le repito / le repito" refuerza información de deuda (+4)
    if last_phase == "INFORMACION_DEUDA" and re.search(r"\b(como le repito|le repito)\b", t, re.I):
        scores["INFORMACION_DEUDA"] += 4

    # 17) Truncado "Ok. Cuando le brindo ..." empuja negociación (+4)
    if last_phase == "NEGOCIACION" and re.search(r"\bok\b", t) and re.search(r"\bcuando le brind", t):
        scores["NEGOCIACION"] += 4

    # Heurística: Saludo/atención solo al inicio (mantener)
    if turn_idx <= 3 and len(t) <= 20:
        if re.search(r"\b(al[oó]|buenos dias|buenas tardes|buenas noches|digame)\b", t, re.I):
            scores["APERTURA"] += 3



    # NEGOCIACION: números + palabras de pago (condicional)
    if scores["NEGOCIACION"] > 0:
        if NUM_RE.search(t) and PAY_WORDS_RE.search(t):
            scores["NEGOCIACION"] += 2

    # CIERRE: bonus solo si ya matcheó algo de cierre y estamos al final
    if is_last_turns and scores["CIERRE"] > 0:
        scores["CIERRE"] += 1  # boost moderado

    # --- BLOQUE DE RETORNO Y CÁLCULO ---
    max_score = max(scores.values())
    CONTINUITY_PHASES = {"INFORMACION_DEUDA","NEGOCIACION","CONSULTA_ACEPTACION","FORMALIZACION_PAGO","CIERRE"}
    if max_score < 2:
        # fallback de continuidad para respuestas cortas
        if last_phase in CONTINUITY_PHASES:
            corto = (len(t) <= 45) or (len(t.split()) <= 7)
            if corto:
                return last_phase, min(1.0, 4/7.0), 4
        return None, 0.0, None

    # Elegir mejor fase con desempate por secuencia
    best = None
    best_score = -1
    for fase in FASE_SEQUENCE:
        sc = scores[fase]
        if sc > best_score:
            best_score = sc
            best = fase

    # Penalización leve por retroceso fuerte
    if last_phase and best:
        li = _phase_index(last_phase)
        bi = _phase_index(best)
        if li >= 0 and bi >= 0 and bi + 2 < li:  # retroceso >=3 fases
            best_score = max(0, best_score - 2)
            if best_score < 2:
                corto = (len(t) <= 45) or (len(t.split()) <= 7)
                if last_phase and (last_phase in CONTINUITY_PHASES) and corto:
                    # 2nd-chance continuity fallback
                    return last_phase, min(1.0, 4/7.0), 4
                return None, 0.0, None

    conf = min(1.0, best_score / 7.0)
    return best, conf, best_score


def ensure_schema_fases(conn):
    """
    Agrega columnas en sa_conversaciones si faltan.
    """
    cur = conn.cursor()
    cur.execute("SELECT DATABASE()")
    db = cur.fetchone()[0]

    cur.execute("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='sa_conversaciones'
    """, (db,))
    existing = {r[0] for r in cur.fetchall()}

    alters = []
    if "fase_final" not in existing:
        alters.append("ADD COLUMN fase_final VARCHAR(32) NULL")
    if "fase_final_turn_idx" not in existing:
        alters.append("ADD COLUMN fase_final_turn_idx INT NULL")
    if "tipo_finalizacion" not in existing:
        alters.append("ADD COLUMN tipo_finalizacion VARCHAR(32) NULL")
    if "llm_usado" not in existing:
        alters.append("ADD COLUMN llm_usado TINYINT NOT NULL DEFAULT 0")

    if alters:
        sql = "ALTER TABLE sa_conversaciones " + ", ".join(alters)
        cur.execute(sql)
        conn.commit()

    cur.close()


def apply_fase_rules_for_run(conn, ejecucion_id: int, limit: int = 0, conf_threshold: float = 0.55, verbose: bool = False):
    """
    Aplica rules-only a sa_turnos para una ejecución.
    Actualiza sa_turnos (fase, fase_conf, fase_source) y sa_conversaciones (fase_final, ...).
    """
    ensure_schema_fases(conn)

    cur = conn.cursor()
    params = [ejecucion_id]
    sql_conv = "SELECT conversacion_pk, conversacion_id FROM sa_conversaciones WHERE ejecucion_id=%s ORDER BY conversacion_pk"
    if limit and limit > 0:
        sql_conv += " LIMIT %s"
        params.append(limit)

    cur.execute(sql_conv, tuple(params))
    convs = cur.fetchall()

    counts = defaultdict(int)
    # Precargar las fases legacy para que aparezcan en orden en el print
    for f in FASE_SEQUENCE:
        counts[f] = 0
    
    null_count = 0
    total_turns_updated = 0

    skip_deepseek_total = 0
    for i, (conv_pk, conv_id) in enumerate(convs, start=1):
        cur2 = conn.cursor()
        cur2.execute(
            "SELECT turno_pk, turno_idx, text, fase, fase_conf, fase_source FROM sa_turnos WHERE conversacion_pk=%s ORDER BY turno_idx ASC",
            (conv_pk,),
        )
        turns = cur2.fetchall()
        cur2.close()

        if not turns:
            # conversación sin turnos
            cur.execute(
                "UPDATE sa_conversaciones SET fase_final=NULL, fase_final_turn_idx=NULL, tipo_finalizacion='CORTE' WHERE conversacion_pk=%s",
                (conv_pk,),
            )
            continue

        total = len(turns)
        last_phase = None
        last_non_null_phase = None
        last_non_null_idx = None

        for (turno_pk, turno_idx, text, fase_actual, fase_conf_actual, fase_source_actual) in turns:
            is_last = (total - int(turno_idx)) < 3
            # Si ya fue clasificado por DEEPSEEK con fase no vacía, no tocar
            if (fase_source_actual == "DEEPSEEK") and (fase_actual is not None) and (str(fase_actual).strip() != ""):
                fa = (str(fase_actual).strip() if fase_actual is not None else "")
                if fa:
                    counts[fa] += 1
                last_phase = str(fase_actual).strip()
                last_non_null_phase = str(fase_actual).strip()
                last_non_null_idx = int(turno_idx)
                skip_deepseek_total += 1
                continue

            # Caso contrario: aplicar reglas
            fase, conf, _ = detect_fase_rules_based(text, int(turno_idx), total, last_phase=last_phase, is_last_turns=is_last)

            if conf < conf_threshold: 
                fase = None
                conf = 0.0

            # actualizar turno (no sobrescribir DEEPSEEK)
            cur.execute(
                "UPDATE sa_turnos SET fase=%s, fase_conf=%s, fase_source=%s WHERE turno_pk=%s AND (fase_source IS NULL OR fase_source='RULES')",
                (fase, conf if fase else None, "RULES" if fase else None, turno_pk),
            )
            total_turns_updated += 1

            if fase:
                counts[fase] += 1
                last_phase = fase
                last_non_null_phase = fase
                last_non_null_idx = int(turno_idx)
            else:
                null_count += 1

        fase_final = last_non_null_phase
        fase_final_idx = last_non_null_idx
        tipo_finalizacion = "CIERRE" if fase_final == "CIERRE" else "CORTE"

        cur.execute(
            "UPDATE sa_conversaciones SET fase_final=%s, fase_final_turn_idx=%s, tipo_finalizacion=%s WHERE conversacion_pk=%s",
            (fase_final, fase_final_idx, tipo_finalizacion, conv_pk),
        )

        if verbose and (i <= 10 or i % 100 == 0):
            print(f"[detect-fases] conv={conv_id} turnos={total} fase_final={fase_final} null_turnos_acum={null_count}")

        if i % 100 == 0:
            conn.commit()

    conn.commit()

    # resumen
    if verbose:
        print("\n--- Conteo por fase (turnos) ---")
        for f in FASE_SEQUENCE:
            print(f"{f}: {counts[f]}")
        print(f"NULL: {null_count}")
        print(f"SKIP por DEEPSEEK: {skip_deepseek_total}")
        
        # Mostrar fases extras (no legacy)
        extras = sorted([k for k in counts.keys() if k not in FASE_SEQUENCE and counts[k] > 0])
        if extras:
            print("\n--- Conteo por fase (extras) ---")
            for k in extras:
                print(f"{k}: {counts[k]}")

    print("\n--- Resumen de Detección de Fases ---")
    print(f"ID de Ejecución: {ejecucion_id}")
    print(f"Conversaciones procesadas: {len(convs)}")
    print(f"Turnos actualizados: {total_turns_updated}")
    print(f"NULL turnos: {null_count}")

    cur.close()
