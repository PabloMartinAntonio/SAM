"""
Test de estructura de la vista DeepSeek
"""
import sys
from pathlib import Path

def test_imports():
    """Test 1: Verifica que los imports funcionen"""
    try:
        from ui.views_deepseek import DeepSeekView
        print("✓ Test 1: Imports OK")
        return True
    except Exception as e:
        print(f"✗ Test 1: Error en imports - {e}")
        return False

def test_config_detection():
    """Test 2: Verifica detección de sección DB"""
    try:
        import configparser
        from pathlib import Path
        
        config_file = Path("config.ini")
        if not config_file.exists():
            print("⚠ Test 2: config.ini no existe, saltando test")
            return True
        
        config = configparser.ConfigParser()
        config.read(config_file, encoding="utf-8")
        
        # Buscar sección DB
        db_section = None
        for section in config.sections():
            if config.has_option(section, "host") and \
               (config.has_option(section, "database") or config.has_option(section, "db")):
                db_section = section
                break
        
        if db_section:
            print(f"✓ Test 2: Sección DB detectada: [{db_section}]")
            return True
        else:
            print("⚠ Test 2: No se detectó sección DB (se creará [mysql])")
            return True
    except Exception as e:
        print(f"✗ Test 2: Error en detección de sección - {e}")
        return False

def test_prompt_file():
    """Test 3: Verifica estructura de carpeta prompts"""
    try:
        from pathlib import Path
        
        prompt_dir = Path("prompts")
        prompt_file = prompt_dir / "deepseek_prompt.txt"
        
        if prompt_file.exists():
            print(f"✓ Test 3: Archivo de prompt existe: {prompt_file}")
        else:
            print(f"ℹ Test 3: Archivo de prompt no existe (se puede crear desde la UI)")
        
        return True
    except Exception as e:
        print(f"✗ Test 3: Error verificando prompt - {e}")
        return False

def test_ui_creation():
    """Test 4: Verifica que la vista se puede instanciar"""
    try:
        import tkinter as tk
        from tkinter import ttk
        from ui.views_deepseek import DeepSeekView
        
        # Crear root temporal
        root = tk.Tk()
        root.withdraw()  # Ocultar ventana
        
        # Crear notebook temporal
        notebook = ttk.Notebook(root)
        
        # Instanciar vista (con db_conn=None para test)
        view = DeepSeekView(notebook, db_conn=None)
        
        # Verificar que tiene los widgets esperados
        assert hasattr(view, 'prompt_text'), "Falta widget prompt_text"
        assert hasattr(view, 'api_key_var'), "Falta variable api_key_var"
        assert hasattr(view, 'db_host_var'), "Falta variable db_host_var"
        
        root.destroy()
        
        print("✓ Test 4: Vista se puede instanciar correctamente")
        return True
    except Exception as e:
        print(f"✗ Test 4: Error instanciando vista - {e}")
        return False

def test_config_preservation():
    """Test 5: Verifica que configparser preserva secciones existentes"""
    try:
        import configparser
        from pathlib import Path
        import tempfile
        
        # Crear config temporal
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.ini') as f:
            f.write("[mysql]\n")
            f.write("host=localhost\n")
            f.write("database=test\n")
            f.write("\n")
            f.write("[app]\n")
            f.write("conf_threshold=0.8\n")
            temp_path = f.name
        
        # Leer y agregar sección deepseek
        config = configparser.ConfigParser()
        config.read(temp_path, encoding="utf-8")
        
        if not config.has_section("deepseek"):
            config.add_section("deepseek")
        config.set("deepseek", "api_key", "test_key")
        
        # Guardar
        with open(temp_path, "w", encoding="utf-8") as f:
            config.write(f)
        
        # Verificar que las secciones originales siguen ahí
        config2 = configparser.ConfigParser()
        config2.read(temp_path, encoding="utf-8")
        
        assert config2.has_section("mysql"), "Sección [mysql] perdida"
        assert config2.has_section("app"), "Sección [app] perdida"
        assert config2.has_section("deepseek"), "Sección [deepseek] no creada"
        assert config2.get("mysql", "host") == "localhost", "Valor host perdido"
        assert config2.get("deepseek", "api_key") == "test_key", "Valor api_key incorrecto"
        
        # Limpiar
        Path(temp_path).unlink()
        
        print("✓ Test 5: configparser preserva secciones existentes")
        return True
    except Exception as e:
        print(f"✗ Test 5: Error en preservación de config - {e}")
        return False

def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("TEST: Vista DeepSeek")
    print("=" * 70)
    print()
    
    tests = [
        test_imports,
        test_config_detection,
        test_prompt_file,
        test_ui_creation,
        test_config_preservation
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Error ejecutando {test.__name__}: {e}")
            results.append(False)
        print()
    
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"RESULTADO: {passed}/{total} tests pasados")
    
    if passed == total:
        print("✓ TODOS LOS TESTS PASARON")
    else:
        print("✗ ALGUNOS TESTS FALLARON")
    
    print("=" * 70)
    
    return all(results)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
