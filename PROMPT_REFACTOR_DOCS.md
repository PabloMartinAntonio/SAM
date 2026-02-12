# 📝 Refactor: Prompt DeepSeek desde Archivo

## Resumen Ejecutivo

Se refactorizó `scripts/reclasificar_turnos_deepseek.py` para:
- ✅ Leer el prompt desde archivo `prompts/deepseek_prompt.txt`
- ✅ Mantener **fallback al prompt hardcodeado** si el archivo no existe
- ✅ Sin cambios en la lógica de clasificación
- ✅ 100% retrocompatible

## Cambios Realizados

### 1. Archivo Modificado

**`scripts/reclasificar_turnos_deepseek.py`**

#### Import agregado
```python
from pathlib import Path
```

#### Función nueva: `_load_prompt_template()`
```python
def _load_prompt_template():
    """
    Carga el prompt desde prompts/deepseek_prompt.txt.
    Retorna (system_msg_template, user_msg_template) o None si no existe.
    """
    prompt_file = Path("prompts/deepseek_prompt.txt")
    if not prompt_file.exists():
        return None
    
    try:
        content = prompt_file.read_text(encoding="utf-8")
        
        # Parsear formato: SYSTEM_MESSAGE: ... USER_MESSAGE_TEMPLATE: ...
        if "SYSTEM_MESSAGE:" in content and "USER_MESSAGE_TEMPLATE:" in content:
            parts = content.split("USER_MESSAGE_TEMPLATE:")
            system_msg = parts[0].replace("SYSTEM_MESSAGE:", "").strip()
            user_msg = parts[1].strip()
        else:
            # Fallback: usar todo como user message
            user_msg = content.strip()
            system_msg = ""
        
        return system_msg, user_msg
    except Exception as e:
        print(f"[WARN] Error cargando prompt desde archivo: {e}")
        return None
```

#### Función modificada: `_build_llm_prompts()`

**ANTES** (hardcoded):
```python
def _build_llm_prompts(context_block: str, last_phase_info: str, allowed_phases: list[str]) -> tuple[str, str]:
    phases_list = ", ".join(allowed_phases)
    rules = (
        "Reglas estrictas de salida:\n"
        "- Devuelve SOLO JSON exacto: {\"fase_id\": \"...\", \"confidence\": 0.xx, \"is_noise\": true|false}.\n"
        # ... más reglas hardcodeadas
    )
    system_msg = "Eres un clasificador de fases de cobranzas. Devuelve SOLO JSON válido y estricto, sin texto adicional."
    user_msg = (
        f"Fases permitidas: {phases_list}\n\n"
        f"{rules}\n"
        # ... más texto hardcodeado
    )
    return system_msg, user_msg
```

**DESPUÉS** (archivo + fallback):
```python
def _build_llm_prompts(context_block: str, last_phase_info: str, allowed_phases: list[str]) -> tuple[str, str]:
    phases_list = ", ".join(allowed_phases)
    
    # Intentar cargar desde archivo
    template = _load_prompt_template()
    
    if template:
        system_template, user_template = template
        
        # Si system_template está vacío, usar default
        if not system_template:
            system_msg = "Eres un clasificador de fases de cobranzas. Devuelve SOLO JSON válido y estricto, sin texto adicional."
        else:
            system_msg = system_template
        
        # Reemplazar placeholders en user_template
        user_msg = user_template.format(
            phases_list=phases_list,
            last_phase_info=last_phase_info,
            context_block=context_block
        )
    else:
        # FALLBACK: Prompt hardcodeado (comportamiento original)
        # ... código original sin cambios ...
    
    return system_msg, user_msg
```

### 2. Archivo de Prompt

**`prompts/deepseek_prompt.txt`**

Formato:
```
SYSTEM_MESSAGE:
[Mensaje para el sistema, ej: "Eres un clasificador..."]

USER_MESSAGE_TEMPLATE:
[Template con placeholders: {phases_list}, {context_block}, {last_phase_info}]
```

