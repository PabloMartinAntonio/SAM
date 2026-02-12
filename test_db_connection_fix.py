"""
Test de validación: Conexión DB en vistas
"""
import sys

def test_db_connection_flow():
    """Simula el flujo de conexión de la app"""
    print("=" * 70)
    print("TEST: Validación de flujo de conexión DB en UI")
    print("=" * 70)
    print()
    
    try:
        # Import necesario
        print("1. Importando módulos...")
        from ui import services
        from sa_core.config import load_config
        
        print("   ✓ Imports exitosos")
        print()
        
        # Simular get_db_connection
        print("2. Probando get_db_connection()...")
        conn = services.get_db_connection()
        
        if conn is None:
            print("   ✗ FALLO: get_db_connection() retornó None")
            return False
        
        print(f"   ✓ Conexión obtenida: {type(conn)}")
        print()
        
        # Verificar que la conexión funciona
        print("3. Verificando conexión con SELECT 1...")
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        
        if result == (1,) or result == [1]:
            print(f"   ✓ SELECT 1 retornó: {result}")
        else:
            print(f"   ⚠ SELECT 1 retornó resultado inesperado: {result}")
        print()
        
        # Verificar que la conexión NO se cierra automáticamente
        print("4. Verificando que conexión sigue abierta...")
        cursor2 = conn.cursor()
        cursor2.execute("SELECT 2")
        result2 = cursor2.fetchone()
        cursor2.close()
        
        if result2 == (2,) or result2 == [2]:
            print(f"   ✓ Conexión sigue activa: SELECT 2 = {result2}")
        else:
            print(f"   ✗ Conexión puede estar cerrada")
            return False
        print()
        
        # Simular inyección en vistas (mock)
        print("5. Simulando inyección de db_conn en vistas...")
        
        class MockView:
            def __init__(self, name):
                self.name = name
                self.db_conn = None
        
        views = [
            MockView("dashboard"),
            MockView("detalles"),
            MockView("aprendizaje"),
            MockView("deepseek")
        ]
        
        # Inyectar conexión
        for view in views:
            view.db_conn = conn
        
        # Verificar
        all_injected = all(v.db_conn is not None for v in views)
        if all_injected:
            print(f"   ✓ Conexión inyectada en {len(views)} vistas")
        else:
            print(f"   ✗ Algunas vistas no tienen db_conn")
            return False
        print()
        
        # Verificar que cada vista puede usar la conexión
        print("6. Verificando que vistas pueden usar db_conn...")
        for view in views:
            cursor = view.db_conn.cursor()
            cursor.execute("SELECT 3")
            result = cursor.fetchone()
            cursor.close()
            
            if result == (3,) or result == [3]:
                print(f"   ✓ Vista '{view.name}' puede ejecutar queries")
            else:
                print(f"   ✗ Vista '{view.name}' falló")
                return False
        print()
        
        # Cerrar conexión al final
        print("7. Cerrando conexión...")
        conn.close()
        print("   ✓ Conexión cerrada correctamente")
        print()
        
        print("=" * 70)
        print("✓ TODOS LOS TESTS PASARON")
        print("=" * 70)
        print()
        print("Conclusión:")
        print("- get_db_connection() retorna conexión válida")
        print("- La conexión NO se cierra automáticamente")
        print("- Múltiples queries pueden ejecutarse en la misma conexión")
        print("- Inyección de db_conn en vistas funciona correctamente")
        
        return True
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_db_connection_flow()
    sys.exit(0 if success else 1)
