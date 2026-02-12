"""
Funciones de importación para la UI
"""
import os
import logging
from typing import List
from sa_core.config import load_config
from sa_core.db import get_conn
from sa_core.ingest import ingest_dir

logger = logging.getLogger(__name__)


def run_import_from_folder(config_path: str, input_dir: str, notas: str = "UI import") -> int:
    """
    Importa todos los archivos .txt de una carpeta a la BD
    
    Args:
        config_path: Ruta al config.ini
        input_dir: Directorio con archivos .txt
        notas: Notas para la ejecución
    
    Returns:
        ejecucion_id creado
    
    Raises:
        Exception si falla la importación
    """
    try:
        cfg = load_config(config_path)
        conn = get_conn(cfg)
        
        logger.info(f"Iniciando importación desde carpeta: {input_dir}")
        ejecucion_id, inserted_count = ingest_dir(conn, input_dir, notas)
        
        conn.close()
        
        if ejecucion_id:
            logger.info(f"Importación exitosa: ejecucion_id={ejecucion_id}, archivos={inserted_count}")
            return ejecucion_id
        else:
            raise Exception("Error en ingest_dir: no se pudo crear ejecución")
    
    except Exception as e:
        logger.error(f"Error importando desde carpeta: {e}")
        raise


def run_import_from_files(config_path: str, files: List[str], notas: str = "UI import (archivos)") -> int:
    """
    Importa archivos específicos a la BD creando una ejecución temporal
    
    Args:
        config_path: Ruta al config.ini
        files: Lista de rutas absolutas a archivos
        notas: Notas para la ejecución
    
    Returns:
        ejecucion_id creado
    
    Raises:
        Exception si falla la importación
    """
    if not files:
        raise ValueError("No se proporcionaron archivos para importar")
    
    try:
        cfg = load_config(config_path)
        conn = get_conn(cfg)
        cursor = conn.cursor()
        
        # Crear ejecución
        input_dir_info = f"{len(files)} archivos seleccionados"
        cursor.execute(
            "INSERT INTO sa_ejecuciones (notas, input_dir) VALUES (%s, %s)",
            (notas, input_dir_info)
        )
        ejecucion_id = cursor.lastrowid
        
        logger.info(f"Creada ejecución {ejecucion_id} para {len(files)} archivos")
        
        # Insertar cada archivo
        inserted_count = 0
        for file_path in files:
            try:
                # Leer archivo
                raw_text = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_text = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        raw_text = f.read()
                    logger.warning(f"Fallback a latin-1 para {file_path}")
                
                # Insertar conversación
                filename = os.path.basename(file_path)
                cursor.execute(
                    """
                    INSERT INTO sa_conversaciones 
                    (ejecucion_id, conversacion_id, raw_path, raw_text, total_turnos)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (ejecucion_id, filename, file_path, raw_text, 0)
                )
                inserted_count += 1
                
            except Exception as e:
                logger.error(f"Error procesando {file_path}: {e}")
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        
        logger.info(f"Importación exitosa: ejecucion_id={ejecucion_id}, archivos={inserted_count}/{len(files)}")
        
        if inserted_count == 0:
            raise Exception("No se pudo importar ningún archivo")
        
        return ejecucion_id
    
    except Exception as e:
        logger.error(f"Error importando archivos: {e}")
        raise
