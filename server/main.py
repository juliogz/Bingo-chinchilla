from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio

app = FastAPI()

# Configuración de CORS para evitar errores de conexión
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DEL JUEGO ---
MIN_JUGADORES = 8  # Cambia a 2 para tus pruebas locales
# ------------------------------

puntuaciones: Dict[str, int] = {}
jugadores_listos = []
juego_iniciado = False
meta_victoria = 0
frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}
votos_actuales = {"si": 0, "no": 0, "votantes": []}
websockets: List[WebSocket] = []

class Jugador(BaseModel):
    nombre: str

async def avisar_a_todos(data: dict):
    for ws in websockets:
        try:
            await ws.send_json(data)
        except:
            if ws in websockets:
                websockets.remove(ws)

@app.get("/")
def home():
    return {"status": "online", "jugadores": list(puntuaciones.keys())}

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    nombre = jugador.nombre
    
    if nombre not in puntuaciones:
        puntuaciones[nombre] = 0
    
    # Si se alcanza el mínimo, cerramos la entrada y avisamos a todos
    if len(puntuaciones) >= MIN_JUGADORES:
        juego_iniciado = True
        meta_victoria = len(puntuaciones)
        await avisar_a_todos({
            "tipo": "FASE_ESCRITURA", 
            "jugadores": list(puntuaciones.keys())
        })
        return {"status": "ok", "jugadores": list(puntuaciones.keys()), "empezar": True}
    
    # Si no, informamos del progreso para el lobby de espera
    return {"status": "ok", "jugadores": list(puntuaciones.keys()), "empezar": False}

@app.post("/listo-para-jugar")
async def listo_para_jugar(jugador: Jugador):
    if jugador.nombre not in jugadores_listos:
        jugadores_listos.append(jugador.nombre)
    
    if len(jugadores_listos) >= len(puntuaciones) and len(puntuaciones) >= MIN_JUGADORES:
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(data: dict):
    global frase_actual, votos_actuales
    frase_actual = {
        "texto": data['texto'], 
        "nombre": data['nombre_jugador'], 
        "casilla_id": data['casilla_id']
    }
    votos_actuales = {"si": 0, "no": 0, "votantes": []}
    await avisar_a_todos({
        "tipo": "NUEVA_VOTACION", 
        "texto": data['texto'], 
        "nombre": data['nombre_jugador']
    })
    return {"status": "ok"}

@app.post("/votar")
async def votar(data: dict):
    global votos_actuales
    nombre_vota = data['nombre_jugador']
    eleccion = data['eleccion']
    
    if nombre_vota not in votos_actuales["votantes"]:
        votos_actuales[eleccion] += 1
        votos_actuales["votantes"].append(nombre_vota)
    
    # La votación termina cuando todos (menos el que reclama) han votado
    if len(votos_actuales["votantes"]) >= (len(puntuaciones) - 1):
        aprobado = votos_actuales["si"] > votos_actuales["no"]
        if aprobado:
            puntuaciones[frase_actual["nombre"]] += 1
        
        ganador_partida = None
        if puntuaciones[frase_actual["nombre"]] >= meta_victoria:
            ganador_partida = frase_actual["nombre"]

        await avisar_a_todos({
            "tipo": "RESULTADO_FINAL",
            "aprobado": aprobado,
            "puntuaciones": puntuaciones,
            "jugador_que_reclamo": frase_actual["nombre"],
            "casilla_id": frase_actual["casilla_id"],
            "ganador_partida": ganador_partida
        })
    return {"status": "ok"}

@app.post("/reset-total")
async def reset_total():
    global puntuaciones, jugadores_listos, juego_iniciado
    puntuaciones = {}
    jugadores_listos = []
    juego_iniciado = False
    await avisar_a_todos({"tipo": "RESET_GLOBAL"})
    return {"status": "ok"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    websockets.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websockets:
            websockets.remove(websocket)

