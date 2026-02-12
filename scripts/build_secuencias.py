"""
Construye análisis de secuencias de macrofases para conversaciones.

Calcula métricas de calidad de secuencia basadas en el flujo de macrofases
y las almacena en la tabla sa_conversacion_secuencias.
"""
import sys
import argparse
from pathlib import Path
from collections import defaultdict

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


# Transiciones permitidas entre macrofases
ALLOWED_TRANSITIONS = {
    ('APERTURA', 'IDENTIFICACION'),
    ('IDENTIFICACION', 'INFORMACION_DEUDA'),
    ('INFORMACION_DEUDA', 'NEGOCIACION'),
    ('NEGOCIACION', 'CONSULTA_ACEPTACION'),
    ('CONSULTA_ACEPTACION', 'FORMALIZACION_PAGO'),
    ('NEGOCIACION', 'FORMALIZACION_PAGO'),
    ('INFORMACION_DEUDA', 'ADVERTENCIAS'),
    ('NEGOCIACION', 'ADVERTENCIAS'),
    ('FORMALIZACION_PAGO', 'ADVERTENCIAS'),
    ('ADVERTENCIAS', 'CIERRE'),
    ('FORMALIZACION_PAGO', 'CIERRE'),
    ('INFORMACION_DEUDA', 'CIERRE'),
    ('NEGOCIACION', 'CIERRE'),
    ('CONSULTA_ACEPTACION', 'CIERRE'),
}


