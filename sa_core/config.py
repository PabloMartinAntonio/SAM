import configparser
import os

def load_config(path='config.ini'):
    if not os.path.exists(path):
        raise FileNotFoundError(f"El archivo de configuración '{path}' no fue encontrado.")
    
    config = configparser.ConfigParser()
    config.read(path)
    return config
