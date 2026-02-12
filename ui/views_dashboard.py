"""
Vista Dashboard: estadísticas globales y por ejecución
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import logging
from typing import List, Optional

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from ui.models import StatsEjecucion
import ui.services as services
import ui.ingest as ingest
import ui.analyze as analyze

logger = logging.getLogger(__name__)


class DashboardView(ttk.Frame):
    def __init__(self, parent, db_conn, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db_conn = db_conn
        self.task_queue = queue.Queue()
        self.app = app  # Referencia a SpeechAnalyticsApp para broadcast
        
        # Variables
        self.ejecuciones = []
        self.mostrar_total_var = tk.BooleanVar(value=True)
        self.conf_threshold_var = tk.StringVar(value="0.08")
        self.importing = False  # Estado de importación
        self.analyzing = False  # Estado de análisis
        
        # Flags para refresh global
        self._pending_preserve_id = None
        self._pending_select_id = None
        
        self._init_styles()
        self._build_ui()
        self._schedule_queue_check()
        
        # Cargar inicial
        self.after(100, self.cargar_ejecuciones)
    
    def _init_styles(self):
        """Inicializa theme y estilos personalizados"""
        style = ttk.Style()
        
        # Intentar usar theme clam
        try:
            style.theme_use('clam')
        except:
            pass  # Usar theme por defecto si clam no está disponible
        
        # Configurar estilos personalizados
        style.configure('Toolbar.TFrame', background='#f0f0f0', relief='flat')
        
        style.configure('Card.TLabelframe', padding=10, relief='groove', borderwidth=1)
        style.configure('Card.TLabelframe.Label', font=('Arial', 10, 'bold'), foreground='#333')
        
        style.configure('CardTitle.TLabel', font=('Arial', 9, 'bold'), foreground='#555', padding=(5, 2))
        style.configure('CardValue.TLabel', font=('Arial', 11), foreground='#000', padding=(5, 2))
        
        style.configure('Treeview', rowheight=25, font=('Arial', 9))
        style.configure('Treeview.Heading', font=('Arial', 9, 'bold'), background='#ddd', foreground='#333')
        
        style.configure('Accent.TButton', font=('Arial', 9, 'bold'), padding=(10, 5))
    
    def _build_ui(self):
        # Configurar grid weights del view principal
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Top frame tipo toolbar: controles (FIJO arriba, no hace scroll)
        top_frame = ttk.Frame(self, style='Toolbar.TFrame', padding=10)
        top_frame.grid(row=0, column=0, sticky='ew', padx=0, pady=0)
        top_frame.columnconfigure(1, weight=1)
        
        # Label ejecuciones
        ttk.Label(top_frame, text="Ejecuciones:", font=('Arial', 9, 'bold')).grid(
            row=0, column=0, sticky='w', padx=(0, 8)
        )
        
        # Listbox multi-select con scrollbar
        list_frame = ttk.Frame(top_frame)
        list_frame.grid(row=0, column=1, sticky='ew', padx=(0, 10))
        list_frame.columnconfigure(0, weight=1)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.ejecuciones_listbox = tk.Listbox(
            list_frame, 
            selectmode=tk.EXTENDED,
            height=4,
            yscrollcommand=scrollbar.set,
            font=('Arial', 9),
            relief='solid',
            borderwidth=1
        )
        scrollbar.config(command=self.ejecuciones_listbox.yview)
        self.ejecuciones_listbox.grid(row=0, column=0, sticky='ew')
        scrollbar.grid(row=0, column=1, sticky='ns')
        
        # Controles derecha (checkbox, umbral, botón)
        controls_frame = ttk.Frame(top_frame)
        controls_frame.grid(row=0, column=2, sticky='e', padx=(10, 0))
        
        ttk.Checkbutton(
            controls_frame, 
            text="Mostrar TOTAL",
            variable=self.mostrar_total_var
        ).grid(row=0, column=0, sticky='w', padx=5)
        
        ttk.Label(controls_frame, text="Umbral:").grid(row=0, column=1, sticky='e', padx=(10, 2))
        ttk.Entry(
            controls_frame, 
            textvariable=self.conf_threshold_var,
            width=8,
            font=('Arial', 9)
        ).grid(row=0, column=2, sticky='w', padx=(0, 10))
        
        ttk.Button(
            controls_frame, 
            text="Refrescar",
            command=self.refrescar_stats,
            style='Accent.TButton'
        ).grid(row=0, column=3, sticky='e', padx=5)
        
        # Botones de carga
        ttk.Button(
            controls_frame,
            text="➕ Cargar carpeta...",
            command=self.cargar_carpeta
        ).grid(row=0, column=4, sticky='e', padx=5)
        
        ttk.Button(
            controls_frame,
            text="➕ Cargar archivos...",
            command=self.cargar_archivos
        ).grid(row=0, column=5, sticky='e', padx=5)
        
        # Botón Analizar
        self.btn_analizar = ttk.Button(
            controls_frame,
            text="▶ Analizar",
            command=self.ejecutar_analisis,
            style='Accent.TButton'
        )
        self.btn_analizar.grid(row=0, column=6, sticky='e', padx=5)
        
        # Container con scroll vertical para el contenido del dashboard
        scroll_container = ttk.Frame(self)
        scroll_container.grid(row=1, column=0, sticky='nsew', padx=0, pady=5)
        scroll_container.grid_rowconfigure(0, weight=1)
        scroll_container.grid_columnconfigure(0, weight=1)
        
        # Canvas + Scrollbar vertical
        self.canvas = tk.Canvas(scroll_container, highlightthickness=0, bg='#f5f5f5')
        scrollbar_v = ttk.Scrollbar(scroll_container, orient=tk.VERTICAL, command=self.canvas.yview)
        
        # Frame interno scrollable (donde va TODO el contenido)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        # Crear ventana en el canvas
        self.canvas_window = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor='nw')
        
        # Configurar scrollregion cuando cambia el tamaño del frame interno
        def _on_frame_configure(event=None):
            self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        
        self.scrollable_frame.bind('<Configure>', _on_frame_configure)
        
        # Adaptar ancho del frame interno al ancho del canvas
        def _on_canvas_configure(event):
            canvas_width = event.width
            self.canvas.itemconfig(self.canvas_window, width=canvas_width)
        
        self.canvas.bind('<Configure>', _on_canvas_configure)
        
        # Bind scroll con rueda del mouse
        def _on_mousewheel(event):
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        
        self.canvas.bind_all('<MouseWheel>', _on_mousewheel)
        
        self.canvas.configure(yscrollcommand=scrollbar_v.set)
        
        # Grid del canvas y scrollbar
        self.canvas.grid(row=0, column=0, sticky='nsew')
        scrollbar_v.grid(row=0, column=1, sticky='ns')
        
        # Notebook para stats dentro del scrollable_frame
        self.stats_notebook = ttk.Notebook(self.scrollable_frame, padding=5)
        self.stats_notebook.grid(row=0, column=0, sticky='nsew', padx=10, pady=5)
        
        # Configurar weights del scrollable_frame
        self.scrollable_frame.grid_rowconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
    
    def cargar_ejecuciones(self):
        """Carga lista de ejecuciones en background"""
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                self.task_queue.put(("ejecuciones_cargadas", ejecuciones))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando ejecuciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def refrescar_stats(self):
        """Refresca estadísticas de ejecuciones seleccionadas"""
        selected_indices = self.ejecuciones_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Seleccione al menos una ejecución")
            return
        
        selected_ids = [self.ejecuciones[i].ejecucion_id for i in selected_indices]
        
        try:
            threshold = float(self.conf_threshold_var.get())
        except ValueError:
            messagebox.showerror("Error", "Umbral de confianza inválido")
            return
        
        def task():
            try:
                # Cargar stats de cada ejecución seleccionada
                stats_list = []
                for ej_id in selected_ids:
                    stats = services.stats_ejecucion(self.db_conn, ej_id, threshold)
                    stats_list.append(stats)
                
                # Cargar total si está habilitado
                total_stats = None
                if self.mostrar_total_var.get():
                    total_stats = services.stats_total(self.db_conn, selected_ids, threshold)
                
                self.task_queue.put(("stats_cargadas", stats_list, total_stats))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando estadísticas: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def cargar_carpeta(self):
        """Abre diálogo para seleccionar carpeta y cargar archivos"""
        if self.importing:
            messagebox.showwarning("Advertencia", "Ya hay una importación en progreso")
            return
        
        input_dir = filedialog.askdirectory(title="Seleccionar carpeta con archivos .txt")
        if not input_dir:
            return
        
        # Verificar que tenga archivos .txt
        import os
        txt_files = [f for f in os.listdir(input_dir) if f.lower().endswith('.txt')]
        if not txt_files:
            messagebox.showerror("Error", "La carpeta no contiene archivos .txt")
            return
        
        # Confirmar
        if not messagebox.askyesno(
            "Confirmar importación",
            f"Se importarán {len(txt_files)} archivos desde:\n{input_dir}\n\n¿Continuar?"
        ):
            return
        
        self._execute_import("folder", input_dir=input_dir)
    
    def cargar_archivos(self):
        """Abre diálogo para seleccionar archivos específicos"""
        if self.importing:
            messagebox.showwarning("Advertencia", "Ya hay una importación en progreso")
            return
        
        files = filedialog.askopenfilenames(
            title="Seleccionar archivos para importar",
            filetypes=[('Archivos de texto', '*.txt'), ('Todos los archivos', '*.*')]
        )
        if not files:
            return
        
        # Confirmar
        if not messagebox.askyesno(
            "Confirmar importación",
            f"Se importarán {len(files)} archivos\n\n¿Continuar?"
        ):
            return
        
        self._execute_import("files", files=list(files))
    
    def ejecutar_analisis(self):
        """Ejecuta análisis completo de las ejecuciones seleccionadas"""
        if self.analyzing or self.importing:
            messagebox.showwarning("Advertencia", "Ya hay una operación en progreso")
            return
        
        selected_indices = self.ejecuciones_listbox.curselection()
        if not selected_indices:
            messagebox.showwarning("Advertencia", "Seleccione al menos una ejecución para analizar")
            return
        
        selected_ids = [self.ejecuciones[i].ejecucion_id for i in selected_indices]
        
        try:
            threshold = float(self.conf_threshold_var.get())
        except ValueError:
            messagebox.showerror("Error", "Umbral de confianza inválido")
            return
        
        # Confirmar
        if not messagebox.askyesno(
            "Confirmar análisis",
            f"Se analizarán {len(selected_ids)} ejecución(es):\n"
            f"- Parse de turnos\n"
            f"- Detección de fases por reglas\n"
            f"- DeepSeek para turnos con confianza < {threshold}\n\n"
            f"¿Continuar?"
        ):
            return
        
        self._execute_analysis(selected_ids, threshold)
    
    def _execute_analysis(self, ejecucion_ids: list, threshold: float):
        """Ejecuta análisis en background"""
        self.analyzing = True
        self.btn_analizar.config(state='disabled')
        
        def task():
            try:
                for ejecucion_id in ejecucion_ids:
                    def progress_cb(msg):
                        self.task_queue.put(("analysis_progress", ejecucion_id, msg))
                    
                    # Ejecutar pipeline completo
                    analyze.run_analysis_for_ejecucion(
                        config_path="config.ini",
                        ejecucion_id=ejecucion_id,
                        conf_threshold=threshold,
                        run_deepseek=True,
                        progress_callback=progress_cb
                    )
                    
                    self.task_queue.put(("analysis_done", ejecucion_id))
                
                self.task_queue.put(("analysis_complete", len(ejecucion_ids)))
            
            except Exception as e:
                logger.error(f"Error en análisis: {e}", exc_info=True)
                self.task_queue.put(("analysis_error", str(e)))
            
            finally:
                self.analyzing = False
        
        threading.Thread(target=task, daemon=True).start()
    
    def _execute_import(self, import_type: str, input_dir: str = None, files: list = None):
        """Ejecuta importación en background"""
        self.importing = True
        
        def task():
            try:
                notas = f"UI import - {import_type}"
                
                if import_type == "folder":
                    ejecucion_id = ingest.run_import_from_folder("config.ini", input_dir, notas)
                else:  # files
                    ejecucion_id = ingest.run_import_from_files("config.ini", files, notas)
                
                self.task_queue.put(("import_success", ejecucion_id))
            
            except Exception as e:
                logger.error(f"Error en importación: {e}", exc_info=True)
                self.task_queue.put(("import_error", str(e)))
            
            finally:
                self.importing = False
        
        threading.Thread(target=task, daemon=True).start()
    
    def _schedule_queue_check(self):
        """Revisa cola de tareas de background"""
        try:
            while True:
                msg = self.task_queue.get_nowait()
                self._process_queue_message(msg)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._schedule_queue_check)
    
    def _process_queue_message(self, msg):
        """Procesa mensajes de la cola"""
        if msg[0] == "ejecuciones_cargadas":
            self.ejecuciones = msg[1]
            self._update_ejecuciones_listbox()
        elif msg[0] == "stats_cargadas":
            stats_list = msg[1]
            total_stats = msg[2]
            self._update_stats_display(stats_list, total_stats)
        elif msg[0] == "import_success":
            ejecucion_id = msg[1]
            messagebox.showinfo(
                "Éxito",
                f"Importación completada exitosamente\nEjecución ID: {ejecucion_id}"
            )
            # Disparar broadcast global para que todas las vistas se actualicen
            if self.app:
                self.app.broadcast_refresh(
                    reason="import_done",
                    select_id=ejecucion_id
                )
            else:
                # Fallback si no hay app
                self.cargar_ejecuciones()
                self.after(500, lambda: self._select_ejecucion_by_id(ejecucion_id))
        elif msg[0] == "import_error":
            messagebox.showerror("Error", f"Error en importación:\n{msg[1]}")
        elif msg[0] == "analysis_progress":
            ejecucion_id = msg[1]
            progress_msg = msg[2]
            logger.info(f"[Ej.{ejecucion_id}] {progress_msg}")
        elif msg[0] == "analysis_done":
            ejecucion_id = msg[1]
            logger.info(f"Análisis completado para ejecución {ejecucion_id}")
        elif msg[0] == "analysis_complete":
            count = msg[1]
            messagebox.showinfo(
                "Éxito",
                f"Análisis completado para {count} ejecución(es)\n\n"
                f"Se han procesado:\n"
                f"- Turnos parseados\n"
                f"- Fases detectadas por reglas\n"
                f"- DeepSeek ejecutado para turnos pendientes"
            )
            self.btn_analizar.config(state='normal')
            
            # Disparar broadcast para que todas las vistas se actualicen
            if self.app:
                # Refrescar todas las vistas (preserve current selection)
                self.app.broadcast_refresh(
                    reason="deepseek_done",
                    preserve_id=None  # Preservar selección actual de cada vista
                )
            else:
                # Fallback si no hay app
                self.refrescar_stats()
        elif msg[0] == "analysis_error":
            messagebox.showerror("Error", f"Error en análisis:\n{msg[1]}")
            self.btn_analizar.config(state='normal')
        elif msg[0] == "error":
            messagebox.showerror("Error", msg[1])
    
    def _update_ejecuciones_listbox(self):
        """Actualiza listbox con ejecuciones y aplica preserve/select"""
        self.ejecuciones_listbox.delete(0, tk.END)
        for ej in self.ejecuciones:
            self.ejecuciones_listbox.insert(
                tk.END, 
                f"Ejecución {ej.ejecucion_id} ({ej.num_conversaciones} convs)"
            )
        
        if not self.ejecuciones:
            return
        
        # Determinar índice a seleccionar
        selected_idx = 0
        
        # Prioridad 1: select_id (selección explícita)
        if self._pending_select_id:
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_select_id:
                    selected_idx = i
                    logger.info(f"[DashboardView] Seleccionando select_id={self._pending_select_id} (idx={i})")
                    break
        # Prioridad 2: preserve_id (preservar selección)
        elif self._pending_preserve_id:
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_preserve_id:
                    selected_idx = i
                    logger.info(f"[DashboardView] Preservando preserve_id={self._pending_preserve_id} (idx={i})")
                    break
        # Prioridad 3: mantener selección actual si existe
        else:
            current_selection = self.ejecuciones_listbox.curselection()
            if current_selection:
                current_idx = current_selection[0]
                if current_idx < len(self.ejecuciones):
                    selected_idx = current_idx
        
        # Aplicar selección
        self.ejecuciones_listbox.selection_clear(0, tk.END)
        self.ejecuciones_listbox.selection_set(selected_idx)
        self.ejecuciones_listbox.see(selected_idx)
        logger.info(f"[DashboardView] Ejecución seleccionada: idx={selected_idx}")
        
        # Limpiar flags
        self._pending_preserve_id = None
        self._pending_select_id = None
    
    def _select_ejecucion_by_id(self, ejecucion_id: int):
        """Selecciona una ejecución por su ID en el listbox"""
        for i, ej in enumerate(self.ejecuciones):
            if ej.ejecucion_id == ejecucion_id:
                self.ejecuciones_listbox.selection_clear(0, tk.END)
                self.ejecuciones_listbox.selection_set(i)
                self.ejecuciones_listbox.see(i)
                break
    
    def on_global_refresh(self, *, reason: str, preserve_id: int = None, select_id: int = None):
        """Handler de refresh global desde event bus
        
        Args:
            reason: Razón del refresh ("import_done", "sequences_built", "deepseek_done", etc.)
            preserve_id: ID de ejecución a preservar si existe
            select_id: ID de ejecución a seleccionar explícitamente (prioridad sobre preserve)
        """
        logger.info(f"[DashboardView] on_global_refresh: reason={reason}, preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags para aplicar cuando llegue la respuesta async
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        # Recargar lista de ejecuciones
        self.reload_runs(preserve_id=preserve_id, select_id=select_id)
        
        # Si el reason implica cambio de datos, refrescar stats
        data_change_reasons = ["sequences_built", "deepseek_done", "import_done", "learning_updated"]
        if reason in data_change_reasons:
            # Dar tiempo a que se actualice el listbox primero
            self.after(200, self.refresh_data)
    
    def reload_runs(self, preserve_id: int = None, select_id: int = None):
        """Recarga lista de ejecuciones desde BD
        
        Args:
            preserve_id: ID a preservar si select_id no está especificado
            select_id: ID a seleccionar explícitamente (prioridad)
        """
        logger.info(f"[DashboardView] reload_runs - preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                # Enviar mensaje simple, los flags ya están guardados
                self.task_queue.put(("ejecuciones_cargadas", ejecuciones))
            except Exception as e:
                logger.error(f"Error recargando ejecuciones: {e}", exc_info=True)
                self.task_queue.put(("error", f"Error recargando ejecuciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def refresh_data(self):
        """Refresca datos (stats/gráficos) de la selección actual"""
        logger.info("[DashboardView] refresh_data")
        self.refrescar_stats()
    
    def _update_stats_display(self, stats_list: List[StatsEjecucion], 
                             total_stats: Optional[StatsEjecucion]):
        """Actualiza display de estadísticas"""
        # Limpiar tabs existentes
        for tab in self.stats_notebook.tabs():
            self.stats_notebook.forget(tab)
        
        # Crear tab para cada ejecución
        for stats in stats_list:
            tab = self._create_stats_tab(stats)
            self.stats_notebook.add(tab, text=f"Ej. {stats.ejecucion_id}")
        
        # Crear tab total si existe
        if total_stats:
            tab = self._create_stats_tab(total_stats)
            self.stats_notebook.add(tab, text="TOTAL")
    
    def _create_stats_tab(self, stats: StatsEjecucion) -> ttk.Frame:
        """Crea un tab con estadísticas"""
        tab = ttk.Frame(self.stats_notebook, padding=8)
        
        # Configurar grid weights para que crezca
        tab.grid_rowconfigure(1, weight=1)  # Tablas
        tab.grid_rowconfigure(2, weight=1)  # Gráficos
        tab.grid_columnconfigure(0, weight=1)
        
        # Frame superior: KPIs principales estilo cards
        kpi_frame = ttk.LabelFrame(tab, text="Resumen General", style='Card.TLabelframe', padding=12)
        kpi_frame.grid(row=0, column=0, sticky='ew', padx=5, pady=5)
        
        # Grid de KPIs con estilo card
        kpis = [
            ("Conversaciones:", stats.total_convs),
            ("Turnos:", stats.total_turnos),
            ("Turnos con fase:", f"{stats.turnos_con_fase} ({self._pct(stats.turnos_con_fase, stats.total_turnos)})"),
            ("Turnos sin fase:", f"{stats.turnos_sin_fase} ({self._pct(stats.turnos_sin_fase, stats.total_turnos)})"),
            ("Pendientes (umbral):", f"{stats.pendientes_por_conf} ({self._pct(stats.pendientes_por_conf, stats.total_turnos)})"),
        ]
        
        if stats.total_promesas > 0:
            kpis.extend([
                ("Promesas:", stats.total_promesas),
                ("Promesas con monto:", f"{stats.promesas_con_monto} ({self._pct(stats.promesas_con_monto, stats.total_promesas)})"),
                ("Promesas sin monto:", f"{stats.promesas_sin_monto} ({self._pct(stats.promesas_sin_monto, stats.total_promesas)})"),
            ])
        
        # Configurar columnas para expandir
        for col in range(4):
            kpi_frame.columnconfigure(col, weight=1 if col % 2 == 1 else 0)
        
        for i, (label, value) in enumerate(kpis):
            row = i // 2
            col = (i % 2) * 2
            
            ttk.Label(kpi_frame, text=label, style='CardTitle.TLabel').grid(
                row=row, column=col, sticky=tk.W, padx=(8, 4), pady=4
            )
            ttk.Label(kpi_frame, text=str(value), style='CardValue.TLabel').grid(
                row=row, column=col+1, sticky=tk.W, padx=(4, 8), pady=4
            )
        
        # Frame distribuciones con grid
        dist_frame = ttk.Frame(tab)
        dist_frame.grid(row=1, column=0, sticky='nsew', padx=5, pady=5)
        dist_frame.rowconfigure(0, weight=1)
        dist_frame.columnconfigure(0, weight=1)
        dist_frame.columnconfigure(1, weight=1)
        
        # Distribución por fase
        fase_frame = ttk.LabelFrame(dist_frame, text="Distribución por Fase", style='Card.TLabelframe', padding=8)
        fase_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        fase_frame.rowconfigure(0, weight=1)
        fase_frame.columnconfigure(0, weight=1)
        
        # Treeview con scrollbars
        fase_scroll_y = ttk.Scrollbar(fase_frame, orient=tk.VERTICAL)
        fase_scroll_x = ttk.Scrollbar(fase_frame, orient=tk.HORIZONTAL)
        
        fase_tree = ttk.Treeview(
            fase_frame, 
            columns=("fase", "count", "pct"),
            show="headings",
            yscrollcommand=fase_scroll_y.set,
            xscrollcommand=fase_scroll_x.set
        )
        fase_scroll_y.config(command=fase_tree.yview)
        fase_scroll_x.config(command=fase_tree.xview)
        
        fase_tree.heading("fase", text="Fase")
        fase_tree.heading("count", text="Cantidad")
        fase_tree.heading("pct", text="%")
        
        fase_tree.column("fase", width=150, anchor=tk.W)
        fase_tree.column("count", width=80, anchor=tk.E)
        fase_tree.column("pct", width=60, anchor=tk.E)
        
        # Configurar zebra striping
        fase_tree.tag_configure('odd', background='#f9f9f9')
        fase_tree.tag_configure('even', background='#ffffff')
        
        for i, (fase, count) in enumerate(stats.dist_fase):
            pct = self._pct(count, stats.turnos_con_fase)
            tag = 'odd' if i % 2 else 'even'
            fase_tree.insert("", tk.END, values=(fase or "(vacío)", count, pct), tags=(tag,))
        
        fase_tree.grid(row=0, column=0, sticky='nsew')
        fase_scroll_y.grid(row=0, column=1, sticky='ns')
        fase_scroll_x.grid(row=1, column=0, sticky='ew')
        
        # Distribución por source
        source_frame = ttk.LabelFrame(dist_frame, text="Distribución por Source", style='Card.TLabelframe', padding=8)
        source_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        source_frame.rowconfigure(0, weight=1)
        source_frame.columnconfigure(0, weight=1)
        
        # Treeview con scrollbars
        source_scroll_y = ttk.Scrollbar(source_frame, orient=tk.VERTICAL)
        source_scroll_x = ttk.Scrollbar(source_frame, orient=tk.HORIZONTAL)
        
        source_tree = ttk.Treeview(
            source_frame,
            columns=("source", "count", "pct"),
            show="headings",
            yscrollcommand=source_scroll_y.set,
            xscrollcommand=source_scroll_x.set
        )
        source_scroll_y.config(command=source_tree.yview)
        source_scroll_x.config(command=source_tree.xview)
        
        source_tree.heading("source", text="Source")
        source_tree.heading("count", text="Cantidad")
        source_tree.heading("pct", text="%")
        
        source_tree.column("source", width=150, anchor=tk.W)
        source_tree.column("count", width=80, anchor=tk.E)
        source_tree.column("pct", width=60, anchor=tk.E)
        
        # Configurar zebra striping
        source_tree.tag_configure('odd', background='#f9f9f9')
        source_tree.tag_configure('even', background='#ffffff')
        
        for i, (source, count) in enumerate(stats.dist_fase_source):
            pct = self._pct(count, stats.total_turnos)
            tag = 'odd' if i % 2 else 'even'
            source_tree.insert("", tk.END, values=(source or "(null)", count, pct), tags=(tag,))
        
        source_tree.grid(row=0, column=0, sticky='nsew')
        source_scroll_y.grid(row=0, column=1, sticky='ns')
        source_scroll_x.grid(row=1, column=0, sticky='ew')
        
        # Sección de gráficos
        graphs_frame = ttk.Frame(tab)
        graphs_frame.grid(row=2, column=0, sticky='nsew', padx=5, pady=5)
        graphs_frame.rowconfigure(0, weight=1)
        graphs_frame.columnconfigure(0, weight=1)
        graphs_frame.columnconfigure(1, weight=1)
        
        # Gráfico de fases
        fase_graph_frame = ttk.LabelFrame(graphs_frame, text="Distribución por Fase (Top 10)", style='Card.TLabelframe', padding=8)
        fase_graph_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        self._create_bar_chart(fase_graph_frame, stats.dist_fase, stats.turnos_con_fase, "Fase")
        
        # Gráfico de sources
        source_graph_frame = ttk.LabelFrame(graphs_frame, text="Distribución por Source (Top 10)", style='Card.TLabelframe', padding=8)
        source_graph_frame.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        self._create_bar_chart(source_graph_frame, stats.dist_fase_source, stats.total_turnos, "Source")
        
        return tab
    
    def _create_bar_chart(self, parent_frame, data: List[tuple], total: int, label: str):
        """Crea un gráfico de barras con matplotlib"""
        if not data:
            ttk.Label(parent_frame, text="Sin datos", font=('Arial', 10)).pack(
                expand=True, fill=tk.BOTH, padx=20, pady=20
            )
            return
        
        # Tomar top 10, agrupar resto como OTROS
        top_10 = data[:10]
        labels = []
        values = []
        
        for item, count in top_10:
            labels.append(item or "(vacío)")
            values.append(count)
        
        # Si hay más de 10, agregar OTROS
        if len(data) > 10:
            otros_count = sum(count for _, count in data[10:])
            labels.append("OTROS")
            values.append(otros_count)
        
        # Crear figura
        fig = Figure(figsize=(5, 3), dpi=80, facecolor='#f9f9f9')
        ax = fig.add_subplot(111)
        
        # Barras horizontales
        colors = ['#4472C4', '#ED7D31', '#A5A5A5', '#FFC000', '#5B9BD5',
                  '#70AD47', '#264478', '#9E480E', '#636363', '#997300', '#CCCCCC']
        
        bars = ax.barh(labels, values, color=colors[:len(labels)])
        
        # Configurar ejes
        ax.set_xlabel('Cantidad', fontsize=9)
        ax.set_ylabel(label, fontsize=9)
        ax.tick_params(axis='both', labelsize=8)
        
        # Agregar valores en las barras
        for i, (bar, val) in enumerate(zip(bars, values)):
            pct = (val / total * 100) if total > 0 else 0
            ax.text(val, bar.get_y() + bar.get_height()/2, 
                   f' {val} ({pct:.1f}%)', 
                   va='center', fontsize=8)
        
        ax.grid(axis='x', alpha=0.3, linestyle='--')
        fig.tight_layout()
        
        # Embedear en tkinter
        canvas = FigureCanvasTkAgg(fig, parent_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
    
    def _pct(self, valor, total):
        """Calcula porcentaje formateado"""
        if total == 0:
            return "0.0%"
        return f"{(valor / total * 100):.1f}%"