**Contenido actual**:
```
SYSTEM_MESSAGE:
Eres un clasificador de fases de cobranzas. Devuelve SOLO JSON válido y estricto, sin texto adicional.

USER_MESSAGE_TEMPLATE:
Fases permitidas: {phases_list}

Reglas estrictas de salida:
- Devuelve SOLO JSON exacto: {{"fase_id": "...", "confidence": 0.xx, "is_noise": true|false}}.
- Si 'is_noise' es true => 'fase_id' debe ser null.
- Si 'is_noise' es false => 'fase_id' debe ser EXACTAMENTE una de las fases permitidas.
- PROHIBIDO devolver fases viejas/legacy.
- Confidence en rango 0..1.

Estado previo: {last_phase_info}

Contexto:
{context_block}

Salida EXACTA JSON: {{"fase_id": "OFERTA_PAGO", "confidence": 0.82, "is_noise": false}}
```

### 3. Tests

**`test_prompt_refactor.py`** (5 tests)

```bash
$ python test_prompt_refactor.py
======================================================================
TEST: Refactor Prompt DeepSeek (archivo + fallback)
======================================================================

✓ Test 1: Archivo de prompt existe
✓ Test 2: Formato correcto (SYSTEM_MESSAGE + USER_MESSAGE_TEMPLATE)
  → Placeholders encontrados: phases_list, context_block, last_phase_info ✓
✓ Test 3: _load_prompt_template() cargó correctamente
✓ Test 4: _build_llm_prompts funciona correctamente
  → Fases permitidas incluidas en user_msg ✓
  → Contexto incluido en user_msg ✓
✓ Test 5: Fallback funciona correctamente (archivo no existe)

======================================================================
RESULTADO: 5/5 tests pasados
✓ TODOS LOS TESTS PASARON
======================================================================
```

## Comportamiento

### Caso 1: Archivo existe y es válido
1. `_load_prompt_template()` lee `prompts/deepseek_prompt.txt`
2. Parsea `SYSTEM_MESSAGE` y `USER_MESSAGE_TEMPLATE`
3. `_build_llm_prompts()` usa el template del archivo
4. Reemplaza placeholders: `{phases_list}`, `{context_block}`, `{last_phase_info}`
5. Retorna system_msg y user_msg generados desde archivo

### Caso 2: Archivo no existe
1. `_load_prompt_template()` retorna `None`
2. `_build_llm_prompts()` usa el **fallback hardcodeado**
3. Comportamiento **idéntico** al código original
4. ✅ **No rompe nada**

### Caso 3: Error leyendo archivo
1. `_load_prompt_template()` captura la excepción
2. Imprime warning: `[WARN] Error cargando prompt desde archivo: ...`
3. Retorna `None`
4. Activa el **fallback hardcodeado**

## Placeholders Disponibles

Al editar `prompts/deepseek_prompt.txt`, puedes usar:

| Placeholder | Descripción | Ejemplo |
|-------------|-------------|---------|
| `{phases_list}` | Lista de fases permitidas separadas por coma | `"SALUDO_INICIAL, VALIDACION_IDENTIDAD, ..."` |
| `{last_phase_info}` | Info de la fase anterior | `"last_phase=OFERTA_PAGO conf=0.85 source=DEEPSEEK"` |
| `{context_block}` | Bloque de contexto con turnos | `"Turno idx=-2: ...\nTurno idx=-1: ...\n..."` |

**Importante**: Los placeholders usan la sintaxis de Python `.format()`:
- Usar llaves dobles `{{` y `}}` para literales de JSON
- Usar llaves simples `{placeholder}` para variables

**Ejemplo correcto**:
```
Salida EXACTA JSON: {{"fase_id": "OFERTA_PAGO", "confidence": 0.82, "is_noise": false}}
```

## Ventajas del Refactor

### ✅ Flexibilidad
- Editar prompts sin modificar código Python
- Experimentar con diferentes formulaciones
- A/B testing de prompts (solo cambiar archivo)

### ✅ Versionado
- Prompts en Git junto con código
- Historial de cambios visible
- Fácil rollback a versiones anteriores

### ✅ Colaboración
- No-programadores pueden editar prompts
- Prompt engineers pueden iterar sin tocar código
- Revisión de cambios en pull requests

