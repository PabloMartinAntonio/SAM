# Speech Analytics - UI Desktop

Aplicación de escritorio desarrollada en Python + Tkinter para visualización, análisis y corrección de datos de Speech Analytics.

## 📋 Requisitos

- Python 3.8+
- Tkinter (incluido en Python estándar)
- MySQL Connector (ya instalado en el proyecto)
- Archivo `config.ini` configurado correctamente

## 🚀 Ejecución

```bash
python run_ui.py
```

O desde la raíz del proyecto:

```bash
python -m run_ui
```

## 🎯 Características

### 1. 📊 Dashboard
Visualización de estadísticas globales y por ejecución:

- **Selección múltiple de ejecuciones**: Listbox con selección extendida (Ctrl+Click, Shift+Click)
- **Opción TOTAL**: Checkbox para mostrar/ocultar agregado de todas las ejecuciones seleccionadas
- **Umbral de confianza configurable**: Entry para ajustar el threshold (default: 0.08)
- **Métricas clave**:
  - Total conversaciones y turnos
  - % turnos con/sin fase
  - Pendientes por umbral de confianza
  - Distribución por fase (tabla con conteo y %)
  - Distribución por fase_source (tabla con conteo y %)
  - Estadísticas de promesas (si existe tabla sa_promesas_pago)
- **Pestañas dinámicas**: Una pestaña por ejecución seleccionada + pestaña TOTAL
- **Botón Refrescar**: Recarga estadísticas bajo demanda

### 2. 🔍 Detalles
Navegación por conversaciones y turnos:

- **Selector de ejecución**: Combobox para elegir ejecución activa
- **Búsqueda de conversaciones**: 
  - Por conversacion_id (substring match)
  - Por conversacion_pk (match exacto)
  - Límite: 500 conversaciones
- **Vista de conversaciones**: TreeView con PK y conversacion_id
- **Vista de turnos**: Al seleccionar conversación, carga turnos con:
  - turno_idx, speaker, fase, fase_source, fase_conf
  - intent, intent_conf (si existen columnas)
- **Panel de detalle**: Texto completo del turno seleccionado
- **Detección dinámica de columnas**: Funciona con schemas variables

### 3. ✏️ Aprendizaje
Módulo de corrección humana de fases:

- **Selector de ejecución + umbral**: Similar a Dashboard
- **Listado de pendientes**: Turnos que cumplen:
  - fase IS NULL OR TRIM(fase) = ''
  - OR fase_conf IS NULL OR fase_conf < threshold
- **Paginación**: 200 turnos por página, navegación Anterior/Siguiente
- **Edición de turnos**:
  - Selector de fase (Combobox con fases existentes en BD)
  - Intent opcional
  - Nota/razón de la corrección
- **Guardar a CSV**: Exporta correcciones a `out_reports/labels_turnos.csv`
- **Aplicar a BD**: Escribe directamente en sa_turnos:
  - SET fase, fase_source='HUMAN', fase_conf=1.0
  - Opcionalmente: intent, intent_conf=1.0
- **Buffer de correcciones**: Permite acumular múltiples correcciones antes de aplicar
- **Aplicación por lotes**: Botón "Aplicar Buffer a BD" para escribir todas juntas

## 🏗️ Arquitectura

```
run_ui.py                    # Punto de entrada
ui/
  ├── __init__.py
  ├── app.py                 # Aplicación principal (Tk root + Notebook)
  ├── models.py              # Dataclasses (EjecucionInfo, StatsEjecucion, etc.)
  ├── services.py            # Lógica de BD (queries, helpers)
  ├── views_dashboard.py     # Vista Dashboard
  ├── views_detalles.py      # Vista Detalles
  └── views_aprendizaje.py   # Vista Aprendizaje
```

### Principios de diseño

1. **Separación de responsabilidades**:
   - `services.py`: Toda la lógica de BD y queries
   - `views_*.py`: Solo lógica de UI y eventos
   - `models.py`: Estructuras de datos

2. **No bloqueo de UI**:
   - Queries en threads separados (threading.Thread)
   - Comunicación via queue.Queue
   - Polling con .after() para actualizar widgets

3. **Detección dinámica de columnas**:
   - Funciones `get_available_turnos_columns()` y `get_available_conversaciones_columns()`
   - Queries construidos dinámicamente según schema disponible
   - Cacheado de metadatos para performance

4. **Manejo de errores**:
   - try/except en todas las operaciones DB
   - messagebox para notificar errores al usuario
   - Logging a consola para debugging

## 📊 Queries Principales

