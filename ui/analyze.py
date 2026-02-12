"""
Pipeline de análisis completo para ejecuciones
"""
import logging
from typing import Callable, Optional
import os

from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.turnos import parse_turns_for_run
from sa_core.fases import detect_fases_for_run
from sa_core.fase_guardrails import apply_guardrails, has_meaningful_text
from sa_core.cliente_id import ensure_cliente_id_column, fill_cliente_id_for_ejecucion

# Scripts de secuencias
from scripts.build_fase_seq import run_build_fase_seq
from scripts.build_secuencias import run_build_secuencias

logger = logging.getLogger(__name__)


def run_analysis_for_ejecucion(
    config_path: str,
    ejecucion_id: int,
    conf_threshold: float = 0.08,
    run_deepseek: bool = True,
    progress_callback: Optional[Callable[[str], None]] = None,
    max_deepseek_iters: int = 5,
    deepseek_batch_size: int = 500
) -> None:
    """
    Ejecuta pipeline completo de análisis para una ejecución:
    1. Parse de turnos desde raw_text
    2. Detección de fases por reglas
    3. DeepSeek para turnos con confianza baja (opcional, en batches iterativos)
    4. Construcción de fase_seq (estabilización de secuencias)
    5. Construcción de secuencias (análisis de calidad)
    
    Args:
        config_path: Ruta al config.ini
        ejecucion_id: ID de la ejecución a analizar
        conf_threshold: Umbral de confianza para considerar pendientes
        run_deepseek: Si ejecutar DeepSeek automáticamente
        progress_callback: Función para reportar progreso (str)
        max_deepseek_iters: Máximo de iteraciones de DeepSeek (default 5)
        deepseek_batch_size: Tamaño de batch por iteración (default 500)
    
    Raises:
        Exception si falla algún paso del pipeline
    """
    
    def report(msg: str):
        logger.info(msg)
        if progress_callback:
            progress_callback(msg)
    
    conn = None
    
    try:
        # Cargar config y conectar
        report("Conectando a base de datos...")
        cfg = load_config(config_path)
        conn = get_conn(cfg)
        ensure_cliente_id_column(conn)
        
        # PASO 1: Parse de turnos
        report(f"[1/5] Parseando turnos para ejecución {ejecucion_id}...")
        parse_turns_for_run(conn, ejecucion_id, limit=0, verbose=False)
        report("✓ Turnos parseados")
        
        # PASO 2: Detección de fases por reglas
        report(f"[2/5] Detectando fases por reglas (umbral={conf_threshold})...")
        detect_fases_for_run(conn, ejecucion_id, limit=0, conf_threshold=conf_threshold, verbose=False)
        report("✓ Fases detectadas por reglas")
        
        # PASO 3: DeepSeek para turnos pendientes (opcional)
        if run_deepseek:
            report(f"[3/5] Ejecutando DeepSeek para turnos pendientes...")
            _run_deepseek_for_pendientes(
                conn, ejecucion_id, conf_threshold, cfg, report,
                max_iters=max_deepseek_iters,
                batch_size=deepseek_batch_size
            )
            report("✓ DeepSeek completado")
        else:
            report("[3/5] DeepSeek omitido")
        
        # Extracción de cliente_id (al final, con todos los datos ya procesados)
        try:
            report("[Final] Extrayendo identificadores de cliente...")
            fill_cliente_id_for_ejecucion(conn, ejecucion_id)
            conn.commit()  # Asegurar persistencia
            logger.info(f"[cliente_id] Filled for ejecucion_id={ejecucion_id}")
            report("✓ Identificadores de cliente actualizados")
        except Exception as e:
            logger.warning(f"Error extrayendo cliente_id: {e}", exc_info=True)
            report("⚠️ No se pudo extraer cliente_id (continuando análisis)")
            # No abortar el análisis
        
        # Cerrar conexión antes de scripts (ellos abren la suya)
        if conn:
            try:
                conn.close()
                logger.debug("Conexión principal cerrada antes de scripts")
                conn = None
            except Exception as e:
                logger.error(f"Error cerrando conexión: {e}")
        
        # PASO 4: Construcción de fase_seq (estabilización)
        try:
            report(f"[4/5] Construyendo fase_seq (estabilización de secuencias)...")
            fase_seq_stats = run_build_fase_seq(config_path, ejecucion_id)
            total_fase_seq = fase_seq_stats.get('total', 0)
            report(f"✓ Fase_seq construido ({total_fase_seq} conversaciones procesadas)")
        except Exception as e:
            logger.error(f"Error construyendo fase_seq: {e}", exc_info=True)
            report(f"⚠️ No se pudo construir fase_seq: {e}")
            # No romper el pipeline, continuar
        
        # PASO 5: Construcción de secuencias (análisis de calidad)
        try:
            report(f"[5/5] Construyendo secuencias (análisis de calidad)...")
            sec_stats = run_build_secuencias(config_path, ejecucion_id, verbose=False)
            total_secs = sec_stats.get('total', 0)
            cumple = sec_stats.get('cumple_secuencia', 0)
            report(f"✓ Secuencias construidas ({total_secs} conversaciones, {cumple} cumplen)")
        except Exception as e:
            logger.error(f"Error construyendo secuencias: {e}", exc_info=True)
            report(f"⚠️ No se pudo construir secuencias: {e}")
            # No romper el pipeline
        
        report(f"✅ Análisis completo para ejecución {ejecucion_id}")
    
    except Exception as e:
        logger.error(f"Error en análisis de ejecución {ejecucion_id}: {e}", exc_info=True)
        if conn:
            try:
                conn.rollback()
            except:
                pass
        raise
    
    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Conexión cerrada")
            except Exception as e:
                logger.error(f"Error cerrando conexión: {e}")


