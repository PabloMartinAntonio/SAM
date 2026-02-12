"""
Script de prueba para función get_turnos_context
"""
from ui.services import get_db_connection, get_turnos_context

def test_context():
    print("=" * 70)
    print("TEST: get_turnos_context()")
    print("=" * 70)
    
    try:
        # Conectar
        print("\n1. Conectando a BD...")
        conn = get_db_connection()
        print("   ✓ Conexión OK")
        
        # Obtener un turno de prueba
        print("\n2. Buscando turno de prueba...")
        cur = conn.cursor(dictionary=True)
        cur.execute("""
            SELECT t.conversacion_pk, t.turno_idx
            FROM sa_turnos t
            JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
            WHERE t.turno_idx > 3
            LIMIT 1
        """)
        row = cur.fetchone()
        cur.close()
        
        if not row:
            print("   ✗ No hay turnos disponibles para probar")
            return
        
        conv_pk = row['conversacion_pk']
        turno_idx = row['turno_idx']
        print(f"   ✓ Turno encontrado: conv_pk={conv_pk}, turno_idx={turno_idx}")
        
        # Probar get_turnos_context con diferentes ventanas
        for window in [1, 3, 5]:
            print(f"\n3. Probando con window={window}...")
            context = get_turnos_context(conn, conv_pk, turno_idx, window)
            
            print(f"   ✓ Contexto obtenido: {len(context)} turnos")
            
            if context:
                print(f"\n   Rango esperado: [{turno_idx-window}, {turno_idx+window}]")
                print(f"   Rango obtenido: [{context[0]['turno_idx']}, {context[-1]['turno_idx']}]")
                
                print("\n   Turnos en contexto:")
                for ctx in context:
                    idx = ctx['turno_idx']
                    speaker = ctx.get('speaker', 'N/A')
                    fase = ctx.get('fase', 'N/A')
                    text_preview = (ctx.get('text') or '')[:40]
                    
                    marker = " <<< SELECCIONADO" if idx == turno_idx else ""
                    print(f"     [{idx}] {speaker:10s} | {fase:20s} | {text_preview}{marker}")
                
                # Verificar que columnas estén presentes
                print("\n   Columnas disponibles:")
                if context:
                    cols = list(context[0].keys())
                    print(f"     {', '.join(cols)}")
        
        print("\n" + "=" * 70)
        print("✓ TEST COMPLETADO EXITOSAMENTE")
        print("=" * 70)
        
        conn.close()
        
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_context()
