from datetime import datetime
import os
import sqlite3
from urllib.parse import urlparse

from flask import Flask, render_template, redirect, request, url_for, flash, jsonify, Blueprint
from config import describir_hora, describir_horas
from modules.db.db_manager import DBManager
from modules.guardias.motor import MotorGuardias
from modules.presencia.registro import registrar_presencia, obtener_estado_actual
from modules.presencia.huella_service import (
    identificar_huella,
    probar_conexion_raspberry,
    registrar_huella_profesor,
)


app = Flask(__name__)
bp = Blueprint("presencia", __name__, url_prefix="/presencia")
app.secret_key = 'your_secret_key'  # Necesario para flash messages
app.config.setdefault("DB_PATH", "ies.db")
app.config.setdefault("AUSENCIA_MINUTOS_GRACIA", 10)
app.config.setdefault("AUSENCIA_HORA_CORTE", "16:00")


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

@bp.route("/")
def vista_presencia():
    try:
        estado = obtener_estado_actual()

        db = DBManager(_obtener_db_path())
        profesores = db.get_profesores()
        profesores = [p for p in profesores if p.activo == 1]

    except Exception as e:
        print(f"[ERROR estado presencia] {e}")
        estado = {}
        profesores = []

    return render_template(
        "presencia.html",
        estado=estado,
        profesores=profesores
    )

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
                hora_corte_global=app.config.get("AUSENCIA_HORA_CORTE", "16:00"),
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


