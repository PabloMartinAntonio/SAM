from sa_core import fase_guardrails as fg

print("HAS_TOLERABLE_RETROCESOS:", hasattr(fg, "TOLERABLE_RETROCESOS"))
print("HAS_is_retroceso_tolerable:", hasattr(fg, "is_retroceso_tolerable"))

# Checks básicos (ajustá si cambiaste nombres)
pairs_true = [
    ("OBJECIONES_CLIENTE","OFERTA_PAGO"),
    ("VALIDACION_IDENTIDAD","PRESENTACION_AGENTE"),
    ("CONSULTA_ACEPTACION","OFERTA_PAGO"),
    ("CONSULTA_ACEPTACION","OBJECIONES_CLIENTE"),
]
pairs_false = [
    ("CIERRE","OFERTA_PAGO"),
    ("FORMALIZACION_PAGO","OFERTA_PAGO"),
    ("OFERTA_PAGO","EXPOSICION_DEUDA"),
]

for a,b in pairs_true:
    print("EXPECT True:", a, "->", b, "=", fg.is_retroceso_tolerable(a,b))

for a,b in pairs_false:
    print("EXPECT False:", a, "->", b, "=", fg.is_retroceso_tolerable(a,b))

print("OK")
