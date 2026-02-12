"""
Inicializa la tabla de mapeo de subfases a macrofases.

Crea la tabla sa_fase_macro_map si no existe e inserta los mapeos base.
"""
import sys
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


# Mapeos de subfases a macrofases (8 macrofases)
FASE_MACRO_MAPPINGS = {
    'APERTURA': 'APERTURA',
    'IDENTIFICACION': 'IDENTIFICACION',
    'INFORMACION_DEUDA': 'INFORMACION_DEUDA',
    'NEGOCIACION': 'NEGOCIACION',
    'CONSULTA_ACEPTACION': 'CONSULTA_ACEPTACION',
    'FORMALIZACION_PAGO': 'FORMALIZACION_PAGO',
    'ADVERTENCIAS': 'ADVERTENCIAS',
    'CIERRE': 'CIERRE',
    'OFERTA_PAGO': 'NEGOCIACION',  # Subfase que mapea a NEGOCIACION
}


def create_table_if_not_exists(conn):
    """Crea la tabla sa_fase_macro_map si no existe"""
    cursor = conn.cursor()
    
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS sa_fase_macro_map (
        fase VARCHAR(64) PRIMARY KEY,
        macro_fase VARCHAR(64) NOT NULL,
        INDEX idx_macro_fase (macro_fase)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
    
    try:
        cursor.execute(create_table_sql)
        conn.commit()
        logger.info("✓ Tabla sa_fase_macro_map verificada/creada")
    except Exception as e:
        logger.error(f"Error creando tabla: {e}")
        raise
    finally:
        cursor.close()


def upsert_mappings(conn, mappings):
    """Inserta o actualiza los mapeos de fases"""
    cursor = conn.cursor()
    
    # MySQL: INSERT ... ON DUPLICATE KEY UPDATE
    upsert_sql = """
    INSERT INTO sa_fase_macro_map (fase, macro_fase)
    VALUES (%s, %s)
    ON DUPLICATE KEY UPDATE macro_fase = VALUES(macro_fase)
    """
    
    try:
        data = [(fase, macro_fase) for fase, macro_fase in mappings.items()]
        cursor.executemany(upsert_sql, data)
        conn.commit()
        
        logger.info(f"✓ {len(data)} mapeos insertados/actualizados")
        return len(data)
    
    except Exception as e:
        logger.error(f"Error insertando mapeos: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()


def print_current_mappings(conn):
    """Imprime el estado actual de los mapeos"""
    cursor = conn.cursor(dictionary=True)
    
    try:
        cursor.execute("""
            SELECT fase, macro_fase 
            FROM sa_fase_macro_map 
            ORDER BY macro_fase, fase
        """)
        
        mappings = cursor.fetchall()
        
        if not mappings:
            logger.info("No hay mapeos registrados")
            return
        
        # Agrupar por macro_fase
        from collections import defaultdict
        by_macro = defaultdict(list)
        for m in mappings:
            by_macro[m['macro_fase']].append(m['fase'])
        
        print("\n" + "="*60)
        print("MAPEO DE SUBFASES A MACROFASES")
        print("="*60)
        
        for macro_fase in sorted(by_macro.keys()):
            subfases = by_macro[macro_fase]
            print(f"\n{macro_fase}:")
            for subfase in sorted(subfases):
                if subfase == macro_fase:
                    print(f"  • {subfase} (identidad)")
                else:
                    print(f"  • {subfase} → {macro_fase}")
        
        print("\n" + "="*60)
        print(f"Total: {len(mappings)} mapeos registrados")
        print("="*60 + "\n")
    
    finally:
        cursor.close()


def main():
    """Función principal"""
    config_path = Path(__file__).parent.parent / "config.ini"
    
    if not config_path.exists():
        logger.error(f"Archivo de configuración no encontrado: {config_path}")
        sys.exit(1)
    
    logger.info(f"Cargando configuración desde {config_path}")
    cfg = load_config(str(config_path))
    
    logger.info("Conectando a la base de datos...")
    conn = get_conn(cfg)
    
    try:
        # 1. Crear tabla si no existe
        create_table_if_not_exists(conn)
        
        # 2. Insertar/actualizar mapeos base
        logger.info("Insertando mapeos base...")
        count = upsert_mappings(conn, FASE_MACRO_MAPPINGS)
        
        # 3. Imprimir resumen
        print_current_mappings(conn)
        
        logger.info("✅ Inicialización completada exitosamente")
    
    except Exception as e:
        logger.error(f"❌ Error durante la inicialización: {e}", exc_info=True)
        sys.exit(1)
    
    finally:
        if conn:
            conn.close()
            logger.info("Conexión cerrada")


if __name__ == "__main__":
    main()
