import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
from supabase import create_client, Client

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CLASES DE DATOS ---
class Jugador(BaseModel):
    nombre: str

# --- CONEXIÓN SUPABASE ---
URL: str = os.environ.get("SUPABASE_URL", "")
KEY: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(URL, KEY)

# --- ESTADO GLOBAL ---
MIN_JUGADORES = 7
TIEMPO_VOTO = 900
puntuaciones: Dict[str, int] = {}
jugadores_listos = [] 
juego_iniciado = False
meta_victoria = 0
frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}
votos_actuales = {"si": 0, "no": 0, "votantes": []}
websockets: List[WebSocket] = []
tarea_temporizador = None

@app.on_event("startup")
async def startup_event():
    global puntuaciones
    try:
        res = supabase.table("partida").select("*").execute()
        if res.data:
            for fila in res.data:
                puntuaciones[fila["nombre"]] = fila["puntos"]
    except Exception as e:
        print(f"Error cargando DB: {e}")

async def guardar_en_db(nombre, puntos):
    try:
        supabase.table("partida").upsert({"nombre": nombre, "puntos": puntos}).execute()
    except Exception as e:
        print(f"Error guardando en DB: {e}")

async def avisar_a_todos(data: dict):
    for ws in websockets:
        try: await ws.send_json(data)
        except: continue

@app.get("/estado-juego")
async def obtener_estado(nombre: Optional[str] = None):
    fase = "ESPERA"
    if len(jugadores_listos) >= len(puntuaciones) and len(puntuaciones) >= MIN_JUGADORES:
        fase = "TABLERO"
    elif len(puntuaciones) >= MIN_JUGADORES:
        fase = "ESCRITURA"
    return {
        "fase": fase,
        "jugadores": list(puntuaciones.keys()),
        "puntuaciones": puntuaciones,
        "ya_listo": nombre in jugadores_listos if nombre else False,
        "votacion_activa": frase_actual if frase_actual["nombre"] else None,
        "ha_votado": nombre in votos_actuales["votantes"] if nombre else False,
        "total_necesario": MIN_JUGADORES
    }

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    if jugador.nombre not in puntuaciones:
        puntuaciones[jugador.nombre] = 0
        await guardar_en_db(jugador.nombre, 0)
    
    if len(puntuaciones) >= MIN_JUGADORES and not juego_iniciado:
        juego_iniciado = True
        meta_victoria = len(puntuaciones)
        await avisar_a_todos({"tipo": "FASE_ESCRITURA", "jugadores": list(puntuaciones.keys())})

    await avisar_a_todos({"tipo": "ACTUALIZACION_LOBBY", "jugadores": list(puntuaciones.keys()), "total_necesario": MIN_JUGADORES})
    return {"status": "ok"}

@app.post("/listo-para-jugar")
async def listo_para_jugar(jugador: Jugador):
    if jugador.nombre not in jugadores_listos:
        jugadores_listos.append(jugador.nombre)
    if len(jugadores_listos) >= len(puntuaciones) and len(puntuaciones) >= MIN_JUGADORES:
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(data: dict):
    global frase_actual, votos_actuales, tarea_temporizador
    if tarea_temporizador: tarea_temporizador.cancel()
    frase_actual = {"texto": data['texto'], "nombre": data['nombre_jugador'], "casilla_id": data['casilla_id']}
    votos_actuales = {"si": 0, "no": 0, "votantes": []}
    await avisar_a_todos({"tipo": "NUEVA_VOTACION", "texto": data['texto'], "nombre": data['nombre_jugador']})
    tarea_temporizador = asyncio.create_task(temporizador_votacion(TIEMPO_VOTO))
    return {"status": "ok"}

async def temporizador_votacion(segundos: int):
    try:
        await asyncio.sleep(segundos)
        await finalizar_votacion_logica()
    except asyncio.CancelledError: pass

@app.post("/votar")
async def votar(data: dict):
    global votos_actuales, tarea_temporizador
    if not frase_actual["nombre"]: return {"status": "error"}
    if data['nombre_jugador'] in votos_actuales["votantes"]: return {"status": "ya_votado"}
    votos_actuales[data['eleccion']] += 1
    votos_actuales["votantes"].append(data['nombre_jugador'])
    if len(votos_actuales["votantes"]) >= (len(puntuaciones) - 1):
        if tarea_temporizador: tarea_temporizador.cancel()
        await finalizar_votacion_logica()
    return {"status": "ok"}

async def finalizar_votacion_logica():
    global votos_actuales, frase_actual
    if not frase_actual["nombre"]: return
    aprobado = votos_actuales["si"] > votos_actuales["no"]
    if aprobado: 
        nombre_ganador = frase_actual["nombre"]
        puntuaciones[nombre_ganador] += 1
        await guardar_en_db(nombre_ganador, puntuaciones[nombre_ganador])
    
    ganador_partida = frase_actual["nombre"] if puntuaciones[frase_actual["nombre"]] >= meta_victoria else None
    await avisar_a_todos({
        "tipo": "RESULTADO_FINAL", 
        "aprobado": aprobado, "puntuaciones": puntuaciones,
        "jugador_que_reclamo": frase_actual["nombre"], "casilla_id": frase_actual["casilla_id"],
        "ganador_partida": ganador_partida
    })
    frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}

@app.post("/reset-total")
async def reset_total():
    global puntuaciones, jugadores_listos, juego_iniciado, frase_actual
    puntuaciones, jugadores_listos, juego_iniciado = {}, [], False
    frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}
    try:
        supabase.table("partida").delete().neq("nombre", "xxx").execute()
    except: pass
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