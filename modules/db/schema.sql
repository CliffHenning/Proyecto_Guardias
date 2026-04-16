-- =========================
-- TABLA: profesores
-- =========================
CREATE TABLE profesores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    rfid TEXT,
    huella_id TEXT,
    face_id TEXT,
    activo INTEGER DEFAULT 1,
    guardias_acumuladas INTEGER DEFAULT 0,
    guardias_semana INTEGER DEFAULT 0
);

-- =========================
-- TABLA: horarios
-- (qué profesor tiene clase y cuándo)
-- =========================
CREATE TABLE horarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profesor_id INTEGER,
    dia TEXT,              -- ej: 'Lunes'
    hora INTEGER,          -- ej: 1..11, asociado al tramo real via config.describir_hora
    aula TEXT,
    asignatura TEXT,
    FOREIGN KEY (profesor_id) REFERENCES profesores(id)
);

-- =========================
-- TABLA: presencia
-- (registros de entrada/salida)
-- =========================
CREATE TABLE presencia (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profesor_id INTEGER,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    tipo TEXT,   -- 'entrada' o 'salida'
    FOREIGN KEY (profesor_id) REFERENCES profesores(id)
);

-- =========================
-- TABLA: ausencias
-- (detectadas automáticamente o manuales)
-- =========================
CREATE TABLE ausencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profesor_id INTEGER,
    dia TEXT,
    hora INTEGER,
    motivo TEXT,
    FOREIGN KEY (profesor_id) REFERENCES profesores(id)
);

-- =========================
-- TABLA: guardias
-- (resultado del cálculo)
-- =========================
CREATE TABLE guardias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dia TEXT,
    hora INTEGER,
    aula TEXT,
    profesor_asignado INTEGER,
    cubierta INTEGER DEFAULT 0,
    FOREIGN KEY (profesor_asignado) REFERENCES profesores(id)
);