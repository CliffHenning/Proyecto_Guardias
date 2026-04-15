from datetime import datetime
import sqlite3

from flask import Flask, render_template, redirect, request, url_for, flash

from modules.db.db_manager import DBManager
from modules.guardias.motor import MotorGuardias
from modules.presencia.registro import registrar_presencia, obtener_estado_actual, identificar_profesor

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necesario para flash messages
app.config.setdefault("DB_PATH", "ies.db")


def _datos_guardias_vacios(fecha):
    return {
        "fecha": fecha,
        "resumen": {
            "ausencias_detectadas": 0,
            "guardias_necesarias": 0,
            "guardias_cubiertas": 0,
        },
        "ranking_profesores": [],
        "guardias": [],
    }


def _obtener_db_path():
    return app.config.get("DB_PATH", "ies.db")


def _obtener_nombre_profesor(db_manager, profesor_id):
    if profesor_id is None:
        return "Sin asignar"

    profesor = db_manager.get_profesor_by_id(profesor_id)
    return profesor.nombre if profesor else f"Profesor {profesor_id}"


def obtener_datos_guardias(db_path=None, dia=None):
    fecha = dia or datetime.now().strftime("%Y-%m-%d")
    db_path = db_path or _obtener_db_path()

    try:
        motor = MotorGuardias(db_path=db_path)
        resultado = motor.calcular_guardias(dia=fecha)
        db_manager = motor.db_manager
    except (sqlite3.Error, ValueError):
        return _datos_guardias_vacios(fecha)

    ranking_profesores = []
    for posicion, profesor_disp in enumerate(resultado["ranking_profesores"], start=1):
        ranking_profesores.append({
            "posicion": posicion,
            "nombre": profesor_disp.profesor.nombre,
            "hora_disponible": profesor_disp.hora_disponible,
            "guardias_semana": profesor_disp.profesor.guardias_semana,
            "guardias_acumuladas": profesor_disp.profesor.guardias_acumuladas,
            "carga_lectiva": getattr(profesor_disp.profesor, "carga_lectiva", 0),
        })

    guardias = []
    for guardia in resultado["guardias"]:
        guardias.append({
            "dia": guardia.dia,
            "hora": guardia.hora,
            "aula": guardia.aula,
            "profesor_ausente": _obtener_nombre_profesor(db_manager, guardia.profesor_ausente_id),
            "profesor_asignado": _obtener_nombre_profesor(db_manager, guardia.profesor_asignado),
            "estado": "Cubierta" if guardia.esta_cubierta() else "Pendiente",
        })

    return {
        "fecha": fecha,
        "resumen": {
            "ausencias_detectadas": len(guardias),
            "guardias_necesarias": len(guardias),
            "guardias_cubiertas": sum(1 for guardia in resultado["guardias"] if guardia.esta_cubierta()),
        },
        "ranking_profesores": ranking_profesores,
        "guardias": guardias,
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardias")
def vista_guardias():
    datos_guardias = obtener_datos_guardias()
    return render_template("guardias.html", datos=datos_guardias)

@app.route("/presencia")
def vista_presencia():
    estado = obtener_estado_actual(_obtener_db_path())
    return render_template("presencia.html", estado=estado)

@app.route("/presencia/registrar", methods=["POST"])
def registrar():
    try:
        profesor_id = request.form.get("profesor_id", type=int)
        if profesor_id is None:
            profesor_id = identificar_profesor()
        if profesor_id:
            tipo = registrar_presencia(profesor_id, _obtener_db_path())
            flash(f"Registro de {tipo} exitoso", "success")
        else:
            flash("Profesor no identificado", "error")
    except ValueError as e:
        flash(str(e), "error")
    except Exception as e:
        flash(f"Error al registrar presencia: {str(e)}", "error")

    return redirect(url_for("vista_presencia"))

if __name__ == "__main__":
    app.run(debug=True)