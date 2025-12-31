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

# --- CONEXIÓN SUPABASE ---
URL: str = os.environ.get("SUPABASE_URL", "")
KEY: str = os.environ.get("SUPABASE_KEY", "")
supabase: Client = create_client(URL, KEY)

# --- ESTADO EN MEMORIA (Se sincroniza con Supabase) ---
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

# Al arrancar el servidor, intentamos recuperar datos antiguos
@app.on_event("startup")
async def startup_event():
    global puntuaciones
    try:
        res = supabase.table("partida").select("*").execute()
        if res.data:
            for fila in res.data:
                puntuaciones[fila["nombre"]] = fila["puntos"]
            print("Datos cargados de Supabase")
    except:
        print("No se pudo cargar de Supabase (tablas no creadas aún)")

async def guardar_en_db(nombre, puntos):
    # Esto guarda o actualiza el punto en Supabase
    supabase.table("partida").upsert({"nombre": nombre, "puntos": puntos}).execute()

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

# ... (El resto de funciones: votar, iniciar-votacion, etc., se quedan igual que el código anterior) ...
# Solo asegúrate de llamar a `await guardar_en_db(nombre, puntos)` dentro de `finalizar_votacion_logica` cuando alguien gane un punto.

@app.post("/reset-total")
async def reset_total():
    global puntuaciones, jugadores_listos, juego_iniciado, frase_actual
    puntuaciones, jugadores_listos, juego_iniciado = {}, [], False
    frase_actual = {"texto": "", "nombre": "", "casilla_id": ""}
    # Borrar base de datos
    supabase.table("partida").delete().neq("nombre", "xxx").execute()
    await avisar_a_todos({"tipo": "RESET_GLOBAL"})
    return {"status": "ok"}