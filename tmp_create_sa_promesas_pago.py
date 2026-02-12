from sa_core.config import load_config
from sa_core.db import get_conn

cfg = load_config("config.ini")
conn = get_conn(cfg)
cur = conn.cursor()

sql = """
CREATE TABLE IF NOT EXISTS sa_promesas_pago (
  promesa_pk BIGINT AUTO_INCREMENT PRIMARY KEY,
  conversacion_pk INT NOT NULL,
  turno_pk BIGINT NULL,
  turno_idx INT NULL,

  monto DECIMAL(12,2) NULL,
  moneda VARCHAR(8) NULL,
  numero_cuotas INT NULL,
  fecha_pago DATE NULL,
  fecha_pago_texto VARCHAR(64) NULL,

  estado_promesa VARCHAR(32) NOT NULL,
  confidence DECIMAL(6,4) NULL,
  source VARCHAR(16) NOT NULL,

  evidence_text VARCHAR(500) NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

  KEY idx_promesas_conv (conversacion_pk),
  KEY idx_promesas_turno (turno_pk)
);
"""
cur.execute(sql)
conn.commit()

# chequeo rápido
cur.execute("SHOW TABLES LIKE 'sa_promesas_pago'")
print("table_exists=", cur.fetchone() is not None)

cur.execute("DESCRIBE sa_promesas_pago")
print("columns:")
for r in cur.fetchall():
  print(r)

cur.close()
conn.close()
print("[OK] sa_promesas_pago ready")