### ✅ Retrocompatibilidad
- Si el archivo no existe, funciona igual que antes
- Migración gradual (opcional)
- No requiere cambios en scripts existentes

### ✅ Consistencia
- Mismo prompt en producción y desarrollo
- Fácil sincronizar entre entornos
- Menos errores de copy-paste

## Uso

### Editar el Prompt

**Opción 1: Desde la UI** (pestaña DeepSeek)
1. Abrir `python run_ui.py`
2. Click en pestaña **🤖 DeepSeek**
3. Scroll a "Editor de Prompt"
4. Modificar el texto
5. Click **💾 Guardar Prompt**

**Opción 2: Editor de texto**
1. Abrir `prompts/deepseek_prompt.txt`
2. Modificar manualmente
3. Guardar (encoding UTF-8)

### Validar Cambios

```bash
# Test del refactor
python test_prompt_refactor.py

# Test de clasificación (requiere API key)
# python scripts/reclasificar_turnos_deepseek.py --help
```

### Restaurar Comportamiento Original

Si quieres volver al prompt hardcodeado:
```bash
# Opción 1: Renombrar el archivo
mv prompts/deepseek_prompt.txt prompts/deepseek_prompt.txt.backup

# Opción 2: Borrar el archivo
rm prompts/deepseek_prompt.txt
```

El código automáticamente usará el fallback hardcodeado.

## Compatibilidad

### ✅ Compatible con:
- Scripts existentes que llaman `reclasificar_turnos_deepseek.py`
- Pipelines CI/CD (funciona sin archivo)
- Configuraciones de producción

### ⚠️ Requiere:
- Python 3.8+ (por uso de `pathlib.Path`)
- Encoding UTF-8 en el archivo de prompt
- Placeholders correctos si se modifica el formato

## Troubleshooting

### Warning: "Error cargando prompt desde archivo"

**Causa**: Archivo corrupto o encoding incorrecto

**Solución**:
1. Verificar que el archivo es UTF-8: `file prompts/deepseek_prompt.txt`
2. Revisar que no hay caracteres especiales inválidos
3. Restaurar desde backup o recrear

### Error: KeyError al usar placeholders

**Causa**: Falta un placeholder en el template

**Solución**:
- Asegurar que el template incluye: `{phases_list}`, `{context_block}`, `{last_phase_info}`
- O modificar la función `_build_llm_prompts()` para agregar más placeholders

### El prompt no cambia después de editar el archivo

**Causa**: Módulo Python ya cargado en memoria (en entorno interactivo)

**Solución**:
- Reiniciar el script
- En Jupyter/IPython: `importlib.reload(scripts.reclasificar_turnos_deepseek)`

## Estructura de Archivos

```
speech_analytic_mejorado/
├── prompts/
│   └── deepseek_prompt.txt           # ← NUEVO (prompt editable)
├── scripts/
│   └── reclasificar_turnos_deepseek.py  # ← MODIFICADO (lee desde archivo)
├── test_prompt_refactor.py           # ← NUEVO (validación)
└── PROMPT_REFACTOR_DOCS.md           # ← NUEVO (este archivo)
```

## Próximos Pasos

### Opcional: Extender Funcionalidad

**1. Versionado de prompts**:
```
prompts/
├── deepseek_prompt.txt           # Activo
├── deepseek_prompt_v1.txt        # Backup versión 1
└── deepseek_prompt_v2.txt        # Backup versión 2
```

**2. Variables de entorno**:
```python
prompt_file = os.getenv("DEEPSEEK_PROMPT_FILE", "prompts/deepseek_prompt.txt")
```

**3. Múltiples prompts por tarea**:
```
prompts/
├── deepseek_prompt_classification.txt
├── deepseek_prompt_noise_detection.txt
└── deepseek_prompt_confidence.txt
```

## Changelog

### v1.0 (2026-02-09)
- ✅ Implementado refactor: prompt desde archivo
- ✅ Fallback a prompt hardcodeado
- ✅ Tests: 5/5 pasando
- ✅ Sin breaking changes
- ✅ Documentación completa

---

**Versión**: 1.0  
**Fecha**: 2026-02-09  
**Tests**: ✓ 5/5 pasados  
**Breaking Changes**: Ninguno
