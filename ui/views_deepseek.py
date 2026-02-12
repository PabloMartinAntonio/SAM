"""
Vista DeepSeek: Editor de prompt + Configuración DeepSeek/DB
"""
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import logging
from pathlib import Path
import configparser

logger = logging.getLogger(__name__)

# Constantes
PROMPT_FILE = Path("prompts/deepseek_prompt.txt")
CONFIG_FILE = Path("config.ini")


class DeepSeekView(ttk.Frame):
    """Vista para configuración de DeepSeek y edición de prompts"""
    
    def __init__(self, parent, db_conn, app=None):
        super().__init__(parent)
        self.db_conn = db_conn
        self.app = app  # Referencia a SpeechAnalyticsApp para broadcast
        
        # Variables de config DeepSeek
        self.api_key_var = tk.StringVar()
        self.base_url_var = tk.StringVar()
        self.model_var = tk.StringVar()
        self.temperature_var = tk.StringVar(value="0.7")
        self.max_tokens_var = tk.StringVar(value="2048")
        self.show_api_key_var = tk.BooleanVar(value=False)
        
        # Variables de config DB
        self.db_host_var = tk.StringVar()
        self.db_port_var = tk.StringVar()
        self.db_user_var = tk.StringVar()
        self.db_password_var = tk.StringVar()
        self.db_database_var = tk.StringVar()
        self.show_db_password_var = tk.BooleanVar(value=False)
        
        # Detectar sección DB automáticamente
        self.db_section = self._detect_db_section()
        
        self._build_ui()
        
        # Cargar configs al inicio
        self._cargar_prompt_inicial()
        self._cargar_config_deepseek_inicial()
        self._cargar_config_db_inicial()
    
    def on_global_refresh(self, *, reason: str, preserve_id: int = None, select_id: int = None):
        """Handler de refresh global - stub básico (DeepSeek no tiene lista de ejecuciones)"""
        logger.info(f"DeepSeekView.on_global_refresh: reason={reason}")
        # Esta vista no tiene lista de ejecuciones, no hace nada
        pass
    
    def reload_runs(self, preserve_id: int = None, select_id: int = None):
        """Stub - DeepSeek no tiene lista de ejecuciones"""
        pass
    
    def refresh_data(self):
        """Stub - DeepSeek no tiene datos que refrescar"""
        pass
    
    def _detect_db_section(self):
        """Detecta automáticamente la sección DB en config.ini"""
        if not CONFIG_FILE.exists():
            return "mysql"
        
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE, encoding="utf-8")
        
        # Buscar sección con keys típicas de DB
        for section in config.sections():
            if config.has_option(section, "host") and \
               (config.has_option(section, "database") or config.has_option(section, "db")):
                logger.info(f"Detectada sección DB: [{section}]")
                return section
        
        # No encontrada, usar mysql por defecto
        logger.info("No se detectó sección DB, usando [mysql] por defecto")
        return "mysql"
    
    def _build_ui(self):
        """Construye la UI de la vista"""
        # Main container con scrollbar
        canvas = tk.Canvas(self, borderwidth=0)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Contenido en scrollable_frame
        main_frame = ttk.Frame(scrollable_frame, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # =================================================================
        # SECCIÓN 1: Editor de Prompt
        # =================================================================
        prompt_frame = ttk.LabelFrame(main_frame, text="📝 Editor de Prompt", padding=10)
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Label con ruta del archivo
        self.prompt_path_label = ttk.Label(
            prompt_frame,
            text=f"Archivo: {PROMPT_FILE}",
            foreground="gray"
        )
        self.prompt_path_label.pack(anchor=tk.W, pady=(0, 5))
        
        # Text widget para el prompt
        self.prompt_text = scrolledtext.ScrolledText(
            prompt_frame,
            height=15,
            width=80,
            wrap=tk.WORD,
            font=("Consolas", 10)
        )
        self.prompt_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Botones
        prompt_btn_frame = ttk.Frame(prompt_frame)
        prompt_btn_frame.pack(fill=tk.X)
        
        ttk.Button(
            prompt_btn_frame,
            text="📂 Cargar Prompt",
            command=self._cargar_prompt
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            prompt_btn_frame,
            text="💾 Guardar Prompt",
            command=self._guardar_prompt
        ).pack(side=tk.LEFT, padx=5)
        
        # =================================================================
        # SECCIÓN 2: Configuración DeepSeek
        # =================================================================
        deepseek_frame = ttk.LabelFrame(main_frame, text="🤖 Configuración DeepSeek", padding=10)
        deepseek_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Grid para inputs
        row = 0
        
        # API Key (enmascarado)
        ttk.Label(deepseek_frame, text="API Key:").grid(row=row, column=0, sticky=tk.W, pady=5)
        api_key_entry = ttk.Entry(
            deepseek_frame,
            textvariable=self.api_key_var,
            show="*",
            width=40
        )
        api_key_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # Checkbox para mostrar API key
        self.api_key_checkbox = ttk.Checkbutton(
            deepseek_frame,
            text="Mostrar",
            variable=self.show_api_key_var,
            command=self._toggle_api_key_visibility
        )
        self.api_key_checkbox.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        self.api_key_entry = api_key_entry  # Guardar referencia
        row += 1
        
        # Base URL
        ttk.Label(deepseek_frame, text="Base URL:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            deepseek_frame,
            textvariable=self.base_url_var,
            width=40
        ).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # Model
        ttk.Label(deepseek_frame, text="Model:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            deepseek_frame,
            textvariable=self.model_var,
            width=40
        ).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # Temperature
        ttk.Label(deepseek_frame, text="Temperature:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            deepseek_frame,
            textvariable=self.temperature_var,
            width=20
        ).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        row += 1
        
        # Max Tokens
        ttk.Label(deepseek_frame, text="Max Tokens:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            deepseek_frame,
            textvariable=self.max_tokens_var,
            width=20
        ).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        row += 1
        
        # Configurar expansión de columna
        deepseek_frame.columnconfigure(1, weight=1)
        
        # Botones
        deepseek_btn_frame = ttk.Frame(deepseek_frame)
        deepseek_btn_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0), sticky=tk.W)
        
        ttk.Button(
            deepseek_btn_frame,
            text="📂 Cargar Config",
            command=self._cargar_config_deepseek
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            deepseek_btn_frame,
            text="💾 Guardar Config",
            command=self._guardar_config_deepseek
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            deepseek_btn_frame,
            text="🔍 Probar DeepSeek",
            command=self._probar_deepseek
        ).pack(side=tk.LEFT, padx=5)
        
        # =================================================================
        # SECCIÓN 3: Configuración DB
        # =================================================================
        db_frame = ttk.LabelFrame(main_frame, text="🗄️ Configuración Base de Datos", padding=10)
        db_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Label con sección detectada
        ttk.Label(
            db_frame,
            text=f"Sección en config.ini: [{self.db_section}]",
            foreground="gray"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))
        
        # Grid para inputs
        row = 1
        
        # Host
        ttk.Label(db_frame, text="Host:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            db_frame,
            textvariable=self.db_host_var,
            width=40
        ).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # Port
        ttk.Label(db_frame, text="Port:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            db_frame,
            textvariable=self.db_port_var,
            width=20
        ).grid(row=row, column=1, sticky=tk.W, padx=5, pady=5)
        row += 1
        
        # User
        ttk.Label(db_frame, text="User:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            db_frame,
            textvariable=self.db_user_var,
            width=40
        ).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # Password (enmascarado)
        ttk.Label(db_frame, text="Password:").grid(row=row, column=0, sticky=tk.W, pady=5)
        db_password_entry = ttk.Entry(
            db_frame,
            textvariable=self.db_password_var,
            show="*",
            width=40
        )
        db_password_entry.grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        
        # Checkbox para mostrar password
        self.db_password_checkbox = ttk.Checkbutton(
            db_frame,
            text="Mostrar",
            variable=self.show_db_password_var,
            command=self._toggle_db_password_visibility
        )
        self.db_password_checkbox.grid(row=row, column=2, sticky=tk.W, padx=5, pady=5)
        self.db_password_entry = db_password_entry  # Guardar referencia
        row += 1
        
        # Database
        ttk.Label(db_frame, text="Database:").grid(row=row, column=0, sticky=tk.W, pady=5)
        ttk.Entry(
            db_frame,
            textvariable=self.db_database_var,
            width=40
        ).grid(row=row, column=1, sticky=tk.EW, padx=5, pady=5)
        row += 1
        
        # Configurar expansión de columna
        db_frame.columnconfigure(1, weight=1)
        
        # Botones
        db_btn_frame = ttk.Frame(db_frame)
        db_btn_frame.grid(row=row, column=0, columnspan=3, pady=(10, 0), sticky=tk.W)
        
        ttk.Button(
            db_btn_frame,
            text="📂 Cargar DB Config",
            command=self._cargar_config_db
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            db_btn_frame,
            text="💾 Guardar DB Config",
            command=self._guardar_config_db
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            db_btn_frame,
            text="🔌 Probar Conexión DB",
            command=self._probar_conexion_db
        ).pack(side=tk.LEFT, padx=5)
    
    # =================================================================
    # MÉTODOS: Editor de Prompt
    # =================================================================
    
    def _cargar_prompt_inicial(self):
        """Carga el prompt al iniciar (si existe)"""
        if PROMPT_FILE.exists():
            try:
                content = PROMPT_FILE.read_text(encoding="utf-8")
                self.prompt_text.delete("1.0", tk.END)
                self.prompt_text.insert("1.0", content)
                logger.info(f"Prompt cargado desde {PROMPT_FILE}")
            except Exception as e:
                logger.warning(f"No se pudo cargar prompt inicial: {e}")
    
    def _cargar_prompt(self):
        """Carga el prompt desde archivo"""
        if not PROMPT_FILE.exists():
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El archivo {PROMPT_FILE} no existe.\n\n"
                "Puede crear uno escribiendo en el editor y guardando."
            )
            return
        
        try:
            content = PROMPT_FILE.read_text(encoding="utf-8")
            self.prompt_text.delete("1.0", tk.END)
            self.prompt_text.insert("1.0", content)
            messagebox.showinfo("OK", f"Prompt cargado desde:\n{PROMPT_FILE}")
            logger.info(f"Prompt cargado desde {PROMPT_FILE}")
        except Exception as e:
            logger.error(f"Error cargando prompt: {e}")
            messagebox.showerror("Error", f"Error cargando prompt:\n{e}")
    
    def _guardar_prompt(self):
        """Guarda el prompt a archivo"""
        try:
            # Crear carpeta si no existe
            PROMPT_FILE.parent.mkdir(parents=True, exist_ok=True)
            
            # Obtener contenido del editor
            content = self.prompt_text.get("1.0", tk.END).rstrip()
            
            # Guardar
            PROMPT_FILE.write_text(content, encoding="utf-8")
            
            messagebox.showinfo("OK", f"Prompt guardado en:\n{PROMPT_FILE}")
            logger.info(f"Prompt guardado en {PROMPT_FILE}")
        except Exception as e:
            logger.error(f"Error guardando prompt: {e}")
            messagebox.showerror("Error", f"Error guardando prompt:\n{e}")
    
    # =================================================================
    # MÉTODOS: Configuración DeepSeek
    # =================================================================
    
    def _cargar_config_deepseek_inicial(self):
        """Carga config DeepSeek al iniciar"""
        if not CONFIG_FILE.exists():
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            
            if config.has_section("deepseek"):
                self.api_key_var.set(config.get("deepseek", "api_key", fallback=""))
                self.base_url_var.set(config.get("deepseek", "base_url", fallback=""))
                self.model_var.set(config.get("deepseek", "model", fallback=""))
                self.temperature_var.set(config.get("deepseek", "temperature", fallback="0.7"))
                self.max_tokens_var.set(config.get("deepseek", "max_tokens", fallback="2048"))
                
                logger.info("Config DeepSeek cargada al iniciar")
        except Exception as e:
            logger.warning(f"No se pudo cargar config DeepSeek inicial: {e}")
    
    def _cargar_config_deepseek(self):
        """Carga config DeepSeek desde config.ini"""
        if not CONFIG_FILE.exists():
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El archivo {CONFIG_FILE} no existe.\n\n"
                "Será creado al guardar la configuración."
            )
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            
            if not config.has_section("deepseek"):
                messagebox.showwarning(
                    "Sección no encontrada",
                    "No se encontró la sección [deepseek] en config.ini.\n\n"
                    "Será creada al guardar."
                )
                return
            
            self.api_key_var.set(config.get("deepseek", "api_key", fallback=""))
            self.base_url_var.set(config.get("deepseek", "base_url", fallback=""))
            self.model_var.set(config.get("deepseek", "model", fallback=""))
            self.temperature_var.set(config.get("deepseek", "temperature", fallback="0.7"))
            self.max_tokens_var.set(config.get("deepseek", "max_tokens", fallback="2048"))
            
            messagebox.showinfo("OK", "Configuración DeepSeek cargada correctamente")
            logger.info("Config DeepSeek cargada desde config.ini")
        except Exception as e:
            logger.error(f"Error cargando config DeepSeek: {e}")
            messagebox.showerror("Error", f"Error cargando configuración:\n{e}")
    
    def _guardar_config_deepseek(self):
        """Guarda config DeepSeek a config.ini"""
        try:
            # Leer config existente (preservar otras secciones)
            config = configparser.ConfigParser()
            if CONFIG_FILE.exists():
                config.read(CONFIG_FILE, encoding="utf-8")
            
            # Crear/actualizar sección deepseek
            if not config.has_section("deepseek"):
                config.add_section("deepseek")
            
            # NO loguear api_key
            config.set("deepseek", "api_key", self.api_key_var.get())
            config.set("deepseek", "base_url", self.base_url_var.get())
            config.set("deepseek", "model", self.model_var.get())
            config.set("deepseek", "temperature", self.temperature_var.get())
            config.set("deepseek", "max_tokens", self.max_tokens_var.get())
            
            # Guardar
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                config.write(f)
            
            messagebox.showinfo("OK", f"Configuración DeepSeek guardada en:\n{CONFIG_FILE}")
            logger.info("Config DeepSeek guardada (api_key no logueada)")
        except Exception as e:
            logger.error(f"Error guardando config DeepSeek: {e}")
            messagebox.showerror("Error", f"Error guardando configuración:\n{e}")
    
    def _probar_deepseek(self):
        """Valida configuración DeepSeek (sin hacer llamadas reales)"""
        errores = []
        
        if not self.api_key_var.get().strip():
            errores.append("• API Key está vacía")
        
        if not self.base_url_var.get().strip():
            errores.append("• Base URL está vacía")
        
        if not self.model_var.get().strip():
            errores.append("• Model está vacío")
        
        try:
            temp = float(self.temperature_var.get())
            if temp < 0 or temp > 2:
                errores.append("• Temperature debe estar entre 0 y 2")
        except ValueError:
            errores.append("• Temperature debe ser un número decimal")
        
        try:
            max_tok = int(self.max_tokens_var.get())
            if max_tok <= 0:
                errores.append("• Max Tokens debe ser mayor a 0")
        except ValueError:
            errores.append("• Max Tokens debe ser un número entero")
        
        if errores:
            messagebox.showerror(
                "Validación Fallida",
                "Se encontraron los siguientes errores:\n\n" + "\n".join(errores)
            )
        else:
            messagebox.showinfo(
                "Validación OK",
                "✓ Configuración DeepSeek válida\n\n"
                "Nota: No se realizaron llamadas reales a la API."
            )
            logger.info("Validación DeepSeek OK (api_key presente, base_url y model válidos)")
    
    def _toggle_api_key_visibility(self):
        """Toggle visibilidad de API key"""
        if self.show_api_key_var.get():
            self.api_key_entry.config(show="")
        else:
            self.api_key_entry.config(show="*")
    
    # =================================================================
    # MÉTODOS: Configuración DB
    # =================================================================
    
    def _cargar_config_db_inicial(self):
        """Carga config DB al iniciar"""
        if not CONFIG_FILE.exists():
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            
            if config.has_section(self.db_section):
                self.db_host_var.set(config.get(self.db_section, "host", fallback=""))
                self.db_port_var.set(config.get(self.db_section, "port", fallback="3306"))
                self.db_user_var.set(config.get(self.db_section, "user", fallback=""))
                self.db_password_var.set(config.get(self.db_section, "password", fallback=""))
                
                # Database puede ser 'database' o 'db'
                db_name = config.get(self.db_section, "database", fallback="")
                if not db_name:
                    db_name = config.get(self.db_section, "db", fallback="")
                self.db_database_var.set(db_name)
                
                logger.info(f"Config DB cargada desde sección [{self.db_section}]")
        except Exception as e:
            logger.warning(f"No se pudo cargar config DB inicial: {e}")
    
    def _cargar_config_db(self):
        """Carga config DB desde config.ini"""
        if not CONFIG_FILE.exists():
            messagebox.showwarning(
                "Archivo no encontrado",
                f"El archivo {CONFIG_FILE} no existe.\n\n"
                "Será creado al guardar la configuración."
            )
            return
        
        try:
            config = configparser.ConfigParser()
            config.read(CONFIG_FILE, encoding="utf-8")
            
            if not config.has_section(self.db_section):
                messagebox.showwarning(
                    "Sección no encontrada",
                    f"No se encontró la sección [{self.db_section}] en config.ini.\n\n"
                    "Será creada al guardar."
                )
                return
            
            self.db_host_var.set(config.get(self.db_section, "host", fallback=""))
            self.db_port_var.set(config.get(self.db_section, "port", fallback="3306"))
            self.db_user_var.set(config.get(self.db_section, "user", fallback=""))
            self.db_password_var.set(config.get(self.db_section, "password", fallback=""))
            
            # Database puede ser 'database' o 'db'
            db_name = config.get(self.db_section, "database", fallback="")
            if not db_name:
                db_name = config.get(self.db_section, "db", fallback="")
            self.db_database_var.set(db_name)
            
            messagebox.showinfo("OK", f"Configuración DB cargada desde sección [{self.db_section}]")
            logger.info(f"Config DB cargada desde [{self.db_section}]")
        except Exception as e:
            logger.error(f"Error cargando config DB: {e}")
            messagebox.showerror("Error", f"Error cargando configuración DB:\n{e}")
    
    def _guardar_config_db(self):
        """Guarda config DB a config.ini"""
        try:
            # Leer config existente (preservar otras secciones)
            config = configparser.ConfigParser()
            if CONFIG_FILE.exists():
                config.read(CONFIG_FILE, encoding="utf-8")
            
            # Crear/actualizar sección DB
            if not config.has_section(self.db_section):
                config.add_section(self.db_section)
            
            # NO loguear password
            config.set(self.db_section, "host", self.db_host_var.get())
            config.set(self.db_section, "port", self.db_port_var.get())
            config.set(self.db_section, "user", self.db_user_var.get())
            config.set(self.db_section, "password", self.db_password_var.get())
            config.set(self.db_section, "database", self.db_database_var.get())
            
            # Guardar
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                config.write(f)
            
            messagebox.showinfo(
                "OK",
                f"Configuración DB guardada en:\n{CONFIG_FILE}\n\n"
                f"Sección: [{self.db_section}]\n\n"
                "Reinicie la aplicación para aplicar los cambios."
            )
            logger.info(f"Config DB guardada en sección [{self.db_section}] (password no logueada)")
        except Exception as e:
            logger.error(f"Error guardando config DB: {e}")
            messagebox.showerror("Error", f"Error guardando configuración DB:\n{e}")
    
    def _probar_conexion_db(self):
        """Prueba la conexión a la base de datos"""
        try:
            import mysql.connector
            
            # Intentar conectar con los valores ingresados
            conn = mysql.connector.connect(
                host=self.db_host_var.get(),
                port=int(self.db_port_var.get()),
                user=self.db_user_var.get(),
                password=self.db_password_var.get(),
                database=self.db_database_var.get()
            )
            
            # Ejecutar SELECT 1
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            
            if result == (1,):
                messagebox.showinfo(
                    "Conexión Exitosa",
                    "✓ Conexión a la base de datos exitosa\n\n"
                    f"Host: {self.db_host_var.get()}\n"
                    f"Database: {self.db_database_var.get()}"
                )
                logger.info("Prueba de conexión DB exitosa")
            else:
                messagebox.showwarning(
                    "Resultado Inesperado",
                    f"SELECT 1 retornó: {result}"
                )
        except Exception as e:
            logger.error(f"Error probando conexión DB: {e}")
            messagebox.showerror(
                "Error de Conexión",
                f"No se pudo conectar a la base de datos:\n\n{e}"
            )
    
    def _toggle_db_password_visibility(self):
        """Toggle visibilidad de password DB"""
        if self.show_db_password_var.get():
            self.db_password_entry.config(show="")
        else:
            self.db_password_entry.config(show="*")
