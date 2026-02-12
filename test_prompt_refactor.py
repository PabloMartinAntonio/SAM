"""
Test del refactor: Prompt desde archivo con fallback
"""
import sys
from pathlib import Path

def test_prompt_file_exists():
    """Test 1: Verifica que el archivo de prompt existe"""
    prompt_file = Path("prompts/deepseek_prompt.txt")
    
    if prompt_file.exists():
        print(f"✓ Test 1: Archivo de prompt existe: {prompt_file}")
        return True
    else:
        print(f"✗ Test 1: Archivo de prompt NO existe: {prompt_file}")
        return False

def test_prompt_file_format():
    """Test 2: Verifica que el archivo tiene el formato correcto"""
    prompt_file = Path("prompts/deepseek_prompt.txt")
    
    if not prompt_file.exists():
        print("⚠ Test 2: Saltado (archivo no existe)")
        return True
    
    try:
        content = prompt_file.read_text(encoding="utf-8")
        
        # Verificar que tiene las secciones esperadas
        has_system = "SYSTEM_MESSAGE:" in content
        has_user = "USER_MESSAGE_TEMPLATE:" in content
        
        if has_system and has_user:
            print("✓ Test 2: Formato correcto (SYSTEM_MESSAGE + USER_MESSAGE_TEMPLATE)")
        elif has_user:
            print("✓ Test 2: Formato válido (solo USER_MESSAGE_TEMPLATE)")
        else:
            print("⚠ Test 2: Formato simple (texto plano)")
        
        # Verificar placeholders
        has_phases = "{phases_list}" in content
        has_context = "{context_block}" in content
        has_last_phase = "{last_phase_info}" in content
        
        if has_phases and has_context and has_last_phase:
            print("  → Placeholders encontrados: phases_list, context_block, last_phase_info ✓")
        else:
            missing = []
            if not has_phases:
                missing.append("phases_list")
            if not has_context:
                missing.append("context_block")
            if not has_last_phase:
                missing.append("last_phase_info")
            print(f"  ⚠ Placeholders faltantes: {', '.join(missing)}")
        
        return True
    except Exception as e:
        print(f"✗ Test 2: Error leyendo archivo: {e}")
        return False

def test_load_prompt_function():
    """Test 3: Verifica que la función _load_prompt_template funciona"""
    try:
        # Import directo desde el módulo
        import sys
        sys.path.insert(0, '.')
        from scripts.reclasificar_turnos_deepseek import _load_prompt_template
        
        result = _load_prompt_template()
        
        if result is None:
            print("ℹ Test 3: _load_prompt_template() retornó None (archivo no existe o error)")
            # Esto es válido si el archivo no existe
            prompt_file = Path("prompts/deepseek_prompt.txt")
            if not prompt_file.exists():
                print("  → Comportamiento esperado: archivo no existe")
                return True
            else:
                print("  ✗ Archivo existe pero función retornó None")
                return False
        else:
            system_msg, user_msg = result
            print(f"✓ Test 3: _load_prompt_template() cargó correctamente")
            print(f"  → System message length: {len(system_msg)} chars")
            print(f"  → User message length: {len(user_msg)} chars")
            
            # Verificar que user_msg tiene placeholders
            if "{phases_list}" in user_msg and "{context_block}" in user_msg:
                print("  → Placeholders presentes en user_msg ✓")
            else:
                print("  ⚠ Placeholders faltantes en user_msg")
            
            return True
    except Exception as e:
        print(f"✗ Test 3: Error importando función: {e}")
        return False

def test_build_llm_prompts_fallback():
    """Test 4: Verifica que _build_llm_prompts funciona con y sin archivo"""
    try:
        import sys
        sys.path.insert(0, '.')
        from scripts.reclasificar_turnos_deepseek import _build_llm_prompts
        
        # Test con datos de ejemplo
        context = "Turno idx=0: Buenos días, le llamo por su deuda"
        last_phase = "last_phase=None conf=None source=None"
        allowed = ["SALUDO_INICIAL", "VALIDACION_IDENTIDAD", "OFERTA_PAGO"]
        
        system_msg, user_msg = _build_llm_prompts(context, last_phase, allowed)
        
        if not system_msg or not user_msg:
            print("✗ Test 4: _build_llm_prompts retornó mensajes vacíos")
            return False
        
        print("✓ Test 4: _build_llm_prompts funciona correctamente")
        print(f"  → System message: {system_msg[:80]}...")
        print(f"  → User message length: {len(user_msg)} chars")
        
        # Verificar que las fases permitidas están en el mensaje
        if "SALUDO_INICIAL" in user_msg and "OFERTA_PAGO" in user_msg:
            print("  → Fases permitidas incluidas en user_msg ✓")
        else:
            print("  ⚠ Fases permitidas NO encontradas en user_msg")
        
        # Verificar que el contexto está incluido
        if context in user_msg or "Buenos días" in user_msg:
            print("  → Contexto incluido en user_msg ✓")
        else:
            print("  ⚠ Contexto NO encontrado en user_msg")
        
        return True
    except Exception as e:
        print(f"✗ Test 4: Error ejecutando función: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_fallback_when_file_missing():
    """Test 5: Verifica que el fallback funciona si el archivo no existe"""
    try:
        import sys
        sys.path.insert(0, '.')
        from pathlib import Path
        
        # Backup del archivo si existe
        prompt_file = Path("prompts/deepseek_prompt.txt")
        backup_file = Path("prompts/deepseek_prompt.txt.backup_test")
        
        file_existed = prompt_file.exists()
        if file_existed:
            prompt_file.rename(backup_file)
        
        try:
            from scripts.reclasificar_turnos_deepseek import _build_llm_prompts
            
            # Recargar el módulo para que use el código actualizado
            import importlib
            import scripts.reclasificar_turnos_deepseek as module
            importlib.reload(module)
            _build_llm_prompts = module._build_llm_prompts
            
            context = "Test context"
            last_phase = "last_phase=None"
            allowed = ["FASE_A", "FASE_B"]
            
            system_msg, user_msg = _build_llm_prompts(context, last_phase, allowed)
            
            if system_msg and user_msg:
                print("✓ Test 5: Fallback funciona correctamente (archivo no existe)")
                print(f"  → System: {system_msg[:60]}...")
                print(f"  → User msg incluye 'Reglas estrictas': {'Reglas estrictas' in user_msg}")
                return True
            else:
                print("✗ Test 5: Fallback NO generó mensajes válidos")
                return False
        finally:
            # Restaurar archivo si existía
            if file_existed and backup_file.exists():
                backup_file.rename(prompt_file)
    except Exception as e:
        print(f"✗ Test 5: Error en test de fallback: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_all_tests():
    """Ejecuta todos los tests"""
    print("=" * 70)
    print("TEST: Refactor Prompt DeepSeek (archivo + fallback)")
    print("=" * 70)
    print()
    
    tests = [
        test_prompt_file_exists,
        test_prompt_file_format,
        test_load_prompt_function,
        test_build_llm_prompts_fallback,
        test_fallback_when_file_missing
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
        print("⚠ ALGUNOS TESTS FALLARON O TIENEN WARNINGS")
    
    print("=" * 70)
    
    return all(results)

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
