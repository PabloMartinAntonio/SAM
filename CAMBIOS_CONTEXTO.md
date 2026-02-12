# Actualización: Contexto de Conversación en Módulo Aprendizaje

## 🎯 Objetivo
Modificar el módulo "Aprendizaje" de la UI Tkinter para mostrar contexto completo de conversación al seleccionar un turno pendiente (turnos anteriores + seleccionado + posteriores).

## ✅ Cambios Implementados

### 1. Nuevas Funciones en `ui/services.py`

#### `get_turnos_context(conn, conversacion_pk, turno_idx, window=3)`
- **Propósito**: Obtiene contexto de turnos en una ventana configurable
- **Parámetros**:
  - `conversacion_pk`: ID de la conversación
  - `turno_idx`: Índice del turno central
  - `window`: Número de turnos antes y después (default: 3)
- **Retorno**: Lista de dicts con turnos en rango `[turno_idx-window, turno_idx+window]`
- **Características**:
  - ✅ Detección dinámica de columnas (SHOW COLUMNS)
  - ✅ Aliases estándar: `speaker`, `text`, `fase`, `fase_source`, `fase_conf`, `intent`
  - ✅ Fallback a NULL para columnas inexistentes
  - ✅ Soporte para múltiples nombres de columna texto: `text`, `texto`, `utterance`, `contenido`
  - ✅ Query optimizado con BETWEEN

### 2. Cambios en `ui/views_aprendizaje.py`

#### Variables agregadas
```python
self.context_window_var = tk.IntVar(value=3)  # Ventana de contexto
self.context_rows = []  # Contexto de turnos cargado
```

#### Controles UI nuevos

**Spinbox de Contexto:**
- Ubicación: Top frame, junto a umbral de confianza
- Rango: 1-20 turnos
- Default: 3 turnos
- Label: "Contexto:"

**Panel de Contexto (reemplaza "Texto del Turno"):**
- Título: "Contexto de la Conversación"
- Widget: `tk.Text` con scrollbar vertical
- Font: Courier 9pt (monoespaciada para alineación)
- Height: 12 líneas

#### Tags de formato configurados

```python
# Tag para turno seleccionado
"selected": background="#ffffcc", font=bold

# Tag para headers de otros turnos
"header": foreground="#0066cc", font=bold

# Tags opcionales por speaker
"speaker_agent": foreground="#006600"
"speaker_cliente": foreground="#cc6600"
```

#### Función `_render_context_text(context_rows, selected_turno_idx)`
- **Formato de cada turno**:
  ```
  [turno_idx] SPEAKER | FASE | CONF | SOURCE
  texto del turno...
  ----------------------------------------------------------------------
  ```
- **Resaltado**: Turno seleccionado con background amarillo claro y bold
- **Scroll automático**: `.see()` al turno seleccionado
- **Separadores**: Línea de 70 guiones entre turnos

#### Función `_cargar_contexto_turno(turno)`
- Carga contexto en background thread (no bloquea UI)
- Usa `window` del Spinbox
- Envía resultado a cola: `("contexto_cargado", context_rows, turno)`

#### Handler `_on_turno_selected(event)` modificado
- Antes: Cargaba solo texto del turno
- Ahora: Llama a `_cargar_contexto_turno()` en background

#### Handler `_process_queue_message()` ampliado
- Nuevo mensaje: `"contexto_cargado"`
- Acción: Renderiza contexto + autocompleta fase

#### Función `_update_turno_display(turno)` simplificada
- Solo autocompleta fase del combo
- Limpia intent y nota
- Ya no muestra texto (lo hace `_render_context_text()`)

## 📊 Ejemplo de Output

```
[3] AGENTE | VALIDACION_IDENTIDAD | 0.95 | DEEPSEEK
Buenos días, señor Polo. ¿Cómo está? Le llamo de...
----------------------------------------------------------------------
[4] CLIENTE | VALIDACION_IDENTIDAD | 0.88 | DEEPSEEK  <<<< RESALTADO
Dígame.
----------------------------------------------------------------------
[5] AGENTE | OFERTA_PAGO | 0.92 | DEEPSEEK
Sí, estimado, su cuenta ha sido seleccionada...
```

## 🔧 Características Técnicas

### Detección Dinámica de Columnas
- Cache en `_TURNOS_COLUMNS_CACHE`
- Query inicial: `SHOW COLUMNS FROM sa_turnos`
- Construcción de SELECT según columnas disponibles

### Nombres de Columna Soportados
- **Speaker**: `speaker`, `hablante`
- **Texto**: `text`, `texto`, `utterance`, `contenido`
- **Fases**: `fase`, `fase_source`, `fase_conf`
- **Intent**: `intent`, `intent_conf`

