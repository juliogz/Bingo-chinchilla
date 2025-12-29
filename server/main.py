from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN ---
MIN_JUGADORES = 2  
# ---------------------

puntuaciones: Dict[str, int] = {}
jugadores_listos = [] # Nombres de quienes ya enviaron sus frases
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

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    nombre = jugador.nombre
    
    if nombre not in puntuaciones:
        puntuaciones[nombre] = 0
    
    lista_jugadores = list(puntuaciones.keys())
    
    # Si el juego ya arrancó (fase tablero), mandamos directo al tablero
    fase = "ESPERA"
    if len(jugadores_listos) >= len(puntuaciones) and len(puntuaciones) >= MIN_JUGADORES:
        fase = "TABLERO"
    elif len(puntuaciones) >= MIN_JUGADORES:
        fase = "ESCRITURA"

    if len(puntuaciones) >= MIN_JUGADORES and not juego_iniciado:
        juego_iniciado = True
        meta_victoria = len(puntuaciones)
        await avisar_a_todos({"tipo": "FASE_ESCRITURA", "jugadores": lista_jugadores})

    await avisar_a_todos({
        "tipo": "ACTUALIZACION_LOBBY",
        "jugadores": lista_jugadores,
        "total_necesario": MIN_JUGADORES
    })
    
    return {
        "status": "ok", 
        "jugadores": lista_jugadores, 
        "fase": fase,
        "ya_listo": nombre in jugadores_listos
    }

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
    frase_actual = {"texto": data['texto'], "nombre": data['nombre_jugador'], "casilla_id": data['casilla_id']}
    votos_actuales = {"si": 0, "no": 0, "votantes": []}
    await avisar_a_todos({"tipo": "NUEVA_VOTACION", "texto": data['texto'], "nombre": data['nombre_jugador']})
    return {"status": "ok"}

@app.post("/votar")
async def votar(data: dict):
    global votos_actuales
    if data['nombre_jugador'] not in votos_actuales["votantes"]:
        votos_actuales[data['eleccion']] += 1
        votos_actuales["votantes"].append(data['nombre_jugador'])
    
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
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in websockets: websockets.remove(websocket)



