import os
from mysql.connector import Error

def ingest_dir(conn, input_dir, notas):
    cursor = conn.cursor()
    try:
        # 1. Crear una ejecución
        cursor.execute("INSERT INTO sa_ejecuciones (notas, input_dir) VALUES (%s, %s)", (notas, input_dir))
        ejecucion_id = cursor.lastrowid
        
        print(f"Creada ejecución con ID: {ejecucion_id}")

        # 2. Recorrer archivos .txt
        inserted_count = 0
        for filename in os.listdir(input_dir):
            if filename.endswith(".txt"):
                file_path = os.path.join(input_dir, filename)
                
                # 3. Leer contenido del archivo
                raw_text = ''
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_text = f.read()
                except UnicodeDecodeError:
                    try:
                        with open(file_path, 'r', encoding='latin-1') as f:
                            raw_text = f.read()
                        print(f"Warning: Fallback a latin-1 para el archivo {filename}")
                    except Exception as e:
                        print(f"Error al leer el archivo {filename} con fallback: {e}")
                        continue
                except Exception as e:
                    print(f"Error al leer el archivo {filename}: {e}")
                    continue

                # 4. Insertar en sa_conversaciones
                try:
                    cursor.execute(
                        """
                        INSERT INTO sa_conversaciones 
                        (ejecucion_id, conversacion_id, raw_path, raw_text, total_turnos)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (ejecucion_id, filename, file_path, raw_text, 0)
                    )
                    inserted_count += 1
                except Error as e:
                    print(f"Error insertando conversación {filename}: {e}")

        # 5. Commit y resumen
        conn.commit()
        print("\n--- Resumen de Ingesta ---")
        print(f"ID de Ejecución: {ejecucion_id}")
        print(f"Total de archivos insertados: {inserted_count}")
        
        return ejecucion_id, inserted_count

    except Error as e:
        conn.rollback()
        print(f"Error durante la ingesta. Rollback realizado. Error: {e}")
        return None, 0
    finally:
        cursor.close()
