# 🤖 Vista DeepSeek - Documentación

## Descripción General

La pestaña **DeepSeek** proporciona una interfaz unificada para:
1. **Editar prompts** utilizados en clasificación con LLM
2. **Configurar credenciales y parámetros** de DeepSeek API
3. **Gestionar configuración de base de datos** sin editar archivos manualmente

## Características

### 📝 Editor de Prompt

- **Text widget grande** con scroll para editar el prompt template
- **Ruta automática**: `prompts/deepseek_prompt.txt`
- **Creación automática** de carpeta `prompts/` si no existe
- **Encoding UTF-8** para caracteres especiales

**Botones**:
- `📂 Cargar Prompt`: Lee desde archivo (si existe)
- `💾 Guardar Prompt`: Escribe a archivo

**Uso típico**:
1. Editar el template con placeholders: `{contexto}`, `{turno_idx}`, `{speaker}`, `{text}`
2. Guardar con el botón
3. El script que llame a DeepSeek puede leer este archivo

---

### 🤖 Configuración DeepSeek

Gestiona las credenciales y parámetros de la API de DeepSeek.

**Campos**:
- `API Key` (enmascarado con `*`):
  - Checkbox "Mostrar" para toggle visibilidad
  - **NO se loguea** al guardar (seguridad)
  
- `Base URL`:
  - Ejemplo: `https://api.deepseek.com`
  
- `Model`:
  - Ejemplo: `deepseek-chat`, `deepseek-coder`
  
- `Temperature` (float):
  - Rango: 0.0 - 2.0
  - Default: 0.7
  - Controla creatividad de respuestas
  
- `Max Tokens` (int):
  - Límite de tokens en respuesta
  - Default: 2048

**Botones**:
- `📂 Cargar Config`: Lee desde `config.ini` sección `[deepseek]`
- `💾 Guardar Config`: Escribe a `config.ini` (preserva otras secciones)
- `🔍 Probar DeepSeek`: Valida campos (sin hacer llamadas reales)

**Persistencia**:
```ini
[deepseek]
api_key = sk-xxxxxxxxxxxxx
base_url = https://api.deepseek.com
model = deepseek-chat
temperature = 0.7
max_tokens = 2048
```

**Validación** (botón "Probar DeepSeek"):
- ✓ API Key no vacía
- ✓ Base URL no vacía
- ✓ Model no vacío
- ✓ Temperature entre 0 y 2
- ✓ Max Tokens > 0

---

### 🗄️ Configuración Base de Datos

Permite modificar configuración DB sin editar `config.ini` manualmente.

**Detección Automática**:
- Busca primera sección con keys `host` + (`database` o `db`)
- Secciones detectadas: `[mysql]`, `[db]`, `[postgres]`, etc.
- Si no se encuentra, crea `[mysql]` por defecto

**Campos**:
- `Host`: Dirección del servidor (ej: `127.0.0.1`, `localhost`)
- `Port`: Puerto (default: `3306` para MySQL)
- `User`: Usuario de la base de datos
- `Password` (enmascarado con `*`):
  - Checkbox "Mostrar" para toggle visibilidad
  - **NO se loguea** al guardar
- `Database`: Nombre de la base de datos

**Botones**:
- `📂 Cargar DB Config`: Lee desde `config.ini`
- `💾 Guardar DB Config`: Escribe a `config.ini`
  - **Nota**: Reiniciar aplicación para aplicar cambios
- `🔌 Probar Conexión DB`: Ejecuta `SELECT 1` para validar

**Sección en config.ini**:
```ini
[mysql]
host = 127.0.0.1
port = 3306
user = sa_app
password = SaApp#2026!Vm_9xQ
database = speech_analytics
```

**Prueba de Conexión**:
- Usa los valores **actuales en los inputs** (no requiere guardar primero)
- Ejecuta `SELECT 1` contra la DB
- Muestra mensaje de éxito o error detallado

---

## Workflow Típico

### Configurar DeepSeek (Primera vez)

