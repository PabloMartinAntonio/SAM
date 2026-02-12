"""
Construye fase_seq (fase estabilizada) para análisis de secuencias.

Aplica reglas de estabilización sobre fase original para reducir zigzag
y mejorar coherencia de secuencias.
"""
import sys
import argparse
import re
from pathlib import Path

# Agregar directorio raíz al path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sa_core.config import load_config
from sa_core.db import get_conn
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Orden de macrofases (para detectar retrocesos)
MACRO_ORDER = {
    'APERTURA': 1,
    'IDENTIFICACION': 2,
    'INFORMACION_DEUDA': 3,
    'NEGOCIACION': 4,
    'CONSULTA_ACEPTACION': 5,
    'FORMALIZACION_PAGO': 6,
    'ADVERTENCIAS': 7,
    'CIERRE': 8,
}

# Patrones para casos especiales
PATTERN_DNI = re.compile(r'\d{7,}')  # DNI/documento
PATTERN_FECHA = re.compile(r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}')  # Fecha
PATTERN_DEUDA = re.compile(r'saldo|deuda|mora|vencid|balance|importe', re.IGNORECASE)


def create_column_if_not_exists(conn):
    """Crea la columna fase_seq si no existe"""
    cursor = conn.cursor()
    
    try:
        # Intentar agregar columna (MySQL ignora si existe con IF NOT EXISTS no disponible en ALTER)
        cursor.execute("""
            SELECT COUNT(*) as col_exists
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = 'sa_turnos'
              AND COLUMN_NAME = 'fase_seq'
        """)
        
        result = cursor.fetchone()
        
        if result[0] == 0:
            logger.info("Creando columna fase_seq en sa_turnos...")
            cursor.execute("""
                ALTER TABLE sa_turnos 
                ADD COLUMN fase_seq VARCHAR(64) NULL
            """)
            conn.commit()
            logger.info("✓ Columna fase_seq creada")
        else:
            logger.info("✓ Columna fase_seq ya existe")
    
    except Exception as e:
        logger.error(f"Error creando columna: {e}")
        raise
    finally:
        cursor.close()


