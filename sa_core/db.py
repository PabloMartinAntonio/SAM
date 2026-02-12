import mysql.connector
from mysql.connector import Error
import os

def get_conn(config):
    try:
        conn = mysql.connector.connect(
            host=config['mysql']['host'],
            port=config['mysql']['port'],
            user=config['mysql']['user'],
            password=config['mysql']['password'],
            database=config['mysql']['database']
        )
        return conn
    except Error as e:
        print(f"Error al conectar a MySQL: {e}")
        return None

def ensure_schema(conn):
    cursor = conn.cursor()
    schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
    with open(schema_path, 'r') as f:
        sql_script = f.read()
    
    # Simple split by ';', might fail with complex statements
    # A more robust solution would parse the SQL properly
    for statement in sql_script.split(';'):
        statement = statement.strip()
        if statement:
            try:
                cursor.execute(statement)
            except Error as e:
                # Ignore "table already exists" errors
                if e.errno != 1050:
                    print(f"Error ejecutando statement: {statement}\n{e}")
    conn.commit()
    cursor.close()
