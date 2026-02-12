CREATE TABLE IF NOT EXISTS sa_ejecuciones (
    ejecucion_id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notas TEXT,
    input_dir VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS sa_conversaciones (
    conversacion_pk INT AUTO_INCREMENT PRIMARY KEY,
    ejecucion_id INT,
    conversacion_id VARCHAR(255),
    raw_path VARCHAR(512),
    raw_text LONGTEXT,
    total_turnos INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ejecucion_id) REFERENCES sa_ejecuciones(ejecucion_id)
);

CREATE TABLE IF NOT EXISTS sa_turnos (
    turno_pk BIGINT AUTO_INCREMENT PRIMARY KEY,
    conversacion_pk BIGINT,
    turno_idx INT NOT NULL,
    speaker VARCHAR(16) NOT NULL,
    text LONGTEXT NOT NULL,
    fase VARCHAR(32) NULL,
    fase_conf DECIMAL(6,4) NULL,
    fase_source VARCHAR(16) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversacion_pk) REFERENCES sa_conversaciones(conversacion_pk),
    INDEX (conversacion_pk, turno_idx)
);
