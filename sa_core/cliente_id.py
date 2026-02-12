"""
Módulo para extracción de identificadores de cliente (DNI/documento)
desde el texto de las conversaciones.
"""
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def ensure_cliente_id_column(conn) -> bool:
    """Verifica y crea columna cliente_id en sa_conversaciones si no existe
    
    Args:
        conn: Conexión a la base de datos
        
    Returns:
        True si la columna existe o fue creada exitosamente
    """
    cursor = conn.cursor()
    
    try:
        # Intentar agregar la columna
        cursor.execute("""
            ALTER TABLE sa_conversaciones 
            ADD COLUMN cliente_id VARCHAR(64) NULL
        """)
        conn.commit()
        logger.info("✓ Columna cliente_id creada en sa_conversaciones")
        return True
        
    except Exception as e:
        error_msg = str(e).lower()
        
        # Si el error es "duplicate column", está bien (ya existe)
        if 'duplicate' in error_msg:
            logger.debug("Columna cliente_id ya existe")
            return True
        else:
            logger.error(f"Error creando columna cliente_id: {e}")
            conn.rollback()
            return False
            
    finally:
        cursor.close()


def extract_cliente_id_from_text(text: str) -> Optional[str]:
    """Extrae DNI/documento del texto
    
    Soporta patrones:
    - "DNI 12345678"
    - "D.N.I. 12345678"
    - "documento 12345678"
    - "doc 12345678"
    - "mi dni es 12345678"
    - "nro de documento 12345678"
    - "cedula 12345678"
    
    Captura 7-12 dígitos, tolerando puntos/espacios.
    
    Args:
        text: Texto donde buscar el DNI
        
    Returns:
        String con solo dígitos (sin espacios ni puntos) o None
    """
    if not text:
        return None
    
    text_lower = text.lower()
    
    # Palabras clave de documento
    keywords = [
        r'\bdni\b',
        r'\bd\.n\.i\.\b',
        r'\bdocumento\b',
        r'\bdoc\b',
        r'\bcedula\b',
        r'\bn[úu]mero de documento\b',
        r'\bnro de documento\b'
    ]
    
    # Buscar cada patrón
    for keyword in keywords:
        # Buscar palabra clave seguida de números con posibles separadores
        # [^0-9]{0,20} permite hasta 20 caracteres no numéricos entre palabra y número
        pattern = keyword + r'[^0-9]{0,20}([\d\s\.\-]{7,20})'
        matches = re.finditer(pattern, text_lower, re.IGNORECASE)
        
        for match in matches:
            candidate = match.group(1)
            
            # Extraer solo dígitos
            digits_only = ''.join(c for c in candidate if c.isdigit())
            
            # Validar longitud (7-12 dígitos)
            if 7 <= len(digits_only) <= 12:
                return digits_only
    
    return None


def extract_cliente_id_from_conversation_id(conversation_id: str) -> Optional[str]:
    """Extrae el cliente_id más probable desde conversacion_id
    
    Busca todos los grupos de 7-12 dígitos y devuelve el ÚLTIMO
    que NO sea una fecha (YYYYMMDD empezando con '20') ni un grupo de 6 dígitos.
    
    Ejemplo:
        '20250523-085739_989551176_FOHCASTI_kavinazarh_40012085_CE38-all-...'
        Devuelve: '40012085' (el último grupo válido)
    
    Args:
        conversation_id: ID de conversación con formato compuesto
        
    Returns:
        String con dígitos del cliente_id o None
    """
    if not conversation_id:
        return None
    
    # Encontrar todos los matches de 7-12 dígitos
    pattern = r'\d{7,12}'
    matches = re.findall(pattern, str(conversation_id))
    
    if not matches:
        return None
    
    # Filtrar candidatos
    candidates = []
    for match in matches:
        # Descartar fechas YYYYMMDD (8 dígitos empezando con '20')
        if len(match) == 8 and match.startswith('20'):
            continue
        
        # Descartar grupos de exactamente 6 dígitos (probablemente hora HHMMSS)
        if len(match) == 6:
            continue
        
        candidates.append(match)
    
    # Devolver el ÚLTIMO candidato válido
    if candidates:
        return candidates[-1]
    
    return None