def load_macro_map(conn):
    """Carga el mapeo de fases a macrofases"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("SELECT fase, macro_fase FROM sa_fase_macro_map")
        rows = cursor.fetchall()
        
        macro_map = {row['fase']: row['macro_fase'] for row in rows}
        logger.info(f"✓ Cargado mapeo de {len(macro_map)} fases a macrofases")
        return macro_map
    
    except Exception as e:
        logger.warning(f"No se pudo cargar sa_fase_macro_map: {e}")
        return {}
    
    finally:
        cursor.close()


def get_macro_fase(fase, macro_map):
    """Obtiene la macrofase para una fase dada"""
    if not fase or fase.strip() == '':
        return None
    
    # Buscar en el mapa
    if fase in macro_map:
        return macro_map[fase]
    
    # Fallback: usar la misma fase como macro
    return fase


def is_short_client_response(text, speaker):
    """Detecta si es una respuesta corta del cliente"""
    if speaker != 'CLIENTE':
        return False
    
    if not text:
        return False
    
    text_clean = text.strip()
    
    # Respuestas muy cortas (<=6 caracteres)
    if len(text_clean) <= 6:
        return True
    
    # Respuestas monosilábicas comunes
    short_responses = {'si', 'sí', 'no', 'ok', 'vale', 'ya', 'ajá', 'ajá', 'mmm', 'ehh', '...'}
    if text_clean.lower() in short_responses:
        return True
    
    return False


def detect_identificacion_indicators(text, speaker):
    """Detecta si el texto contiene indicadores de IDENTIFICACION"""
    if speaker != 'CLIENTE':
        return False
    
    if not text:
        return False
    
    # Buscar DNI o fecha
    if PATTERN_DNI.search(text) or PATTERN_FECHA.search(text):
        return True
    
    return False


def detect_informacion_deuda_indicators(text):
    """Detecta si el texto contiene indicadores de INFORMACION_DEUDA"""
    if not text:
        return False
    
    return bool(PATTERN_DEUDA.search(text))


def apply_stabilization_rules(turnos, macro_map):
    """
    Aplica reglas de estabilización para calcular fase_seq
    
    Returns:
        list: Lista de (turno_pk, fase_seq) para actualizar
        dict: Estadísticas de aplicación de reglas
    """
    updates = []
    stats = {
        'total': len(turnos),
        'null_kept': 0,
        'short_client_kept': 0,
        'backtrack_prevented': 0,
        'identificacion_forced': 0,
        'info_deuda_forced': 0,
        'apertura_blocked': 0,          # F
        'formalizacion_blocked': 0,     # G
        'info_deuda_blocked': 0,        # H
        'formalizacion_kept': 0,        # I
        'advertencias_kept': 0,         # J
        'normal': 0,
    }
    
    prev_macro = None
    
    for idx, turno in enumerate(turnos):
        turno_pk = turno['turno_pk']
        turno_idx = turno['turno_idx']
        fase = turno['fase']
        speaker = turno['speaker']
        text = turno['text'] or ''
        
        # REGLA A: NULL/vacío -> mantener NULL
        if not fase or fase.strip() == '':
            updates.append((turno_pk, None))
            stats['null_kept'] += 1
            continue
        
        # Mapear a macro
        current_macro = get_macro_fase(fase, macro_map)
        
        if not current_macro:
            updates.append((turno_pk, None))
            stats['null_kept'] += 1
            continue
        
        # REGLA B: Respuestas cortas del CLIENTE -> mantener fase anterior
        if is_short_client_response(text, speaker):
            if prev_macro:
                updates.append((turno_pk, prev_macro))
                stats['short_client_kept'] += 1
                continue
        
        # REGLA D: IDENTIFICACION al inicio (primeros 6 turnos)
        if turno_idx <= 6 and detect_identificacion_indicators(text, speaker):
            current_macro = 'IDENTIFICACION'
            updates.append((turno_pk, current_macro))
            stats['identificacion_forced'] += 1
            prev_macro = current_macro
            continue
        
        # REGLA E: INFORMACION_DEUDA por keywords
        # PERO NO si ya estamos en NEGOCIACION o más (evitar zigzag)
        if detect_informacion_deuda_indicators(text):
            # Verificar si ya estamos en NEGOCIACION o más
            allow_info_deuda = True
            if prev_macro and prev_macro in MACRO_ORDER:
                prev_order = MACRO_ORDER[prev_macro]
                if prev_order >= 4:  # NEGOCIACION o posterior
                    allow_info_deuda = False
            
            if allow_info_deuda:
                current_macro = 'INFORMACION_DEUDA'
                updates.append((turno_pk, current_macro))
                stats['info_deuda_forced'] += 1
                prev_macro = current_macro
                continue
        
        # REGLA C: No retroceder más de 2 niveles
        if prev_macro and current_macro in MACRO_ORDER and prev_macro in MACRO_ORDER:
            current_order = MACRO_ORDER[current_macro]
            prev_order = MACRO_ORDER[prev_macro]
            
            if current_order < prev_order:
                diff = prev_order - current_order
                if diff >= 2:
                    # Retroceso fuerte: mantener fase anterior
                    updates.append((turno_pk, prev_macro))
                    stats['backtrack_prevented'] += 1
                    continue
        
        # REGLAS MONOTÓNICAS F-J (modifican current_macro, no hacen continue)
        
        # REGLA F: BLOQUEAR APERTURA una vez en IDENTIFICACION o más
        if prev_macro and prev_macro in MACRO_ORDER:
            prev_order = MACRO_ORDER[prev_macro]
            if prev_order >= 2 and current_macro == 'APERTURA':
                current_macro = prev_macro
                stats['apertura_blocked'] += 1
        
        # REGLA G: BLOQUEAR FORMALIZACION_PAGO antes de NEGOCIACION
        if prev_macro and prev_macro in MACRO_ORDER:
            prev_order = MACRO_ORDER[prev_macro]
            if current_macro == 'FORMALIZACION_PAGO' and prev_order < 4:
                current_macro = prev_macro
                stats['formalizacion_blocked'] += 1
        
        # REGLA H: Una vez en NEGOCIACION, no volver a INFORMACION_DEUDA
        if prev_macro == 'NEGOCIACION' and current_macro == 'INFORMACION_DEUDA':
            current_macro = 'NEGOCIACION'
            stats['info_deuda_blocked'] += 1
        
        # REGLA I: Una vez en FORMALIZACION_PAGO, mantener hasta CIERRE (salvo ADVERTENCIAS y CIERRE)
        if prev_macro == 'FORMALIZACION_PAGO':
            if current_macro in ('NEGOCIACION', 'CONSULTA_ACEPTACION', 'INFORMACION_DEUDA', 'IDENTIFICACION', 'APERTURA'):
                current_macro = 'FORMALIZACION_PAGO'
                stats['formalizacion_kept'] += 1
        
        # REGLA J: Después de ADVERTENCIAS, no volver a FORMALIZACION/CONSULTA/NEGOCIACION/INFO_DEUDA
        if prev_macro == 'ADVERTENCIAS':
            if current_macro in ('FORMALIZACION_PAGO', 'CONSULTA_ACEPTACION', 'NEGOCIACION', 'INFORMACION_DEUDA'):
                current_macro = 'ADVERTENCIAS'
                stats['advertencias_kept'] += 1
        
        # Caso normal: usar macro actual (posiblemente modificado por F-J)
        updates.append((turno_pk, current_macro))
        stats['normal'] += 1
        prev_macro = current_macro
    
    return updates, stats


def get_conversations_for_ejecucion(conn, ejecucion_id):
    """Obtiene todas las conversaciones con sus turnos para una ejecución"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener conversaciones
        cursor.execute("""
            SELECT conversacion_pk
            FROM sa_conversaciones
            WHERE ejecucion_id = %s
            ORDER BY conversacion_pk
        """, (ejecucion_id,))
        
        conversations = cursor.fetchall()
        
        if not conversations:
            logger.warning(f"No se encontraron conversaciones para ejecucion_id={ejecucion_id}")
            return {}
        
        logger.info(f"✓ Encontradas {len(conversations)} conversaciones")
        
        # Para cada conversación, obtener sus turnos
        result = {}
        for conv in conversations:
            conv_pk = conv['conversacion_pk']
            
            cursor.execute("""
                SELECT turno_pk, turno_idx, fase, fase_conf, fase_source, speaker, text
                FROM sa_turnos
                WHERE conversacion_pk = %s
                ORDER BY turno_idx ASC
            """, (conv_pk,))
            
            turnos = cursor.fetchall()
            result[conv_pk] = turnos
        
        return result
    
    finally:
        cursor.close()


