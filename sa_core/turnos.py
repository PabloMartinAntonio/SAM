import re
from mysql.connector import Error
from collections import defaultdict

# Regex para parsear "Hablante N: texto"
SPEAKER_LINE_RE = re.compile(r"^\s*Hablante\s*(\d+)\s*:\s*(.+)$", re.IGNORECASE)

# Regex para parsear "AGENTE: texto" / "CLIENTE: texto"
SPEAKER_LABEL_RE = re.compile(r"^\s*(AGENTE|CLIENTE)\s*:\s*(.+)$", re.IGNORECASE)

# Pesos para la detección del agente
AGENT_SCORE_PATTERNS = {
    re.compile(r"le saluda", re.I): 4,
    re.compile(r"por encargo", re.I): 4,
    re.compile(r"estudio jurídico|abogados|CR abogados", re.I): 3,
    re.compile(r"área judicial|área de conciliación|cobranzas|legal", re.I): 3,
    re.compile(r"me comunico con usted|me estoy comunicando", re.I): 2,
    re.compile(r"financiera|OH!", re.I): 2,
    re.compile(r"deuda|importe|saldo|mora|balance", re.I): 2,
    re.compile(r"beneficio|descuento|liquidar", re.I): 2,
    re.compile(r"transferencia|acciones judiciales|notificación", re.I): 2,
    re.compile(r"¿Aló\?|Buenos días|Buenas tardes", re.I): 1,
}

def _get_speaker_roles(utterances):
    """
    Determina los roles (AGENTE, CLIENTE, UNKNOWN) basado en las intervenciones.
    """
    if not utterances:
        return {}, "No utterances"

    speakers_utterances = defaultdict(list)
    for speaker_id, text in utterances:
        speakers_utterances[speaker_id].append(text)

    # 1. Calcular score de agente para cada speaker
    agent_scores = defaultdict(int)
    for speaker_id, texts in speakers_utterances.items():
        # Usar solo las primeras 20 intervenciones para el score
        for text in texts[:20]:
            for pattern, weight in AGENT_SCORE_PATTERNS.items():
                if pattern.search(text):
                    agent_scores[speaker_id] += weight
    
    # 2. Determinar AGENTE
    agent_speaker_id = -1
    if any(s > 0 for s in agent_scores.values()):
        agent_speaker_id = max(agent_scores, key=agent_scores.get)
    else:
        # Fallback: el que tiene más intervenciones
        agent_speaker_id = max(speakers_utterances, key=lambda spk: len(speakers_utterances[spk]))

    # 3. Determinar CLIENTE
    client_speaker_id = -1
    client_candidates = {}
    for speaker_id, texts in speakers_utterances.items():
        if speaker_id == agent_speaker_id:
            continue
        # Score = (cantidad_intervenciones - 0.5 * score_agente_total_del_speaker)
        score = len(texts) - (0.5 * agent_scores.get(speaker_id, 0))
        client_candidates[speaker_id] = score
    
    if client_candidates:
        client_speaker_id = max(client_candidates, key=client_candidates.get)

    # 4. Mapear roles
    role_map = {}
    unknown_speakers = []
    for speaker_id in speakers_utterances.keys():
        if speaker_id == agent_speaker_id:
            role_map[speaker_id] = "AGENTE"
        elif speaker_id == client_speaker_id:
            role_map[speaker_id] = "CLIENTE"
        else:
            role_map[speaker_id] = "UNKNOWN"
            unknown_speakers.append(speaker_id)
            
    mapping_str = f"agente={agent_speaker_id} cliente={client_speaker_id} unknown={unknown_speakers}"
    return role_map, mapping_str


