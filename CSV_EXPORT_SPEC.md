# Especificación: Exportación CSV de Correcciones Humanas

## Descripción General

El módulo **Aprendizaje** de la UI permite exportar correcciones humanas a CSV con **contexto completo** de la conversación. El archivo generado contiene toda la información necesaria para:

- Auditar las decisiones de corrección
- Analizar patrones de error del modelo
- Entrenar modelos de ML con contexto conversacional
- Revisar la calidad de las anotaciones humanas

## Ubicación del Archivo

```
out_reports/labels_turnos.csv
```

**Modo de escritura**: `append` (las nuevas correcciones se agregan al final sin sobrescribir)

## Estructura del CSV

### Columnas (11 total)

| # | Columna | Tipo | Descripción | Ejemplo |
|---|---------|------|-------------|---------|
| 1 | `ts` | ISO timestamp | Momento exacto de la corrección | `2026-02-09T23:00:49.451266` |
| 2 | `ejecucion_id` | int | ID de la ejecución del modelo | `1` |
| 3 | `conversacion_pk` | int | Primary key de la conversación | `123456` |
| 4 | `turno_idx` | int | Índice del turno corregido (1-based) | `5` |
| 5 | `fase_old` | string | Fase original (predicción del modelo) | `VALIDACION_IDENTIDAD` |
| 6 | `fase_new` | string | Fase corregida (decisión humana) | `OFERTA_PAGO` |
| 7 | `intent_old` | string | Intent original (puede ser vacío) | `validar_datos` |
| 8 | `intent_new` | string | Intent corregido | `solicitar_pago` |
| 9 | `nota` | string | Observaciones del anotador (opcional) | `Cliente acepta pago inmediato` |
| 10 | `contexto_window` | int | Tamaño de la ventana de contexto usada (1-20) | `3` |
| 11 | `contexto_text` | string | Texto concatenado del contexto (max 2000 chars) | Ver formato abajo |

### Formato de `contexto_text`

```
[idx] SPEAKER: texto | [idx] SPEAKER: texto | [idx] SPEAKER: texto | ...
```

**Ejemplo real**:
```
[3] AGENTE: Buenos días | [4] CLIENTE: Hola | [5] AGENTE: Le llamo por su deuda | [6] CLIENTE: Entiendo | [7] AGENTE: Puede pagar hoy
```

**Características**:
- Formato compacto separado por `|`
- Incluye: índice del turno, speaker, texto
- **Truncado a 2000 caracteres**: si el contexto completo excede 2000 chars, se trunca en 1997 y se agrega `...`
- El turno seleccionado (corregido) está **incluido** en el contexto
- **Ventana simétrica**: `N turnos antes + seleccionado + N turnos después`

### Valores Faltantes

- Si un campo no tiene valor (ej: `intent_old` es `None`), se guarda como **string vacío** (`""`)
- Esto garantiza compatibilidad CSV sin valores `NULL`

## Workflow de Exportación

### En la UI (Módulo Aprendizaje)

1. **Seleccionar ejecución**: Cargar lista de turnos pendientes
2. **Ajustar contexto**: Usar Spinbox (1-20) para definir ventana de contexto
3. **Seleccionar turno**: Click en Treeview carga el contexto en panel inferior
4. **Visualizar**: El contexto se muestra con highlighting del turno seleccionado
5. **Corregir**: Modificar Fase y/o Intent en los comboboxes
6. **Agregar nota** (opcional): Explicar la razón de la corrección
7. **Guardar a CSV**: Click en botón → los datos se escriben al archivo

### Datos Capturados

El sistema captura automáticamente:
- Timestamp ISO del momento del guardado
- ID de la ejecución seleccionada
- Datos del turno: conversacion_pk, turno_idx
- Fase e Intent: valores originales (old) y corregidos (new)
- Nota ingresada por el usuario
- **contexto_window**: Valor del Spinbox (ej: `3`)
- **contexto_text**: Generado desde `self.context_rows` ya cargados en memoria

### Código Relevante

**Función**: `guardar_correccion_csv()` en `ui/views_aprendizaje.py`

**Lógica de generación de contexto_text**:

```python
# Generar contexto_text desde self.context_rows
contexto_parts = []
for row in self.context_rows:
    idx = row.get("turno_idx", "?")
    spk = row.get("speaker", "?")
    txt = row.get("text", "")
    contexto_parts.append(f"[{idx}] {spk}: {txt}")

contexto_text = " | ".join(contexto_parts)

# Truncar si excede 2000 chars
if len(contexto_text) > 2000:
    contexto_text = contexto_text[:1997] + "..."
```

## Casos de Uso

### 1. Auditoría de Correcciones

```python
import pandas as pd

df = pd.read_csv("out_reports/labels_turnos.csv")

# Ver qué contexto se usó para cada corrección
print(df[["turno_idx", "contexto_window", "fase_old", "fase_new", "nota"]])

# Detectar correcciones con poco contexto
low_context = df[df["contexto_window"] < 3]
print(f"Correcciones con contexto < 3: {len(low_context)}")
```

### 2. Análisis de Patrones de Error