def obtener_datos_horario(fecha=None, db_path=None):
    """Obtiene datos para mostrar el horario del día con ausencias."""
    ahora = _obtener_ahora()
    fecha = fecha or ahora.strftime("%Y-%m-%d")
    db_path = db_path or _obtener_db_path()

    try:
        db_manager = DBManager(db_path)
        dia_semana = datetime.strptime(fecha, "%Y-%m-%d").weekday()  # 0=Lunes, 6=Domingo

        # Obtener profesores activos
        profesores = db_manager.get_profesores()
        profesores_activos = [p for p in profesores if p.activo == 1]

        # Obtener horas del día
        horas = list(range(1, 12))  # Horas 1-11

        # Obtener horarios del día
        horarios_dia = db_manager.get_horarios_by_dia(dia_semana)

        # Obtener presencias y ausencias del día
        presencias = db_manager.get_presencias_by_fecha(fecha)
        ausencias = db_manager.get_ausencias_by_fecha(fecha)

        # Crear mapa de ausencias por profesor y hora
        ausencias_map = {}
        for ausencia in ausencias:
            ausencias_map[(ausencia.profesor_id, ausencia.hora)] = ausencia.motivo or "Ausencia registrada"

        # Crear mapa de presencias por profesor
        presencias_map = {}
        for presencia in presencias:
            if presencia.profesor_id not in presencias_map:
                presencias_map[presencia.profesor_id] = []
            presencias_map[presencia.profesor_id].append(presencia)

        # Determinar estado de cada profesor en cada hora
        celdas = {}
        ausencias_totales = 0
        for profesor in profesores_activos:
            profesor_id = profesor.id
            celdas[profesor_id] = {}

            # Última presencia del día
            presencias_profesor = sorted(
                presencias_map.get(profesor_id, []),
                key=lambda p: p.timestamp
            )
            ultima_presencia = presencias_profesor[-1] if presencias_profesor else None
            presente_hoy = ultima_presencia and ultima_presencia.tipo == 'entrada'

            for hora in horas:
                horario = None
                for h in horarios_dia:
                    if h.profesor_id == profesor_id and h.hora == hora:
                        horario = h
                        break

                if horario:
                    ausente = (profesor_id, hora) in ausencias_map
                    if ausente:
                        ausencias_totales += 1
                        motivo = ausencias_map[(profesor_id, hora)]
                    else:
                        motivo = ""

                    celdas[profesor_id][hora] = {
                        "tiene_horario": True,
                        "tipo": horario.tipo_guardia or "clase",
                        "asignatura": horario.asignatura or "Sin asignatura",
                        "aula": horario.aula or "Sin aula",
                        "ausente": ausente,
                        "motivo": motivo,
                    }
                else:
                    celdas[profesor_id][hora] = {
                        "tiene_horario": False,
                        "tipo": "",
                        "asignatura": "",
                        "aula": "",
                        "ausente": False,
                        "motivo": "",
                    }

        # Preparar lista de profesores para la vista
        profesores_lista = [{
            "id": p.id,
            "nombre": p.nombre,
            "departamento": getattr(p, 'departamento', 'Sin departamento')
        } for p in profesores_activos]

        # Preparar lista de horas
        horas_lista = [{
            "hora": h,
            "hora_texto": describir_hora(h)
        } for h in horas]

        return {
            "fecha": fecha,
            "fecha_texto": _describir_fecha(fecha),
            "dia_semana": ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"][dia_semana],
            "profesores": profesores_lista,
            "horas": horas_lista,
            "celdas": celdas,
            "ausencias_totales": ausencias_totales,
        }

    except Exception as e:
        # En caso de error, devolver datos vacíos
        return {
            "fecha": fecha,
            "fecha_texto": _describir_fecha(fecha),
            "dia_semana": "Desconocido",
            "profesores": [],
            "horas": [],
            "celdas": {},
            "ausencias_totales": 0,
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


@bp.route("/confirmar-presencia-huella", methods=["POST"])
def confirmar_presencia_huella():
    db = DBManager(_obtener_db_path())

    print("[HUELLA] Confirmando presencia automática...")

    # 1. detectar huella desde sensor
    huella_id = identificar_huella(db_path=_obtener_db_path())

    if huella_id is None:
        return jsonify({
            "ok": False,
            "mensaje": "No se detectó ninguna huella"
        }), 400

    print(f"[HUELLA] ID detectado: {huella_id}")

    # 2. buscar profesor por huella
    profesor = db.get_profesor_por_huella_id(huella_id)

    if profesor is None:
        return jsonify({
            "ok": False,
            "mensaje": f"Huella no registrada ({huella_id})"
        }), 404

    print(f"[HUELLA] Profesor encontrado: {profesor.nombre}")

    # 3. registrar presencia automáticamente
    tipo = registrar_presencia(profesor.id, db_path=_obtener_db_path())

    print(f"[HUELLA] Presencia registrada correctamente: {tipo}")

    # 4. respuesta final
    return jsonify({
        "ok": True,
        "tipo": tipo,
        "nombre": profesor.nombre,
        "profesor_id": profesor.id,
        "huella_id": huella_id,
        "mensaje": f"{profesor.nombre}: {'presente' if tipo == 'entrada' else 'ausente'}"
    })

@bp.route("/enrolar", methods=["POST"])
def enrolar_huella_profesor():
    profesor_id = request.form.get("profesor_id", type=int)

    if profesor_id is None:
        return jsonify({
            "ok": False,
            "message": "Profesor no seleccionado"
        }), 400

    try:
        ok, mensaje, huella_id = registrar_huella_profesor(
            profesor_id,
            db_path=_obtener_db_path()
        )

        return jsonify({
            "ok": ok,
            "message": mensaje,
            "huella_id": huella_id
        })

    except Exception as e:
        return jsonify({
            "ok": False,
            "message": str(e)
        }), 500

@app.route("/presencia/borrar-huella-bd", methods=["POST"])
def borrar_huella_bd_route():
    destino = request.form.get("next") or request.args.get("next")
    profesor_id = request.form.get("profesor_id", type=int)
    if profesor_id is None:
        flash("Selecciona un profesor", "error")
        return _redireccion_segura(destino, endpoint_fallback="vista_presencia")
    try:
        db_manager = DBManager(_obtener_db_path())
        actualizados = db_manager.set_profesor_huella_id(profesor_id, None)
        if actualizados >= 1:
            flash("Huella eliminada de la base de datos", "success")
        else:
            flash("No se encontró el profesor", "error")
    except Exception as e:
        flash(f"Error al borrar huella de la BD: {e}", "error")
    return _redireccion_segura(destino, endpoint_fallback="vista_presencia")


@app.route("/horario")
def vista_horario():
    fecha = request.args.get("fecha")
    datos_horario = obtener_datos_horario(fecha=fecha)
    return render_template("horario.html", datos=datos_horario)


app.register_blueprint(bp)

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