def parse_turns_for_run(conn, ejecucion_id, limit=0, verbose=False):
    cursor = conn.cursor(dictionary=True)
    
    try:
        # 1. Buscar conversaciones
        query = "SELECT conversacion_pk, conversacion_id, raw_text FROM sa_conversaciones WHERE ejecucion_id = %s"
        params = [ejecucion_id]
        if limit > 0:
            query += " LIMIT %s"
            params.append(limit)
            
        cursor.execute(query, tuple(params))
        conversations = cursor.fetchall()
        
        if not conversations:
            print(f"No se encontraron conversaciones para la ejecución ID: {ejecucion_id}")
            return

        total_turns_inserted = 0
        processed_conversations = 0
        batch_size = 100

        for i, conv in enumerate(conversations):
            try:
                # 2. Parsear intervenciones y determinar roles
                lines = conv['raw_text'].splitlines()
                utterances = []
                format_detected = None  # Track formato: 'hablante_n' o 'agente_cliente'
                
                for line in lines:
                    # Intentar primero formato "Hablante N:"
                    match = SPEAKER_LINE_RE.match(line)
                    if match:
                        speaker_id, text = match.groups()
                        utterances.append((int(speaker_id), text))
                        if format_detected is None:
                            format_detected = 'hablante_n'
                        continue
                    
                    # Intentar formato "AGENTE:" / "CLIENTE:"
                    match = SPEAKER_LABEL_RE.match(line)
                    if match:
                        label, text = match.groups()
                        # Mapear AGENTE->1, CLIENTE->2
                        speaker_id = 1 if label.upper() == 'AGENTE' else 2
                        utterances.append((speaker_id, text))
                        if format_detected is None:
                            format_detected = 'agente_cliente'

                if not utterances:
                    if verbose:
                        print(f"Conversación {conv['conversacion_id']}: No se encontraron líneas con formato válido. Saltando.")
                    continue
                
                role_map, mapping_str = _get_speaker_roles(utterances)
                
                # Si el formato es agente_cliente, forzar el mapeo correcto
                if format_detected == 'agente_cliente':
                    role_map[1] = 'AGENTE'
                    role_map[2] = 'CLIENTE'

                # 3. Agrupar intervenciones en turnos
                turns = []
                if utterances:
                    current_speaker_id = utterances[0][0]
                    current_text = [utterances[0][1]]
                    for speaker_id, text in utterances[1:]:
                        if speaker_id != current_speaker_id:
                            turns.append({
                                "speaker_id": current_speaker_id,
                                "text": "\n".join(current_text)
                            })
                            current_speaker_id = speaker_id
                            current_text = [text]
                        else:
                            current_text.append(text)
                    
                    turns.append({
                        "speaker_id": current_speaker_id,
                        "text": "\n".join(current_text)
                    })

                # 4. Borrar turnos previos e insertar nuevos
                cursor.execute("DELETE FROM sa_turnos WHERE conversacion_pk = %s", (conv['conversacion_pk'],))
                
                turn_inserts = []
                for idx, turn in enumerate(turns):
                    speaker_role = role_map.get(turn['speaker_id'], 'UNKNOWN')
                    turn_inserts.append((
                        conv['conversacion_pk'],
                        idx + 1,
                        speaker_role,
                        turn['text']
                    ))
                
                if turn_inserts:
                    cursor.executemany(
                        """
                        INSERT INTO sa_turnos (conversacion_pk, turno_idx, speaker, text)
                        VALUES (%s, %s, %s, %s)
                        """,
                        turn_inserts
                    )
                    total_turns_inserted += len(turn_inserts)

                # 5. Actualizar total_turnos en la conversación
                cursor.execute(
                    "UPDATE sa_conversaciones SET total_turnos = %s WHERE conversacion_pk = %s",
                    (len(turns), conv['conversacion_pk'])
                )
                
                processed_conversations += 1
                if verbose:
                    format_msg = f"Formato: {'AGENTE/CLIENTE' if format_detected == 'agente_cliente' else 'Hablante N'}"
                    print(f"Conversación {conv['conversacion_id']}: {len(turns)} turnos. {format_msg}. Mapping: {mapping_str}")

                if (i + 1) % batch_size == 0:
                    conn.commit()
                    if verbose:
                        print(f"--- Lote de {batch_size} procesado. Commit realizado. ---")

            except Error as e:
                print(f"Error procesando conversación {conv['conversacion_id']} (PK: {conv['conversacion_pk']}): {e}")
                conn.rollback() # Revertir cambios de la conversación actual
        
        conn.commit() # Commit final para el último lote

        # 6. Imprimir resumen
        avg_turns = total_turns_inserted / processed_conversations if processed_conversations > 0 else 0
        print("\n--- Resumen de Parseo de Turnos ---")
        print(f"ID de Ejecución: {ejecucion_id}")
        print(f"Conversaciones procesadas: {processed_conversations}")
        print(f"Total de turnos insertados: {total_turns_inserted}")
        print(f"Promedio de turnos por conversación: {avg_turns:.2f}")

    except Error as e:
        print(f"Error general durante el parseo de turnos. Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