def batch_update_fase_seq(conn, updates):
    """Actualiza fase_seq en batch"""
    if not updates:
        return
    
    cursor = conn.cursor()
    
    try:
        cursor.executemany(
            "UPDATE sa_turnos SET fase_seq = %s WHERE turno_pk = %s",
            [(fase_seq, turno_pk) for turno_pk, fase_seq in updates]
        )
        conn.commit()
    
    except Exception as e:
        logger.error(f"Error en batch update: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()


def print_summary(global_stats):
    """Imprime resumen de procesamiento"""
    print("\n" + "="*70)
    print("RESUMEN DE ESTABILIZACIÓN DE FASES (fase_seq)")
    print("="*70)
    
    total = global_stats['total']
    
    print(f"\nTurnos procesados: {total}")
    
    if total > 0:
        print(f"\n--- Aplicación de Reglas ---")
        print(f"NULL mantenido (A):              {global_stats['null_kept']:6d} ({global_stats['null_kept']/total*100:5.1f}%)")
        print(f"Respuestas cortas (B):           {global_stats['short_client_kept']:6d} ({global_stats['short_client_kept']/total*100:5.1f}%)")
        print(f"Retrocesos evitados (C):         {global_stats['backtrack_prevented']:6d} ({global_stats['backtrack_prevented']/total*100:5.1f}%)")
        print(f"IDENTIFICACION forzada (D):      {global_stats['identificacion_forced']:6d} ({global_stats['identificacion_forced']/total*100:5.1f}%)")
        print(f"INFORMACION_DEUDA forzada (E):   {global_stats['info_deuda_forced']:6d} ({global_stats['info_deuda_forced']/total*100:5.1f}%)")
        
        print(f"\n--- Reglas Monotónicas ---")
        print(f"APERTURA bloqueada (F):          {global_stats['apertura_blocked']:6d} ({global_stats['apertura_blocked']/total*100:5.1f}%)")
        print(f"FORMALIZACION bloqueada (G):     {global_stats['formalizacion_blocked']:6d} ({global_stats['formalizacion_blocked']/total*100:5.1f}%)")
        print(f"INFO_DEUDA bloqueada (H):        {global_stats['info_deuda_blocked']:6d} ({global_stats['info_deuda_blocked']/total*100:5.1f}%)")
        print(f"FORMALIZACION mantenida (I):     {global_stats['formalizacion_kept']:6d} ({global_stats['formalizacion_kept']/total*100:5.1f}%)")
        print(f"ADVERTENCIAS mantenida (J):      {global_stats['advertencias_kept']:6d} ({global_stats['advertencias_kept']/total*100:5.1f}%)")
        
        print(f"\nSin cambios (normal):            {global_stats['normal']:6d} ({global_stats['normal']/total*100:5.1f}%)")
        
        total_changes = (global_stats['short_client_kept'] + 
                        global_stats['backtrack_prevented'] + 
                        global_stats['identificacion_forced'] + 
                        global_stats['info_deuda_forced'] +
                        global_stats['apertura_blocked'] +
                        global_stats['formalizacion_blocked'] +
                        global_stats['info_deuda_blocked'] +
                        global_stats['formalizacion_kept'] +
                        global_stats['advertencias_kept'])
        
        print(f"\n--- Resumen ---")
        print(f"Total de cambios aplicados: {total_changes} ({total_changes/total*100:.1f}%)")
    
    print("\n" + "="*70 + "\n")


def run_build_fase_seq(config_path, ejecucion_id):
    """
    Función reutilizable para construir fase_seq (llamable desde UI).
    
    Args:
        config_path: Ruta al archivo config.ini
        ejecucion_id: ID de la ejecución a procesar
    
    Returns:
        dict con estadísticas del proceso
    
    Raises:
        Exception si hay errores críticos
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
    
    logger.info(f"Cargando configuración desde {config_path}")
    cfg = load_config(str(config_path))
    
    logger.info("Conectando a la base de datos...")
    conn = get_conn(cfg)
    
    try:
        # Crear columna si no existe
        create_column_if_not_exists(conn)
        
        # Cargar mapeo de fases a macrofases
        macro_map = load_macro_map(conn)
        
        # Obtener conversaciones y turnos
        logger.info(f"Obteniendo conversaciones para ejecucion_id={ejecucion_id}...")
        conversations = get_conversations_for_ejecucion(conn, ejecucion_id)
        
        if not conversations:
            logger.warning("No hay conversaciones para procesar")
            return {'total': 0, 'message': 'No hay conversaciones para procesar'}
        
        # Estadísticas globales
        global_stats = {
            'total': 0,
            'null_kept': 0,
            'short_client_kept': 0,
            'backtrack_prevented': 0,
            'identificacion_forced': 0,
            'info_deuda_forced': 0,
            'apertura_blocked': 0,
            'formalizacion_blocked': 0,
            'info_deuda_blocked': 0,
            'formalizacion_kept': 0,
            'advertencias_kept': 0,
            'normal': 0,
        }
        
        logger.info(f"Procesando {len(conversations)} conversaciones...")
        
        # Procesar cada conversación
        all_updates = []
        
        for conv_pk, turnos in conversations.items():
            # Aplicar reglas de estabilización
            updates, stats = apply_stabilization_rules(turnos, macro_map)
            
            # Acumular updates y stats
            all_updates.extend(updates)
            for key in global_stats:
                global_stats[key] += stats.get(key, 0)
        
        # Batch update
        logger.info(f"Actualizando {len(all_updates)} turnos en base de datos...")
        batch_update_fase_seq(conn, all_updates)
        
        # Imprimir resumen
        print_summary(global_stats)
        
        logger.info("✅ Procesamiento completado exitosamente")
        return global_stats
    
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {e}", exc_info=True)
        raise
    
    finally:
        if conn:
            conn.close()
            logger.info("Conexión cerrada")


def main():
    """Función principal CLI"""
    parser = argparse.ArgumentParser(description='Construye fase_seq estabilizada para análisis de secuencias')
    parser.add_argument('--config', default='config.ini', help='Ruta al archivo de configuración')
    parser.add_argument('--ejecucion_id', type=int, required=True, help='ID de la ejecución a procesar')
    
    args = parser.parse_args()
    
    try:
        stats = run_build_fase_seq(args.config, args.ejecucion_id)
        logger.info("Proceso completado exitosamente")
        logger.info(f"Estadísticas finales: {stats}")
    except Exception as e:
        logger.error(f"Error en el proceso: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
