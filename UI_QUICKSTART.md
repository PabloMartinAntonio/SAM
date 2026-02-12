# 🚀 Inicio Rápido - UI Speech Analytics

## Ejecución

```bash
# Desde la raíz del proyecto:
python run_ui.py
```

## Primera vez

1. **Verificar config.ini**: Asegúrate de que el archivo `config.ini` existe y tiene la configuración correcta de MySQL:

```ini
[database]
host = localhost
port = 3306
database = speech_analytics
user = root
password = tu_password
```

2. **Verificar MySQL**: MySQL debe estar corriendo y accesible.

3. **Ejecutar UI**: `python run_ui.py`

## Flujo de trabajo típico

### 📊 Dashboard - Análisis General

1. Seleccionar una o más ejecuciones (Ctrl+Click para multi-selección)
2. Marcar/desmarcar "Mostrar TOTAL" según necesidad
3. Ajustar "Umbral conf" si se desea (default: 0.08)
4. Click en "Refrescar" para cargar estadísticas
5. Navegar por las pestañas creadas para ver métricas de cada ejecución

**Métricas mostradas:**
- Total conversaciones y turnos
- % turnos clasificados vs sin clasificar
- Turnos pendientes según umbral
- Distribución por fase (top fases)
- Distribución por source (DEEPSEEK, RULES, etc.)
- Estadísticas de promesas (si existen)

### 🔍 Detalles - Navegación

1. Seleccionar ejecución del combo
2. Buscar conversaciones:
   - Dejar vacío para ver las últimas 500
   - Escribir parte del conversacion_id para buscar
   - Escribir número para buscar por PK
3. Click en conversación para ver sus turnos
4. Click en turno para ver texto completo en panel inferior

**Útil para:**
- Revisar conversaciones específicas
- Ver contexto de turnos clasificados
- Inspeccionar fases asignadas

### ✏️ Aprendizaje - Corrección Humana

#### Opción 1: Guardar a CSV (sin modificar BD)

1. Seleccionar ejecución
2. Ajustar umbral si se desea
3. Click "Cargar Pendientes" (carga 200 turnos)
4. Navegar con "Anterior"/"Siguiente"
5. Click en turno pendiente para verlo
6. Seleccionar fase del combo
7. Opcionalmente: agregar intent y nota
8. Click "Guardar a CSV"
9. Repetir para más turnos

**Resultado:** Archivo `out_reports/labels_turnos.csv` con correcciones

#### Opción 2: Aplicar directo a BD

1. Igual que opción 1, pero click "Aplicar a BD" en vez de CSV
2. Confirmar en diálogo
3. La BD se actualiza inmediatamente:
   - fase = nueva_fase
   - fase_source = 'HUMAN'
   - fase_conf = 1.0
   - (opcional) intent = nuevo_intent, intent_conf = 1.0

#### Opción 3: Buffer de correcciones

1. Realizar múltiples correcciones sin escribir a BD
2. Acumular en buffer
3. Click "Aplicar Buffer a BD (WRITE)" para escribir todas juntas
4. Útil para revisar lote antes de commitear

## ⌨️ Atajos de teclado

- **Multi-selección en listas**: Ctrl+Click, Shift+Click
- **Búsqueda en Detalles**: Enter en campo de búsqueda
- **Navegación de pestañas**: Ctrl+Tab (estándar OS)

## 🔄 Refrescar datos

- Dashboard: Click "Refrescar"
- Detalles: Cambiar ejecución o hacer nueva búsqueda
- Aprendizaje: Click "Cargar Pendientes" de nuevo

## ⚠️ Solución de problemas

### "Error de Conexión"

1. Verificar que MySQL está corriendo:
   ```bash
   # Windows
   net start MySQL80
   
   # O verificar en Services
   ```

2. Verificar config.ini (host, port, user, password, database)

3. Probar conexión manual:
   ```bash
   mysql -u root -p -h localhost speech_analytics
   ```

4. Si persiste: Menú → Archivo → Reconectar DB

### "No hay ejecuciones"

- La tabla `sa_conversaciones` debe tener datos
- Verificar con query manual:
  ```sql
  SELECT DISTINCT ejecucion_id FROM sa_conversaciones;
  ```

### "Columna no existe"

- La UI detecta columnas automáticamente
- Si hay error, verificar que tablas existan:
  ```sql
  SHOW TABLES LIKE 'sa_%';
  SHOW COLUMNS FROM sa_turnos;
  ```

### UI no responde

- Queries grandes pueden tardar
- Esperar unos segundos
- Si se congela >30s, cerrar y reabrir
- Considerar limitar ejecuciones seleccionadas

## 📁 Archivos generados

- `out_reports/labels_turnos.csv`: Correcciones exportadas
  - Formato: timestamp, conversacion_pk, turno_idx, fase_original, fase_nueva, intent_nuevo, nota
  - Se crea si no existe
  - Modo append (no sobrescribe)

## 🎯 Tips de uso

1. **Dashboard**: Usar "Mostrar TOTAL" para comparar múltiples ejecuciones agregadas
2. **Detalles**: Buscar por conversacion_id es más rápido que listar todas
3. **Aprendizaje**: Trabajar por lotes de 200 turnos, usar paginación
4. **CSV**: Útil para auditoría y backup de correcciones antes de escribir a BD
5. **Buffer**: Permite corregir varios turnos y luego aplicar todos juntos (más eficiente)

## 🔐 Seguridad

- Las escrituras a BD requieren confirmación
- CSV guarda historial con timestamp
- fase_source='HUMAN' permite identificar correcciones manuales
- No hay "undo" directo, usar backups de BD antes de correcciones masivas

## 📊 Métricas del Dashboard explicadas

- **Turnos con fase**: `fase IS NOT NULL AND TRIM(fase) != ''`
- **Turnos sin fase**: `fase IS NULL OR TRIM(fase) = ''`
- **Pendientes (umbral)**: Sin fase OR `fase_conf < threshold`
- **Distribución por fase**: Solo turnos con fase != null/empty
- **Distribución por source**: Todas las filas (incluye nulls)

## 🆘 Soporte

Para errores o dudas:
1. Revisar logs en consola (stdout)
2. Verificar tablas en MySQL
3. Consultar [UI_README.md](UI_README.md) para documentación completa
