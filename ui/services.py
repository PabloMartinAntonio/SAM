"""
Servicios de acceso a base de datos y lógica de negocio
"""
import logging
import threading
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager

from sa_core.config import load_config
from sa_core.db import get_conn
from ui.models import EjecucionInfo, StatsEjecucion, Conversacion, Turno, SecuenciaInfo, SecuenciaKPIs

logger = logging.getLogger(__name__)

# Cache de columnas disponibles
_TURNOS_COLUMNS_CACHE = None
_CONVERSACIONES_COLUMNS_CACHE = None

# Thread-local storage para conexiones (una por thread)
_TLS = threading.local()

def _get_tls_conn():
    """Obtiene la conexión del thread actual"""
    return getattr(_TLS, "conn", None)

def _set_tls_conn(conn):
    """Guarda la conexión en el thread actual"""
    _TLS.conn = conn

def close_thread_connection():
    """Cierra la conexión del thread actual (cleanup opcional)"""
    conn = _get_tls_conn()
    if conn:
        try:
            conn.close()
            logger.debug("Conexión del thread cerrada")
        except:
            pass
        _set_tls_conn(None)

def is_conn_alive(conn) -> bool:
    """Verifica si la conexión está activa"""
    if conn is None:
        return False
    
    # Verificar que la conexión pertenezca al thread actual
    owner = getattr(conn, "_owner_thread_ident", None)
    if owner is not None and owner != threading.get_ident():
        # Conexión creada en otro thread => no se usa acá
        logger.debug(f"Conexión pertenece a thread {owner}, actual: {threading.get_ident()}")
        return False
    
    try:
        # Intentar ping con reconexión automática si está disponible
        if hasattr(conn, 'ping'):
            try:
                conn.ping(reconnect=True, attempts=2, delay=0)
                return True
            except:
                return False
        
        # Fallback: usar is_connected()
        if hasattr(conn, 'is_connected'):
            return conn.is_connected()
        
        # Último recurso: intentar un SELECT 1
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        return True
    except Exception as e:
        logger.debug(f"Conexión no está viva: {e}")
        return False

def get_db_connection(config_path="config.ini"):
    """Obtiene conexión thread-local a la base de datos con reconexión automática"""
    tls_conn = _get_tls_conn()
    
    # Si la conexión del thread actual existe y está viva, retornarla
    if tls_conn is not None and is_conn_alive(tls_conn):
        return tls_conn
    
    # Conexión no existe o está caída, crear nueva para este thread
    try:
        logger.info(f"Creando nueva conexión a MySQL en thread {threading.current_thread().name}...")
        cfg = load_config(config_path)
        new_conn = get_conn(cfg)
        
        # IMPORTANTE: Activar autocommit para ver commits de otras conexiones
        try:
            new_conn.autocommit = True
            logger.debug("Autocommit activado en conexión MySQL")
        except AttributeError:
            # Fallback para drivers que usan método
            try:
                new_conn.autocommit(True)
                logger.debug("Autocommit activado en conexión MySQL (método)")
            except:
                logger.warning("No se pudo activar autocommit automáticamente")
        
        # Marcar conexión con el thread que la creó
        setattr(new_conn, "_owner_thread_ident", threading.get_ident())
        _set_tls_conn(new_conn)
        logger.info(f"Conexión MySQL establecida en thread {threading.current_thread().name}")
        return new_conn
    except Exception as e:
        logger.error(f"Error al conectar a DB: {e}")
        raise

def ensure_conn(conn=None, config_path="config.ini"):
    """Asegura que la conexión esté activa, reconecta si es necesario"""
    # Si no se pasó conexión, usar la del thread actual
    if conn is None:
        return get_db_connection(config_path)
    
    # Si la conexión pasada está viva, usarla
    if is_conn_alive(conn):
        return conn
    
    # Conexión caída, usar/crear la del thread actual
    logger.warning("Conexión pasada está caída, usando conexión del thread actual")
    return get_db_connection(config_path)

