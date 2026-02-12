"""
Aplicación principal: ventana root + Notebook con 3 vistas
"""
import tkinter as tk
from tkinter import ttk, messagebox
import logging
import sys

from ui.views_dashboard import DashboardView
from ui.views_detalles import DetallesView
from ui.views_aprendizaje import AprendizajeView
from ui.views_deepseek import DeepSeekView
from ui.views_secuencias import SecuenciasView
import ui.services as services

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

logger = logging.getLogger(__name__)


class SpeechAnalyticsApp:
    """Aplicación principal de Speech Analytics UI"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Speech Analytics - Dashboard")
        self.root.geometry("1200x800")
        
        # Maximizar ventana por defecto
        try:
            self.root.state('zoomed')  # Windows
        except:
            try:
                self.root.attributes('-zoomed', True)  # Fallback
            except:
                pass  # Si falla, usar geometry normal
        
        # Configurar grid para que crezca
        self.root.grid_rowconfigure(0, weight=1)  # Main content
        self.root.grid_rowconfigure(1, weight=0)  # Status bar (altura fija)
        self.root.grid_columnconfigure(0, weight=1)
        
        self.db_conn = None
        self.db_status = "Desconectado"
        
        # Event Bus: lista de vistas registradas para broadcast_refresh
        self.registered_views = []
        
        self._setup_styles()
        self._build_ui()
        self._connect_db()
        
        # Manejar cierre
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
    
    def _setup_styles(self):
        """Configura estilos ttk"""
        style = ttk.Style()
        style.theme_use("clam")  # Tema más moderno
    
    def _build_ui(self):
        """Construye UI principal"""
        # Menu bar (opcional)
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # Menú archivo
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Archivo", menu=file_menu)
        file_menu.add_command(label="Reconectar DB", command=self._reconnect_db)
        file_menu.add_separator()
        file_menu.add_command(label="Salir", command=self._on_closing)
        
        # Menú ayuda
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Ayuda", menu=help_menu)
        help_menu.add_command(label="Acerca de", command=self._show_about)
        
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
        main_frame.grid_rowconfigure(0, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        
        # Notebook con 3 pestañas
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.grid(row=0, column=0, sticky='nsew')
        
        # Nota: las vistas se crearán después de conectar DB
        self.dashboard_view = None
        self.detalles_view = None
        self.aprendizaje_view = None
        self.deepseek_view = None
        self.secuencias_view = None
        
        # Status bar
        status_frame = ttk.Frame(self.root, relief=tk.SUNKEN, borderwidth=1)
        status_frame.grid(row=1, column=0, sticky='ew')
        
        self.status_label = ttk.Label(
            status_frame,
            text=f"Estado: {self.db_status}",
            anchor=tk.W
        )
        self.status_label.pack(side=tk.LEFT, padx=5, pady=2)
        
        self.version_label = ttk.Label(
            status_frame,
            text="v1.0.0",
            anchor=tk.E
        )
        self.version_label.pack(side=tk.RIGHT, padx=5, pady=2)
    
    def _connect_db(self):
        """Conecta a la base de datos"""
        try:
            logger.info("Conectando a base de datos...")
            self.db_conn = services.get_db_connection()
            
            # ✅ Verificar que la conexión es válida
            if self.db_conn is None:
                raise Exception("get_db_connection() retornó None")
            
            self.db_status = "Conectado"
            self._update_status()
            
            # ✅ Inyectar conexión ANTES de crear vistas
            self._inject_db_conn_into_views()
            
            # Crear vistas
            self._create_views()
            
            # ✅ Inyectar conexión DESPUÉS de crear vistas (garantía)
            self._inject_db_conn_into_views()
            
            logger.info("Conexión exitosa")
        except Exception as e:
            logger.error(f"Error conectando a DB: {e}")
            self.db_status = f"Error: {str(e)[:50]}"
            self._update_status()
            
            messagebox.showerror(
                "Error de Conexión",
                f"No se pudo conectar a la base de datos:\n\n{e}\n\n"
                "Verifique config.ini y asegúrese de que MySQL esté corriendo."
            )
    
    def _reconnect_db(self):
        """Reconecta a la base de datos"""
        if self.db_conn:
            try:
                self.db_conn.close()
            except:
                pass
        
        self._connect_db()
    
    def _inject_db_conn_into_views(self):
        """Inyecta la conexión DB en todas las vistas existentes"""
        if self.db_conn is None:
            logger.warning("No se puede inyectar db_conn: conexión es None")
            return
    
        views = [
            ('dashboard_view', self.dashboard_view),
            ('detalles_view', self.detalles_view),
            ('aprendizaje_view', self.aprendizaje_view),
            ('deepseek_view', self.deepseek_view),
            ('secuencias_view', self.secuencias_view)
        ]
        
        for view_name, view_instance in views:
            if view_instance is not None:
                view_instance.db_conn = self.db_conn
                logger.debug(f"DB conn inyectada en {view_name}")
    
    def _create_views(self):
        """Crea las vistas del notebook"""
        if not self.db_conn:
            logger.warning("No se pueden crear vistas sin conexión DB")
            return
        
        # ✅ Verificar que la conexión sigue activa con SELECT 1
        try:
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            logger.debug("Conexión DB verificada antes de crear vistas")
        except Exception as e:
            logger.error(f"Conexión DB no válida: {e}")
            messagebox.showerror("Error", f"Conexión DB no válida: {e}")
            return
        
        # Limpiar vistas existentes
        for tab in self.notebook.tabs():
            self.notebook.forget(tab)
        
        # Crear vistas con conexión válida...
        try:
            self.dashboard_view = DashboardView(self.notebook, self.db_conn, app=self)
            self.notebook.add(self.dashboard_view, text="📊 Dashboard")
            self.register_view(self.dashboard_view)
            
            self.detalles_view = DetallesView(self.notebook, self.db_conn, app=self)
            self.notebook.add(self.detalles_view, text="🔍 Detalles")
            self.register_view(self.detalles_view)
            
            self.aprendizaje_view = AprendizajeView(self.notebook, self.db_conn, app=self)
            self.notebook.add(self.aprendizaje_view, text="✏️ Aprendizaje")
            self.register_view(self.aprendizaje_view)
            
            self.deepseek_view = DeepSeekView(self.notebook, self.db_conn, app=self)
            self.notebook.add(self.deepseek_view, text="🤖 DeepSeek")
            self.register_view(self.deepseek_view)
            
            # Vista de Secuencias con callback para abrir detalles
            self.secuencias_view = SecuenciasView(
                self.notebook, 
                self.db_conn, 
                open_detalle_callback=self._open_detalle_conversacion,
                app=self
            )
            self.notebook.add(self.secuencias_view, text="📈 Secuencias")
            self.register_view(self.secuencias_view)
            
            logger.info("Vistas creadas exitosamente")
        except Exception as e:
            logger.error(f"Error creando vistas: {e}")
            messagebox.showerror("Error", f"Error creando vistas: {e}")
    
    def register_view(self, view):
        """Registra una vista para recibir eventos de refresh global
        
        Args:
            view: Vista que implementa on_global_refresh(reason, preserve_id, select_id)
        """
        if view not in self.registered_views:
            self.registered_views.append(view)
            logger.debug(f"Vista registrada para broadcast: {type(view).__name__}")
    
    def broadcast_refresh(self, reason: str, preserve_id: int = None, select_id: int = None):
        """Dispara refresh global en todas las vistas registradas (thread-safe)
        
        Args:
            reason: Razón del refresh ("import_done", "sequences_built", "deepseek_done", etc.)
            preserve_id: ID de ejecución a preservar en selección (si existe)
            select_id: ID de ejecución a seleccionar explícitamente (tiene prioridad sobre preserve)
        """
        logger.info(f"broadcast_refresh: reason={reason}, preserve_id={preserve_id}, select_id={select_id}")
        
        def notify_views():
            for view in self.registered_views:
                try:
                    if hasattr(view, 'on_global_refresh'):
                        view.on_global_refresh(
                            reason=reason,
                            preserve_id=preserve_id,
                            select_id=select_id
                        )
                except Exception as e:
                    logger.error(f"Error en broadcast a {type(view).__name__}: {e}", exc_info=True)
        
        # Ejecutar en thread de Tk (thread-safe)
        self.root.after(0, notify_views)
    
    def _update_status(self):
        """Actualiza barra de estado"""
        self.status_label.config(text=f"Estado: {self.db_status}")
    
    def _open_detalle_conversacion(self, conversacion_pk: int):
        """Abre vista de detalles para una conversación específica
        
        Args:
            conversacion_pk: PK de la conversación a mostrar
        """
        if not self.detalles_view:
            messagebox.showwarning("Advertencia", "Vista de detalles no disponible")
            return
        
        # Cambiar a pestaña de Detalles
        for i, tab in enumerate(self.notebook.tabs()):
            tab_text = self.notebook.tab(tab, "text")
            if "Detalles" in tab_text:
                self.notebook.select(i)
                break
        
        # Cargar conversación en la vista de detalles
        # Buscar ejecución de esta conversación
        try:
            cursor = self.db_conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT ejecucion_id 
                FROM sa_conversaciones 
                WHERE conversacion_pk = %s
            """, (conversacion_pk,))
            row = cursor.fetchone()
            cursor.close()
            
            if row:
                ejecucion_id = row['ejecucion_id']
                
                # Seleccionar ejecución en combo
                for i, ej in enumerate(self.detalles_view.ejecuciones):
                    if ej.ejecucion_id == ejecucion_id:
                        self.detalles_view.ejecucion_combo.current(i)
                        self.detalles_view.ejecucion_actual = ejecucion_id
                        break
                
                # Cargar conversaciones de esa ejecución
                self.detalles_view.buscar_conversaciones()
                
                # Esperar a que se carguen y seleccionar la conversación
                def select_after_load():
                    # Buscar y seleccionar conversación en el tree
                    for item in self.detalles_view.conversaciones_tree.get_children():
                        values = self.detalles_view.conversaciones_tree.item(item, 'values')
                        if values and int(values[0]) == conversacion_pk:
                            self.detalles_view.conversaciones_tree.selection_set(item)
                            self.detalles_view.conversaciones_tree.see(item)
                            # Trigger evento de selección
                            self.detalles_view._on_conversacion_selected(None)
                            break
                
                # Ejecutar después de 500ms para dar tiempo a la carga
                self.root.after(500, select_after_load)
                
        except Exception as e:
            logger.error(f"Error abriendo detalle: {e}")
            messagebox.showerror("Error", f"No se pudo abrir detalle: {e}")
    
    def _show_about(self):
        """Muestra diálogo Acerca de"""
        messagebox.showinfo(
            "Acerca de Speech Analytics",
            "Speech Analytics Dashboard v1.0.0\n\n"
            "Herramienta de análisis y corrección de clasificación de fases.\n\n"
            "Desarrollado con Python + Tkinter"
        )
    
    def _on_closing(self):
        """Handler de cierre de ventana"""
        if messagebox.askokcancel("Salir", "¿Desea cerrar la aplicación?"):
            if self.db_conn:
                try:
                    self.db_conn.close()
                    logger.info("Conexión DB cerrada")
                except Exception as e:
                    logger.error(f"Error cerrando DB: {e}")
            
            self.root.destroy()
    
    def run(self):
        """Inicia el loop principal de la aplicación"""
        logger.info("Iniciando Speech Analytics UI...")
        self.root.mainloop()
        logger.info("Aplicación cerrada")
