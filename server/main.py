import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Set, Optional, Any
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE TIEMPO ---
FECHA_FIN = datetime(2026, 1, 1, 16, 0, 0)

class Jugador(BaseModel):
    nombre: str

class Voto(BaseModel):
    eleccion: str
    nombre_jugador: str

class InicioVotacion(BaseModel):
    casilla_id: str
    nombre_jugador: str
    texto: str

conexiones_activas: List[WebSocket] = []
puntuaciones: Dict[str, int] = {} 
jugadores_listos: Set[str] = set()
juego_iniciado = False
meta_victoria: Optional[int] = None 
MIN_JUGADORES = 2 

votos_actuales: Dict[str, str] = {}
estado_voto: Dict[str, Any] = {"casilla_id": None, "autor": None}

async def avisar_a_todos(mensaje: dict):
    for conexion in conexiones_activas:
        try: await conexion.send_json(mensaje)
        except: pass

async def finalizar_votacion():
    global meta_victoria 
    autor = estado_voto["autor"]
    if isinstance(autor, str) and autor in puntuaciones:
        si = list(votos_actuales.values()).count("si")
        no = list(votos_actuales.values()).count("no")
        aprobado = si >= no
        ganador_partida = None
        if aprobado:
            puntuaciones[autor] += 1
            if meta_victoria and puntuaciones[autor] >= meta_victoria:
                ganador_partida = autor
        await avisar_a_todos({
            "tipo": "RESULTADO_FINAL",
            "aprobado": aprobado,
            "casilla_id": estado_voto["casilla_id"],
            "jugador_que_reclamo": autor,
            "puntuaciones": puntuaciones,
            "ganador_partida": ganador_partida
        })
    estado_voto["casilla_id"] = None
    estado_voto["autor"] = None
    votos_actuales.clear()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    conexiones_activas.append(websocket)
    try:
        while True:
            if datetime.now() >= FECHA_FIN:
                await avisar_a_todos({"tipo": "FIN_TIEMPO", "puntuaciones": puntuaciones})
            await websocket.receive_text()
    except WebSocketDisconnect:
        conexiones_activas.remove(websocket)

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    nombre = jugador.nombre
    if juego_iniciado and nombre not in puntuaciones:
        return {"status": "error", "mensaje": "Partida en curso"}
    if nombre not in puntuaciones:
        puntuaciones[nombre] = 0
    await avisar_a_todos({"tipo": "ACTUALIZACION_MARCADOR", "puntuaciones": puntuaciones})
    if len(puntuaciones) >= MIN_JUGADORES and not juego_iniciado:
        juego_iniciado = True
        # La meta es el número de jugadores (n casillas por persona)
        meta_victoria = len(puntuaciones)
        await avisar_a_todos({
            "tipo": "FASE_ESCRITURA", 
            "meta": meta_victoria, 
            "jugadores": list(puntuaciones.keys())
        })
    return {"status": "ok"}

@app.post("/listo-para-jugar")
async def jugador_listo(jugador: Jugador):
    jugadores_listos.add(jugador.nombre)
    if len(jugadores_listos) >= len(puntuaciones):
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(accion: InicioVotacion):
    estado_voto["casilla_id"] = accion.casilla_id
    estado_voto["autor"] = accion.nombre_jugador
    votos_actuales.clear()
    await avisar_a_todos({
        "tipo": "NUEVA_VOTACION", 
        "casilla_id": accion.casilla_id, 
        "nombre": accion.nombre_jugador,
        "texto": accion.texto
    })
    return {"status": "ok"}

@app.post("/votar")
async def registrar_voto(voto: Voto):
    votos_actuales[voto.nombre_jugador] = voto.eleccion
    if len(votos_actuales) >= len(puntuaciones):
        await finalizar_votacion()
    return {"status": "ok"}

@app.post("/reset-total")
async def reset():
    global puntuaciones, jugadores_listos, juego_iniciado, meta_victoria
    puntuaciones.clear()
    jugadores_listos.clear()
    juego_iniciado = False
    meta_victoria = None
    await avisar_a_todos({"tipo": "RESET_GLOBAL"})
    return {"status": "ok"}