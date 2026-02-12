"""
Vista Aprendizaje: corrección humana de fases
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
import csv
from pathlib import Path
from typing import List, Optional, Dict
from datetime import datetime

from ui.models import Turno, CorreccionTurno
import ui.services as services

logger = logging.getLogger(__name__)


class AprendizajeView(ttk.Frame):
    def __init__(self, parent, db_conn, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db_conn = db_conn
        self.task_queue = queue.Queue()
        self.app = app  # Referencia a SpeechAnalyticsApp para broadcast
        
        # Variables
        self.ejecuciones = []
        self.turnos_pendientes = []
        self.fases_disponibles = []
        self.correcciones_buffer = []  # Buffer de correcciones antes de aplicar
        self.context_rows = []  # Contexto de turnos cargado
        
        self.ejecucion_actual = None
        self.turno_seleccionado = None
        self.offset_actual = 0
        self.limit = 200
        
        self.conf_threshold_var = tk.StringVar(value="0.08")
        self.context_window_var = tk.IntVar(value=3)  # Ventana de contexto
        
        # Flags para refresh global
        self._pending_preserve_id = None
        self._pending_select_id = None
        
        self._build_ui()
        self._schedule_queue_check()
        
        # Cargar inicial
        self.after(100, self.cargar_inicial)
    
    def on_global_refresh(self, *, reason: str, preserve_id: int = None, select_id: int = None):
        """Handler de refresh global desde event bus"""
        logger.info(f"[AprendizajeView] on_global_refresh: reason={reason}, preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags para aplicar cuando llegue la respuesta async
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        # Recargar lista de ejecuciones (async)
        self.reload_runs(preserve_id=preserve_id, select_id=select_id)
    
    def reload_runs(self, preserve_id: int = None, select_id: int = None):
        """Recarga lista de ejecuciones desde BD"""
        logger.info(f"[AprendizajeView] reload_runs - preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        # Recargar inicial (ejecuciones + fases)
        self.cargar_inicial()
    
    def refresh_data(self):
        """Refresca datos (turnos pendientes) de la ejecución actual"""
        logger.info(f"[AprendizajeView] refresh_data - ejecucion_actual={self.ejecucion_actual}")
        try:
            if hasattr(self, 'ejecucion_actual') and self.ejecucion_actual:
                self.cargar_pendientes()
        except Exception as e:
            logger.error(f"[AprendizajeView] Error en refresh_data: {e}", exc_info=True)
    
    def _build_ui(self):
        # Top frame: controles
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(top_frame, text="Ejecución:").pack(side=tk.LEFT, padx=5)
        
        self.ejecucion_combo = ttk.Combobox(top_frame, width=20, state="readonly")
        self.ejecucion_combo.pack(side=tk.LEFT, padx=5)
        self.ejecucion_combo.bind("<<ComboboxSelected>>", self._on_ejecucion_selected)
        
        ttk.Label(top_frame, text="Umbral:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(top_frame, textvariable=self.conf_threshold_var, width=8).pack(side=tk.LEFT, padx=2)
        
        ttk.Label(top_frame, text="Contexto:").pack(side=tk.LEFT, padx=5)
        context_spinbox = ttk.Spinbox(
            top_frame, 
            from_=1, 
            to=20, 
            textvariable=self.context_window_var,
            width=5
        )
        context_spinbox.pack(side=tk.LEFT, padx=2)
        
        ttk.Button(top_frame, text="Cargar Pendientes", command=self.cargar_pendientes).pack(side=tk.LEFT, padx=5)
        
        # Paginación
        self.page_label = ttk.Label(top_frame, text="Página: 1")
        self.page_label.pack(side=tk.LEFT, padx=10)
        
        ttk.Button(top_frame, text="Anterior", command=self.pagina_anterior).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Siguiente", command=self.pagina_siguiente).pack(side=tk.LEFT, padx=2)
        
        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=5)
        
        # PanedWindow para split
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo: lista de turnos pendientes
        left_frame = ttk.LabelFrame(paned, text="Turnos Pendientes", padding=5)
        paned.add(left_frame, weight=1)
        
        turnos_tree_frame = ttk.Frame(left_frame)
        turnos_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        turnos_scrollbar = ttk.Scrollbar(turnos_tree_frame, orient=tk.VERTICAL)
        self.turnos_tree = ttk.Treeview(
            turnos_tree_frame,
            columns=("conv_pk", "idx", "speaker", "fase", "conf", "texto_prev"),
            show="headings",
            yscrollcommand=turnos_scrollbar.set
        )
        turnos_scrollbar.config(command=self.turnos_tree.yview)
        
        self.turnos_tree.heading("conv_pk", text="Conv PK")
        self.turnos_tree.heading("idx", text="Idx")
        self.turnos_tree.heading("speaker", text="Speaker")
        self.turnos_tree.heading("fase", text="Fase Actual")
        self.turnos_tree.heading("conf", text="Conf")
        self.turnos_tree.heading("texto_prev", text="Preview")
        
        self.turnos_tree.column("conv_pk", width=80, anchor=tk.E)
        self.turnos_tree.column("idx", width=50, anchor=tk.E)
        self.turnos_tree.column("speaker", width=80)
        self.turnos_tree.column("fase", width=120)
        self.turnos_tree.column("conf", width=60, anchor=tk.E)
        self.turnos_tree.column("texto_prev", width=200)
        
        self.turnos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        turnos_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.turnos_tree.bind("<<TreeviewSelect>>", self._on_turno_selected)
        
        # Panel derecho: edición
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=1)
        
        # Contexto de la conversación
        context_frame = ttk.LabelFrame(right_frame, text="Contexto de la Conversación", padding=5)
        context_frame.pack(fill=tk.BOTH, expand=True)
        
        context_scroll = ttk.Scrollbar(context_frame, orient=tk.VERTICAL)
        self.context_text = tk.Text(
            context_frame,
            height=12,
            wrap=tk.WORD,
            yscrollcommand=context_scroll.set,
            font=("Courier", 9)
        )
        context_scroll.config(command=self.context_text.yview)
        self.context_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        context_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Configurar tags para resaltado
        self.context_text.tag_config("selected", background="#ffffcc", font=("Courier", 9, "bold"))
        self.context_text.tag_config("header", foreground="#0066cc", font=("Courier", 9, "bold"))
        self.context_text.tag_config("speaker_agent", foreground="#006600")
        self.context_text.tag_config("speaker_cliente", foreground="#cc6600")
        
        # Controles de corrección
        correccion_frame = ttk.LabelFrame(right_frame, text="Corrección", padding=10)
        correccion_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(correccion_frame, text="Fase:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.fase_combo = ttk.Combobox(correccion_frame, width=30)
        self.fase_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        
        ttk.Label(correccion_frame, text="Intent (opcional):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.intent_var = tk.StringVar()
        ttk.Entry(correccion_frame, textvariable=self.intent_var, width=32).grid(
            row=1, column=1, sticky=tk.EW, pady=5, padx=5
        )
        
        ttk.Label(correccion_frame, text="Nota:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.nota_var = tk.StringVar()
        ttk.Entry(correccion_frame, textvariable=self.nota_var, width=32).grid(
            row=2, column=1, sticky=tk.EW, pady=5, padx=5
        )
        
        correccion_frame.columnconfigure(1, weight=1)
        
        btn_frame = ttk.Frame(correccion_frame)
        btn_frame.grid(row=3, column=0, columnspan=2, pady=10)
        
        ttk.Button(btn_frame, text="Guardar a CSV", command=self.guardar_correccion_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Aplicar a BD", command=self.aplicar_correccion_bd).pack(side=tk.LEFT, padx=5)
        
        # Info y acciones globales
        info_frame = ttk.LabelFrame(right_frame, text="Acciones Globales", padding=10)
        info_frame.pack(fill=tk.X, pady=(5, 0))
        
        self.correcciones_label = ttk.Label(info_frame, text="Correcciones en buffer: 0")
        self.correcciones_label.pack(pady=5)
        
        ttk.Button(
            info_frame, 
            text="Aplicar Buffer a BD (WRITE)",
            command=self.aplicar_buffer_bd
        ).pack(pady=5, fill=tk.X)
        
        ttk.Button(
            info_frame,
            text="Limpiar Buffer",
            command=self.limpiar_buffer
        ).pack(pady=5, fill=tk.X)
    
    def cargar_inicial(self):
        """Carga datos iniciales"""
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                fases = services.get_fases_disponibles(self.db_conn)
                self.task_queue.put(("inicial_cargado", ejecuciones, fases))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando inicial: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def cargar_pendientes(self):
        """Carga turnos pendientes"""
        if self.ejecucion_actual is None:
            messagebox.showwarning("Advertencia", "Seleccione una ejecución")
            return
        
        try:
            threshold = float(self.conf_threshold_var.get())
        except ValueError:
            messagebox.showerror("Error", "Umbral inválido")
            return
        
        def task():
            try:
                turnos = services.listar_turnos_pendientes(
                    self.db_conn,
                    self.ejecucion_actual,
                    threshold,
                    self.offset_actual,
                    self.limit
                )
                self.task_queue.put(("pendientes_cargados", turnos))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando pendientes: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def pagina_anterior(self):
        """Va a página anterior"""
        if self.offset_actual >= self.limit:
            self.offset_actual -= self.limit
            self._update_page_label()
            self.cargar_pendientes()
    
    def pagina_siguiente(self):
        """Va a página siguiente"""
        if len(self.turnos_pendientes) == self.limit:
            self.offset_actual += self.limit
            self._update_page_label()
            self.cargar_pendientes()
    
    def _update_page_label(self):
        """Actualiza label de página"""
        page_num = (self.offset_actual // self.limit) + 1
        self.page_label.config(text=f"Página: {page_num}")
    
    def guardar_correccion_csv(self):
        """Guarda corrección actual a CSV"""
        if self.turno_seleccionado is None:
            messagebox.showwarning("Advertencia", "Seleccione un turno")
            return
        
        fase_nueva = self.fase_combo.get().strip()
        if not fase_nueva:
            messagebox.showwarning("Advertencia", "Ingrese una fase")
            return
        
        intent_nuevo = self.intent_var.get().strip() or None
        nota = self.nota_var.get().strip() or None
        
        # Crear corrección
        correccion = CorreccionTurno(
            conversacion_pk=self.turno_seleccionado.conversacion_pk,
            turno_idx=self.turno_seleccionado.turno_idx,
            fase_nueva=fase_nueva,
            intent_nuevo=intent_nuevo,
            nota=nota
        )
        
        # Generar contexto_text desde context_rows (max 2000 chars)
        contexto_window = self.context_window_var.get()
        contexto_text = ""
        
        if self.context_rows:
            context_parts = []
            for row in self.context_rows:
                idx = row.get("turno_idx", 0)
                speaker = row.get("speaker") or "?"
                text = row.get("text") or ""
                # Formato compacto: [idx] SPEAKER: texto
                context_parts.append(f"[{idx}] {speaker}: {text}")
            
            contexto_text = " | ".join(context_parts)
            # Truncar a 2000 chars
            if len(contexto_text) > 2000:
                contexto_text = contexto_text[:1997] + "..."
        
        # Guardar a CSV
        try:
            csv_path = Path("out_reports") / "labels_turnos.csv"
            csv_path.parent.mkdir(exist_ok=True)
            
            file_exists = csv_path.exists()
            
            with open(csv_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                
                if not file_exists:
                    writer.writerow([
                        "ts", "ejecucion_id", "conversacion_pk", "turno_idx", 
                        "fase_old", "fase_new", "intent_old", "intent_new", 
                        "nota", "contexto_window", "contexto_text"
                    ])
                
                writer.writerow([
                    datetime.now().isoformat(),
                    self.ejecucion_actual or "",
                    correccion.conversacion_pk,
                    correccion.turno_idx,
                    self.turno_seleccionado.fase or "",
                    correccion.fase_nueva,
                    self.turno_seleccionado.intent or "",
                    correccion.intent_nuevo or "",
                    correccion.nota or "",
                    contexto_window,
                    contexto_text
                ])
            
            messagebox.showinfo("Éxito", f"Corrección guardada en {csv_path}")
            
            # Limpiar campos
            self.intent_var.set("")
            self.nota_var.set("")
        
        except Exception as e:
            messagebox.showerror("Error", f"Error guardando CSV: {e}")
    
    def aplicar_correccion_bd(self):
        """Aplica corrección actual directamente a BD"""
        if self.turno_seleccionado is None:
            messagebox.showwarning("Advertencia", "Seleccione un turno")
            return
        
        fase_nueva = self.fase_combo.get().strip()
        if not fase_nueva:
            messagebox.showwarning("Advertencia", "Ingrese una fase")
            return
        
        intent_nuevo = self.intent_var.get().strip() or None
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Aplicar corrección a BD?\n\nConv PK: {self.turno_seleccionado.conversacion_pk}\n"
            f"Turno Idx: {self.turno_seleccionado.turno_idx}\n"
            f"Fase: {self.turno_seleccionado.fase or '(none)'} → {fase_nueva}"
        )
        
        if not respuesta:
            return
        
        def task():
            try:
                success = services.aplicar_correccion_turno(
                    self.db_conn,
                    self.turno_seleccionado.conversacion_pk,
                    self.turno_seleccionado.turno_idx,
                    fase_nueva,
                    intent_nuevo,
                    commit=True
                )
                
                if success:
                    self.task_queue.put(("correccion_aplicada", None))
                else:
                    self.task_queue.put(("error", "Error aplicando corrección"))
            except Exception as e:
                self.task_queue.put(("error", f"Error: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def aplicar_buffer_bd(self):
        """Aplica todas las correcciones del buffer a BD"""
        if not self.correcciones_buffer:
            messagebox.showinfo("Info", "No hay correcciones en buffer")
            return
        
        respuesta = messagebox.askyesno(
            "Confirmar",
            f"¿Aplicar {len(self.correcciones_buffer)} correcciones a BD?"
        )
        
        if not respuesta:
            return
        
        def task():
            try:
                success_count = 0
                for corr in self.correcciones_buffer:
                    success = services.aplicar_correccion_turno(
                        self.db_conn,
                        corr.conversacion_pk,
                        corr.turno_idx,
                        corr.fase_nueva,
                        corr.intent_nuevo,
                        commit=False  # Commit al final
                    )
                    if success:
                        success_count += 1
                
                self.db_conn.commit()
                self.task_queue.put(("buffer_aplicado", success_count))
            except Exception as e:
                self.db_conn.rollback()
                self.task_queue.put(("error", f"Error aplicando buffer: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def limpiar_buffer(self):
        """Limpia buffer de correcciones"""
        self.correcciones_buffer.clear()
        self._update_buffer_label()
        messagebox.showinfo("Info", "Buffer limpiado")
    
    def _on_ejecucion_selected(self, event):
        """Handler selección de ejecución"""
        idx = self.ejecucion_combo.current()
        if idx >= 0 and idx < len(self.ejecuciones):
            self.ejecucion_actual = self.ejecuciones[idx].ejecucion_id
            self.offset_actual = 0
            self._update_page_label()
    
    def _on_turno_selected(self, event):
        """Handler selección de turno"""
        selection = self.turnos_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.turnos_tree.item(item, "values")
        conv_pk = int(values[0])
        turno_idx = int(values[1])
        
        # Buscar turno
        turno = next(
            (t for t in self.turnos_pendientes 
             if t.conversacion_pk == conv_pk and t.turno_idx == turno_idx),
            None
        )
        
        if turno:
            self.turno_seleccionado = turno
            # Cargar contexto en background
            self._cargar_contexto_turno(turno)
    
    def _cargar_contexto_turno(self, turno: Turno):
        """Carga contexto de un turno en background"""
        window = self.context_window_var.get()
        
        def task():
            try:
                context_rows = services.get_turnos_context(
                    self.db_conn,
                    turno.conversacion_pk,
                    turno.turno_idx,
                    window
                )
                self.task_queue.put(("contexto_cargado", context_rows, turno))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando contexto: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def _update_turno_display(self, turno: Turno):
        """Actualiza display del turno seleccionado (solo autocompleta fase)"""
        # Pre-llenar fase si existe
        if turno.fase:
            self.fase_combo.set(turno.fase)
        else:
            self.fase_combo.set("")
        
        # Limpiar intent y nota
        self.intent_var.set("")
        self.nota_var.set("")
    
    def _render_context_text(self, context_rows: List[dict], selected_turno_idx: int):
        """Renderiza contexto de turnos en el Text widget"""
        self.context_text.delete("1.0", tk.END)
        
        if not context_rows:
            self.context_text.insert("1.0", "(No hay contexto disponible)")
            return
        
        # Variable para trackear posición del turno seleccionado
        selected_line = None
        
        for i, row in enumerate(context_rows):
            idx = row.get("turno_idx", 0)
            speaker = row.get("speaker") or "?"
            fase = row.get("fase") or "(none)"
            fase_source = row.get("fase_source") or "(none)"
            fase_conf = row.get("fase_conf")
            text = row.get("text") or "(sin texto)"
            
            # Formatear confianza
            conf_str = f"{fase_conf:.2f}" if fase_conf is not None else "N/A"
            
            # Header del turno
            is_selected = (idx == selected_turno_idx)
            header = f"[{idx}] {speaker} | {fase} | {conf_str} | {fase_source}\n"
            
            # Insertar header
            start_pos = self.context_text.index(tk.INSERT)
            self.context_text.insert(tk.INSERT, header)
            end_pos = self.context_text.index(tk.INSERT)
            
            # Aplicar tag al header
            if is_selected:
                self.context_text.tag_add("selected", start_pos, end_pos)
                selected_line = start_pos
            else:
                self.context_text.tag_add("header", start_pos, end_pos)
            
            # Insertar texto del turno
            text_start = self.context_text.index(tk.INSERT)
            self.context_text.insert(tk.INSERT, f"{text}\n")
            text_end = self.context_text.index(tk.INSERT)
            
            # Aplicar tag al texto si es seleccionado
            if is_selected:
                self.context_text.tag_add("selected", text_start, text_end)
            
            # Aplicar tag por speaker (opcional)
            speaker_lower = speaker.lower()
            if "agent" in speaker_lower or "asesor" in speaker_lower:
                self.context_text.tag_add("speaker_agent", text_start, text_end)
            elif "client" in speaker_lower or "usuario" in speaker_lower:
                self.context_text.tag_add("speaker_cliente", text_start, text_end)
            
            # Separador
            if i < len(context_rows) - 1:
                self.context_text.insert(tk.INSERT, "-" * 70 + "\n")
        
        # Scroll para hacer visible el turno seleccionado
        if selected_line:
            self.context_text.see(selected_line)
    
    def _update_buffer_label(self):
        """Actualiza label de buffer"""
        self.correcciones_label.config(text=f"Correcciones en buffer: {len(self.correcciones_buffer)}")
    
    def _schedule_queue_check(self):
        """Revisa cola de tareas"""
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
        if msg[0] == "inicial_cargado":
            self.ejecuciones = msg[1]
            self.fases_disponibles = msg[2]
            self._update_ejecuciones_combo()
            self._update_fases_combo()
        elif msg[0] == "pendientes_cargados":
            self.turnos_pendientes = msg[1]
            self._update_turnos_tree()
        elif msg[0] == "contexto_cargado":
            context_rows = msg[1]
            turno = msg[2]
            self.context_rows = context_rows
            self._render_context_text(context_rows, turno.turno_idx)
            self._update_turno_display(turno)
        elif msg[0] == "correccion_aplicada":
            messagebox.showinfo("Éxito", "Corrección aplicada a BD")
            self.cargar_pendientes()  # Recargar lista
        elif msg[0] == "buffer_aplicado":
            count = msg[1]
            messagebox.showinfo("Éxito", f"{count} correcciones aplicadas a BD")
            self.correcciones_buffer.clear()
            self._update_buffer_label()
            self.cargar_pendientes()
        elif msg[0] == "error":
            messagebox.showerror("Error", msg[1])
    
    def _update_ejecuciones_combo(self):
        """Actualiza combo de ejecuciones con soporte para preserve/select"""
        values = [f"Ejecución {ej.ejecucion_id} ({ej.num_conversaciones} convs)"
                 for ej in self.ejecuciones]
        self.ejecucion_combo["values"] = values
        
        if not values:
            return
        
        # Determinar índice a seleccionar
        selected_idx = 0
        
        # Prioridad 1: select_id (selección explícita)
        if self._pending_select_id:
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_select_id:
                    selected_idx = i
                    logger.info(f"[AprendizajeView] Seleccionando select_id={self._pending_select_id} (idx={i})")
                    break
        # Prioridad 2: preserve_id (preservar selección)
        elif self._pending_preserve_id:
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_preserve_id:
                    selected_idx = i
                    logger.info(f"[AprendizajeView] Preservando preserve_id={self._pending_preserve_id} (idx={i})")
                    break
        # Prioridad 3: mantener actual si existe
        elif self.ejecucion_actual:
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self.ejecucion_actual:
                    selected_idx = i
                    break
        
        # Aplicar selección
        self.ejecucion_combo.current(selected_idx)
        self.ejecucion_actual = self.ejecuciones[selected_idx].ejecucion_id
        logger.info(f"[AprendizajeView] Ejecución seleccionada: {self.ejecucion_actual}")
        
        # Limpiar flags
        self._pending_preserve_id = None
        self._pending_select_id = None
    
    def _update_fases_combo(self):
        """Actualiza combo de fases"""
        self.fase_combo["values"] = self.fases_disponibles
    
    def _update_turnos_tree(self):
        """Actualiza tree de turnos pendientes"""
        # Limpiar
        for item in self.turnos_tree.get_children():
            self.turnos_tree.delete(item)
        
        # Llenar
        for turno in self.turnos_pendientes:
            preview = (turno.text or "")[:60]
            if len(turno.text or "") > 60:
                preview += "..."
            
            conf_str = f"{turno.fase_conf:.2f}" if turno.fase_conf is not None else "N/A"
            
            self.turnos_tree.insert(
                "", tk.END,
                values=(
                    turno.conversacion_pk,
                    turno.turno_idx,
                    turno.speaker or "?",
                    turno.fase or "(none)",
                    conf_str,
                    preview
                )
            )
