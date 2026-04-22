-- =========================
-- TABLA: profesores
-- =========================
CREATE TABLE IF NOT EXISTS profesores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre TEXT NOT NULL,
    departamento TEXT,
    huella_id INTEGER,
    activo INTEGER DEFAULT 1,
    guardias_acumuladas INTEGER DEFAULT 0,
    guardias_semana INTEGER DEFAULT 0
);

-- =========================
-- TABLA: horarios
-- (qué profesor tiene clase y cuándo)
-- =========================
CREATE TABLE IF NOT EXISTS horarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profesor_id INTEGER,
    dia TEXT,
    hora INTEGER,
    tipo TEXT DEFAULT 'clase',
    aula TEXT,
    asignatura TEXT,
    FOREIGN KEY (profesor_id) REFERENCES profesores(id)
);

-- =========================
-- TABLA: presencia
-- (registros de entrada/salida)
-- =========================
CREATE TABLE IF NOT EXISTS presencia (
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
CREATE TABLE IF NOT EXISTS ausencias (
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
CREATE TABLE IF NOT EXISTS guardias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dia TEXT,
    hora INTEGER,
    aula TEXT,
    asignatura TEXT,
    id_profesor_ausente INTEGER,
    id_profesor_cubre INTEGER,
    cubierta INTEGER DEFAULT 0,
    FOREIGN KEY (id_profesor_ausente) REFERENCES profesores(id),
    FOREIGN KEY (id_profesor_cubre) REFERENCES profesores(id)
);