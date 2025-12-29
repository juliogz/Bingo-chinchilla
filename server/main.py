from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
import asyncio

app = FastAPI()

# Permisos para que la web no se bloquee
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

puntuaciones: Dict[str, int] = {}
jugadores_listos = []
juego_iniciado = False
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
    global juego_iniciado
    nombre = jugador.nombre
    
    if nombre not in puntuaciones:
        puntuaciones[nombre] = 0
    
    # Avisamos a todos que alguien entró para que se actualicen las cajas
    await avisar_a_todos({
        "tipo": "FASE_ESCRITURA", 
        "jugadores": list(puntuaciones.keys())
    })
    
    return {"status": "ok", "jugadores": list(puntuaciones.keys())}

@app.post("/listo-para-jugar")
async def listo_para_jugar(jugador: Jugador):
    if jugador.nombre not in jugadores_listos:
        jugadores_listos.append(jugador.nombre)
    if len(jugadores_listos) >= len(puntuaciones) and len(puntuaciones) > 1:
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(data: dict):
    await avisar_a_todos({"tipo": "NUEVA_VOTACION", "texto": data['texto'], "nombre": data['nombre_jugador']})
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