def _is_connection_error(e: Exception) -> bool:
    """Detecta si el error es de conexión perdida"""
    error_msg = str(e).lower()
    
    # Mensajes típicos de conexión perdida
    connection_errors = [
        "lost connection",
        "mysql server has gone away",
        "connection not available",
        "can't connect to mysql",
        "mysql connection not available"
    ]
    
    if any(err in error_msg for err in connection_errors):
        return True
    
    # Códigos de error MySQL típicos (2006, 2013)
    if hasattr(e, 'errno'):
        if e.errno in (2006, 2013):
            return True
    
    return False

@contextmanager
def get_cursor(conn, dictionary=True):
    """Context manager para cursores con reconexión automática"""
    conn = ensure_conn(conn)
    cursor = conn.cursor(dictionary=dictionary)
    try:
        yield cursor
    finally:
        cursor.close()

def with_reconnect(func):
    """Decorador para reintentar funciones si hay error de conexión"""
    def wrapper(*args, **kwargs):
        try:
            # Primer intento
            return func(*args, **kwargs)
        except Exception as e:
            # Si es error de conexión, reintentar una vez
            if _is_connection_error(e):
                logger.info(f"Reconnecting to MySQL in thread {threading.current_thread().name} due to: {e}")
                try:
                    # Forzar reconexión del thread actual
                    _set_tls_conn(None)
                    get_db_connection()
                    
                    # Reintentar función
                    logger.info(f"Retrying {func.__name__} after reconnection")
                    return func(*args, **kwargs)
                except Exception as retry_error:
                    logger.error(f"Error after reconnect in {func.__name__}: {retry_error}")
                    raise
            else:
                # No es error de conexión, re-lanzar
                raise
    
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    return wrapper

@with_reconnect
def get_available_turnos_columns(conn) -> List[str]:
    """Detecta columnas disponibles en sa_turnos (cacheado)"""
    conn = ensure_conn(conn)
    global _TURNOS_COLUMNS_CACHE
    if _TURNOS_COLUMNS_CACHE is not None:
        return _TURNOS_COLUMNS_CACHE
    
    with get_cursor(conn, dictionary=True) as cur:
        cur.execute("SHOW COLUMNS FROM sa_turnos")
        columns = [row["Field"] for row in cur.fetchall()]
        _TURNOS_COLUMNS_CACHE = columns
        logger.info(f"Columnas sa_turnos detectadas: {columns}")
        return columns

@with_reconnect
def get_available_conversaciones_columns(conn) -> List[str]:
    """Detecta columnas disponibles en sa_conversaciones (cacheado)"""
    conn = ensure_conn(conn)
    global _CONVERSACIONES_COLUMNS_CACHE
    if _CONVERSACIONES_COLUMNS_CACHE is not None:
        return _CONVERSACIONES_COLUMNS_CACHE
    
    with get_cursor(conn, dictionary=True) as cur:
        cur.execute("SHOW COLUMNS FROM sa_conversaciones")
        columns = [row["Field"] for row in cur.fetchall()]
        _CONVERSACIONES_COLUMNS_CACHE = columns
        logger.info(f"Columnas sa_conversaciones detectadas: {columns}")
        return columns

@with_reconnect
def tabla_existe(conn, tabla: str) -> bool:
    """Verifica si una tabla existe"""
    conn = ensure_conn(conn)
    try:
        with get_cursor(conn, dictionary=False) as cur:
            cur.execute(f"SHOW TABLES LIKE '{tabla}'")
            return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"Error verificando tabla {tabla}: {e}")
        return False