### Listar ejecuciones
```sql
SELECT ejecucion_id, COUNT(*) as num_conversaciones
FROM sa_conversaciones
GROUP BY ejecucion_id
ORDER BY ejecucion_id
```

### Estadísticas de ejecución
```sql
-- Total turnos
SELECT COUNT(*) FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id = %s

-- Distribución por fase
SELECT t.fase, COUNT(*) 
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id = %s
  AND t.fase IS NOT NULL AND TRIM(t.fase) != ''
GROUP BY t.fase
ORDER BY COUNT(*) DESC
```

### Turnos pendientes
```sql
SELECT t.* 
FROM sa_turnos t
JOIN sa_conversaciones c ON c.conversacion_pk = t.conversacion_pk
WHERE c.ejecucion_id = %s
  AND (t.fase IS NULL OR TRIM(t.fase) = '' 
       OR t.fase_conf IS NULL OR t.fase_conf < threshold)
ORDER BY t.conversacion_pk, t.turno_idx
LIMIT 200 OFFSET offset
```

### Aplicar corrección
```sql
UPDATE sa_turnos
SET fase = %s, fase_source = 'HUMAN', fase_conf = 1.0,
    intent = %s, intent_conf = 1.0
WHERE conversacion_pk = %s AND turno_idx = %s
```

## 📁 Archivos generados

- `out_reports/labels_turnos.csv`: Correcciones humanas exportadas
  - Columnas: timestamp, conversacion_pk, turno_idx, fase_original, fase_nueva, intent_nuevo, nota

## 🔧 Configuración

La UI reutiliza la configuración existente del proyecto:

```ini
# config.ini
[database]
host = localhost
port = 3306
database = speech_analytics
user = root
password = tu_password
```

## 🎨 Interfaz

- **Tema**: clam (ttk theme moderno)
- **Iconos**: Emojis en títulos de pestañas (📊🔍✏️)
- **Componentes**:
  - ttk.Notebook para navegación por pestañas
  - ttk.Treeview para tablas y listas
  - ttk.PanedWindow para split views
  - tk.Text para texto multilínea
  - ttk.Combobox para selectores
  - tk.Listbox con selectmode=EXTENDED para multi-selección

## 🐛 Debugging

Ejecutar con logging visible:

```bash
python run_ui.py
```

Los logs aparecen en consola con formato:
```
[2026-02-09 15:30:45] ui.services - INFO - Columnas sa_turnos detectadas: [...]
[2026-02-09 15:30:46] ui.app - INFO - Vistas creadas exitosamente
```

## ⚠️ Limitaciones conocidas

1. **Límite de conversaciones**: 500 máximo en vista Detalles (performance)
2. **Paginación simple**: No hay "ir a página N" directamente
3. **Mono-thread para writes**: Las escrituras a BD son secuenciales
4. **Sin validación de fases**: Acepta cualquier texto en campo fase
5. **Sin preview de buffer**: No se muestra contenido del buffer antes de aplicar

## 🔮 Mejoras futuras

- [ ] Gráficos con matplotlib (distribuciones de fases)
- [ ] Filtros avanzados (por speaker, por fase_source, por rango de fechas)
- [ ] Exportación de reports a Excel
- [ ] Búsqueda full-text en texto de turnos
- [ ] Undo/Redo de correcciones
- [ ] Validación de fases contra lista oficial
- [ ] Indicador de progreso para queries largas
- [ ] Soporte para múltiples config.ini (ambientes)

## 📝 Notas técnicas

### Threading seguro
- Solo threads de lectura acceden a DB sin locks
- Escrituras siempre en thread separado con commit explícito
- UI actualizada solo desde main thread via queue + .after()

### Caché de metadatos
- Columnas de tablas se cachean en memoria (módulo services)
- Limpiar caché: reiniciar aplicación

### CSV encoding
- UTF-8 con BOM opcional
- Newline mode='auto' en Windows

### MySQL connector
- Pool de conexiones: No usado (single connection)
- Reconnect automático: No implementado (usar menú "Reconectar DB")

## 👥 Contribución

Para agregar nuevas vistas:

1. Crear `ui/views_nueva.py` con clase `NuevaView(ttk.Frame)`
2. Implementar `__init__(parent, db_conn, **kwargs)`
3. Agregar al Notebook en `ui/app.py._create_views()`
4. Agregar queries necesarias en `ui/services.py`
5. Opcionalmente: agregar modelos en `ui/models.py`

## 📄 Licencia

Código interno del proyecto Speech Analytics.