def create_table_if_not_exists(conn):
    """Crea la tabla sa_conversacion_secuencias si no existe"""
    cursor = conn.cursor()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS sa_conversacion_secuencias (
        conversacion_pk BIGINT PRIMARY KEY,
        ejecucion_id INT NOT NULL,
        secuencia_macro TEXT NOT NULL,
        fase_inicio VARCHAR(64),
        fase_fin VARCHAR(64),
        cobertura_fases INT,
        tiene_informacion_deuda TINYINT(1),
        tiene_negociacion TINYINT(1),
        violaciones_transicion INT,
        cumple_secuencia TINYINT(1),
        corte_antes_negociacion TINYINT(1),
        inicio_valido TINYINT(1),
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        INDEX idx_ejecucion_id (ejecucion_id),
        INDEX idx_cumple_secuencia (cumple_secuencia),
        INDEX idx_corte_antes_negociacion (corte_antes_negociacion)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    
    # Agregar columna inicio_valido si no existe (para bases de datos existentes)
    add_column_sql = """
    ALTER TABLE sa_conversacion_secuencias 
    ADD COLUMN IF NOT EXISTS inicio_valido TINYINT(1) DEFAULT 0
    """
    
    try:
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("✓ Tabla sa_conversacion_secuencias verificada/creada")
        
        # Intentar agregar columna si no existe (MySQL 8.0+)
        try:
            cursor.execute(add_column_sql)
            conn.commit()
        except Exception:
            # Si falla, intentar método alternativo para MySQL 5.7
            try:
                cursor.execute("""
                    SELECT COUNT(*) as col_exists 
                    FROM information_schema.COLUMNS 
                    WHERE TABLE_SCHEMA = DATABASE() 
                    AND TABLE_NAME = 'sa_conversacion_secuencias' 
                    AND COLUMN_NAME = 'inicio_valido'
                """)
                result = cursor.fetchone()
                if result and result[0] == 0:
                    cursor.execute("""
                        ALTER TABLE sa_conversacion_secuencias 
                        ADD COLUMN inicio_valido TINYINT(1) DEFAULT 0
                    """)
                    conn.commit()
                    logger.info("✓ Columna inicio_valido agregada")
            except Exception:
                pass  # Columna ya existe o no es crítica
        
    except Exception as e:
        logger.error(f"Error creando tabla: {e}")
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
    """Obtiene la macrofase para una fase dada (con fallback)"""
    if not fase or fase.strip() == '':
        return None
    
    # Buscar en el mapa
    if fase in macro_map:
        return macro_map[fase]
    
    # Fallback: usar la misma fase como macro
    return fase


def build_compact_sequence(macro_phases):
    """Construye secuencia compacta colapsando repeticiones consecutivas"""
    if not macro_phases:
        return []
    
    compact = [macro_phases[0]]
    for macro in macro_phases[1:]:
        if macro != compact[-1]:
            compact.append(macro)
    
    return compact


def count_violations(compact_sequence):
    """Cuenta violaciones de transiciones en la secuencia compacta"""
    violations = 0
    
    for i in range(len(compact_sequence) - 1):
        from_phase = compact_sequence[i]
        to_phase = compact_sequence[i + 1]
        
        # Auto-transiciones (X->X) no son violaciones
        if from_phase == to_phase:
            continue
        
        transition = (from_phase, to_phase)
        if transition not in ALLOWED_TRANSITIONS:
            violations += 1
    
    return violations


def analyze_conversation(conversacion_pk, turnos, macro_map, verbose=False):
    """Analiza una conversación y calcula métricas de secuencia"""
    
    # Mapear fases a macrofases (respetar orden de turno_idx)
    macro_phases = []
    debug_info = []  # Para logging verbose
    
    for turno in turnos:
        # Prioridad: fase_seq (ya es macro) > fase > fase_8
        fase_seq = turno.get('fase_seq')
        
        if fase_seq and fase_seq.strip():
            # fase_seq ya es macrofase, NO mapear
            macro = fase_seq
            fase_raw = fase_seq
        else:
            # Fallback: usar fase o fase_8 y mapear a macro
            fase_raw = turno.get('fase')
            if not fase_raw or fase_raw.strip() == '':
                fase_raw = turno.get('fase_8')
            
            macro = get_macro_fase(fase_raw, macro_map)
        
        if macro:
            macro_phases.append(macro)
            
            # Guardar info de debug para primeros 12 turnos
            if verbose and len(debug_info) < 12:
                debug_info.append({
                    'turno_idx': turno.get('turno_idx'),
                    'fase_raw': fase_raw,
                    'macro_fase': macro
                })
    
    # Log de debug si verbose
    if verbose and debug_info:
        logger.debug(f"\nConversacion {conversacion_pk} - Primeros {len(debug_info)} turnos:")
        for d in debug_info:
            logger.debug(f"  Turno {d['turno_idx']:3d}: fase_raw={d['fase_raw']:20s} -> macro={d['macro_fase']}")
    
    # Si no hay fases, retornar None
    if not macro_phases:
        return None
    
    # Construir secuencia compacta
    compact = build_compact_sequence(macro_phases)
    secuencia_str = '>'.join(compact)
    
    # Métricas básicas
    fase_inicio = compact[0] if compact else None
    fase_fin = compact[-1] if compact else None
    cobertura_fases = len(set(compact))
    
    # Presencia de fases clave
    tiene_informacion_deuda = 1 if 'INFORMACION_DEUDA' in compact else 0
    tiene_negociacion = 1 if 'NEGOCIACION' in compact else 0
    
    # Violaciones de transición
    violaciones = count_violations(compact)
    
    # Inicio válido: APERTURA o IDENTIFICACION
    inicio_valido = 1 if fase_inicio in ('APERTURA', 'IDENTIFICACION') else 0
    
    # Cumple secuencia ideal (flexibilizado para aceptar APERTURA o IDENTIFICACION)
    cumple_secuencia = 1 if (
        violaciones == 0 and
        fase_inicio in ('APERTURA', 'IDENTIFICACION') and
        tiene_informacion_deuda == 1
    ) else 0
    
    # Corte antes de negociación
    corte_antes_negociacion = 1 if (
        tiene_informacion_deuda == 1 and
        tiene_negociacion == 0
    ) else 0
    
    return {
        'conversacion_pk': conversacion_pk,
        'secuencia_macro': secuencia_str,
        'fase_inicio': fase_inicio,
        'fase_fin': fase_fin,
        'cobertura_fases': cobertura_fases,
        'tiene_informacion_deuda': tiene_informacion_deuda,
        'tiene_negociacion': tiene_negociacion,
        'violaciones_transicion': violaciones,
        'cumple_secuencia': cumple_secuencia,
        'corte_antes_negociacion': corte_antes_negociacion,
        'inicio_valido': inicio_valido,
    }


def get_conversations_for_ejecucion(conn, ejecucion_id):
    """Obtiene todas las conversaciones con sus turnos para una ejecución"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener conversaciones
        cursor.execute("""
            SELECT conversacion_pk, conversacion_id
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
                SELECT turno_pk, turno_idx, fase, fase_8, fase_seq, fase_conf, fase_source
                FROM sa_turnos
                WHERE conversacion_pk = %s
                ORDER BY turno_idx ASC
            """, (conv_pk,))
            
            turnos = cursor.fetchall()
            result[conv_pk] = turnos
        
        return result
    
    finally:
        cursor.close()


def upsert_secuencia(conn, ejecucion_id, data):
    """Inserta o actualiza una secuencia en la tabla"""
    cursor = conn.cursor()
    
    upsert_sql = """
    INSERT INTO sa_conversacion_secuencias (
        conversacion_pk, ejecucion_id, secuencia_macro,
        fase_inicio, fase_fin, cobertura_fases,
        tiene_informacion_deuda, tiene_negociacion,
        violaciones_transicion, cumple_secuencia, corte_antes_negociacion,
        inicio_valido
    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        ejecucion_id = VALUES(ejecucion_id),
        secuencia_macro = VALUES(secuencia_macro),
        fase_inicio = VALUES(fase_inicio),
        fase_fin = VALUES(fase_fin),
        cobertura_fases = VALUES(cobertura_fases),
        tiene_informacion_deuda = VALUES(tiene_informacion_deuda),
        tiene_negociacion = VALUES(tiene_negociacion),
        violaciones_transicion = VALUES(violaciones_transicion),
        cumple_secuencia = VALUES(cumple_secuencia),
        corte_antes_negociacion = VALUES(corte_antes_negociacion),
        inicio_valido = VALUES(inicio_valido),
        updated_at = CURRENT_TIMESTAMP
    """
    
    try:
        cursor.execute(upsert_sql, (
            data['conversacion_pk'],
            ejecucion_id,
            data['secuencia_macro'],
            data['fase_inicio'],
            data['fase_fin'],
            data['cobertura_fases'],
            data['tiene_informacion_deuda'],
            data['tiene_negociacion'],
            data['violaciones_transicion'],
            data['cumple_secuencia'],
            data['corte_antes_negociacion'],
            data['inicio_valido'],
        ))
        conn.commit()
    
    except Exception as e:
        logger.error(f"Error en upsert de secuencia: {e}")
        conn.rollback()
        raise
    
    finally:
        cursor.close()


def print_summary(stats):
    """Imprime resumen de procesamiento"""
    print("\n" + "="*70)
    print("RESUMEN DE ANÁLISIS DE SECUENCIAS")
    print("="*70)
    
    print(f"\nConversaciones procesadas: {stats['total']}")
    print(f"Conversaciones sin fases: {stats['sin_fases']}")
    
    if stats['total'] > 0:
        print(f"\n--- Métricas de Calidad ---")
        print(f"Inicio válido (APERTURA/IDENTIFICACION): {stats['inicio_valido']} ({stats['inicio_valido']/stats['total']*100:.1f}%)")
        print(f"Cumplen secuencia ideal: {stats['cumple_secuencia']} ({stats['cumple_secuencia']/stats['total']*100:.1f}%)")
        print(f"Corte antes de negociación: {stats['corte_antes_negociacion']} ({stats['corte_antes_negociacion']/stats['total']*100:.1f}%)")
        
        if stats['total'] > stats['sin_fases']:
            avg_violations = stats['total_violaciones'] / (stats['total'] - stats['sin_fases'])
            print(f"Promedio de violaciones: {avg_violations:.2f}")
        
        print(f"\n--- Fases Clave ---")
        print(f"Tienen INFORMACION_DEUDA: {stats['tiene_info_deuda']}")
        print(f"Tienen NEGOCIACION: {stats['tiene_negociacion']}")
    
    print("\n" + "="*70 + "\n")


def run_build_secuencias(config_path, ejecucion_id, verbose=False):
    """
    Función reutilizable para construir análisis de secuencias (llamable desde UI).
    
    Args:
        config_path: Ruta al archivo config.ini
        ejecucion_id: ID de la ejecución a procesar
        verbose: Si es True, imprime logs detallados
    
    Returns:
        dict con estadísticas del proceso
    
    Raises:
        Exception si hay errores críticos
    """
    config_path = Path(config_path)
    if not config_path.exists():
        raise FileNotFoundError(f"Archivo de configuración no encontrado: {config_path}")
    
    if verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
    
    logger.info(f"Cargando configuración desde {config_path}")
    cfg = load_config(str(config_path))
    
    logger.info("Conectando a la base de datos...")
    conn = get_conn(cfg)
    
    try:
        # Crear tabla si no existe
        create_table_if_not_exists(conn)
        
        # Cargar mapeo de fases a macrofases
        macro_map = load_macro_map(conn)
        
        # Obtener conversaciones y turnos
        logger.info(f"Obteniendo conversaciones para ejecucion_id={ejecucion_id}...")
        conversations = get_conversations_for_ejecucion(conn, ejecucion_id)
        
        if not conversations:
            logger.warning("No hay conversaciones para procesar")
            return {'total': 0, 'message': 'No hay conversaciones para procesar'}
        
        # Procesar cada conversación
        stats = {
            'total': 0,
            'sin_fases': 0,
            'cumple_secuencia': 0,
            'corte_antes_negociacion': 0,
            'total_violaciones': 0,
            'tiene_info_deuda': 0,
            'tiene_negociacion': 0,
            'inicio_valido': 0,
        }
        
        logger.info(f"Procesando {len(conversations)} conversaciones...")
        
        for conv_pk, turnos in conversations.items():
            stats['total'] += 1
            
            # Analizar conversación
            result = analyze_conversation(conv_pk, turnos, macro_map, verbose=verbose)
            
            if result is None:
                stats['sin_fases'] += 1
                continue
            
            # Actualizar estadísticas
            stats['cumple_secuencia'] += result['cumple_secuencia']
            stats['corte_antes_negociacion'] += result['corte_antes_negociacion']
            stats['total_violaciones'] += result['violaciones_transicion']
            stats['tiene_info_deuda'] += result['tiene_informacion_deuda']
            stats['tiene_negociacion'] += result['tiene_negociacion']
            stats['inicio_valido'] += result['inicio_valido']
            
            # Guardar en base de datos
            upsert_secuencia(conn, ejecucion_id, result)
        
        # Imprimir resumen
        print_summary(stats)
        
        logger.info("✅ Procesamiento completado exitosamente")
        return stats
    
    except Exception as e:
        logger.error(f"❌ Error durante el procesamiento: {e}", exc_info=True)
        raise
    
    finally:
        if conn:
            conn.close()
            logger.info("Conexión cerrada")


def main():
    """Función principal CLI"""
    parser = argparse.ArgumentParser(description='Construye análisis de secuencias de macrofases')
    parser.add_argument('--config', default='config.ini', help='Ruta al archivo de configuración')
    parser.add_argument('--ejecucion_id', type=int, required=True, help='ID de la ejecución a procesar')
    parser.add_argument('--verbose', action='store_true', help='Imprimir logs de debug detallados')
    
    args = parser.parse_args()
    
    try:
        stats = run_build_secuencias(args.config, args.ejecucion_id, verbose=args.verbose)
        logger.info("Proceso completado exitosamente")
        logger.info(f"Estadísticas finales: {stats}")
    except Exception as e:
        logger.error(f"Error en el proceso: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