@with_reconnect
def listar_ejecuciones(conn) -> List[EjecucionInfo]:
    """Lista todas las ejecuciones con conteo de conversaciones"""
    conn = ensure_conn(conn)
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT ejecucion_id, COUNT(*) as num_conversaciones
                FROM sa_conversaciones
                GROUP BY ejecucion_id
                ORDER BY ejecucion_id
            """)
            rows = cur.fetchall()
            return [EjecucionInfo(
                ejecucion_id=r["ejecucion_id"],
                num_conversaciones=r["num_conversaciones"]
            ) for r in rows]
    except Exception as e:
        if _is_connection_error(e):
            raise
        logger.error(f"Error listando ejecuciones: {e}")
        return []

@with_reconnect
def stats_ejecucion(conn, ejecucion_id: int, conf_threshold: float = 0.08) -> StatsEjecucion:
    """Obtiene estadísticas de una ejecución específica"""
    conn = ensure_conn(conn)
    stats = StatsEjecucion(ejecucion_id=ejecucion_id)
    
    try:
        with get_cursor(conn) as cur:
            # Total conversaciones
            cur.execute("""
                SELECT COUNT(*) as total
                FROM sa_conversaciones
                WHERE ejecucion_id = %s
            """, (ejecucion_id,))
            stats.total_convs = cur.fetchone()["total"]
            
            # Total turnos, con fase, sin fase
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN t.fase IS NOT NULL AND TRIM(t.fase) != '' THEN 1 ELSE 0 END) as con_fase,
                    SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase) = '' THEN 1 ELSE 0 END) as sin_fase
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
            """, (ejecucion_id,))
            row = cur.fetchone()
            stats.total_turnos = row["total"]
            stats.turnos_con_fase = row["con_fase"]
            stats.turnos_sin_fase = row["sin_fase"]
            
            # Pendientes por confianza
            cur.execute(f"""
                SELECT COUNT(*) as pendientes
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND (t.fase IS NULL OR TRIM(t.fase) = '' 
                       OR t.fase_conf IS NULL OR t.fase_conf < {conf_threshold})
            """, (ejecucion_id,))
            stats.pendientes_por_conf = cur.fetchone()["pendientes"]
            
            # Distribución por fase
            cur.execute("""
                SELECT t.fase, COUNT(*) as count
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND t.fase IS NOT NULL AND TRIM(t.fase) != ''
                GROUP BY t.fase
                ORDER BY count DESC
            """, (ejecucion_id,))
            stats.dist_fase = [(r["fase"], r["count"]) for r in cur.fetchall()]
            
            # Distribución por fase_source
            cur.execute("""
                SELECT t.fase_source, COUNT(*) as count
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND t.fase_source IS NOT NULL
                GROUP BY t.fase_source
                ORDER BY count DESC
            """, (ejecucion_id,))
            stats.dist_fase_source = [(r["fase_source"], r["count"]) for r in cur.fetchall()]
            
            # Opcional: promesas
            if tabla_existe(conn, "sa_promesas_pago"):
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN monto IS NOT NULL THEN 1 ELSE 0 END) as con_monto,
                        SUM(CASE WHEN monto IS NULL THEN 1 ELSE 0 END) as sin_monto
                    FROM sa_promesas_pago p
                    JOIN sa_conversaciones c ON c.conversacion_pk = p.conversacion_pk
                    WHERE c.ejecucion_id = %s
                """, (ejecucion_id,))
                row = cur.fetchone()
                if row:
                    stats.total_promesas = row["total"] or 0
                    stats.promesas_con_monto = row["con_monto"] or 0
                    stats.promesas_sin_monto = row["sin_monto"] or 0
    
    except Exception as e:
        logger.error(f"Error obteniendo stats para ejecucion_id={ejecucion_id}: {e}")
    
    return stats

@with_reconnect
def stats_total(conn, ejecucion_ids: List[int], conf_threshold: float = 0.08) -> StatsEjecucion:
    """Obtiene estadísticas agregadas para múltiples ejecuciones"""
    conn = ensure_conn(conn)
    stats = StatsEjecucion(ejecucion_id=None)  # None = total
    
    if not ejecucion_ids:
        return stats
    
    placeholders = ",".join(["%s"] * len(ejecucion_ids))
    
    try:
        with get_cursor(conn) as cur:
            # Total conversaciones
            cur.execute(f"""
                SELECT COUNT(*) as total
                FROM sa_conversaciones
                WHERE ejecucion_id IN ({placeholders})
            """, tuple(ejecucion_ids))
            stats.total_convs = cur.fetchone()["total"]
            
            # Total turnos, con fase, sin fase
            cur.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN t.fase IS NOT NULL AND TRIM(t.fase) != '' THEN 1 ELSE 0 END) as con_fase,
                    SUM(CASE WHEN t.fase IS NULL OR TRIM(t.fase) = '' THEN 1 ELSE 0 END) as sin_fase
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id IN ({placeholders})
            """, tuple(ejecucion_ids))
            row = cur.fetchone()
            stats.total_turnos = row["total"]
            stats.turnos_con_fase = row["con_fase"]
            stats.turnos_sin_fase = row["sin_fase"]
            
            # Pendientes por confianza
            cur.execute(f"""
                SELECT COUNT(*) as pendientes
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id IN ({placeholders})
                  AND (t.fase IS NULL OR TRIM(t.fase) = '' 
                       OR t.fase_conf IS NULL OR t.fase_conf < {conf_threshold})
            """, tuple(ejecucion_ids))
            stats.pendientes_por_conf = cur.fetchone()["pendientes"]
            
            # Distribución por fase
            cur.execute(f"""
                SELECT t.fase, COUNT(*) as count
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id IN ({placeholders})
                  AND t.fase IS NOT NULL AND TRIM(t.fase) != ''
                GROUP BY t.fase
                ORDER BY count DESC
            """, tuple(ejecucion_ids))
            stats.dist_fase = [(r["fase"], r["count"]) for r in cur.fetchall()]
            
            # Distribución por fase_source
            cur.execute(f"""
                SELECT t.fase_source, COUNT(*) as count
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id IN ({placeholders})
                  AND t.fase_source IS NOT NULL
                GROUP BY t.fase_source
                ORDER BY count DESC
            """, tuple(ejecucion_ids))
            stats.dist_fase_source = [(r["fase_source"], r["count"]) for r in cur.fetchall()]
            
            # Opcional: promesas
            if tabla_existe(conn, "sa_promesas_pago"):
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN monto IS NOT NULL THEN 1 ELSE 0 END) as con_monto,
                        SUM(CASE WHEN monto IS NULL THEN 1 ELSE 0 END) as sin_monto
                    FROM sa_promesas_pago p
                    JOIN sa_conversaciones c ON c.conversacion_pk = p.conversacion_pk
                    WHERE c.ejecucion_id IN ({placeholders})
                """, tuple(ejecucion_ids))
                row = cur.fetchone()
                if row:
                    stats.total_promesas = row["total"] or 0
                    stats.promesas_con_monto = row["con_monto"] or 0
                    stats.promesas_sin_monto = row["sin_monto"] or 0
    
    except Exception as e:
        logger.error(f"Error obteniendo stats totales: {e}")
    
    return stats

@with_reconnect
def listar_conversaciones(conn, ejecucion_id: int, search: str = "", limit: int = 500) -> List[Conversacion]:
    """Lista conversaciones de una ejecución con búsqueda opcional"""
    conn = ensure_conn(conn)
    try:
        cols = get_available_conversaciones_columns(conn)
        has_conv_id = "conversacion_id" in cols
        
        with get_cursor(conn) as cur:
            if search and has_conv_id:
                cur.execute(f"""
                    SELECT conversacion_pk, conversacion_id, ejecucion_id
                    FROM sa_conversaciones
                    WHERE ejecucion_id = %s
                      AND conversacion_id LIKE %s
                    ORDER BY conversacion_pk DESC
                    LIMIT {limit}
                """, (ejecucion_id, f"%{search}%"))
            elif search:
                # Buscar por pk si no existe conversacion_id
                try:
                    pk_search = int(search)
                    cur.execute(f"""
                        SELECT conversacion_pk, ejecucion_id
                        FROM sa_conversaciones
                        WHERE ejecucion_id = %s
                          AND conversacion_pk = %s
                        LIMIT {limit}
                    """, (ejecucion_id, pk_search))
                except ValueError:
                    # No es número, retornar vacío
                    return []
            else:
                if has_conv_id:
                    cur.execute(f"""
                        SELECT conversacion_pk, conversacion_id, ejecucion_id
                        FROM sa_conversaciones
                        WHERE ejecucion_id = %s
                        ORDER BY conversacion_pk DESC
                        LIMIT {limit}
                    """, (ejecucion_id,))
                else:
                    cur.execute(f"""
                        SELECT conversacion_pk, ejecucion_id
                        FROM sa_conversaciones
                        WHERE ejecucion_id = %s
                        ORDER BY conversacion_pk DESC
                        LIMIT {limit}
                    """, (ejecucion_id,))
            
            rows = cur.fetchall()
            return [Conversacion(
                conversacion_pk=r["conversacion_pk"],
                conversacion_id=r.get("conversacion_id"),
                ejecucion_id=r["ejecucion_id"]
            ) for r in rows]
    
    except Exception as e:
        logger.error(f"Error listando conversaciones: {e}")
        return []

@with_reconnect
def listar_turnos(conn, conversacion_pk: int) -> List[Turno]:
    """Lista turnos de una conversación"""
    conn = ensure_conn(conn)
    try:
        cols = get_available_turnos_columns(conn)
        
        # Construir SELECT dinámico con columnas disponibles
        base_cols = ["turno_pk", "conversacion_pk", "turno_idx"]
        optional_cols = ["speaker", "text", "fase", "fase_source", "fase_conf", "intent", "intent_conf", "fase_seq"]
        select_cols = base_cols + [c for c in optional_cols if c in cols]
        
        with get_cursor(conn) as cur:
            cur.execute(f"""
                SELECT {", ".join(select_cols)}
                FROM sa_turnos
                WHERE conversacion_pk = %s
                ORDER BY turno_idx
            """, (conversacion_pk,))
            
            rows = cur.fetchall()
            return [Turno(
                turno_pk=r["turno_pk"],
                conversacion_pk=r["conversacion_pk"],
                turno_idx=r["turno_idx"],
                speaker=r.get("speaker"),
                text=r.get("text"),
                fase=r.get("fase"),
                fase_source=r.get("fase_source"),
                fase_conf=r.get("fase_conf"),
                intent=r.get("intent"),
                intent_conf=r.get("intent_conf"),
                fase_seq=r.get("fase_seq")
            ) for r in rows]
    
    except Exception as e:
        logger.error(f"Error listando turnos: {e}")
        return []

@with_reconnect
def listar_turnos_pendientes(conn, ejecucion_id: int, conf_threshold: float = 0.08, 
                             offset: int = 0, limit: int = 200) -> List[Turno]:
    """Lista turnos pendientes de clasificación con paginación"""
    conn = ensure_conn(conn)
    try:
        cols = get_available_turnos_columns(conn)
        
        base_cols = ["t.turno_pk", "t.conversacion_pk", "t.turno_idx"]
        optional_cols = ["speaker", "text", "fase", "fase_source", "fase_conf", "intent", "intent_conf"]
        select_cols = base_cols + [f"t.{c}" for c in optional_cols if c in cols]
        
        with get_cursor(conn) as cur:
            cur.execute(f"""
                SELECT {", ".join(select_cols)}
                FROM sa_turnos t
                JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
                WHERE c.ejecucion_id = %s
                  AND (t.fase IS NULL OR TRIM(t.fase) = '' 
                       OR t.fase_conf IS NULL OR t.fase_conf < {conf_threshold})
                ORDER BY t.conversacion_pk, t.turno_idx
                LIMIT {limit} OFFSET {offset}
            """, (ejecucion_id,))
            
            rows = cur.fetchall()
            return [Turno(
                turno_pk=r["turno_pk"],
                conversacion_pk=r["conversacion_pk"],
                turno_idx=r["turno_idx"],
                speaker=r.get("speaker"),
                text=r.get("text"),
                fase=r.get("fase"),
                fase_source=r.get("fase_source"),
                fase_conf=r.get("fase_conf"),
                intent=r.get("intent"),
                intent_conf=r.get("intent_conf")
            ) for r in rows]
    
    except Exception as e:
        logger.error(f"Error listando turnos pendientes: {e}")
        return []

@with_reconnect
def aplicar_correccion_turno(conn, conversacion_pk: int, turno_idx: int, 
                             fase_nueva: str, intent_nuevo: Optional[str] = None,
                             commit: bool = True) -> bool:
    """Aplica corrección humana a un turno en la BD"""
    conn = ensure_conn(conn)
    try:
        cols = get_available_turnos_columns(conn)
        has_intent = "intent" in cols
        has_intent_conf = "intent_conf" in cols
        
        with get_cursor(conn, dictionary=False) as cur:
            if intent_nuevo and has_intent:
                if has_intent_conf:
                    cur.execute("""
                        UPDATE sa_turnos
                        SET fase = %s, fase_source = 'HUMAN', fase_conf = 1.0,
                            intent = %s, intent_conf = 1.0
                        WHERE conversacion_pk = %s AND turno_idx = %s
                    """, (fase_nueva, intent_nuevo, conversacion_pk, turno_idx))
                else:
                    cur.execute("""
                        UPDATE sa_turnos
                        SET fase = %s, fase_source = 'HUMAN', fase_conf = 1.0,
                            intent = %s
                        WHERE conversacion_pk = %s AND turno_idx = %s
                    """, (fase_nueva, intent_nuevo, conversacion_pk, turno_idx))
            else:
                cur.execute("""
                    UPDATE sa_turnos
                    SET fase = %s, fase_source = 'HUMAN', fase_conf = 1.0
                    WHERE conversacion_pk = %s AND turno_idx = %s
                """, (fase_nueva, conversacion_pk, turno_idx))
            
            if commit:
                conn.commit()
            
            return True
    
    except Exception as e:
        logger.error(f"Error aplicando corrección: {e}")
        conn.rollback()
        return False

@with_reconnect
def get_fases_disponibles(conn) -> List[str]:
    """Obtiene lista de fases únicas existentes en la BD"""
    conn = ensure_conn(conn)
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT DISTINCT fase
                FROM sa_turnos
                WHERE fase IS NOT NULL AND TRIM(fase) != ''
                ORDER BY fase
            """)
            return [r["fase"] for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error obteniendo fases: {e}")
        return []

@with_reconnect
def listar_secuencias_ejecucion(conn, ejecucion_id: int) -> List[SecuenciaInfo]:
    """Lista secuencias de conversaciones para una ejecución"""
    conn = ensure_conn(conn)
    
    # Rollback para limpiar transacciones viejas y ver commits recientes
    try:
        conn.rollback()
    except:
        pass
    
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT 
                    s.conversacion_pk,
                    c.conversacion_id,
                    s.secuencia_macro,
                    s.fase_inicio,
                    s.fase_fin,
                    s.violaciones_transicion,
                    s.cumple_secuencia,
                    s.inicio_valido,
                    s.corte_antes_negociacion,
                    s.tiene_negociacion,
                    s.tiene_informacion_deuda
                FROM sa_conversacion_secuencias s
                JOIN sa_conversaciones c ON c.conversacion_pk = s.conversacion_pk
                WHERE s.ejecucion_id = %s
                ORDER BY s.cumple_secuencia DESC, s.violaciones_transicion ASC
            """, (ejecucion_id,))
            
            rows = cur.fetchall()
            return [SecuenciaInfo(
                conversacion_pk=r["conversacion_pk"],
                conversacion_id=r["conversacion_id"],
                secuencia_macro=r["secuencia_macro"],
                fase_inicio=r.get("fase_inicio"),
                fase_fin=r.get("fase_fin"),
                violaciones_transicion=r.get("violaciones_transicion", 0),
                cumple_secuencia=r.get("cumple_secuencia", 0),
                inicio_valido=r.get("inicio_valido", 0),
                corte_antes_negociacion=r.get("corte_antes_negociacion", 0),
                tiene_negociacion=r.get("tiene_negociacion", 0),
                tiene_informacion_deuda=r.get("tiene_informacion_deuda", 0)
            ) for r in rows]
    
    except Exception as e:
        logger.error(f"Error listando secuencias: {e}")
        return []

@with_reconnect
def get_secuencia_kpis(conn, ejecucion_id: int) -> Optional[SecuenciaKPIs]:
    """Obtiene KPIs agregados de secuencias para una ejecución"""
    conn = ensure_conn(conn)
    
    # Rollback para limpiar transacciones viejas y ver commits recientes
    try:
        conn.rollback()
    except:
        pass
    
    try:
        with get_cursor(conn) as cur:
            cur.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(inicio_valido) as inicio_valido_count,
                    SUM(cumple_secuencia) as cumple_count,
                    SUM(corte_antes_negociacion) as corte_count,
                    AVG(violaciones_transicion) as avg_violaciones
                FROM sa_conversacion_secuencias
                WHERE ejecucion_id = %s
            """, (ejecucion_id,))
            
            row = cur.fetchone()
            if not row or row["total"] == 0:
                return None
            
            total = row["total"]
            return SecuenciaKPIs(
                total=total,
                pct_inicio_valido=(row["inicio_valido_count"] or 0) / total * 100,
                pct_cumple=(row["cumple_count"] or 0) / total * 100,
                pct_corte_antes_negociacion=(row["corte_count"] or 0) / total * 100,
                avg_violaciones=row["avg_violaciones"] or 0.0
            )
    
    except Exception as e:
        logger.error(f"Error obteniendo KPIs de secuencias: {e}")
        return None

