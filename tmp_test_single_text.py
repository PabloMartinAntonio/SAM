from sa_core.fases_rules import detect_fase_rules_based

txt = "Ya. Déjeme, entonces, un mañana me podría llamar, yo iría al coordino con mi hijo, ¿no? Ojalá que me pueda dar. ¿Con quién tengo el gusto?"

tests = [
    (None, False),
    ("FORMALIZACION_PAGO", False),
    ("NEGOCIACION", False),
    ("FORMALIZACION_PAGO", True),
]

for last_phase, is_last in tests:
    fase, conf, score = detect_fase_rules_based(
        txt, 31, 43, last_phase=last_phase, is_last_turns=is_last
    )
    print(f"last_phase={last_phase} is_last={is_last} -> fase={fase} conf={conf:.4f} score={score}")
