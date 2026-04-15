from flask import Flask, render_template, request, redirect, url_for, flash
from modules.presencia.registro import registrar_presencia, obtener_estado_actual, identificar_profesor

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necesario para flash messages


def obtener_guardias_ejemplo():
    """Devuelve datos de ejemplo para la vista de guardias mientras se integra el motor real."""
    return {
        "fecha": "2026-04-10",
        "resumen": {
            "ausencias_detectadas": 2,
            "guardias_necesarias": 2,
            "guardias_cubiertas": 2,
        },
        "ranking_profesores": [
            {
                "posicion": 1,
                "nombre": "Ana Garcia",
                "hora_disponible": 1,
                "guardias_semana": 0,
                "guardias_acumuladas": 1,
                "carga_lectiva": 15,
            },
            {
                "posicion": 2,
                "nombre": "Luis Perez",
                "hora_disponible": 2,
                "guardias_semana": 1,
                "guardias_acumuladas": 3,
                "carga_lectiva": 17,
            },
            {
                "posicion": 3,
                "nombre": "Maria Lopez",
                "hora_disponible": 3,
                "guardias_semana": 1,
                "guardias_acumuladas": 4,
                "carga_lectiva": 18,
            },
        ],
        "guardias": [
            {
                "dia": "Viernes",
                "hora": 1,
                "aula": "A101",
                "profesor_ausente": "Profesor de Matematicas",
                "profesor_asignado": "Ana Garcia",
                "estado": "Cubierta",
            },
            {
                "dia": "Viernes",
                "hora": 2,
                "aula": "B203",
                "profesor_ausente": "Profesor de Lengua",
                "profesor_asignado": "Luis Perez",
                "estado": "Cubierta",
            },
        ],
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardias")
def vista_guardias():
    datos_guardias = obtener_guardias_ejemplo()
    return render_template("guardias.html", datos=datos_guardias)

@app.route("/presencia")
def vista_presencia():
    estado = obtener_estado_actual()
    return render_template("presencia.html", estado=estado)

@app.route("/presencia/registrar", methods=["POST"])
def registrar():
    try:
        profesor_id = identificar_profesor()
        if profesor_id:
            tipo = registrar_presencia(profesor_id)
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