def _run_deepseek_for_pendientes(conn, ejecucion_id: int, conf_threshold: float, cfg: dict, report: Callable, max_iters: int = 5, batch_size: int = 500):
    """
    Ejecuta DeepSeek solo para turnos pendientes de una ejecución en batches iterativos
    
    Criterio de pendiente:
    - fase IS NULL OR TRIM(fase) = ''
    
    Args:
        max_iters: Máximo de iteraciones/batches a procesar
        batch_size: Tamaño del batch por iteración
    """
    
    def should_skip_deepseek(text: str) -> bool:
        """Filtro previo para evitar enviar basura a DeepSeek
        
        Returns:
            True si se debe saltar (no enviar a DeepSeek)
        """
        if not text:
            return True
        
        text_trim = text.strip()
        
        # Textos muy cortos
        if len(text_trim) < 12:
            return True
        
        # ACKs típicos (normalizado a minúsculas)
        text_lower = text_trim.lower()
        acks = {
            "si", "sí", "ya", "ok", "okay", "listo", "dale", "ajá", "aja", 
            "mm", "mhm", "gracias", "bien", "perfecto", "entiendo", "claro"
        }
        if text_lower in acks:
            return True
        
        # Solo dígitos y símbolos comunes
        import re
        if re.match(r'^[0-9\s\.,\-]+$', text_trim):
            return True
        
        # 3 palabras o menos
        words = text_trim.split()
        if len(words) <= 3:
            return True
        
        return False
    
    try:
        # Importar módulo de DeepSeek
        try:
            from scripts.reclasificar_turnos_deepseek import call_deepseek
        except ImportError as e:
            logger.warning(f"No se pudo importar módulo DeepSeek: {e}")
            report("⚠️ DeepSeek no disponible (módulo no encontrado)")
            return
        
        # Verificar config de DeepSeek
        deepseek_base_url = cfg.get('deepseek', 'base_url', fallback=None)
        deepseek_api_key = cfg.get('deepseek', 'api_key', fallback=None)
        deepseek_model = cfg.get('deepseek', 'model', fallback='deepseek-chat')
        
        if not deepseek_base_url or not deepseek_api_key:
            logger.warning("Configuración de DeepSeek incompleta en config.ini")
            report("⚠️ DeepSeek no configurado (revisar config.ini)")
            return
        
        # Cargar prompt
        from pathlib import Path
        prompt_file = Path("prompts/deepseek_prompt.txt")
        if not prompt_file.exists():
            logger.warning("Archivo de prompt de DeepSeek no encontrado")
            report("⚠️ Prompt de DeepSeek no encontrado (prompts/deepseek_prompt.txt)")
            return
        
        # Obtener fases disponibles
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT DISTINCT fase FROM sa_turnos WHERE fase IS NOT NULL AND TRIM(fase) != '' ORDER BY fase")
        allowed_phases = [r['fase'] for r in cursor.fetchall()]
        
        if not allowed_phases:
            allowed_phases = [
                "APERTURA", "IDENTIFICACION", "INFORMACION_DEUDA", "NEGOCIACION",
                "CONSULTA_ACEPTACION", "FORMALIZACION_PAGO", "ADVERTENCIAS", "CIERRE"
            ]
        
        # Obtener turnos pendientes (solo NULL o vacíos)
        # Criterio: fase NULL O vacía (sin considerar confianza)
        query = """
            SELECT t.turno_pk, t.conversacion_pk, t.turno_idx, t.text, t.speaker,
                   t.fase, t.fase_conf, t.fase_source,
                   c.total_turnos, c.conversacion_id
            FROM sa_turnos t
            JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
            WHERE c.ejecucion_id = %s
              AND (t.fase IS NULL OR TRIM(t.fase) = '')
            ORDER BY c.conversacion_pk, t.turno_idx
        """
        
        # Agregar LIMIT para batch_size
        query_params = (ejecucion_id,)
        if batch_size > 0:
            query += " LIMIT %s"
            query_params = query_params + (batch_size,)
        
        report(f"  📊 Iniciando DeepSeek en batches (max_iters={max_iters}, batch_size={batch_size})")
        
        # Fases legacy explícitas
        allowed_phases = [
            "APERTURA", "IDENTIFICACION", "INFORMACION_DEUDA", "NEGOCIACION",
            "CONSULTA_ACEPTACION", "FORMALIZACION_PAGO", "ADVERTENCIAS", "CIERRE"
        ]
        
        # Sistema de batches iterativos
        total_processed_all = 0
        total_updates_all = 0
        
        for iter_num in range(1, max_iters + 1):
            # Contar pendientes ANTES del batch
            cursor.execute(
                """
                SELECT COUNT(*) as pendientes
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND (t.fase IS NULL OR TRIM(t.fase) = '')
                """,
                (ejecucion_id,)
            )
            pendientes_antes = cursor.fetchone()['pendientes']
            
            # Si no hay pendientes, terminar
            if pendientes_antes == 0:
                report(f"  ℹ️ Iteración {iter_num}/{max_iters}: Sin pendientes, finalizando")
                break
            
            report(f"  🔄 Iteración {iter_num}/{max_iters}: {pendientes_antes} turnos pendientes")
            logger.info(f"[DeepSeek] Iter {iter_num}/{max_iters}: pendientes_antes={pendientes_antes}, batch_size={batch_size}")
            
            # Recargar pending_turns para este batch
            cursor.execute(query, query_params)
            pending_turns = cursor.fetchall()
            
            if len(pending_turns) == 0:
                report(f"  ℹ️ Iteración {iter_num}/{max_iters}: Query retornó 0 turnos, finalizando")
                break
            
            # Agrupar por conversación para calcular contextos
            from collections import defaultdict
            convs = defaultdict(list)
            for turn in pending_turns:
                convs[turn['conversacion_pk']].append(turn)
            
            # Cargar todos los turnos de cada conversación para calcular contextos
            conv_all_turns = {}
            for conv_pk in convs.keys():
                cursor.execute(
                    """
                    SELECT turno_pk, turno_idx, text, speaker, fase, fase_conf, fase_source
                    FROM sa_turnos
                    WHERE conversacion_pk = %s
                    ORDER BY turno_idx
                    """,
                    (conv_pk,)
                )
                conv_all_turns[conv_pk] = {row['turno_idx']: row for row in cursor.fetchall()}
            
            # Procesar cada turno del batch
            updates = []
            processed = 0
            errors = 0
            noise_count = 0
            guardrails_count = 0
            deepseek_count = 0
            skipped_filter = 0
            batch_total = len(pending_turns)
            
            for turn in pending_turns:
                try:
                    # Construir contexto enriquecido con turnos cercanos
                    text = turn['text'] or ""
                    turno_idx = turn['turno_idx']
                    conv_pk = turn['conversacion_pk']
                    all_turns = conv_all_turns[conv_pk]
                    total_turns = turn['total_turnos']
                    
                    # Filtro previo: saltar basura antes de llamar DeepSeek
                    if should_skip_deepseek(text):
                        skipped_filter += 1
                        processed += 1
                        continue
                    
                    # Derivar prev_fase y next_fase de turnos inmediatos
                    prev_fase = None
                    next_fase = None
                    prev_idx = turno_idx - 1
                    next_idx = turno_idx + 1
                    
                    if prev_idx in all_turns and all_turns[prev_idx].get('fase'):
                        prev_fase = all_turns[prev_idx]['fase'].strip() or None
                    
                    if next_idx in all_turns and all_turns[next_idx].get('fase'):
                        next_fase = all_turns[next_idx]['fase'].strip() or None
                    
                    # Construir context_block con turnos cercanos (idx-2 a idx+2)
                    context_lines = []
                    for i in range(turno_idx - 2, turno_idx + 3):
                        if i in all_turns:
                            t = all_turns[i]
                            t_text = (t.get('text') or '').replace('\r', ' ').replace('\n', ' ')[:280]
                            t_speaker = t.get('speaker') or 'unknown'
                            
                            if i == turno_idx:
                                context_lines.append(f"Turno idx={i} (OBJETIVO): {t_speaker}: {t_text}")
                            else:
                                context_lines.append(f"Turno idx={i}: {t_speaker}: {t_text}")
                    
                    context_block = "\n".join(context_lines)
                    
                    # Información de última fase para contexto adicional
                    last_phase_info = ""
                    if prev_idx in all_turns:
                        prev_t = all_turns[prev_idx]
                        last_phase_info = f"last_phase={prev_t.get('fase')} conf={prev_t.get('fase_conf')} source={prev_t.get('fase_source')}"
                    
                    # Llamar DeepSeek con contexto enriquecido
                    result = call_deepseek(
                        text=text,
                        prev_fase=prev_fase,
                        next_fase=next_fase,
                        turn_idx=turno_idx,
                        total_turns=total_turns,
                        base_url=deepseek_base_url,
                        api_key=deepseek_api_key,
                        model=deepseek_model,
                        timeout=60,
                        context_block=context_block,
                        last_phase_info=last_phase_info,
                        allowed_phases=allowed_phases
                    )
                    
                    # Extraer resultado (keys: "fase", "conf", "is_noise", "raw", "noise_reason", "rationale")
                    fase = (result.get("fase") or "").strip()
                    conf = float(result.get("conf") or 0.0)
                    is_noise = int(result.get("is_noise") or 0)
                    
                    # Si es NOISE o fase vacío, no guardar (dejar NULL/vacío)
                    if is_noise == 1 or not fase or fase.upper() == 'NOISE':
                        noise_count += 1
                        # No agregar a updates para este turno (dejar sin modificar)
                        processed += 1
                        continue
                    
                    # Si confianza muy baja, no actualizar
                    if conf < conf_threshold:
                        # No agregar a updates (dejar sin modificar)
                        processed += 1
                        continue
                    
                    # Calcular contextos para guardrails
                    # 1. last_phase: última fase no vacía antes del turno_idx
                    last_phase = None
                    for idx in range(turno_idx - 1, 0, -1):
                        if idx in all_turns:
                            prev_fase = all_turns[idx].get('fase')
                            if prev_fase and prev_fase.strip():
                                last_phase = prev_fase
                                break
                    
                    # 2. has_next_meaningful_text: si turno_idx+1 tiene texto significativo
                    has_next_meaningful = False
                    next_idx = turno_idx + 1
                    if next_idx in all_turns:
                        next_text = all_turns[next_idx].get('text') or ""
                        has_next_meaningful = has_meaningful_text(next_text)
                    
                    # 3. prev_texts: hasta 2 textos previos
                    prev_texts = []
                    for idx in [turno_idx - 1, turno_idx - 2]:
                        if idx > 0 and idx in all_turns:
                            prev_text = all_turns[idx].get('text') or ""
                            prev_texts.append(prev_text)
                    
                    # Aplicar guardrails
                    final_fase, final_conf, final_source, reason = apply_guardrails(
                        pred_fase=fase,
                        pred_conf=conf,
                        is_noise=is_noise,
                        last_phase=last_phase,
                        has_next_meaningful_text=has_next_meaningful,
                        curr_text=text,
                        prev_texts=prev_texts
                    )
                    
                    # Preparar update (solo si es DEEPSEEK o GUARDRAILS válido)
                    # Si guardrails lo marca como NOISE, no actualizar
                    if final_source == 'NOISE':
                        noise_count += 1
                        processed += 1
                        continue
                    
                    # UPDATE con valores finales
                    updates.append((
                        final_fase if final_fase else '',
                        float(final_conf) if final_conf is not None else 0.0,
                        final_source,
                        turn['turno_pk']
                    ))
                    
                    # Contadores por fuente
                    if final_source == 'GUARDRAILS':
                        guardrails_count += 1
                    elif final_source == 'DEEPSEEK':
                        deepseek_count += 1
                    
                    processed += 1
                    
                    # Batch commit cada 50 turnos
                    if len(updates) >= 50:
                        _commit_deepseek_updates(conn, cursor, updates)
                        updates = []
                        report(f"     Procesados {processed}/{batch_total} turnos (DEEPSEEK={deepseek_count}, GUARDRAILS={guardrails_count}, NOISE={noise_count})...")
                
                except Exception as e:
                    logger.error(f"Error procesando turno {turn['turno_pk']}: {e}", exc_info=True)
                    errors += 1
                    processed += 1
                    continue
        
            # Commit final del batch
            if updates:
                _commit_deepseek_updates(conn, cursor, updates)
            
            # Contar pendientes DESPUÉS del batch
            cursor.execute(
                """
                SELECT COUNT(*) as pendientes
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND (t.fase IS NULL OR TRIM(t.fase) = '')
                """,
                (ejecucion_id,)
            )
            pendientes_despues = cursor.fetchone()['pendientes']
            
            # Estadísticas del batch
            total_updates_batch = deepseek_count + guardrails_count + noise_count
            total_processed_all += processed
            total_updates_all += total_updates_batch
            
            report(f"     ✓ Batch {iter_num} completado:")
            report(f"       - Procesados: {processed}")
            report(f"       - Skipped (filtro): {skipped_filter}")
            report(f"       - Updates: {total_updates_batch} (DEEPSEEK={deepseek_count}, GUARDRAILS={guardrails_count}, NOISE={noise_count})")
            report(f"       - Errores: {errors}")
            report(f"       - Pendientes restantes: {pendientes_despues}")
            
            logger.info(
                f"[DeepSeek] Iter {iter_num}/{max_iters}: "
                f"pendientes_antes={pendientes_antes}, "
                f"updates_escritos={total_updates_batch}, "
                f"pendientes_despues={pendientes_despues}"
            )
        
        cursor.close()
        
        # Logs finales globales
        report(f"  ✅ Pipeline DeepSeek finalizado:")
        report(f"    - Total procesados: {total_processed_all}")
        report(f"    - Total updates: {total_updates_all}")
    
    except Exception as e:
        logger.error(f"Error en DeepSeek: {e}", exc_info=True)
        raise


def _commit_deepseek_updates(conn, cursor, updates):
    """Commit de updates de DeepSeek"""
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
    except Exception as e:
        logger.error(f"Error en commit de DeepSeek updates: {e}")
        conn.rollback()
        raise
