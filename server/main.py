from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from typing import List, Dict
import asyncio

app = FastAPI()

# --- CONFIGURACIÓN ---
# Cámbialo al número real para Nochevieja
MIN_JUGADORES = 2  
# ---------------------

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

@app.post("/unirse")
async def unirse_juego(jugador: Jugador):
    global juego_iniciado, meta_victoria
    nombre = jugador.nombre
    
    # 1. Si el jugador ya existe (reconexión), lo dejamos pasar
    if nombre in puntuaciones:
        return {"status": "ok", "jugadores": list(puntuaciones.keys()), "fase": "ESCRITURA" if juego_iniciado else "ESPERA"}

    # 2. Si la partida ya empezó o ya llegamos al cupo, BLOQUEO
    if juego_iniciado or len(puntuaciones) >= MIN_JUGADORES:
        return {"status": "error", "mensaje": "La sala está llena o la partida ya comenzó."}

    # 3. Registrar al jugador
    puntuaciones[nombre] = 0
    lista_nombres = list(puntuaciones.keys())
    
    # 4. Si es el último en entrar, disparamos el juego
    if len(puntuaciones) == MIN_JUGADORES:
        juego_iniciado = True
        meta_victoria = len(puntuaciones)
        # Avisamos por socket a los que ya estaban esperando
        asyncio.create_task(avisar_a_todos({
            "tipo": "FASE_ESCRITURA", 
            "meta": meta_victoria, 
            "jugadores": lista_nombres
        }))
        # Al último le respondemos directamente que ya empiece
        return {"status": "ok", "jugadores": lista_nombres, "fase": "ESCRITURA"}
        
    # Si no es el último, avisamos del nuevo marcador y lo dejamos en espera
    await avisar_a_todos({"tipo": "ACTUALIZACION_MARCADOR", "puntuaciones": puntuaciones})
    return {"status": "ok", "jugadores": lista_nombres, "fase": "ESPERA"}

# ... (El resto de funciones: votar, listo-para-jugar, etc., se mantienen igual que antes)
@app.post("/listo-para-jugar")
async def listo_para_jugar(jugador: Jugador):
    if jugador.nombre not in jugadores_listos:
        jugadores_listos.append(jugador.nombre)
    if len(jugadores_listos) >= len(puntuaciones):
        await avisar_a_todos({"tipo": "EMPEZAR_JUEGO"})
    return {"status": "ok"}

@app.post("/iniciar-votacion")
async def iniciar_votacion(reclamo: dict):
    global frase_actual, votos_actuales
    frase_actual = {"texto": reclamo['texto'], "nombre": reclamo['nombre_jugador'], "casilla_id": reclamo['casilla_id']}
    votos_actuales = {"si": 0, "no": 0, "votantes": []}
    await avisar_a_todos({"tipo": "NUEVA_VOTACION", "texto": reclamo['texto'], "nombre": reclamo['nombre_jugador']})
    return {"status": "ok"}

@app.post("/votar")
async def votar(voto: dict):
    global votos_actuales
    if voto['nombre_jugador'] not in votos_actuales["votantes"]:
        votos_actuales[voto['eleccion']] += 1
        votos_actuales["votantes"].append(voto['nombre_jugador'])
    if len(votos_actuales["votantes"]) >= (len(puntuaciones) - 1):
        aprobado = votos_actuales["si"] > votos_actuales["no"]
        if aprobado: puntuaciones[frase_actual["nombre"]] += 1
        ganador_partida = frase_actual["nombre"] if puntuaciones[frase_actual["nombre"]] >= meta_victoria else None
        await avisar_a_todos({
            "tipo": "RESULTADO_FINAL", "aprobado": aprobado, "puntuaciones": puntuaciones,
            "jugador_que_reclamo": frase_actual["nombre"], "casilla_id": frase_actual["casilla_id"],
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

