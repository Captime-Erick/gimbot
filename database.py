import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "gimnasio.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS registros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            fecha TEXT,
            grupo TEXT,
            ejercicio TEXT,
            series INTEGER,
            reps INTEGER,
            peso REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Tabla para ejercicios personalizados que el usuario agrega
    c.execute('''
        CREATE TABLE IF NOT EXISTS ejercicios_custom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            grupo TEXT,
            ejercicio TEXT,
            UNIQUE(user_id, grupo, ejercicio)
        )
    ''')
    conn.commit()
    conn.close()

def guardar_registro(user_id, fecha, grupo, ejercicio, series, reps, peso):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO registros (user_id, fecha, grupo, ejercicio, series, reps, peso)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, fecha, grupo, ejercicio, series, reps, peso))
    conn.commit()
    conn.close()

def obtener_ultimo_registro(user_id, ejercicio):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT fecha, series, reps, peso FROM registros
        WHERE user_id = ? AND ejercicio = ?
        ORDER BY fecha DESC, created_at DESC LIMIT 1
    ''', (user_id, ejercicio))
    row = c.fetchone()
    conn.close()
    return row

def obtener_registros_hoy(user_id, fecha):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT ejercicio, series, reps, peso FROM registros
        WHERE user_id = ? AND fecha = ?
        ORDER BY created_at
    ''', (user_id, fecha))
    rows = c.fetchall()
    conn.close()
    return rows

def agregar_ejercicio_custom(user_id, grupo, ejercicio):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO ejercicios_custom (user_id, grupo, ejercicio)
            VALUES (?, ?, ?)
        ''', (user_id, grupo, ejercicio))
        conn.commit()
    finally:
        conn.close()

def obtener_ejercicios_custom(user_id, grupo):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT ejercicio FROM ejercicios_custom
        WHERE user_id = ? AND grupo = ?
    ''', (user_id, grupo))
    rows = [r[0] for r in c.fetchall()]
    conn.close()
    return rows