1. Ir a pestaña **🤖 DeepSeek**
2. Scroll a "Configuración DeepSeek"
3. Ingresar:
   - API Key (obtener de https://platform.deepseek.com)
   - Base URL: `https://api.deepseek.com`
   - Model: `deepseek-chat`
   - Temperature: `0.7`
   - Max Tokens: `2048`
4. Click **💾 Guardar Config**
5. Click **🔍 Probar DeepSeek** para validar

### Editar Prompt

1. Scroll a "Editor de Prompt"
2. Click **📂 Cargar Prompt** (si ya existe)
3. Modificar el texto:
   - Agregar instrucciones
   - Modificar placeholders: `{contexto}`, `{turno_idx}`, etc.
   - Ajustar formato de respuesta esperada
4. Click **💾 Guardar Prompt**

### Modificar Config DB

1. Scroll a "Configuración Base de Datos"
2. Click **📂 Cargar DB Config**
3. Modificar campos (ej: cambiar password)
4. Click **🔌 Probar Conexión DB** para verificar
5. Si funciona, click **💾 Guardar DB Config**
6. **Reiniciar la aplicación** para aplicar

---

## Seguridad

### Enmascaramiento de Credenciales

- **API Key** y **Password DB** se muestran con `*` por defecto
- Checkbox "Mostrar" permite toggle temporal de visibilidad
- Al cerrar la app, vuelven a enmascararse

### No Logging de Credenciales

Al guardar configuración:
```python
logger.info("Config DeepSeek guardada (api_key no logueada)")
logger.info("Config DB guardada en sección [mysql] (password no logueada)")
```

Los valores reales de `api_key` y `password` **NUNCA** se escriben en logs.

### Preservación de Config.ini

Al guardar, se usa `configparser` que:
- ✅ Lee el archivo completo existente
- ✅ Modifica SOLO la sección objetivo (`[deepseek]` o `[mysql]`)
- ✅ Preserva TODAS las demás secciones y claves
- ✅ No borra comentarios (aunque pueden reordenarse)

**Ejemplo**: Si `config.ini` tiene:
```ini
[mysql]
host = localhost
database = mydb

[app]
conf_threshold = 0.8

[custom_section]
my_key = my_value
```

Al guardar config DeepSeek, se agrega:
```ini
[mysql]
host = localhost
database = mydb

[app]
conf_threshold = 0.8

[custom_section]
my_key = my_value

[deepseek]          # ← NUEVA SECCIÓN
api_key = sk-xxx
base_url = https://api.deepseek.com
model = deepseek-chat
temperature = 0.7
max_tokens = 2048
```

Las secciones `[app]` y `[custom_section]` **NO se pierden**.

---

## Troubleshooting

### Error: "Archivo config.ini no existe"

**Causa**: Primera ejecución o archivo borrado

**Solución**: Simplemente ingresa los valores y guarda. El archivo se creará automáticamente.

### Error al cargar config: "Sección no encontrada"

**Causa**: La sección `[deepseek]` o `[mysql]` no existe en `config.ini`

**Solución**: Ingresa los valores manualmente y guarda. La sección se creará.

### Prompt no se carga

**Causa**: Archivo `prompts/deepseek_prompt.txt` no existe

**Solución**: Escribe el prompt en el editor y usa **💾 Guardar Prompt**. La carpeta se creará automáticamente.

### Cambios en DB Config no se aplican

**Causa**: La aplicación carga `config.ini` al inicio

**Solución**: **Reiniciar la aplicación** después de guardar cambios en DB Config.

### Error de conexión DB después de modificar config

**Diagnóstico**:
1. Usar **🔌 Probar Conexión DB** ANTES de guardar
2. Verificar valores: host, port, user, password, database
3. Asegurar que MySQL esté corriendo: `mysql -u sa_app -p`

**Errores comunes**:
- `2003: Can't connect to MySQL server`: MySQL no está corriendo o host/port incorrectos
- `1045: Access denied`: User/password incorrectos
- `1049: Unknown database`: Database no existe

### Validación DeepSeek falla

**Errores y soluciones**:

| Error | Solución |
|-------|----------|
| API Key está vacía | Ingresar API Key obtenida de plataforma DeepSeek |
| Base URL está vacía | Usar `https://api.deepseek.com` u otra URL válida |
| Model está vacío | Ingresar nombre de modelo (ej: `deepseek-chat`) |
| Temperature fuera de rango | Usar valor entre 0.0 y 2.0 |
| Max Tokens inválido | Usar número entero positivo |

---

## Integración con Scripts

### Leer Prompt desde Script

```python
from pathlib import Path

prompt_file = Path("prompts/deepseek_prompt.txt")
if prompt_file.exists():
    prompt_template = prompt_file.read_text(encoding="utf-8")
    
    # Reemplazar placeholders
    prompt = prompt_template.format(
        contexto="...",
        turno_idx=5,
        speaker="AGENTE",
        text="Buenos días, le llamo por..."
    )
else:
    print("Error: Prompt no encontrado. Edite desde la UI.")
```

### Leer Config DeepSeek desde Script

```python
import configparser

config = configparser.ConfigParser()
config.read("config.ini", encoding="utf-8")

if config.has_section("deepseek"):
    api_key = config.get("deepseek", "api_key")
    base_url = config.get("deepseek", "base_url")
    model = config.get("deepseek", "model")
    temperature = config.getfloat("deepseek", "temperature")
    max_tokens = config.getint("deepseek", "max_tokens")
    
    # Usar con cliente DeepSeek
    # client = OpenAI(api_key=api_key, base_url=base_url)
    # ...
else:
    print("Error: Configuración DeepSeek no encontrada en config.ini")
```

---

## Archivos Relacionados

```
speech_analytic_mejorado/
├── config.ini                      # ← Configuración (DeepSeek + DB)
├── prompts/
│   └── deepseek_prompt.txt        # ← Prompt template
├── ui/
│   ├── app.py                     # ← Registro de pestaña DeepSeek
│   └── views_deepseek.py          # ← Vista principal (este módulo)
└── test_deepseek_view.py          # ← Tests (5/5 pasando)
```

---

## Tests

**Ejecutar validación**:
```bash
python test_deepseek_view.py
```

**Tests incluidos** (5 total):
1. ✓ Imports correctos
2. ✓ Detección automática de sección DB
3. ✓ Verificación de archivo de prompt
4. ✓ Instanciación de vista
5. ✓ Preservación de secciones en configparser

**Resultado esperado**:
```
✓ TODOS LOS TESTS PASARON
```

---

## Ejemplo de config.ini Completo

```ini
[mysql]
host = 127.0.0.1
port = 3306
user = sa_app
password = SaApp#2026!Vm_9xQ
database = speech_analytics

[app]
conf_threshold = 0.8
input_encoding = utf-8

[deepseek]
api_key = sk-abc123def456...
base_url = https://api.deepseek.com
model = deepseek-chat
temperature = 0.7
max_tokens = 2048
```

---

## Notas Finales

- **No requiere reinicio** para cambios en DeepSeek o Prompt
- **Requiere reinicio** para cambios en DB Config (aplicación carga config al inicio)
- **Todos los archivos son UTF-8**: Soporta caracteres especiales en prompts
- **Validación sin API calls**: "Probar DeepSeek" NO consume créditos, solo valida campos
- **Conexión DB no afecta config**: Probar conexión no modifica `config.ini`

---

**Última actualización**: 2026-02-09  
**Versión**: 1.0.0  
**Tests**: ✓ 5/5 pasados
