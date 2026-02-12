"""
Vista Detalles: navegación por conversaciones y turnos
"""
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import logging
from typing import List, Optional

from ui.models import Conversacion, Turno
import ui.services as services

logger = logging.getLogger(__name__)


class DetallesView(ttk.Frame):
    def __init__(self, parent, db_conn, app=None, **kwargs):
        super().__init__(parent, **kwargs)
        self.db_conn = db_conn
        self.task_queue = queue.Queue()
        self.app = app  # Referencia a SpeechAnalyticsApp para broadcast
        
        # Variables
        self.ejecuciones = []
        self.conversaciones = []
        self.turnos = []
        self.ejecucion_actual = None
        self.conversacion_actual = None
        
        # Flags para refresh global
        self._pending_preserve_id = None
        self._pending_select_id = None
        
        self._build_ui()
        self._schedule_queue_check()
        
        # Cargar inicial
        self.after(100, self.cargar_ejecuciones)
    
    def on_global_refresh(self, *, reason: str, preserve_id: int = None, select_id: int = None):
        """Handler de refresh global desde event bus"""
        logger.info(f"[DetallesView] on_global_refresh: reason={reason}, preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags para aplicar cuando llegue la respuesta async
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        # Recargar lista de ejecuciones (async)
        self.reload_runs(preserve_id=preserve_id, select_id=select_id)
    
    def reload_runs(self, preserve_id: int = None, select_id: int = None):
        """Recarga lista de ejecuciones desde BD"""
        logger.info(f"[DetallesView] reload_runs - preserve_id={preserve_id}, select_id={select_id}")
        
        # Guardar flags
        self._pending_preserve_id = preserve_id
        self._pending_select_id = select_id
        
        # Recargar ejecuciones (enviará "ejecuciones_cargadas")
        self.cargar_ejecuciones()
    
    def refresh_data(self):
        """Refresca datos (conversaciones) de la ejecución actual"""
        logger.info(f"[DetallesView] refresh_data - ejecucion_actual={self.ejecucion_actual}")
        try:
            if self.ejecucion_actual:
                self.buscar_conversaciones()
        except Exception as e:
            logger.error(f"[DetallesView] Error en refresh_data: {e}", exc_info=True)
        
        # Cargar inicial
        self.after(100, self.cargar_ejecuciones)
    
    def _build_ui(self):
        # Top frame: selector ejecución + búsqueda
        top_frame = ttk.Frame(self)
        top_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(top_frame, text="Ejecución:").pack(side=tk.LEFT, padx=5)
        
        self.ejecucion_combo = ttk.Combobox(top_frame, width=20, state="readonly")
        self.ejecucion_combo.pack(side=tk.LEFT, padx=5)
        self.ejecucion_combo.bind("<<ComboboxSelected>>", self._on_ejecucion_selected)
        
        ttk.Label(top_frame, text="Buscar:").pack(side=tk.LEFT, padx=5)
        
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=self.search_var, width=30)
        search_entry.pack(side=tk.LEFT, padx=5)
        search_entry.bind("<Return>", lambda e: self.buscar_conversaciones())
        
        ttk.Button(top_frame, text="Buscar", command=self.buscar_conversaciones).pack(side=tk.LEFT, padx=2)
        ttk.Button(top_frame, text="Limpiar", command=self.limpiar_busqueda).pack(side=tk.LEFT, padx=2)
        
        # PanedWindow para split horizontal
        paned = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Panel izquierdo: conversaciones
        left_frame = ttk.LabelFrame(paned, text="Conversaciones (max 500)", padding=5)
        paned.add(left_frame, weight=1)
        
        conv_tree_frame = ttk.Frame(left_frame)
        conv_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        conv_scrollbar = ttk.Scrollbar(conv_tree_frame, orient=tk.VERTICAL)
        self.conversaciones_tree = ttk.Treeview(
            conv_tree_frame,
            columns=("pk", "id"),
            show="headings",
            yscrollcommand=conv_scrollbar.set
        )
        conv_scrollbar.config(command=self.conversaciones_tree.yview)
        
        self.conversaciones_tree.heading("pk", text="PK")
        self.conversaciones_tree.heading("id", text="Conversación ID")
        self.conversaciones_tree.column("pk", width=80, anchor=tk.E)
        self.conversaciones_tree.column("id", width=200)
        
        self.conversaciones_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conv_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.conversaciones_tree.bind("<<TreeviewSelect>>", self._on_conversacion_selected)
        
        # Panel derecho: turnos + detalle
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=2)
        
        # Turnos arriba
        turnos_frame = ttk.LabelFrame(right_frame, text="Turnos", padding=5)
        turnos_frame.pack(fill=tk.BOTH, expand=True)
        
        turnos_tree_frame = ttk.Frame(turnos_frame)
        turnos_tree_frame.pack(fill=tk.BOTH, expand=True)
        
        turnos_scrollbar = ttk.Scrollbar(turnos_tree_frame, orient=tk.VERTICAL)
        self.turnos_tree = ttk.Treeview(
            turnos_tree_frame,
            columns=("idx", "speaker", "fase", "fase_seq", "source", "conf"),
            show="headings",
            yscrollcommand=turnos_scrollbar.set
        )
        turnos_scrollbar.config(command=self.turnos_tree.yview)
        
        self.turnos_tree.heading("idx", text="Idx")
        self.turnos_tree.heading("speaker", text="Speaker")
        self.turnos_tree.heading("fase", text="Fase")
        self.turnos_tree.heading("fase_seq", text="Macrofase")
        self.turnos_tree.heading("source", text="Source")
        self.turnos_tree.heading("conf", text="Conf")
        
        self.turnos_tree.column("idx", width=50, anchor=tk.E)
        self.turnos_tree.column("speaker", width=80)
        self.turnos_tree.column("fase", width=130)
        self.turnos_tree.column("fase_seq", width=130)
        self.turnos_tree.column("source", width=90)
        self.turnos_tree.column("conf", width=60, anchor=tk.E)
        
        self.turnos_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        turnos_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.turnos_tree.bind("<<TreeviewSelect>>", self._on_turno_selected)
        
        # Detalle abajo
        detalle_frame = ttk.LabelFrame(right_frame, text="Texto del Turno", padding=5)
        detalle_frame.pack(fill=tk.BOTH, expand=False, pady=(5, 0))
        
        detalle_text_frame = ttk.Frame(detalle_frame)
        detalle_text_frame.pack(fill=tk.BOTH, expand=True)
        
        detalle_scrollbar = ttk.Scrollbar(detalle_text_frame, orient=tk.VERTICAL)
        self.detalle_text = tk.Text(
            detalle_text_frame,
            height=6,
            wrap=tk.WORD,
            yscrollcommand=detalle_scrollbar.set
        )
        detalle_scrollbar.config(command=self.detalle_text.yview)
        
        self.detalle_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detalle_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    
    def cargar_ejecuciones(self):
        """Carga lista de ejecuciones"""
        def task():
            try:
                ejecuciones = services.listar_ejecuciones(self.db_conn)
                self.task_queue.put(("ejecuciones_cargadas", ejecuciones))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando ejecuciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def buscar_conversaciones(self):
        """Busca conversaciones según criterios"""
        if self.ejecucion_actual is None:
            messagebox.showwarning("Advertencia", "Seleccione una ejecución primero")
            return
        
        search = self.search_var.get().strip()
        
        def task():
            try:
                conversaciones = services.listar_conversaciones(
                    self.db_conn, 
                    self.ejecucion_actual,
                    search=search
                )
                self.task_queue.put(("conversaciones_cargadas", conversaciones))
            except Exception as e:
                self.task_queue.put(("error", f"Error buscando conversaciones: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def limpiar_busqueda(self):
        """Limpia búsqueda y recarga"""
        self.search_var.set("")
        self.buscar_conversaciones()
    
    def _on_ejecucion_selected(self, event):
        """Handler selección de ejecución"""
        idx = self.ejecucion_combo.current()
        if idx >= 0 and idx < len(self.ejecuciones):
            self.ejecucion_actual = self.ejecuciones[idx].ejecucion_id
            self.buscar_conversaciones()
    
    def _on_conversacion_selected(self, event):
        """Handler selección de conversación"""
        selection = self.conversaciones_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        values = self.conversaciones_tree.item(item, "values")
        conv_pk = int(values[0])
        
        self.conversacion_actual = conv_pk
        
        def task():
            try:
                turnos = services.listar_turnos(self.db_conn, conv_pk)
                self.task_queue.put(("turnos_cargados", turnos))
            except Exception as e:
                self.task_queue.put(("error", f"Error cargando turnos: {e}"))
        
        threading.Thread(target=task, daemon=True).start()
    
    def _on_turno_selected(self, event):
        """Handler selección de turno"""
        selection = self.turnos_tree.selection()
        if not selection:
            return
        
        item = selection[0]
        # Obtener turno desde la lista
        idx_str = self.turnos_tree.item(item, "values")[0]
        turno_idx = int(idx_str)
        
        # Buscar turno en lista
        turno = next((t for t in self.turnos if t.turno_idx == turno_idx), None)
        if turno:
            self._update_detalle_text(turno)
    
    def _update_detalle_text(self, turno: Turno):
        """Actualiza panel de detalle con texto del turno"""
        self.detalle_text.delete("1.0", tk.END)
        
        text = turno.text or "(sin texto)"
        info = f"Turno {turno.turno_idx} - {turno.speaker or '?'}\n"
        info += f"Fase: {turno.fase or '(none)'} | Source: {turno.fase_source or '(none)'} | Conf: {turno.fase_conf or 'N/A'}\n"
        if turno.fase_seq:
            info += f"Macrofase (fase_seq): {turno.fase_seq}\n"
        if turno.intent:
            info += f"Intent: {turno.intent} | Intent Conf: {turno.intent_conf or 'N/A'}\n"
        info += f"\n{text}"
        
        self.detalle_text.insert("1.0", info)
    
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
        if msg[0] == "ejecuciones_cargadas":
            self.ejecuciones = msg[1]
            self._update_ejecuciones_combo()
        elif msg[0] == "conversaciones_cargadas":
            self.conversaciones = msg[1]
            self._update_conversaciones_tree()
        elif msg[0] == "turnos_cargados":
            self.turnos = msg[1]
            self._update_turnos_tree()
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
        target_id = None
        
        # Prioridad 1: select_id (selección explícita)
        if self._pending_select_id:
            target_id = self._pending_select_id
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_select_id:
                    selected_idx = i
                    logger.info(f"[DetallesView] Seleccionando select_id={self._pending_select_id} (idx={i})")
                    break
        # Prioridad 2: preserve_id (preservar selección)
        elif self._pending_preserve_id:
            target_id = self._pending_preserve_id
            for i, ej in enumerate(self.ejecuciones):
                if ej.ejecucion_id == self._pending_preserve_id:
                    selected_idx = i
                    logger.info(f"[DetallesView] Preservando preserve_id={self._pending_preserve_id} (idx={i})")
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
        logger.info(f"[DetallesView] Ejecución seleccionada: {self.ejecucion_actual}")
        
        # Limpiar flags
        self._pending_preserve_id = None
        self._pending_select_id = None
    
    def _update_conversaciones_tree(self):
        """Actualiza tree de conversaciones"""
        # Limpiar
        for item in self.conversaciones_tree.get_children():
            self.conversaciones_tree.delete(item)
        
        # Llenar
        for conv in self.conversaciones:
            self.conversaciones_tree.insert(
                "", tk.END,
                values=(conv.conversacion_pk, conv.conversacion_id or "(sin ID)")
            )
    
    def _update_turnos_tree(self):
        """Actualiza tree de turnos"""
        # Limpiar
        for item in self.turnos_tree.get_children():
            self.turnos_tree.delete(item)
        
        # Limpiar detalle
        self.detalle_text.delete("1.0", tk.END)
        
        # Llenar
        for turno in self.turnos:
            conf_str = f"{turno.fase_conf:.2f}" if turno.fase_conf is not None else "N/A"
            self.turnos_tree.insert(
                "", tk.END,
                values=(
                    turno.turno_idx,
                    turno.speaker or "?",
                    turno.fase or "(none)",
                    turno.fase_seq or "",
                    turno.fase_source or "(none)",
                    conf_str
                )
            )