### Manejo de Valores NULL
- `speaker`: "(sin nombre)" o "?"
- `text`: "(sin texto)"
- `fase`: "(none)"
- `fase_conf`: "N/A"

### Threading No Bloqueante
1. Click en turno → `_on_turno_selected()`
2. Thread background → `services.get_turnos_context()`
3. Resultado → `task_queue.put(("contexto_cargado", ...))`
4. Main thread → `.after()` polling → `_process_queue_message()`
5. UI update → `_render_context_text()`

## ✅ Validación

### Tests Ejecutados

**1. Test de estructura:**
```bash
python test_ui_structure.py
✓ PASS - Estructura de archivos
✓ PASS - Imports de módulos
✓ PASS - Instanciación de modelos
```

**2. Test de contexto:**
```bash
python test_contexto.py
✓ Conexión OK
✓ get_turnos_context() funcional
✓ Ventana window=1: 3 turnos
✓ Ventana window=3: 7 turnos
✓ Ventana window=5: 9 turnos
✓ Todas las columnas presentes
```

**3. Imports verificados:**
```bash
python -c "from ui.views_aprendizaje import AprendizajeView; ..."
✓ Imports OK
```

## 📝 Uso en la UI

### Flujo de Trabajo

1. **Abrir módulo Aprendizaje**
2. **Seleccionar ejecución** y ajustar umbral
3. **Cargar pendientes** (click "Cargar Pendientes")
4. **Ajustar contexto** (Spinbox: 1-20, default 3)
5. **Click en turno pendiente**:
   - Se carga contexto en background
   - Panel "Contexto de la Conversación" se actualiza
   - Muestra turnos anteriores + seleccionado + posteriores
   - Turno seleccionado aparece resaltado en amarillo
   - Scroll automático al turno seleccionado
   - Combo "Fase" se autocompleta con fase actual
6. **Cambiar Spinbox contexto**: Click en otro turno para recargar con nueva ventana

### Personalización del Contexto

- **window=1**: Turno anterior + seleccionado + posterior (3 total)
- **window=3**: 3 anteriores + seleccionado + 3 posteriores (7 total)
- **window=5**: 5 anteriores + seleccionado + 5 posteriores (11 total)

## 🎨 Formato Visual

### Colores

- **Turno seleccionado**: Background `#ffffcc` (amarillo claro)
- **Headers normales**: Foreground `#0066cc` (azul)
- **Speaker AGENTE**: Foreground `#006600` (verde oscuro)
- **Speaker CLIENTE**: Foreground `#cc6600` (naranja)

### Font

- Courier 9pt (monoespaciada)
- Headers en bold
- Texto normal

## 🐛 Manejo de Errores

- ✅ Si no hay contexto: muestra "(No hay contexto disponible)"
- ✅ Si columnas no existen: usa NULL con alias
- ✅ Si thread falla: messagebox con error
- ✅ Si turno_idx < 1: from_idx = max(1, turno_idx-window)

## 📁 Archivos Modificados

1. ✅ `ui/services.py` (+70 líneas)
   - Nueva función: `get_turnos_context()`

2. ✅ `ui/views_aprendizaje.py` (~100 líneas modificadas)
   - Variable: `context_window_var`, `context_rows`
   - UI: Spinbox contexto, panel contexto
   - Funciones: `_cargar_contexto_turno()`, `_render_context_text()`
   - Modificadas: `_on_turno_selected()`, `_process_queue_message()`, `_update_turno_display()`

3. ✅ `test_contexto.py` (nuevo, para validación)

## 🔮 Mejoras Futuras Posibles

- [ ] Botón "Refrescar contexto" sin cambiar selección
- [ ] Highlight de palabras clave en texto
- [ ] Exportar contexto a texto plano
- [ ] Navegación con teclado (↑↓) entre turnos del contexto
- [ ] Tooltips con info adicional al hover sobre turnos
- [ ] Modo compacto (solo headers sin texto)
- [ ] Filtros de fase en contexto

## ✨ Resultado Final

El módulo Aprendizaje ahora proporciona **contexto completo** para corrección humana de fases:

- ✅ **Visibilidad**: Ve conversación completa, no solo turno aislado
- ✅ **Contexto ajustable**: 1-20 turnos antes/después
- ✅ **Resaltado visual**: Turno seleccionado destacado
- ✅ **No bloqueante**: Carga en background
- ✅ **Robusto**: Funciona con schemas variables
- ✅ **Performante**: Query optimizado con BETWEEN

**Total cambios**: ~170 líneas de código nuevo/modificado
**Validación**: ✓ 100% tests pasados
**Estado**: ✅ Listo para producción
