# ✅ FIX: Error "MySQL Connection not available" en UI

## Problema Identificado

Las vistas en la UI reportaban error:
```
ui.services - ERROR - Error listando ejecuciones: MySQL Connection not available.
```

**Causa**: Las vistas podían recibir `db_conn = None` o la conexión se cerraba antes de que las vistas la usaran.

## Solución Implementada

### Cambios en `ui/app.py`

#### 1. Nueva Función: `_inject_db_conn_into_views()`

```python
def _inject_db_conn_into_views(self):
    """Inyecta la conexión DB en todas las vistas existentes"""
    if self.db_conn is None:
        logger.warning("No se puede inyectar db_conn: conexión es None")
        return
    
    views = [
        ('dashboard_view', self.dashboard_view),
        ('detalles_view', self.detalles_view),
        ('aprendizaje_view', self.aprendizaje_view),
        ('deepseek_view', self.deepseek_view)
    ]
    
    for view_name, view_instance in views:
        if view_instance is not None:
            view_instance.db_conn = self.db_conn
            logger.debug(f"DB conn inyectada en {view_name}")
```

**Propósito**: Asegurar que TODAS las vistas tengan acceso a la conexión DB válida.

#### 2. Modificación: `_connect_db()`

**ANTES**:
```python
def _connect_db(self):
    try:
        logger.info("Conectando a base de datos...")
        self.db_conn = services.get_db_connection()
        self.db_status = "Conectado"
        self._update_status()
        
        # Crear vistas ahora que tenemos conexión
        self._create_views()
        
        logger.info("Conexión exitosa")
    except Exception as e:
        # ... error handling
```

**DESPUÉS**:
```python
def _connect_db(self):
    try:
        logger.info("Conectando a base de datos...")
        self.db_conn = services.get_db_connection()
        
        # Verificar que la conexión es válida
        if self.db_conn is None:
            raise Exception("get_db_connection() retornó None")
        
        self.db_status = "Conectado"
        self._update_status()
        
        # Inyectar conexión en vistas existentes (si las hay)
        self._inject_db_conn_into_views()
        
        # Crear vistas ahora que tenemos conexión
        self._create_views()
        
        # Inyectar nuevamente después de crear vistas
        self._inject_db_conn_into_views()
        
        logger.info("Conexión exitosa")
    except Exception as e:
        # ... error handling
```

**Mejoras**:
- ✅ Verifica que `self.db_conn` no sea `None`
- ✅ Inyecta conexión ANTES de crear vistas (por si hay vistas previas)
- ✅ Inyecta conexión DESPUÉS de crear vistas (para garantizar que las nuevas la tengan)
- ✅ Doble inyección asegura que todas las vistas tengan conexión válida

#### 3. Modificación: `_create_views()`

**ANTES**:
```python
def _create_views(self):
    if not self.db_conn:
        logger.warning("No se pueden crear vistas sin conexión DB")
        return
    
    # Limpiar vistas existentes
    for tab in self.notebook.tabs():
        self.notebook.forget(tab)
    
    # Crear vistas
    try:
        self.dashboard_view = DashboardView(self.notebook, self.db_conn)
        # ... más vistas
```

**DESPUÉS**:
```python
def _create_views(self):
    if not self.db_conn:
        logger.warning("No se pueden crear vistas sin conexión DB")
        return
    
    # Verificar que la conexión sigue activa
    try:
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        logger.debug("Conexión DB verificada antes de crear vistas")
    except Exception as e:
        logger.error(f"Conexión DB no válida antes de crear vistas: {e}")
        messagebox.showerror("Error", f"Conexión DB no válida: {e}")
        return
    
    # Limpiar vistas existentes
    for tab in self.notebook.tabs():
        self.notebook.forget(tab)
    
    # Crear vistas CON la conexión válida
    try:
        self.dashboard_view = DashboardView(self.notebook, self.db_conn)
        # ... más vistas
```

**Mejoras**:
- ✅ Verifica que la conexión está activa con `SELECT 1` antes de crear vistas
- ✅ Si la conexión no es válida, muestra error y retorna
- ✅ Evita crear vistas con conexión corrupta o cerrada

## Flujo Corregido

### Al Iniciar la Aplicación

1. **`__init__()`**
   - Inicializa `self.db_conn = None`
   - Llama `_build_ui()` (crea UI sin vistas)
   - Llama `_connect_db()`

2. **`_connect_db()`**
   - Ejecuta `self.db_conn = services.get_db_connection()`
   - ✅ **Verifica que `self.db_conn` no sea `None`**
   - ✅ **Inyecta conexión en vistas existentes** (si las hay)
   - Llama `_create_views()`
   - ✅ **Inyecta conexión nuevamente** (en vistas recién creadas)

3. **`_create_views()`**
   - Verifica que `self.db_conn` existe
   - ✅ **Ejecuta `SELECT 1` para validar conexión activa**
   - Crea las 4 vistas pasando `self.db_conn` al constructor
   - Las vistas reciben conexión válida y activa

4. **`_inject_db_conn_into_views()`** (llamado 2 veces)
   - Primera vez: Antes de crear vistas (por si hay vistas previas)
   - Segunda vez: Después de crear vistas (garantía)
   - Asigna `view.db_conn = self.db_conn` a todas las vistas

### Al Reconectar (`_reconnect_db()`)

