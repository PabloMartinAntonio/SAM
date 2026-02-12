"""
Dataclasses para modelos de datos
"""
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class EjecucionInfo:
    """Información de una ejecución"""
    ejecucion_id: int
    num_conversaciones: int

@dataclass
class StatsEjecucion:
    """Estadísticas de una ejecución"""
    ejecucion_id: Optional[int]  # None para total
    total_convs: int = 0
    total_turnos: int = 0
    turnos_con_fase: int = 0
    turnos_sin_fase: int = 0
    pendientes_por_conf: int = 0
    dist_fase: List[tuple] = field(default_factory=list)  # [(fase, count), ...]
    dist_fase_source: List[tuple] = field(default_factory=list)  # [(source, count), ...]
    
    # Opcional: promesas
    total_promesas: int = 0
    promesas_con_monto: int = 0
    promesas_sin_monto: int = 0

@dataclass
class Conversacion:
    """Información de conversación"""
    conversacion_pk: int
    conversacion_id: Optional[str] = None
    ejecucion_id: Optional[int] = None

@dataclass
class Turno:
    """Información de turno"""
    turno_pk: int
    conversacion_pk: int
    turno_idx: int
    speaker: Optional[str] = None
    text: Optional[str] = None
    fase: Optional[str] = None
    fase_source: Optional[str] = None
    fase_conf: Optional[float] = None
    intent: Optional[str] = None
    intent_conf: Optional[float] = None
    fase_seq: Optional[str] = None

@dataclass
class SecuenciaInfo:
    """Información de secuencia de conversación"""
    conversacion_pk: int
    conversacion_id: str
    secuencia_macro: str
    fase_inicio: Optional[str] = None
    fase_fin: Optional[str] = None
    violaciones_transicion: int = 0
    cumple_secuencia: int = 0
    inicio_valido: int = 0
    corte_antes_negociacion: int = 0
    tiene_negociacion: int = 0
    tiene_informacion_deuda: int = 0

@dataclass
class SecuenciaKPIs:
    """KPIs agregados de secuencias"""
    total: int = 0
    pct_inicio_valido: float = 0.0
    pct_cumple: float = 0.0
    pct_corte_antes_negociacion: float = 0.0
    avg_violaciones: float = 0.0

@dataclass
class CorreccionTurno:
    """Corrección humana de un turno"""
    conversacion_pk: int
    turno_idx: int
    fase_nueva: str
    intent_nuevo: Optional[str] = None
    nota: Optional[str] = None