@with_reconnect
def get_turnos_context(conn, conversacion_pk: int, turno_idx: int, window: int = 3) -> List[Dict[str, Any]]:
    """Obtiene contexto de turnos (anteriores + seleccionado + posteriores)
    
    Args:
        conn: Conexión a BD
        conversacion_pk: PK de la conversación
        turno_idx: Índice del turno central
        window: Número de turnos antes y después (default: 3)
    
    Returns:
        Lista de dicts con turnos en rango [turno_idx-window, turno_idx+window]
    """
    conn = ensure_conn(conn)
    try:
        cols = get_available_turnos_columns(conn)
        
        # Construir SELECT con columnas disponibles y aliases estándar
        # Base: conversacion_pk, turno_idx
        select_parts = ["conversacion_pk", "turno_idx"]
        
        # Speaker: preferir 'speaker', 'hablante'
        if "speaker" in cols:
            select_parts.append("speaker")
        elif "hablante" in cols:
            select_parts.append("hablante AS speaker")
        else:
            select_parts.append("NULL AS speaker")
        
        # Texto: preferir 'text', 'texto', 'utterance', 'contenido'
        text_col = None
        for col in ["text", "texto", "utterance", "contenido"]:
            if col in cols:
                text_col = col
                break
        
        if text_col and text_col != "text":
            select_parts.append(f"{text_col} AS text")
        elif text_col:
            select_parts.append("text")
        else:
            select_parts.append("NULL AS text")
        
        # Fase, fase_source, fase_conf, intent
        for col in ["fase", "fase_source", "fase_conf", "intent", "intent_conf"]:
            if col in cols:
                select_parts.append(col)
            else:
                select_parts.append(f"NULL AS {col}")
        
        # Calcular rango
        from_idx = max(1, turno_idx - window)
        to_idx = turno_idx + window
        
        with get_cursor(conn) as cur:
            query = f"""
                SELECT {', '.join(select_parts)}
                FROM sa_turnos
                WHERE conversacion_pk = %s
                  AND turno_idx BETWEEN %s AND %s
                ORDER BY turno_idx
            """
            cur.execute(query, (conversacion_pk, from_idx, to_idx))
            return cur.fetchall()
    
    except Exception as e:
        logger.error(f"Error obteniendo contexto de turnos: {e}")
        return []


