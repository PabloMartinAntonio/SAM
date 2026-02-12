"""
Script de prueba para guardado CSV con contexto
"""
import csv
from pathlib import Path
from datetime import datetime

def test_csv_format():
    print("=" * 70)
    print("TEST: Formato CSV labels_turnos.csv")
    print("=" * 70)
    
    # Simular datos de corrección con contexto
    test_data = {
        "ts": datetime.now().isoformat(),
        "ejecucion_id": 1,
        "conversacion_pk": 123,
        "turno_idx": 5,
        "fase_old": "VALIDACION_IDENTIDAD",
        "fase_new": "OFERTA_PAGO",
        "intent_old": "",
        "intent_new": "solicitar_pago",
        "nota": "Cliente acepta pago inmediato",
        "contexto_window": 3,
        "contexto_text": "[3] AGENTE: Buenos días | [4] CLIENTE: Hola | [5] AGENTE: Le llamo por su deuda | [6] CLIENTE: Entiendo | [7] AGENTE: Puede pagar hoy"
    }
    
    # Crear archivo de prueba
    csv_path = Path("out_reports") / "labels_turnos_test.csv"
    csv_path.parent.mkdir(exist_ok=True)
    
    print(f"\n1. Creando archivo: {csv_path}")
    
    # Escribir header + fila de prueba
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        
        # Header
        header = [
            "ts", "ejecucion_id", "conversacion_pk", "turno_idx", 
            "fase_old", "fase_new", "intent_old", "intent_new", 
            "nota", "contexto_window", "contexto_text"
        ]
        writer.writerow(header)
        
        # Data row
        writer.writerow([
            test_data["ts"],
            test_data["ejecucion_id"],
            test_data["conversacion_pk"],
            test_data["turno_idx"],
            test_data["fase_old"],
            test_data["fase_new"],
            test_data["intent_old"],
            test_data["intent_new"],
            test_data["nota"],
            test_data["contexto_window"],
            test_data["contexto_text"]
        ])
    
    print("   ✓ Archivo creado")
    
    # Leer y validar
    print("\n2. Validando contenido...")
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        
        if not rows:
            print("   ✗ No hay filas")
            return
        
        row = rows[0]
        
        print(f"   ✓ Filas leídas: {len(rows)}")
        print(f"\n3. Contenido de la fila:")
        print(f"   Timestamp: {row['ts']}")
        print(f"   Ejecución ID: {row['ejecucion_id']}")
        print(f"   Conversación PK: {row['conversacion_pk']}")
        print(f"   Turno Idx: {row['turno_idx']}")
        print(f"   Fase: {row['fase_old']} → {row['fase_new']}")
        print(f"   Intent: '{row['intent_old']}' → '{row['intent_new']}'")
        print(f"   Nota: {row['nota']}")
        print(f"   Contexto Window: {row['contexto_window']}")
        print(f"   Contexto Text (preview): {row['contexto_text'][:80]}...")
        
        # Validar columnas
        print(f"\n4. Validando columnas...")
        expected_cols = set(header)
        actual_cols = set(row.keys())
        
        if expected_cols == actual_cols:
            print("   ✓ Todas las columnas presentes")
        else:
            missing = expected_cols - actual_cols
            extra = actual_cols - expected_cols
            if missing:
                print(f"   ✗ Columnas faltantes: {missing}")
            if extra:
                print(f"   ✗ Columnas extra: {extra}")
    
    # Test de append
    print(f"\n5. Probando modo append...")
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            2,
            456,
            10,
            "OFERTA_PAGO",
            "FORMALIZACION_PAGO",
            "",
            "confirmar_fecha",
            "Fecha confirmada para mañana",
            5,
            "[8] AGENTE: Texto | [9] CLIENTE: Texto | [10] AGENTE: Texto..."
        ])
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(f"   ✓ Filas después de append: {len(rows)}")
    
    # Test de contexto truncado (>2000 chars)
    print(f"\n6. Probando truncado de contexto largo...")
    long_context = " | ".join([f"[{i}] SPEAKER: Texto muy largo aquí..." for i in range(100)])
    truncated = long_context[:2000]
    if len(long_context) > 2000:
        truncated = long_context[:1997] + "..."
    
    print(f"   Original: {len(long_context)} chars")
    print(f"   Truncado: {len(truncated)} chars")
    print(f"   ✓ Truncado correctamente: {truncated[-3:] == '...'}")
    
    print("\n" + "=" * 70)
    print("✓ TEST COMPLETADO")
    print("=" * 70)
    print(f"\nArchivo de prueba: {csv_path}")
    print("Para eliminar: rm out_reports/labels_turnos_test.csv")

if __name__ == "__main__":
    test_csv_format()
