from mysql.connector import Error
from sa_core.fases_rules import detect_fase_rules_based
import inspect

_RULES_PARAMS = None

def _call_detect_fase_rules_based(text, turno_idx, total_turnos, last_phase=None, is_last_turn=False, speaker=None):
    global _RULES_PARAMS
    if _RULES_PARAMS is None:
        _RULES_PARAMS = set(inspect.signature(detect_fase_rules_based).parameters.keys())

    kwargs = {}
    if 'last_phase' in _RULES_PARAMS:
        kwargs['last_phase'] = last_phase
    if 'speaker' in _RULES_PARAMS and speaker is not None:
        kwargs['speaker'] = speaker
    # compat: el proyecto usa is_last_turns (plural). Si existiera is_last_turn (singular), soportarlo también.
    if 'is_last_turns' in _RULES_PARAMS:
        kwargs['is_last_turns'] = is_last_turn
    elif 'is_last_turn' in _RULES_PARAMS:
        kwargs['is_last_turn'] = is_last_turn

    return detect_fase_rules_based(text, int(turno_idx), int(total_turnos), **kwargs)

def detect_fases_for_run(conn, ejecucion_id, limit=0, conf_threshold=0.0, verbose=False):
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT t.turno_pk, t.conversacion_pk, c.conversacion_id, t.turno_idx, c.total_turnos, t.speaker, t.text
            FROM sa_turnos t
            JOIN sa_conversaciones c ON t.conversacion_pk = c.conversacion_pk
            WHERE c.ejecucion_id = %s
            ORDER BY t.conversacion_pk, t.turno_idx
        """
        params = [ejecucion_id]
        cursor.execute(query, tuple(params))
        all_turns = cursor.fetchall()

        if not all_turns:
            print(f"No se encontraron turnos para la ejecución ID: {ejecucion_id}")
            return

        # Agrupar turnos por conversacion_pk
        turns_by_conv_pk = {}
        for turn in all_turns:
            conv_pk = turn['conversacion_pk']
            if conv_pk not in turns_by_conv_pk:
                turns_by_conv_pk[conv_pk] = []
            turns_by_conv_pk[conv_pk].append(turn)

        conv_pks = list(turns_by_conv_pk.keys())
        if limit > 0:
            conv_pks = conv_pks[:limit]

        processed_conversations = 0
        total_fases_detected = 0
        batch_size = 100
        updates_to_commit = []

        for conv_pk in conv_pks:
            turns = turns_by_conv_pk[conv_pk]
            conv_id = turns[0]['conversacion_id']
            total_turnos = max(t['turno_idx'] for t in turns)
            fases_in_conv = 0
            last_phase = None
            for turn in turns:
                is_last_turn = (turn['turno_idx'] == total_turnos)
                try:
                    res = _call_detect_fase_rules_based(
                        turn['text'],
                        turn['turno_idx'],
                        turn['total_turnos'],
                        last_phase=last_phase,
                        is_last_turn=is_last_turn,
                        speaker=turn.get('speaker')
                    )
                    fase = res[0] if res else None
                    confianza = float(res[1]) if (isinstance(res, tuple) and len(res) > 1 and res[1] is not None) else 0.0
                    if fase is not None and confianza >= conf_threshold:
                        updates_to_commit.append((
                            fase,
                            confianza,
                            'rules-v1-peru',
                            turn['turno_pk']
                        ))
                        fases_in_conv += 1
                        last_phase = fase
                    # Si fase es None o confianza < conf_threshold, NO cambiar last_phase
                except Exception as e:
                    print(f"Error detectando fase para turno {turn['turno_pk']} en conv {conv_id}: {e}")
            if verbose:
                print(f"Conversación {conv_id} (PK: {conv_pk}): {fases_in_conv} fases detectadas.")
            processed_conversations += 1
            total_fases_detected += fases_in_conv
            if len(updates_to_commit) >= batch_size:
                n = len(updates_to_commit)
                _commit_updates(conn, cursor, updates_to_commit)
                updates_to_commit = []
                if verbose:
                    print(f"--- Lote de {n} actualizaciones de fase procesado. Commit realizado. ---")
        # Commit final
        if updates_to_commit:
            _commit_updates(conn, cursor, updates_to_commit)
        print("\n--- Resumen de Detección de Fases ---")
        print(f"ID de Ejecución: {ejecucion_id}")
        print(f"Conversaciones procesadas: {processed_conversations}")
        print(f"Total de fases detectadas: {total_fases_detected}")
    except Error as e:
        print(f"Error general durante la detección de fases. Error: {e}")
        conn.rollback()
    finally:
        cursor.close()

def _commit_updates(conn, cursor, updates):
    try:
        cursor.executemany(
            """
            UPDATE sa_turnos 
            SET fase = %s, fase_conf = %s, fase_source = %s
            WHERE turno_pk = %s
            """,
            updates
        )
        conn.commit()
    except Error as e:
        print(f"Error al hacer commit de las actualizaciones de fase: {e}")
        conn.rollback()