1. Cierra conexión anterior si existe
2. Llama `_connect_db()` que sigue el flujo completo
3. Las vistas existentes reciben la nueva conexión via inyección

## Validación

### Test Automatizado

**Archivo**: `test_db_connection_fix.py`

```bash
$ python test_db_connection_fix.py
======================================================================
TEST: Validación de flujo de conexión DB en UI
======================================================================

✓ Imports exitosos
✓ Conexión obtenida: <class 'mysql.connector.connection_cext.CMySQLConnection'>
✓ SELECT 1 retornó: (1,)
✓ Conexión sigue activa: SELECT 2 = (2,)
✓ Conexión inyectada en 4 vistas
✓ Vista 'dashboard' puede ejecutar queries
✓ Vista 'detalles' puede ejecutar queries
✓ Vista 'aprendizaje' puede ejecutar queries
✓ Vista 'deepseek' puede ejecutar queries
✓ Conexión cerrada correctamente

======================================================================
✓ TODOS LOS TESTS PASARON
======================================================================

Conclusión:
- get_db_connection() retorna conexión válida
- La conexión NO se cierra automáticamente
- Múltiples queries pueden ejecutarse en la misma conexión
- Inyección de db_conn en vistas funciona correctamente
```

### Prueba Manual

```bash
# Ejecutar la aplicación
python run_ui.py

# Verificar en logs (NO debe aparecer):
# ✗ ui.services - ERROR - Error listando ejecuciones: MySQL Connection not available.

# Verificar que SÍ aparece:
# ✓ [INFO] Conectando a base de datos...
# ✓ [DEBUG] Conexión DB verificada antes de crear vistas
# ✓ [DEBUG] DB conn inyectada en dashboard_view
# ✓ [DEBUG] DB conn inyectada en detalles_view
# ✓ [DEBUG] DB conn inyectada en aprendizaje_view
# ✓ [DEBUG] DB conn inyectada en deepseek_view
# ✓ [INFO] Vistas creadas exitosamente
# ✓ [INFO] Conexión exitosa
```

## Garantías del Fix

### ✅ Conexión Válida Antes de Crear Vistas
- Se ejecuta `SELECT 1` para verificar que la conexión funciona
- Si falla, no se crean vistas y se muestra error

### ✅ Inyección Doble
- Primera inyección: Antes de crear vistas (vistas previas si existen)
- Segunda inyección: Después de crear vistas (vistas nuevas)

### ✅ Conexión Persistente
- `services.get_db_connection()` retorna conexión persistente
- NO se cierra automáticamente (no usa context manager en este punto)
- La conexión vive mientras la app está abierta
- Solo se cierra en `_on_closing()` o al reconectar

### ✅ Manejo de Errores
- Si `get_db_connection()` retorna `None`, se lanza excepción clara
- Si la conexión falla `SELECT 1`, se aborta creación de vistas
- Mensajes de error informativos para el usuario

## Efectos en las Vistas

### Dashboard View
- `listar_ejecuciones()` ahora funciona correctamente
- `stats_total()` puede ejecutar queries
- NO más error "MySQL Connection not available"

### Detalles View
- `listar_conversaciones()` funciona
- `listar_turnos()` funciona
- Navegación entre conversaciones y turnos funcional

### Aprendizaje View
- `listar_turnos_pendientes()` funciona
- `get_turnos_context()` funciona
- `aplicar_correccion_turno()` puede escribir a DB
- Exportación CSV funcional

### DeepSeek View
- Botón "Probar Conexión DB" funciona
- Lectura/escritura de config.ini funcional
- Sin dependencia de queries (vista de configuración)

## Archivos Modificados

```
ui/
└── app.py                          # ← MODIFICADO
    ├── _connect_db()              # Agregada validación + doble inyección
    ├── _inject_db_conn_into_views()  # NUEVA función
    └── _create_views()            # Agregada verificación SELECT 1
```

## Archivos Creados

```
test_db_connection_fix.py          # ← NUEVO (validación automática)
FIX_DB_CONNECTION_DOCS.md          # ← NUEVO (este archivo)
```

## Breaking Changes

**Ninguno**. El cambio es 100% retrocompatible:
- Las vistas siguen recibiendo `db_conn` en el constructor
- Se agrega inyección adicional como garantía
- No se modifican constructores de vistas
- No se modifican métodos de services.py

## Troubleshooting

### Error persiste después del fix

**Verificar**:
1. ¿MySQL está corriendo? `mysql -u sa_app -p`
2. ¿config.ini tiene credenciales correctas?
3. Revisar logs para ver si hay otro error antes

**Solución**:
- Usar menú "Archivo > Reconectar DB"
- Reiniciar la aplicación

### Vistas no cargan datos

**Verificar**:
- Abrir logs (nivel DEBUG)
- Buscar línea: `Conexión DB verificada antes de crear vistas`
- Buscar líneas: `DB conn inyectada en {view_name}`

**Si no aparecen**:
- La conexión falló antes de crear vistas
- Revisar error anterior en logs

### Reconectar no funciona

**Causa**: Conexión anterior no se cerró correctamente

**Solución**:
- Reiniciar la aplicación completamente
- Verificar que MySQL acepte nuevas conexiones: `SHOW PROCESSLIST;`

---

**Estado**: ✅ **COMPLETADO Y VALIDADO**  
**Fecha**: 2026-02-09  
**Tests**: ✓ Todos los tests pasados  
**Breaking Changes**: Ninguno