def generar_secuencias(conn, ejecucion_id: int, config_path: str = "config.ini") -> Dict[str, Any]:
    """
    Genera secuencias para una ejecución (ejecuta build_fase_seq y build_secuencias).
    
    Args:
        conn: Conexión a la base de datos (no se usa, cada script abre su propia conexión)
        ejecucion_id: ID de la ejecución a procesar
        config_path: Ruta al archivo de configuración
    
    Returns:
        dict con estadísticas del proceso
    
    Raises:
        Exception si hay errores en alguno de los procesos
    """
    from scripts.build_fase_seq import run_build_fase_seq
    from scripts.build_secuencias import run_build_secuencias
    
    logger.info(f"Generando secuencias para ejecucion_id={ejecucion_id}")
    
    try:
        # Paso 1: Construir fase_seq
        logger.info("Paso 1/2: Construyendo fase_seq...")
        stats_fase_seq = run_build_fase_seq(config_path, ejecucion_id)
        logger.info(f"Fase_seq completada: {stats_fase_seq}")
        
        # Paso 2: Construir análisis de secuencias
        logger.info("Paso 2/2: Construyendo análisis de secuencias...")
        stats_secuencias = run_build_secuencias(config_path, ejecucion_id, verbose=False)
        logger.info(f"Análisis de secuencias completado: {stats_secuencias}")
        
        return {
            'success': True,
            'fase_seq_stats': stats_fase_seq,
            'secuencias_stats': stats_secuencias,
            'message': 'Secuencias generadas correctamente'
        }
    
    except Exception as e:
        logger.error(f"Error generando secuencias: {e}", exc_info=True)
        raise
