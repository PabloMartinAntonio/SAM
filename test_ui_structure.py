"""
Script de validación de la UI (sin ejecutar el mainloop)
Verifica imports y estructura básica
"""
import sys

def test_imports():
    """Verifica que todos los módulos se importen correctamente"""
    try:
        print("Importando módulos UI...")
        import ui.app
        import ui.services
        import ui.models
        import ui.views_dashboard
        import ui.views_detalles
        import ui.views_aprendizaje
        print("✓ Todos los módulos importados correctamente\n")
        return True
    except Exception as e:
        print(f"✗ Error importando módulos: {e}")
        return False

def test_models():
    """Verifica que los modelos se puedan instanciar"""
    try:
        print("Probando modelos...")
        from ui.models import EjecucionInfo, StatsEjecucion, Conversacion, Turno, CorreccionTurno
        
        ej = EjecucionInfo(ejecucion_id=1, num_conversaciones=10)
        stats = StatsEjecucion(ejecucion_id=1)
        conv = Conversacion(conversacion_pk=1)
        turno = Turno(turno_pk=1, conversacion_pk=1, turno_idx=1)
        corr = CorreccionTurno(conversacion_pk=1, turno_idx=1, fase_nueva="TEST")
        
        print("✓ Todos los modelos instanciados correctamente\n")
        return True
    except Exception as e:
        print(f"✗ Error con modelos: {e}")
        return False

def test_structure():
    """Verifica estructura de archivos"""
    from pathlib import Path
    
    print("Verificando estructura de archivos...")
    required_files = [
        "run_ui.py",
        "ui/__init__.py",
        "ui/app.py",
        "ui/services.py",
        "ui/models.py",
        "ui/views_dashboard.py",
        "ui/views_detalles.py",
        "ui/views_aprendizaje.py",
    ]
    
    all_ok = True
    for filepath in required_files:
        path = Path(filepath)
        if path.exists():
            print(f"  ✓ {filepath}")
        else:
            print(f"  ✗ {filepath} NO EXISTE")
            all_ok = False
    
    print()
    return all_ok

if __name__ == "__main__":
    print("=" * 60)
    print("VALIDACIÓN DE UI - Speech Analytics")
    print("=" * 60)
    print()
    
    tests = [
        ("Estructura de archivos", test_structure),
        ("Imports de módulos", test_imports),
        ("Instanciación de modelos", test_models),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"--- {name} ---")
        result = test_func()
        results.append((name, result))
    
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    
    all_passed = True
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:10s} {name}")
        if not result:
            all_passed = False
    
    print()
    if all_passed:
        print("✓✓✓ TODOS LOS TESTS PASARON ✓✓✓")
        print("\nPara ejecutar la UI:")
        print("  python run_ui.py")
        sys.exit(0)
    else:
        print("✗✗✗ ALGUNOS TESTS FALLARON ✗✗✗")
        sys.exit(1)
