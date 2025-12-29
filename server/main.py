from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict
import asyncio
import json

app = FastAPI()

# --- CONFIGURACIÓN ---
MIN_JUGADORES = 2  # <--- ¡CAMBIA ESTO AL TOTAL DE PERSONAS QUE SERÉIS!
# ---------------------

jugadores = []
puntuaciones: Dict[str, int] = {}
jugadores_listos = []
juego_iniciado = False
meta_victoria = 0
frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}
votos_actuales = {"si": 0, "no": 0, "votantes": []}
websockets: List[WebSocket] = []

class Jugador(BaseModel):
    nombre: str

class Voto(BaseModel):
    eleccion: str
    nombre_jugador: str

class Reclamo(BaseModel):
    casilla_id: str
    nombre_jugador: str
    texto: str

async def avisar_a_todos(data: dict):
    for ws in websockets:
        try:
            await ws.send_json(data)
        except:
            websockets.remove(ws)

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    nombre = jugador.nombre
    
    # Cerrojazo: si ya llegamos al número o el juego ya arrancó
    if (len(puntuaciones) >= MIN_JUGADORES or juego_iniciado) and nombre not in puntuaciones:
        return {"status": "error", "mensaje": "La sala está llena o la partida ya comenzó"}

    if nombre not in puntuaciones:
        puntuaciones[nombre] = 0
    
    await avisar_a_todos({"tipo": "ACTUALIZACION_MARCADOR", "puntuaciones": puntuaciones})
    
    # Si con este nuevo llegamos al mínimo, activamos la fase de escritura
    if len(puntuaciones) >= MIN_JUGADORES:
        juego_iniciado = True
        meta_victoria = len(puntuaciones)
        await avisar_a_todos({
            "tipo": "FASE_ESCRITURA", 
            "meta": meta_victoria, 
            "jugadores": list(puntuaciones.keys())
        })
        
    return {"status": "ok"}

@app.post("/listo-para-jugar")
async def listo_para_jugar(jugador: Jugador):
    if jugador.nombre not in jugadores_listos:
        jugadores_listos.append(jugador.nombre)
    
    if len(jugadores_listos) >= len(puntuaciones):
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(reclamo: Reclamo):
    global frase_actual, votos_actuales
    frase_actual = {"texto": reclamo.texto, "nombre": reclamo.nombre_jugador, "casilla_id": reclamo.casilla_id}
    votos_actuales = {"si": 0, "no": 0, "votantes": []}
    await avisar_a_todos({"tipo": "NUEVA_VOTACION", "texto": reclamo.texto, "nombre": reclamo.nombre_jugador})
    return {"status": "ok"}

@app.post("/votar")
async def votar(voto: Voto):
    global votos_actuales
    if voto.nombre_jugador not in votos_actuales["votantes"]:
        votos_actuales[voto.eleccion] += 1
        votos_actuales["votantes"].append(voto.nombre_jugador)
    
    # Se cierra la votación cuando todos (menos el que reclama) votan
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
    global puntuaciones, jugadores_listos, juego_iniciado, websockets
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
