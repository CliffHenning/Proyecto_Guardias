from flask import Flask, render_template, request, redirect, url_for, flash
from modules.presencia.registro import registrar_presencia, obtener_estado_actual, identificar_profesor

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necesario para flash messages

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardias")
def vista_guardias():
    return render_template("guardias.html")

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