def fill_cliente_id_for_ejecucion(conn, ejecucion_id: int):
    """Extrae y guarda cliente_id para todas las conversaciones de una ejecución
    
    Para cada conversación:
    - Si cliente_id ya existe (no NULL y no vacío), NO tocar
    - Buscar en sa_turnos el primer texto que contenga DNI
    - Si no encuentra, fallback: extraer dígitos de conversacion_id
    - Si no hay nada, dejar NULL
    
    Args:
        conn: Conexión a la base de datos
        ejecucion_id: ID de la ejecución a procesar
    """
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Obtener conversaciones que NO tienen cliente_id
        cursor.execute("""
            SELECT conversacion_pk, conversacion_id
            FROM sa_conversaciones
            WHERE ejecucion_id = %s
              AND (cliente_id IS NULL OR TRIM(cliente_id) = '')
        """, (ejecucion_id,))
        
        conversaciones = cursor.fetchall()
        total = len(conversaciones)
        
        if total == 0:
            logger.info(f"No hay conversaciones sin cliente_id en ejecución {ejecucion_id}")
            return
        
        logger.info(f"Procesando cliente_id para {total} conversaciones de ejecución {ejecucion_id}")
        
        updated = 0
        fallback = 0
        no_id = 0
        
        # Procesar cada conversación
        for conv in conversaciones:
            conversacion_pk = conv['conversacion_pk']
            conversacion_id = conv.get('conversacion_id', '')
            cliente_id = None
            
            # Buscar en turnos (ordenados por turno_idx)
            cursor.execute("""
                SELECT text
                FROM sa_turnos
                WHERE conversacion_pk = %s
                  AND text IS NOT NULL
                  AND TRIM(text) != ''
                ORDER BY turno_idx
            """, (conversacion_pk,))
            
            turnos = cursor.fetchall()
            
            # Buscar DNI en primer turno que lo contenga
            for turno in turnos:
                text = turno.get('text') or ''
                cliente_id = extract_cliente_id_from_text(text)
                if cliente_id:
                    break
            
            # Fallback: extraer cliente_id desde conversacion_id
            if not cliente_id and conversacion_id:
                cliente_id = extract_cliente_id_from_conversation_id(conversacion_id)
                if cliente_id:
                    fallback += 1
            
            # Actualizar si encontró algo
            if cliente_id:
                update_cursor = conn.cursor()
                update_cursor.execute("""
                    UPDATE sa_conversaciones
                    SET cliente_id = %s
                    WHERE conversacion_pk = %s
                """, (cliente_id, conversacion_pk))
                update_cursor.close()
                updated += 1
            else:
                no_id += 1
            
            # Log de progreso cada 100
            if (updated + no_id) % 100 == 0:
                logger.info(f"Progreso: {updated + no_id}/{total} conversaciones procesadas")
        
        # Commit al final
        conn.commit()
        
        logger.info(f"✓ cliente_id completado para ejecución {ejecucion_id}: "
                   f"updated={updated}, fallback={fallback}, sin_id={no_id}")
        
    except Exception as e:
        logger.error(f"Error procesando cliente_id: {e}", exc_info=True)
        conn.rollback()
        raise
        
    finally:
        cursor.close()


def run_fill_cliente_id(config_path: str, ejecucion_id: int):
    """Ejecuta extracción de cliente_id para una ejecución
    
    Args:
        config_path: Ruta al config.ini
        ejecucion_id: ID de la ejecución a procesar
    """
    from sa_core.config import load_config
    from sa_core.db import get_conn
    
    cfg = load_config(config_path)
    conn = get_conn(cfg)
    
    try:
        ensure_cliente_id_column(conn)
        fill_cliente_id_for_ejecucion(conn, ejecucion_id)
    finally:
        if conn:
            conn.close()