```python
# Agrupar por tipo de corrección
cambios = df.groupby(["fase_old", "fase_new"]).size()
print("Top 10 correcciones más frecuentes:")
print(cambios.sort_values(ascending=False).head(10))

# Ver contexto típico de errores específicos
error_validacion = df[
    (df["fase_old"] == "VALIDACION_IDENTIDAD") & 
    (df["fase_new"] == "OFERTA_PAGO")
]
print(error_validacion[["contexto_text", "nota"]])
```

### 3. Entrenamiento con Contexto

```python
# Exportar ejemplos con contexto para fine-tuning
train_data = []
for _, row in df.iterrows():
    train_data.append({
        "context": row["contexto_text"],
        "target_fase": row["fase_new"],
        "target_intent": row["intent_new"]
    })

import json
with open("train_contexts.jsonl", "w") as f:
    for item in train_data:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
```

### 4. Validación de Calidad

```python
# Detectar inconsistencias (mismo contexto, diferentes correcciones)
from collections import Counter

ctx_groups = df.groupby("contexto_text")[["fase_new", "intent_new"]].apply(
    lambda x: list(zip(x["fase_new"], x["intent_new"]))
)

inconsistent = []
for ctx, labels in ctx_groups.items():
    if len(set(labels)) > 1:
        inconsistent.append((ctx[:100], Counter(labels)))

print(f"Contextos con etiquetas inconsistentes: {len(inconsistent)}")
for ctx, counts in inconsistent[:5]:
    print(f"\nContexto: {ctx}...")
    print(f"Etiquetas: {counts}")
```

## Consideraciones Técnicas

### Encoding
- **UTF-8** obligatorio (conversaciones en español)
- Usar `encoding="utf-8"` al abrir el archivo

### Delimitador
- Coma (`,`) estándar CSV
- El `contexto_text` usa pipe (`|`) internamente para separar turnos → no conflicto

### Newlines
- `newline=""` en Python para evitar problemas cross-platform

### Performance
- **Append mode**: O(1) por escritura, no recarga todo el archivo
- **Límite práctico**: hasta ~100K filas sin problemas de lectura

### Compatibilidad
- Excel: Abrir con "Datos > Desde Texto" especificando UTF-8
- Pandas: `pd.read_csv("labels_turnos.csv", encoding="utf-8")`
- Google Sheets: Importar directamente (detecta UTF-8)

## Validación del Archivo

### Test Automatizado

```bash
python test_csv_contexto.py
```

**Validaciones incluidas**:
- ✓ Header con 11 columnas
- ✓ Escritura de fila completa
- ✓ Modo append funcional
- ✓ Truncado de contexto largo (>2000 chars)
- ✓ Codificación UTF-8

### Inspección Manual

```bash
# Ver primeras líneas
head -n 5 out_reports/labels_turnos.csv

# Contar filas (sin header)
wc -l out_reports/labels_turnos.csv
```

## Migración desde Versión Anterior

Si tienes un archivo `labels_turnos.csv` **sin** las columnas `contexto_window` y `contexto_text`:

### Opción 1: Renombrar (conservar histórico)

```bash
mv out_reports/labels_turnos.csv out_reports/labels_turnos_v1.csv
```

La UI creará el nuevo archivo con el formato actualizado.

### Opción 2: Migrar datos (agregar columnas vacías)

```python
import pandas as pd

# Leer archivo antiguo
df = pd.read_csv("out_reports/labels_turnos.csv")

# Agregar nuevas columnas con valores vacíos
df["contexto_window"] = ""
df["contexto_text"] = ""

# Guardar con nuevo formato
df.to_csv("out_reports/labels_turnos.csv", index=False, encoding="utf-8")
```

**Nota**: El histórico no tendrá contexto real, solo campos vacíos.

## Troubleshooting

### Error: `UnicodeDecodeError`
**Solución**: Especificar `encoding="utf-8"` al leer

### Error: Columnas faltantes al leer
**Solución**: Verificar que el header esté presente (primera línea del archivo)

### Contexto truncado inesperadamente
**Causa**: Suma total de textos excede 2000 chars
**Solución**: Aumentar `contexto_window` para incluir turnos más cortos

### Archivo no se crea
**Causa**: Carpeta `out_reports/` no existe
**Solución**: La UI la crea automáticamente con `mkdir(exist_ok=True)`

## Changelog

### v2.0 (Actual)
- ✨ Agregado: `contexto_window` (tamaño ventana de contexto)
- ✨ Agregado: `contexto_text` (texto completo del contexto, max 2000 chars)
- ✨ Agregado: `ejecucion_id` (ID de la ejecución del modelo)
- ✨ Agregado: `intent_old` (intent original del modelo)
- 🔄 Renombrado: `timestamp` → `ts`
- 🔄 Renombrado: `fase_original` → `fase_old`
- 🔄 Renombrado: `fase_nueva` → `fase_new`
- 🔄 Renombrado: `intent_nuevo` → `intent_new`

### v1.0 (Anterior)
- Columnas básicas: timestamp, conversacion_pk, turno_idx, fase_original, fase_nueva, intent_nuevo, nota

---

**Última actualización**: 2026-02-09
**Autor**: Sistema Speech Analytics - Módulo Aprendizaje
