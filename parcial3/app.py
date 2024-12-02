from flask import Flask, request, jsonify, render_template
from datetime import datetime
import firebase_admin
from firebase_admin import credentials, db
import random

# Inicializar Firebase con las credenciales y URL de la base de datos Realtime Database
cred = credentials.Certificate("cultivo-46d9e-firebase-adminsdk-n6rhv-9441769c10.json")  # Archivo de credenciales
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://cultivo-46d9e-default-rtdb.firebaseio.com/'  # URL de la base de datos
})

# Crear la aplicación Flask
app = Flask(__name__)

# Identificador único del sensor
ID_SENSOR = "AJG1988"

# Rango de temperatura ideal para el invernadero
RANGO_TEMP_IDEAL = (18, 25)  # Entre 18°C y 25°C

# Función para simular la temperatura
def simular_temperatura():
    # Generar una temperatura aleatoria dentro o fuera del rango ideal
    if random.random() < 0.5:
        temperatura = random.uniform(0, RANGO_TEMP_IDEAL[0] - 2)  # Valor menor al mínimo ideal
    else:
        temperatura = random.uniform(RANGO_TEMP_IDEAL[0], RANGO_TEMP_IDEAL[1])  # Valor dentro del rango ideal
    
    temperatura = round(temperatura, 2)  # Redondear a 2 decimales

    # Determinar si es necesario abrir o cerrar las cortinas
    if temperatura < RANGO_TEMP_IDEAL[0]:
        accion_cortinas = "Cerrar"  # Si está por debajo del rango, cerramos las cortinas para mantener el calor
    elif temperatura > RANGO_TEMP_IDEAL[1]:
        accion_cortinas = "Abrir"  # Si está por encima del rango, abrimos las cortinas para dejar entrar aire fresco
    else:
        accion_cortinas = "Mantener"  # Si está dentro del rango, mantenemos las cortinas tal como están

    return {
        "temperatura": temperatura,
        "accion_cortinas": accion_cortinas
    }

# Ruta para generar datos automáticamente y enviarlos a Firebase
@app.route('/api/generar-temperatura', methods=['POST'])
def generar_temperatura():
    try:
        # Simular datos del sensor de temperatura
        datos = simular_temperatura()

        # Agregar metadatos y guardar en Firebase
        datos["idsensor"] = ID_SENSOR
        datos["fecha"] = datetime.now().strftime("%Y-%m-%d")
        datos["hora"] = datetime.now().strftime("%H:%M:%S")
        ref = db.reference('temperatura')
        ref.push(datos)  # Guardar datos en la base de datos

        return jsonify({
            "mensaje": "Datos de temperatura generados y enviados correctamente",
            "datos": datos
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Ruta principal para la página web
@app.route('/')
def home():
    return render_template('index.html')

# Ruta para recibir y guardar datos de temperatura
@app.route('/api/temperatura', methods=['POST', 'GET'])
def temperatura():
    if request.method == 'POST':
        try:
            # Procesar datos enviados desde el cliente
            data = request.json
            temperatura = data.get("temperatura")
            accion_cortinas = data.get("accion_cortinas")

            # Validar datos obligatorios
            if temperatura is None or not accion_cortinas:
                return jsonify({"error": "Datos incompletos"}), 400

            # Crear registro con metadatos
            fecha_actual = datetime.now().strftime("%Y-%m-%d")
            hora_actual = datetime.now().strftime("%H:%M:%S")

            registro = {
                "fecha": fecha_actual,
                "hora": hora_actual,
                "idsensor": ID_SENSOR,
                "temperatura": temperatura,
                "accion_cortinas": accion_cortinas
            }

            # Guardar el registro en Firebase
            ref = db.reference('temperatura')
            ref.push(registro)

            return jsonify({
                "mensaje": "Datos de temperatura recibidos correctamente",
                "registro": registro
            }), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

    elif request.method == 'GET':
        try:
            # Filtrar datos por sensor y fecha
            idsensor = request.args.get('idsensor')
            fecha = request.args.get('fecha')

            if not idsensor or not fecha:
                return jsonify({"error": "Faltan parámetros: idsensor o fecha"}), 400

            ref = db.reference('temperatura')
            datos = ref.order_by_child('idsensor').equal_to(idsensor).get()

            if datos is None:
                return jsonify({"error": "No se encontraron datos para el sensor especificado."}), 404

            # Filtrar datos por los criterios especificados
            resultados = [
                v for v in datos.values()
                if v['fecha'] == fecha
            ]

            if not resultados:
                return jsonify({"error": "No se encontraron registros para los criterios especificados."}), 404

            return jsonify(resultados), 200

        except Exception as e:
            return jsonify({"error": str(e)}), 500

# Ruta para obtener las fechas disponibles de un sensor
@app.route('/api/fechas-temperatura', methods=['GET'])
def obtener_fechas_temperatura():
    try:
        idsensor = request.args.get('idsensor')
        if not idsensor:
            return jsonify({"error": "ID del Sensor no proporcionado"}), 400

        ref = db.reference('temperatura')
        registros = ref.order_by_child('idsensor').equal_to(idsensor).get()

        if registros is None:
            return jsonify({"error": "No se encontraron registros para el sensor especificado."}), 404

        # Extraer fechas únicas de los registros
        fechas = list({registro['fecha'] for registro in registros.values()})

        return jsonify(fechas), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Inicializar datos para el sensor de temperatura si no hay suficientes registros en la base de datos
def inicializar_datos_temperatura():
    ref = db.reference('temperatura')

    # Recuperar datos existentes
    datos_existentes = ref.get() or {}

    # Contar la cantidad de registros por sensor
    conteo_por_sensor = {ID_SENSOR: 0}
    for dato in datos_existentes.values():
        sensor = dato.get('idsensor')
        if sensor == ID_SENSOR:
            conteo_por_sensor[ID_SENSOR] += 1

    # Generar datos faltantes para el sensor de temperatura
    for sensor, conteo in conteo_por_sensor.items():
        if conteo < 6:
            print(f"Creando datos para el sensor: {sensor} (Faltan {6 - conteo} datos)")
            for _ in range(6 - conteo):
                datos = simular_temperatura()
                datos["idsensor"] = ID_SENSOR
                datos["fecha"] = datetime.now().strftime("%Y-%m-%d")
                datos["hora"] = datetime.now().strftime("%H:%M:%S")
                ref.push(datos)

    print("Inicialización completada: Datos generados para el sensor de temperatura.")

# Ejecutar la aplicación Flask
if __name__ == '__main__':
    inicializar_datos_temperatura()  # Asegurar que haya datos iniciales en Firebase
    app.run(debug=True)