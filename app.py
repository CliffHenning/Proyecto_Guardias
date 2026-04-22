from datetime import datetime
import os
import sqlite3
from urllib.parse import urlparse

from flask import Flask, render_template, redirect, request, url_for, flash

from config import describir_hora, describir_horas
from modules.db.db_manager import DBManager
from modules.guardias.motor import MotorGuardias
from modules.presencia.registro import registrar_presencia, obtener_estado_actual, identificar_profesor
from modules.presencia.huella_service import probar_conexion_raspberry

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Necesario para flash messages
app.config.setdefault("DB_PATH", "ies.db")
app.config.setdefault("AUSENCIA_MINUTOS_GRACIA", 10)


def _datos_guardias_vacios(fecha):
    return {
        "fecha": fecha,
        "fecha_texto": _describir_fecha(fecha),
        "fechas_disponibles": [],
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


def _obtener_ahora():
    return datetime.now()


def _obtener_fecha_consulta(valor_fecha=None, ahora=None):
    ahora = ahora or _obtener_ahora()
    if not valor_fecha:
        return ahora.strftime("%Y-%m-%d")

    return datetime.strptime(valor_fecha, "%Y-%m-%d").strftime("%Y-%m-%d")


def _describir_fecha(fecha):
    fecha_dt = datetime.strptime(fecha, "%Y-%m-%d")
    dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    return f"{dias[fecha_dt.weekday()]} {fecha}"


def _obtener_nombre_profesor(db_manager, profesor_id):
    if profesor_id is None:
        return "Sin asignar"

    profesor = db_manager.get_profesor_by_id(profesor_id)
    return profesor.nombre if profesor else f"Profesor {profesor_id}"


def _redireccion_segura(destino, endpoint_fallback="vista_presencia"):
    if destino and destino.startswith("/") and not destino.startswith("//"):
        return redirect(destino)
    return redirect(url_for(endpoint_fallback))


def _obtener_ip_y_puerto_raspberry():
    url_base = os.environ.get("PIFINGER_URL", "http://192.168.208.120:5001")
    parsed = urlparse(url_base)
    host = parsed.hostname or "192.168.208.120"
    port = parsed.port or (443 if parsed.scheme == "https" else 5001)
    return host, port


def _agrupar_candidatos_por_hora(ranking_profesores):
    candidatos_por_hora = {}
    for profesor_disp in ranking_profesores:
        candidatos_por_hora.setdefault(profesor_disp.hora_disponible, []).append({
            "id": profesor_disp.profesor.id,
            "nombre": profesor_disp.profesor.nombre,
            "guardias_semana": profesor_disp.profesor.guardias_semana,
            "guardias_acumuladas": profesor_disp.profesor.guardias_acumuladas,
            "carga_lectiva": getattr(profesor_disp.profesor, "carga_lectiva", 0),
        })
    return candidatos_por_hora


def _agrupar_ranking_por_profesor(ranking_profesores):
    ranking_agrupado = []
    profesores_por_id = {}

    for profesor_disp in ranking_profesores:
        profesor_id = profesor_disp.profesor.id
        profesor_existente = profesores_por_id.get(profesor_id)

        if profesor_existente is None:
            profesor_existente = {
                "nombre": profesor_disp.profesor.nombre,
                "guardias_semana": profesor_disp.profesor.guardias_semana,
                "guardias_acumuladas": profesor_disp.profesor.guardias_acumuladas,
                "carga_lectiva": getattr(profesor_disp.profesor, "carga_lectiva", 0),
                "horas_disponibles": [],
            }
            profesores_por_id[profesor_id] = profesor_existente
            ranking_agrupado.append(profesor_existente)

        if profesor_disp.hora_disponible not in profesor_existente["horas_disponibles"]:
            profesor_existente["horas_disponibles"].append(profesor_disp.hora_disponible)

    for posicion, profesor in enumerate(ranking_agrupado, start=1):
        profesor["posicion"] = posicion
        profesor["horas_disponibles"].sort()
        profesor["horas_disponibles_texto"] = describir_horas(profesor["horas_disponibles"])

    return ranking_agrupado


def obtener_datos_guardias(db_path=None, dia=None, ahora=None):
    ahora = ahora or _obtener_ahora()
    fecha = _obtener_fecha_consulta(dia, ahora=ahora)
    db_path = db_path or _obtener_db_path()

    try:
        motor = MotorGuardias(db_path=db_path)
        if fecha == ahora.strftime("%Y-%m-%d"):
            motor.detectar_ausencias_automaticas(
                ahora=ahora,
                margen_minutos=app.config.get("AUSENCIA_MINUTOS_GRACIA", 10),
            )
        db_manager = motor.db_manager
        resultado = motor.calcular_guardias(dia=fecha)
        guardias_persistidas = db_manager.get_guardias_by_dia(fecha)
        fechas_disponibles = db_manager.get_fechas_con_ausencias()
    except (sqlite3.Error, ValueError):
        return _datos_guardias_vacios(fecha)

    candidatos_por_hora = _agrupar_candidatos_por_hora(resultado["ranking_profesores"])

    ranking_profesores = _agrupar_ranking_por_profesor(resultado["ranking_profesores"])

    guardias = []
    for guardia in guardias_persistidas:
        guardia_registrada = guardia.cubierta == 1
        profesor_asignado_id = guardia.profesor_cubre_id if guardia_registrada else None
        guardias.append({
            "dia": guardia.dia,
            "hora": guardia.hora,
            "hora_texto": describir_hora(guardia.hora),
            "aula": guardia.aula,
            "asignatura": guardia.asignatura or "Sin asignatura",
            "profesor_ausente_id": guardia.profesor_ausente_id,
            "profesor_asignado_id": profesor_asignado_id,
            "profesor_ausente": _obtener_nombre_profesor(db_manager, guardia.profesor_ausente_id),
            "profesor_asignado": _obtener_nombre_profesor(db_manager, profesor_asignado_id),
            "estado": "Registrada" if guardia_registrada else "Calculada",
            "registrada": guardia_registrada,
            "candidatos": candidatos_por_hora.get(guardia.hora, []),
        })

    return {
        "fecha": fecha,
        "fecha_texto": _describir_fecha(fecha),
        "fechas_disponibles": fechas_disponibles,
        "resumen": {
            "ausencias_detectadas": len(guardias),
            "guardias_necesarias": len(guardias),
            "guardias_cubiertas": sum(1 for guardia in guardias if guardia["registrada"]),
        },
        "ranking_profesores": ranking_profesores,
        "guardias": guardias,
    }

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/guardias")
def vista_guardias():
    fecha = request.args.get("fecha")
    try:
        datos_guardias = obtener_datos_guardias(dia=fecha)
    except ValueError:
        flash("Fecha no válida", "error")
        return redirect(url_for("vista_guardias"))
    return render_template("guardias.html", datos=datos_guardias)


@app.route("/guardias/registrar", methods=["POST"])
def registrar_guardia():
    db_path = _obtener_db_path()
    dia = request.form.get("dia")
    hora = request.form.get("hora", type=int)
    aula = request.form.get("aula")
    asignatura = request.form.get("asignatura")
    profesor_ausente_id = request.form.get("profesor_ausente_id", type=int)
    profesor_asignado = request.form.get("profesor_asignado", type=int)

    if not dia or hora is None or not aula or profesor_asignado is None:
        flash("Datos incompletos para registrar la guardia", "error")
        return redirect(url_for("vista_guardias", fecha=dia))

    try:
        db_manager = DBManager(db_path)
        registrado = db_manager.registrar_guardia_realizada(
            dia,
            hora,
            aula,
            profesor_asignado,
            asignatura=asignatura,
            profesor_ausente_id=profesor_ausente_id,
        )
        if registrado:
            flash("Guardia registrada correctamente", "success")
        else:
            flash("La guardia ya estaba registrada", "error")
    except sqlite3.Error as e:
        flash(f"Error al registrar la guardia: {str(e)}", "error")

    return redirect(url_for("vista_guardias", fecha=dia))


@app.route("/guardias/registrar-huella", methods=["POST"])
def registrar_huella_guardias():
    fecha = request.form.get("fecha")
    ip_raspberry, puerto_raspberry = _obtener_ip_y_puerto_raspberry()

    if not probar_conexion_raspberry(ip=ip_raspberry, port=puerto_raspberry, timeout=10):
        flash(
            f"No hay conexión con Raspberry Pi ({ip_raspberry}:{puerto_raspberry}).",
            "error",
        )
        return redirect(url_for("vista_guardias", fecha=fecha))

    try:
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

    return redirect(url_for("vista_guardias", fecha=fecha))

@app.route("/presencia")
def vista_presencia():
    estado = obtener_estado_actual(_obtener_db_path())
    return render_template("presencia.html", estado=estado)

@app.route("/presencia/registrar", methods=["POST"])
def registrar():
    destino = request.form.get("next") or request.args.get("next")
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

    return _redireccion_segura(destino, endpoint_fallback="vista_presencia")

if __name__ == "__main__":
    app.run(debug=True)