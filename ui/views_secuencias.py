"""
Vista Secuencias: análisis de secuencias de macrofases
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
from typing import List, Optional

from ui.models import SecuenciaInfo, SecuenciaKPIs
import ui.services as services

logger = logging.getLogger(__name__)


class SecuenciasView(ttk.Frame):
    def __init__(self, parent, db_conn, open_detalle_callback=None, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db_conn = db_conn
        self.task_queue = queue.Queue()
        self.open_detalle_callback = open_detalle_callback
        self.app = app  # Referencia a SpeechAnalyticsApp para broadcast
        
        # Variables
        self.ejecuciones = []
        self.secuencias = []
        self.ejecucion_actual = None
        
        # Frames de contenido
        self.frame_empty = None
        self.frame_content = None
        
        # Tooltip
        self.tooltip = None
        self.tooltip_text = ""
        self.tooltip_timer = None  # Timer para delay
        
        # FIX: Diccionario para guardar secuencias completas (evita crash de column #0)
        self._full_seq_by_item = {}
        
        self._init_styles()
        self._build_ui()
        self._schedule_queue_check()
        
        # Cargar inicial
        self.after(100, self.cargar_ejecuciones)
    
    def _init_styles(self):
        """Inicializa estilos personalizados"""
        style = ttk.Style()
        
        try:
            style.theme_use('clam')
        except:
            pass
        
        # Estilos para tabla
        style.configure('Secuencias.Treeview', rowheight=28, font=('Segoe UI', 9))
        style.configure('Secuencias.Treeview.Heading', 
                       font=('Segoe UI', 9, 'bold'), 
                       background='#34495e', 
                       foreground='white')
        style.map('Secuencias.Treeview.Heading', background=[('active', '#2c3e50')])
        
        # Botón Ver
        style.configure('Ver.TButton', font=('Segoe UI', 9), padding=(8, 4))
    
    def _build_ui(self):
        """Construye interfaz de usuario"""
        # Top toolbar
        top_frame = ttk.Frame(self, relief='flat', padding=(15, 10))
        top_frame.pack(fill=tk.X)
        
        # Izquierda: selector
        left_controls = ttk.Frame(top_frame)
        left_controls.pack(side=tk.LEFT)
        
        ttk.Label(left_controls, text="Ejecución:", 
                 font=('Segoe UI', 10, 'bold')).pack(side=tk.LEFT, padx=(0, 10))
        
        self.ejecucion_combo = ttk.Combobox(left_controls, width=35, 
                                           state="readonly", font=('Segoe UI', 9))
        self.ejecucion_combo.pack(side=tk.LEFT)
        # FIX: Bind correcto para actualizar ejecucion_actual
        self.ejecucion_combo.bind("<<ComboboxSelected>>", self._on_ejecucion_selected)
        
        # Derecha: botón refrescar
        right_controls = ttk.Frame(top_frame)
        right_controls.pack(side=tk.RIGHT)
        
        ttk.Button(right_controls, text="🔄 Refrescar", 
                  command=self.refresh_total, style='Ver.TButton').pack(side=tk.RIGHT, padx=5)
        
        # Body container (fondo gris claro)
        self.body_frame = ttk.Frame(self)
        self.body_frame.pack(fill=tk.BOTH, expand=True)
        self.body_frame.configure(style='TFrame')
    
    def cargar_ejecuciones(self):
        """Carga lista de ejecuciones en background"""
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                self.task_queue.put(("ejecuciones_cargadas", ejecuciones))
            except Exception as e:
                logger.error(f"Error cargando ejecuciones: {e}", exc_info=True)
                self.task_queue.put(("error", f"Error cargando ejecuciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def refresh_total(self):
        """Recarga lista completa de ejecuciones desde BD y preserva selección actual"""
        # Guardar selección actual
        current_id = self.ejecucion_actual
        logger.info(f"refresh_total - preservando ejecucion_id={current_id}")
        
        # Recargar ejecuciones (enviará mensaje "ejecuciones_cargadas" con preserve_id)
        self.cargar_ejecuciones()
    
    def on_global_refresh(self, *, reason: str, preserve_id: int = None, select_id: int = None):
        """Handler de refresh global desde event bus
        
        Args:
            reason: Razón del refresh ("import_done", "sequences_built", "deepseek_done", etc.)
            preserve_id: ID de ejecución a preservar si existe
            select_id: ID de ejecución a seleccionar explícitamente (prioridad sobre preserve)
        """
        logger.info(f"SecuenciasView.on_global_refresh: reason={reason}, preserve_id={preserve_id}, select_id={select_id}")
        
        # Recargar lista de ejecuciones
        self.reload_runs(preserve_id=preserve_id, select_id=select_id)
        
        # Si el reason implica cambio de datos y estamos viendo la ejecución afectada, refrescar data
        data_change_reasons = ["sequences_built", "deepseek_done", "import_done", "learning_updated"]
        affected_id = select_id if select_id else preserve_id
        
        if reason in data_change_reasons and affected_id and self.ejecucion_actual == affected_id:
            # Dar tiempo a que se actualice el combo primero
            self.after(200, self.refresh_data)
    
    def reload_runs(self, preserve_id: int = None, select_id: int = None):
        """Recarga lista de ejecuciones desde BD
        
        Args:
            preserve_id: ID a preservar si select_id no está especificado
            select_id: ID a seleccionar explícitamente (prioridad)
        """
        # Determinar qué ID usar
        target_id = select_id if select_id else (preserve_id if preserve_id else self.ejecucion_actual)
        
        logger.info(f"SecuenciasView.reload_runs - target_id={target_id}")
        
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                # Pasar target_id para que se preserve/seleccione
                self.task_queue.put(("ejecuciones_cargadas_with_target", ejecuciones, target_id))
            except Exception as e:
                logger.error(f"Error recargando ejecuciones: {e}", exc_info=True)
                self.task_queue.put(("error", f"Error recargando ejecuciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def refresh_data(self):
        """Refresca datos (secuencias/KPIs) de la ejecución actual"""
        if not self.ejecucion_actual:
            logger.warning("refresh_data llamado sin ejecucion_actual")
            return
        
        logger.info(f"SecuenciasView.refresh_data - ejecucion_id={self.ejecucion_actual}")
        self.refresh()
    
    def refresh(self):
        """Refresca secuencias de la ejecución seleccionada"""
        # Asegurar que ejecucion_actual esté sincronizado con el combo
        idx = self.ejecucion_combo.current()
        if idx >= 0 and idx < len(self.ejecuciones):
            self.ejecucion_actual = self.ejecuciones[idx].ejecucion_id
        
        if not self.ejecucion_actual:
            logger.warning("refresh() llamado sin ejecucion_actual")
            return
        
        logger.info(f"refresh ejecucion_id={self.ejecucion_actual}")
        
        def task():
            try:
                # Forzar rollback para ver commits nuevos de otras conexiones
                try:
                    self.db_conn.rollback()
                    logger.debug("Rollback ejecutado antes de consultar secuencias")
                except Exception:
                    pass
                
                # Cargar secuencias
                secuencias = services.listar_secuencias_ejecucion(
                    self.db_conn, self.ejecucion_actual)
                
                # Cargar KPIs
                kpis = services.get_secuencia_kpis(
                    self.db_conn, self.ejecucion_actual)
                
                logger.info(f"rows_secuencias={len(secuencias) if secuencias else 0}")
                
                self.task_queue.put(("secuencias_cargadas", secuencias, kpis))
            except Exception as e:
                logger.error(f"Error cargando secuencias: {e}", exc_info=True)
                self.task_queue.put(("error", f"Error cargando secuencias: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def _on_ejecucion_selected(self, event=None):
        """Maneja selección de ejecución - FIX: actualiza ejecucion_actual antes de refresh"""
        idx = self.ejecucion_combo.current()
        if idx >= 0:
            self.ejecucion_actual = self.ejecuciones[idx].ejecucion_id
            logger.info(f"Ejecución seleccionada: {self.ejecucion_actual}")
            self.refresh()
    
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
            # Preservar selección actual antes de actualizar
            prev_id = self.ejecucion_actual
            self.ejecuciones = msg[1]
            self._update_ejecuciones_combo(preserve_id=prev_id)
        elif msg[0] == "ejecuciones_cargadas_with_target":
            # Reload con target_id específico (de reload_runs)
            self.ejecuciones = msg[1]
            target_id = msg[2]
            self._update_ejecuciones_combo(preserve_id=target_id)
        elif msg[0] == "secuencias_cargadas":
            secuencias = msg[1]
            kpis = msg[2]
            self._update_display(secuencias, kpis)
        elif msg[0] == "generacion_completada":
            self._on_generacion_completada(msg[1])
        elif msg[0] == "generacion_error":
            self._on_generacion_error(msg[1])
        elif msg[0] == "error":
            messagebox.showerror("Error", msg[1])
    
    def _update_ejecuciones_combo(self, preserve_id=None):
        """Actualiza combo con ejecuciones, opcionalmente preservando selección"""
        values = [f"Ejecución {ej.ejecucion_id} ({ej.num_conversaciones} convs)" 
                  for ej in self.ejecuciones]
        self.ejecucion_combo['values'] = values
        
        if not values:
            return
        
        # Intentar restaurar selección previa
        selected_idx = 0
        if preserve_id:
            # Buscar índice de la ejecución preservada
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == preserve_id:
                    selected_idx = i
                    logger.info(f"Restaurando selección a ejecucion_id={preserve_id} (idx={i})")
                    break
        
        # Seleccionar en combo
        self.ejecucion_combo.current(selected_idx)
        self.ejecucion_actual = self.ejecuciones[selected_idx].ejecucion_id
        
        # Refrescar datos de la ejecución seleccionada
        self.refresh()
    
    def _update_display(self, secuencias: List[SecuenciaInfo], 
                       kpis: Optional[SecuenciaKPIs]):
        """Actualiza display con secuencias y KPIs"""
        # Guardar datos en atributos de instancia
        self.secuencias = secuencias if secuencias else []
        
        # SOLO mostrar empty si NO hay secuencias
        if not secuencias:
            self.kpis = None
            self._show_empty_state()
            return
        
        # Si hay secuencias pero kpis es None, calcular KPI fallback
        if kpis is None:
            logger.info("KPIs None pero hay secuencias, calculando fallback")
            total = len(secuencias)
            count_inicio_valido = sum(1 for s in secuencias if s.inicio_valido)
            count_cumple = sum(1 for s in secuencias if s.cumple_secuencia)
            count_corte = sum(1 for s in secuencias if s.corte_antes_negociacion)
            sum_violaciones = sum(s.violaciones_transicion for s in secuencias)
            
            kpis = SecuenciaKPIs(
                total=total,
                pct_inicio_valido=(count_inicio_valido / total * 100) if total > 0 else 0,
                pct_cumple=(count_cumple / total * 100) if total > 0 else 0,
                pct_corte_antes_negociacion=(count_corte / total * 100) if total > 0 else 0,
                avg_violaciones=(sum_violaciones / total) if total > 0 else 0
            )
        
        # Guardar KPIs (originales o fallback)
        self.kpis = kpis
        
        # Mostrar contenido
        self._show_content(secuencias, kpis)
    
    def _show_empty_state(self):
        """Muestra mensaje de sin datos - MEJORADO: UI limpia con acción de generar"""
        # Ocultar frame de contenido si existe
        if self.frame_content:
            self.frame_content.pack_forget()
        
        # Crear o mostrar frame empty
        if not self.frame_empty:
            # Frame principal con fondo gris
            self.frame_empty = tk.Frame(self.body_frame, bg='#f5f5f5')
            
            # Card blanca centrada
            card = tk.Frame(self.frame_empty, bg='white', relief='solid', 
                          borderwidth=1, padx=50, pady=40)
            card.place(relx=0.5, rely=0.5, anchor='center', width=520)
            
            # Icono grande
            icon_label = tk.Label(card, text="⚠️", font=('Segoe UI', 60),
                                bg='white', fg='#f39c12')
            icon_label.pack(pady=(0, 25))
            
            # Título
            title_label = tk.Label(card, 
                                 text="Aún no hay secuencias para esta ejecución",
                                 font=('Segoe UI', 14, 'bold'),
                                 bg='white', fg='#2c3e50')
            title_label.pack(pady=(0, 15))
            
            # Mensaje breve
            msg_text = "Podés generarlas desde la aplicación."
            msg_label = tk.Label(card, text=msg_text, font=('Segoe UI', 11),
                               justify=tk.CENTER, bg='white', fg='#7f8c8d')
            msg_label.pack(pady=(0, 30))
            
            # Frame de botones
            btn_frame = tk.Frame(card, bg='white')
            btn_frame.pack(pady=(0, 10))
            
            # Botón Generar secuencias (principal)
            self.btn_generar = ttk.Button(btn_frame, text="✨ Generar secuencias",
                                         command=self._generar_secuencias_ui,
                                         style='Ver.TButton')
            self.btn_generar.pack(side=tk.LEFT, padx=5)
            
            # Botón Reintentar
            ttk.Button(btn_frame, text="🔄 Reintentar",
                      command=self.refresh).pack(side=tk.LEFT, padx=5)
            
            # Botón Ayuda
            ttk.Button(btn_frame, text="❓ Ayuda",
                      command=self._mostrar_ayuda).pack(side=tk.LEFT, padx=5)
            
            # Label de estado (oculto por defecto)
            self.status_label = tk.Label(card, text="", font=('Segoe UI', 9),
                                        bg='white', fg='#7f8c8d')
            self.status_label.pack(pady=(15, 0))
            
            # Progressbar (oculto por defecto)
            self.progress_frame = tk.Frame(card, bg='white')
            self.progressbar = ttk.Progressbar(self.progress_frame, mode='indeterminate',
                                              length=300)
        
        self.frame_empty.pack(fill=tk.BOTH, expand=True)
    
    def _mostrar_ayuda(self):
        """Muestra ayuda sobre las secuencias"""
        ayuda_text = (
            "Las secuencias de macrofases analizan el flujo de la conversación.\n\n"
            "El proceso de generación realiza dos pasos:\n\n"
            "1. Estabilización de fases: Reduce cambios zigzag entre fases\n"
            "   para obtener una secuencia más coherente.\n\n"
            "2. Análisis de secuencias: Calcula métricas de calidad como\n"
            "   cumplimiento de la secuencia esperada, violaciones de\n"
            "   transición, y cortes prematuros.\n\n"
            "El proceso puede demorar varios minutos dependiendo de\n"
            "la cantidad de conversaciones en la ejecución."
        )
        messagebox.showinfo("Ayuda - Secuencias", ayuda_text)
    
    def _generar_secuencias_ui(self):
        """Genera secuencias desde la UI (background thread con progress)"""
        if not self.ejecucion_actual:
            messagebox.showwarning("Advertencia", "Seleccione una ejecución primero")
            return
        
        # Confirmar acción
        respuesta = messagebox.askyesno(
            "Confirmar generación",
            f"¿Desea generar las secuencias para la Ejecución {self.ejecucion_actual}?\n\n"
            "Este proceso puede demorar varios minutos.",
            icon='question'
        )
        
        if not respuesta:
            return
        
        # Deshabilitar botones y mostrar progress
        self.btn_generar.config(state='disabled')
        self.status_label.config(text="Generando secuencias, por favor espere...")
        self.status_label.pack()
        self.progress_frame.pack(pady=(10, 0))
        self.progressbar.pack()
        self.progressbar.start(10)
        
        # Lanzar en background
        def task():
            try:
                # Obtener config_path desde la app (usamos el mismo que la conexión)
                config_path = "config.ini"
                
                # Llamar a la función de generación
                result = services.generar_secuencias(
                    self.db_conn, 
                    self.ejecucion_actual,
                    config_path=config_path
                )
                
                self.task_queue.put(("generacion_completada", result))
            
            except Exception as e:
                logger.error(f"Error generando secuencias: {e}", exc_info=True)
                self.task_queue.put(("generacion_error", str(e)))
        
        threading.Thread(target=task, daemon=True).start()
    
    def _on_generacion_completada(self, result):
        """Maneja finalización exitosa de la generación"""
        # Ocultar progress
        self.progressbar.stop()
        self.progressbar.pack_forget()
        self.progress_frame.pack_forget()
        self.status_label.pack_forget()
        
        # Re-habilitar botón
        self.btn_generar.config(state='normal')
        
        # Mostrar éxito
        stats_seq = result.get('secuencias_stats', {})
        total = stats_seq.get('total', 0)
        cumple = stats_seq.get('cumple_secuencia', 0)
        
        messagebox.showinfo(
            "✓ Generación completada",
            f"Secuencias generadas correctamente.\n\n"
            f"Conversaciones procesadas: {total}\n"
            f"Cumplen secuencia: {cumple}\n\n"
            "Los datos se mostrarán a continuación."
        )
        
        # Disparar broadcast para que todas las vistas se actualicen
        if self.app:
            self.app.broadcast_refresh(
                reason="sequences_built",
                preserve_id=self.ejecucion_actual
            )
        else:
            # Fallback si no hay app (refrescar solo esta vista)
            self.refresh()
    
    def _on_generacion_error(self, error_msg):
        """Maneja error en la generación"""
        # Ocultar progress
        self.progressbar.stop()
        self.progressbar.pack_forget()
        self.progress_frame.pack_forget()
        self.status_label.pack_forget()
        
        # Re-habilitar botón
        self.btn_generar.config(state='normal')
        
        # Mostrar error
        messagebox.showerror(
            "Error en generación",
            f"Ocurrió un error al generar las secuencias:\n\n{error_msg}\n\n"
            "Verifique los logs para más detalles."
        )
    
    def _show_content(self, secuencias: List[SecuenciaInfo], kpis: SecuenciaKPIs):
        """Muestra contenido con KPIs y tabla"""
        # Guardar datos SIEMPRE
        self.secuencias = secuencias
        self.kpis = kpis
        
        # Ocultar frame empty si existe
        if self.frame_empty:
            self.frame_empty.pack_forget()
        
        # Destruir COMPLETAMENTE frame_content anterior para forzar recreación
        if self.frame_content:
            self.frame_content.destroy()
            self.frame_content = None
        
        # Crear frame de contenido de cero
        self.frame_content = ttk.Frame(self.body_frame)
        
        # Limpiar diccionario de secuencias completas
        self._full_seq_by_item.clear()
        
        # KPIs Cards
        self._create_kpis_cards(kpis)
        
        # Tabla de secuencias
        self._create_secuencias_table()
        
        self.frame_content.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    def _create_kpis_cards(self, kpis: SecuenciaKPIs):
        """Crea cards con KPIs en estilo moderno - MEJORADO: bordes sutiles y colores condicionales"""
        kpi_container = ttk.Frame(self.frame_content)
        kpi_container.pack(fill=tk.X, pady=(0, 25), padx=5)
        
        # Configurar grid para 5 columnas con pesos iguales
        for i in range(5):
            kpi_container.columnconfigure(i, weight=1, uniform='kpi')
        
        # Colores condicionales para alertas
        corte_pct = kpis.pct_corte_antes_negociacion
        corte_color = "#e67e22" if corte_pct > 0 else "#95a5a6"
        
        violaciones_avg = kpis.avg_violaciones
        violaciones_color = "#e74c3c" if violaciones_avg > 0 else "#95a5a6"
        
        cumple_pct = kpis.pct_cumple
        cumple_color = "#27ae60" if cumple_pct > 0 else "#95a5a6"
        
        # Datos de KPIs
        kpi_data = [
            ("Total\nConversaciones", f"{kpis.total:,}", "#5dade2"),
            ("Inicio\nVálido", f"{kpis.pct_inicio_valido:.1f}%", "#2ecc71"),
            ("Cumplen\nSecuencia", f"{cumple_pct:.1f}%", cumple_color),
            ("Corte antes\nNegociación", f"{corte_pct:.1f}%", corte_color),
            ("Promedio\nViolaciones", f"{violaciones_avg:.2f}", violaciones_color),
        ]
        
        for i, (label, value, color) in enumerate(kpi_data):
            # Card frame con borde sutil gris
            card = tk.Frame(kpi_container, relief='solid', borderwidth=1, 
                          bg='white', padx=20, pady=15,
                          highlightbackground='#dfe6e9', highlightthickness=1)
            card.grid(row=0, column=i, sticky='nsew', padx=8, pady=5)
            
            # Número grande centrado
            num_label = tk.Label(card, text=value, font=('Segoe UI', 20, 'bold'),
                               fg=color, bg='white')
            num_label.pack(pady=(5, 8))
            
            # Label pequeño centrado
            text_label = tk.Label(card, text=label, font=('Segoe UI', 9),
                                fg='#636e72', bg='white', justify=tk.CENTER)
            text_label.pack()
    
    def _create_secuencias_table(self):
        """Crea tabla de secuencias con estilo mejorado"""
        table_container = ttk.Frame(self.frame_content)
        table_container.pack(fill=tk.BOTH, expand=True)
        # FIX: corregir nombre de método (era grid_rowconfigureframe_content)
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)
        
        # Scrollbars
        scroll_y = ttk.Scrollbar(table_container, orient=tk.VERTICAL)
        scroll_x = ttk.Scrollbar(table_container, orient=tk.HORIZONTAL)
        
        # Treeview con estilo
        columns = ("conv_id", "secuencia", "inicio", "fin", "violaciones", 
                  "cumple", "inicio_ok", "corte", "acciones")
        self.secuencias_tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            yscrollcommand=scroll_y.set,
            xscrollcommand=scroll_x.set,
            height=20,
            style='Secuencias.Treeview'
        )
        
        scroll_y.config(command=self.secuencias_tree.yview)
        scroll_x.config(command=self.secuencias_tree.xview)
        
        # Configurar columnas
        self.secuencias_tree.heading("conv_id", text="Conversación ID")
        self.secuencias_tree.heading("secuencia", text="Secuencia Macro")
        self.secuencias_tree.heading("inicio", text="Fase Inicio")
        self.secuencias_tree.heading("fin", text="Fase Fin")
        self.secuencias_tree.heading("violaciones", text="Violaciones")
        self.secuencias_tree.heading("cumple", text="Cumple")
        self.secuencias_tree.heading("inicio_ok", text="Inicio OK")
        self.secuencias_tree.heading("corte", text="Corte")
        self.secuencias_tree.heading("acciones", text="Acciones")
        
        self.secuencias_tree.column("conv_id", width=220, anchor=tk.W, stretch=False)
        self.secuencias_tree.column("secuencia", width=520, anchor=tk.W, stretch=True)
        self.secuencias_tree.column("inicio", width=170, anchor=tk.W, stretch=False)
        self.secuencias_tree.column("fin", width=170, anchor=tk.W, stretch=False)
        self.secuencias_tree.column("violaciones", width=80, anchor=tk.CENTER, stretch=False)
        self.secuencias_tree.column("cumple", width=70, anchor=tk.CENTER, stretch=False)
        self.secuencias_tree.column("inicio_ok", width=90, anchor=tk.CENTER, stretch=False)
        self.secuencias_tree.column("corte", width=70, anchor=tk.CENTER, stretch=False)
        self.secuencias_tree.column("acciones", width=90, anchor=tk.CENTER, stretch=False)
        
        # Tags para colores - zebra stripes + estados
        self.secuencias_tree.tag_configure('odd', background='#f8f9fa')
        self.secuencias_tree.tag_configure('even', background='#ffffff')
        
        # Tags para estados visuales (se combinan con zebra)
        self.secuencias_tree.tag_configure('ok', foreground='#27ae60')  # Verde para cumple
        self.secuencias_tree.tag_configure('warn', foreground='#e67e22')  # Naranja para corte
        self.secuencias_tree.tag_configure('bad', foreground='#e74c3c')  # Rojo para violaciones
        
        # Poblar datos
        for i, sec in enumerate(self.secuencias):
            # Símbolos unicode para badges (sin variantes de texto para evitar checkboxes)
            cumple_txt = "✅" if sec.cumple_secuencia else "—"
            inicio_ok_txt = "✅" if sec.inicio_valido else "—"
            corte_txt = "⚠" if sec.corte_antes_negociacion else "—"
            
            # Truncar secuencia para mostrar
            secuencia_display = sec.secuencia_macro
            if len(secuencia_display) > 60:
                secuencia_display = secuencia_display[:57] + "..."
            
            # Tags con priorización: zebra base + estado visual
            base_tag = 'odd' if i % 2 else 'even'
            tags = [base_tag]
            
            # Priorizar estado visual según condiciones
            if sec.corte_antes_negociacion:
                tags.append('warn')  # Naranja si hay corte
            elif sec.violaciones_transicion > 0 and not sec.cumple_secuencia:
                tags.append('bad')  # Rojo si hay violaciones y no cumple
            elif sec.cumple_secuencia:
                tags.append('ok')  # Verde si cumple
            
            item_id = self.secuencias_tree.insert("", tk.END, values=(
                sec.conversacion_id,
                secuencia_display,
                sec.fase_inicio or "",
                sec.fase_fin or "",
                sec.violaciones_transicion,
                cumple_txt,
                inicio_ok_txt,
                corte_txt,
                "Ver ▶"
            ), tags=tuple(tags), iid=str(sec.conversacion_pk))
            
            # FIX: Guardar secuencia completa en diccionario (no en column #0)
            self._full_seq_by_item[item_id] = sec.secuencia_macro
        
        # Bind eventos
        self.secuencias_tree.bind("<Double-Button-1>", self._on_ver_detalle)
        self.secuencias_tree.bind("<Motion>", self._on_tree_motion)
        self.secuencias_tree.bind("<Motion>", self._on_tree_motion_actions, add="+")
        self.secuencias_tree.bind("<Leave>", self._hide_tooltip)
        self.secuencias_tree.bind("<Leave>", lambda e: self.secuencias_tree.configure(cursor=""), add="+")
        self.secuencias_tree.bind("<MouseWheel>", self._hide_tooltip)
        self.secuencias_tree.bind("<<TreeviewSelect>>", self._hide_tooltip)
        self.secuencias_tree.bind("<Button-1>", self._on_tree_click, add="+")
        
        # Grid
        self.secuencias_tree.grid(row=0, column=0, sticky='nsew')
        scroll_y.grid(row=0, column=1, sticky='ns')
        scroll_x.grid(row=1, column=0, sticky='ew')
        
        # Botón Ver separado
        btn_frame = ttk.Frame(table_container)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(10, 0))
        
        ttk.Button(btn_frame, text="👁 Ver Detalles",
                  command=self._ver_detalle_seleccionado,
                  style='Ver.TButton').pack(side=tk.LEFT, padx=5)
        
        ttk.Button(btn_frame, text="📋 Copiar secuencia",
                  command=self._copiar_secuencia_seleccionada,
                  style='Ver.TButton').pack(side=tk.LEFT, padx=5)
    
    def _on_tree_click(self, event):
        """Maneja clicks en el Treeview - detecta clicks en columna acciones"""
        # Identificar región
        region = self.secuencias_tree.identify_region(event.x, event.y)
        if region != "cell":
            return
        
        # Identificar columna
        column = self.secuencias_tree.identify_column(event.x)
        
        # Solo procesar clicks en columna "acciones" (#9)
        if column != "#9":
            return
        
        # Identificar item
        item = self.secuencias_tree.identify_row(event.y)
        if not item:
            return
        
        # Convertir iid a conversacion_pk
        try:
            conversacion_pk = int(item)
        except ValueError:
            return
        
        # Abrir detalle
        if self.open_detalle_callback:
            self.open_detalle_callback(conversacion_pk)
        else:
            # Seleccionar el item primero para que _ver_detalle_seleccionado funcione
            self.secuencias_tree.selection_set(item)
            self._ver_detalle_seleccionado()
    
    def _on_tree_motion_actions(self, event):
        """Cambia el cursor a mano cuando está sobre la columna acciones"""
        # Identificar región
        region = self.secuencias_tree.identify_region(event.x, event.y)
        if region != "cell":
            self.secuencias_tree.configure(cursor="")
            return
        
        # Identificar columna
        column = self.secuencias_tree.identify_column(event.x)
        
        # Identificar item
        item = self.secuencias_tree.identify_row(event.y)
        
        # Cursor mano solo en columna acciones (#9) con item válido
        if column == "#9" and item:
            self.secuencias_tree.configure(cursor="hand2")
        else:
            self.secuencias_tree.configure(cursor="")
    
    def _copiar_secuencia_seleccionada(self):
        """Copia la secuencia completa de la fila seleccionada al clipboard"""
        selection = self.secuencias_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una conversación primero")
            return
        
        # Obtener secuencia completa del diccionario
        item_id = selection[0]
        secuencia_completa = self._full_seq_by_item.get(item_id, "")
        
        if not secuencia_completa:
            messagebox.showwarning("Advertencia", "No se encontró la secuencia")
            return
        
        # Copiar al clipboard
        self.clipboard_clear()
        self.clipboard_append(secuencia_completa)
        self.update()  # Actualizar para que se registre
        
        messagebox.showinfo("Copiado", "Secuencia copiada al portapapeles.")
    
    def _on_ver_detalle(self, event):
        """Maneja doble click en fila"""
        self._ver_detalle_seleccionado()
    
    def _ver_detalle_seleccionado(self):
        """Abre vista de detalle para la conversación seleccionada"""
        selection = self.secuencias_tree.selection()
        if not selection:
            messagebox.showwarning("Advertencia", "Seleccione una conversación")
            return
        
        # El iid es el conversacion_pk
        conversacion_pk = int(selection[0])
        
        # Si hay callback, usarlo para abrir vista de detalles
        if self.open_detalle_callback:
            self.open_detalle_callback(conversacion_pk)
        else:
            # Mostrar info básica
            sec = next((s for s in self.secuencias 
                       if s.conversacion_pk == conversacion_pk), None)
            if sec:
                messagebox.showinfo(
                    f"Conversación {sec.conversacion_id}",
                    f"Secuencia: {sec.secuencia_macro}\n\n"
                    f"Fase inicio: {sec.fase_inicio}\n"
                    f"Fase fin: {sec.fase_fin}\n"
                    f"Violaciones: {sec.violaciones_transicion}\n"
                    f"Cumple secuencia: {'Sí' if sec.cumple_secuencia else 'No'}"
                )
    
    def _on_tree_motion(self, event):
        """Muestra tooltip en columna de secuencia si está truncada - FIX: usa diccionario"""
        # Cancelar timer anterior si existe
        if self.tooltip_timer:
            self.after_cancel(self.tooltip_timer)
            self.tooltip_timer = None
        
        # Identificar item y región
        region = self.secuencias_tree.identify_region(event.x, event.y)
        if region != "cell":
            self._hide_tooltip()
            return
        
        item = self.secuencias_tree.identify_row(event.y)
        column = self.secuencias_tree.identify_column(event.x)
        
        # Solo mostrar tooltip en columna "secuencia" (#2)
        if column != "#2" or not item:
            self._hide_tooltip()
            return
        
        # FIX: Obtener secuencia completa desde diccionario (no desde column #0)
        secuencia_completa = self._full_seq_by_item.get(item, "")
        
        # Si es corta, no mostrar tooltip
        if len(secuencia_completa) <= 60:
            self._hide_tooltip()
            return
        
        # Si ya está mostrando el mismo texto, no hacer nada
        if self.tooltip and self.tooltip_text == secuencia_completa:
            return
        
        # Delay de 120ms antes de mostrar (evita parpadeo)
        self.tooltip_timer = self.after(120, 
            lambda: self._show_tooltip(event.x_root, event.y_root, secuencia_completa))
    
    def _show_tooltip(self, x, y, text):
        """Muestra tooltip estilo card con sombra"""
        if self.tooltip and self.tooltip_text == text:
            return  # Ya está mostrando el mismo tooltip
        
        self._hide_tooltip()
        
        self.tooltip_text = text
        self.tooltip = tk.Toplevel(self)
        self.tooltip.wm_overrideredirect(True)
        
        # Frame contenedor transparente
        container = tk.Frame(self.tooltip, bg='#bbbbbb')
        container.pack()
        
        # Frame sombra (offset 2px)
        shadow = tk.Frame(container, bg='#bbbbbb')
        shadow.place(x=2, y=2)
        
        # Frame card blanco
        card = tk.Frame(container, bg='white', relief='solid', 
                       borderwidth=1, highlightbackground='#d0d0d0',
                       highlightthickness=1)
        card.place(x=0, y=0)
        
        # Label con contenido
        label = tk.Label(
            card,
            text=text,
            background="#ffffff",
            foreground="#2c3e50",
            font=('Segoe UI', 9),
            padx=12,
            pady=8,
            wraplength=780,
            justify=tk.LEFT
        )
        label.pack()
        
        # Actualizar para obtener tamaño real
        self.tooltip.update_idletasks()
        width = label.winfo_reqwidth() + 26  # +26 por padding y bordes
        height = label.winfo_reqheight() + 20
        
        # Configurar tamaños de sombra y card
        shadow.config(width=width, height=height)
        card.config(width=width, height=height)
        
        # Posicionamiento inteligente (no salir de pantalla)
        pos_x = x + 12
        pos_y = y + 12
        
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        
        # Ajustar si se sale por la derecha
        if pos_x + width + 4 > screen_width:
            pos_x = screen_width - width - 10
        
        # Ajustar si se sale por abajo
        if pos_y + height + 4 > screen_height:
            pos_y = y - height - 12
        
        # Asegurar que no sea negativo
        pos_x = max(10, pos_x)
        pos_y = max(10, pos_y)
        
        self.tooltip.wm_geometry(f"+{pos_x}+{pos_y}")
    
    def _hide_tooltip(self, event=None):
        """Oculta tooltip y cancela timer"""
        # Cancelar timer si existe
        if self.tooltip_timer:
            self.after_cancel(self.tooltip_timer)
            self.tooltip_timer = None
        
        # Destruir tooltip si existe
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except:
                pass
            self.tooltip = None
            self.tooltip_text = ""
