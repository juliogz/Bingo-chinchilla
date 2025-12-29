const URL_BASE = 'https://bingo-backend-rdqx.onrender.com'; 
const socket = new WebSocket(URL_BASE.replace('https', 'wss') + '/ws');
const MIN_JUGADORES = 7; 

let miNombre = localStorage.getItem("nombreBingo");

window.onload = () => {
    if (miNombre) enviarRegistro(miNombre);
};

socket.onmessage = (event) => {
    const datos = JSON.parse(event.data);

    if (datos.tipo === "ACTUALIZACION_LOBBY") {
        const registro = document.getElementById('seccion-registro');
        if (miNombre && registro.innerHTML.includes("Esperando")) {
            registro.innerHTML = `<div class="lobby-wait">⏳ Esperando a la familia...<br><span style="font-size:2rem">${datos.jugadores.length}/${datos.total_necesario}</span></div>`;
        }
    }

    if (datos.tipo === "FASE_ESCRITURA" && miNombre) mostrarSeccionEscritura(datos.jugadores);
    if (datos.tipo === "EMPEZAR_JUEGO") irATablero();

    if (datos.tipo === "NUEVA_VOTACION") {
        document.getElementById('panel-voto').style.display = "block";
        document.getElementById('texto-voto').innerText = `¿Ha pasado: "${datos.texto}"? (Punto para ${datos.nombre})`;
        resetearBotonesVoto();
    }

    if (datos.tipo === "RESULTADO_FINAL") {
        document.getElementById('panel-voto').style.display = "none";
        if (datos.aprobado) {
            const casilla = document.getElementById(datos.casilla_id);
            if (datos.jugador_que_reclamo === miNombre && casilla) {
                casilla.style.backgroundColor = "#27ae60";
                casilla.style.boxShadow = "inset 0 0 10px #000";
                casilla.style.pointerEvents = "none";
            }
        }
        actualizarMarcador(datos.puntuaciones);
        if (datos.ganador_partida) mostrarPantallaFinal(datos.ganador_partida, datos.puntuaciones);
    }

    if (datos.tipo === "RESET_GLOBAL") {
        localStorage.clear();
        location.reload();
    }
};

async function enviarRegistro(nombre) {
    miNombre = nombre;
    localStorage.setItem("nombreBingo", nombre);
    try {
        const respuesta = await fetch(`${URL_BASE}/unirse`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ nombre: nombre })
        });
        const datos = await respuesta.json();
        if (datos.status === "ok") {
            if (datos.fase === "TABLERO") irATablero();
            else if (datos.fase === "ESCRITURA") {
                if (datos.ya_listo) {
                    document.getElementById('seccion-registro').style.display = "none";
                    document.getElementById('seccion-casillas').style.display = "block";
                    document.getElementById('seccion-casillas').innerHTML = "<div class='lobby-wait'>✅ Frases enviadas.<br>Esperando al resto...</div>";
                } else mostrarSeccionEscritura(datos.jugadores);
            } else {
                document.getElementById('seccion-registro').innerHTML = `<div class="lobby-wait">⏳ Esperando a la familia...<br><span style="font-size:2rem">${datos.jugadores.length}/${MIN_JUGADORES}</span></div>`;
            }
        }
    } catch (e) { console.error(e); }
}

function irATablero() {
    document.getElementById('pantalla-lobby').style.display = "none";
    document.getElementById('pantalla-juego').style.display = "block";
    dibujarTableroBingo();
}

function mostrarSeccionEscritura(listaJugadores) {
    document.getElementById('seccion-registro').style.display = "none";
    document.getElementById('seccion-casillas').style.display = "block";
    generarCamposEscritura(listaJugadores);
}

function generarCamposEscritura(jugadores) {
    const contenedor = document.getElementById('contenedor-inputs-casillas');
    contenedor.innerHTML = "<h2 style='color:#f1c40f'>📝 Escribe tus predicciones</h2>"; 
    const otros = jugadores.filter(j => j !== miNombre);
    otros.forEach(n => crearInputFrase(contenedor, `Sobre ${n}:`));
    crearInputFrase(contenedor, "General (algo que pasará):");
    document.getElementById('btn-confirmar-frases').style.display = "block";
}

function crearInputFrase(padre, etiqueta) {
    const div = document.createElement('div');
    div.className = "input-group";
    div.innerHTML = `<label>${etiqueta}</label><input class="input-frase" placeholder="...">`;
    padre.appendChild(div);
}

document.getElementById('btn-confirmar-frases').onclick = () => {
    const frases = Array.from(document.querySelectorAll('.input-frase')).map(i => i.value).filter(v => v);
    if(frases.length < 1) return alert("¡Escribe algo!");
    localStorage.setItem("bingo_mis_frases", JSON.stringify(frases));
    fetch(`${URL_BASE}/listo-para-jugar`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: miNombre })
    });
    document.getElementById('seccion-casillas').innerHTML = "<div class='lobby-wait'>✅ Frases enviadas.<br>Esperando al resto...</div>";
};

function dibujarTableroBingo() {
    const frases = JSON.parse(localStorage.getItem("bingo_mis_frases")) || [];
    const tablero = document.getElementById('tablero');
    tablero.innerHTML = "";
    frases.forEach((f, i) => {
        const div = document.createElement('div');
        div.className = "casilla";
        div.id = `casilla-${i}`;
        div.innerText = f;
        div.onclick = () => {
            if (confirm(`¿Seguro que ha pasado: "${f}"?`)) {
                fetch(`${URL_BASE}/iniciar-votacion`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({casilla_id: div.id, nombre_jugador: miNombre, texto: f})
                });
            }
        };
        tablero.appendChild(div);
    });
}

function enviarVoto(eleccion, idBtn) {
    resetearBotonesVoto();
    const btn = document.getElementById(idBtn);
    if(btn) btn.style.background = eleccion === 'si' ? '#27ae60' : '#c0392b';
    fetch(`${URL_BASE}/votar`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eleccion, nombre_jugador: miNombre})
    });
}

function resetearBotonesVoto() {
    document.getElementById('btn-si').style.background = '#2ecc71';
    document.getElementById('btn-no').style.background = '#e74c3c';
}

function actualizarMarcador(puntos) {
    const lista = document.getElementById('lista-puntos');
    if (!lista) return;
    lista.innerHTML = "";
    Object.entries(puntos).sort((a,b)=>b[1]-a[1]).forEach(([n, p]) => {
        const li = document.createElement('li');
        li.innerHTML = `<span>${n}</span> <strong>${p} pts</strong>`;
        lista.appendChild(li);
    });
}

function mostrarPantallaFinal(ganador, puntuaciones) {
    // Ocultamos lo demás por si acaso
    document.getElementById('pantalla-juego').style.display = "none";
    
    let finalDiv = document.getElementById('pantalla-final');
    if (!finalDiv) {
        finalDiv = document.createElement('div');
        finalDiv.id = "pantalla-final";
        document.body.appendChild(finalDiv);
    }

    // Ordenamos el ranking
    const ranking = Object.entries(puntuaciones)
        .sort((a, b) => b[1] - a[1])
        .map(([n, p], i) => {
            let medalla = i === 0 ? '🥇' : (i === 1 ? '🥈' : (i === 2 ? '🥉' : '👤'));
            return `
            <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px; background:rgba(255,255,255,0.1); margin:8px 0; border-radius:12px; font-size:1.3rem; border: 1px solid rgba(255,255,255,0.05);">
                <span>${medalla} ${n}</span>
                <strong style="color:#f1c40f">${p} pts</strong>
            </div>`;
        }).join("");

    // Aplicamos el HTML y forzamos el estilo para que NO sea una rendija
    finalDiv.innerHTML = `
        <div style="
            position: fixed; 
            top: 0; 
            left: 0; 
            width: 100vw; 
            height: 100vh; 
            background: radial-gradient(circle at center, #1a2a6c, #b21f1f, #fdbb2d);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;
            color: white; 
            z-index: 99999; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: center; 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            padding: 20px;
            box-sizing: border-box;
        ">
            <style>
                @keyframes gradientBG {
                    0% { background-position: 0% 50%; }
                    50% { background-position: 100% 50%; }
                    100% { background-position: 0% 50%; }
                }
            </style>
            
            <h1 style="font-size: clamp(3rem, 10vw, 5rem); margin: 0; color:#fff; text-shadow: 0 0 20px rgba(255,255,255,0.5); text-align:center;">¡BINGO! 🥂</h1>
            <h2 style="font-size: 1.8rem; margin: 10px 0 30px 0; text-align:center; font-weight: 300;">¡<span style="color:#f1c40f; font-weight:bold;">${ganador}</span> ha ganado la noche!</h2>
            
            <div style="width:100%; max-width:450px; background:rgba(0,0,0,0.6); padding:25px; border-radius:30px; border:2px solid rgba(241, 196, 15, 0.3); backdrop-filter: blur(10px); box-shadow: 0 20px 50px rgba(0,0,0,0.5);">
                <h3 style="text-align:center; border-bottom:1px solid rgba(255,255,255,0.1); padding-bottom:15px; margin-top:0; letter-spacing: 2px;">RANKING FINAL</h3>
                <div style="max-height: 40vh; overflow-y: auto; padding-right: 5px;">
                    ${ranking}
                </div>
            </div>
            
            <button onclick="reinicioMaestro()" style="
                margin-top: 40px;
                background: #f1c40f; 
                color: #000; 
                border: none; 
                padding: 18px 50px; 
                font-size: 1.4rem; 
                font-weight: bold; 
                border-radius: 50px; 
                cursor: pointer; 
                transition: transform 0.2s;
                box-shadow: 0 8px 0 #b7950b;
            " onmousedown="this.style.transform='translateY(4px)'; this.style.boxShadow='0 4px 0 #b7950b'" 
               onmouseup="this.style.transform='translateY(0)'; this.style.boxShadow='0 8px 0 #b7950b'">
                NUEVA PARTIDA 🔄
            </button>
        </div>`;
}

function reinicioMaestro() { fetch(`${URL_BASE}/reset-total`, { method: 'POST' }); }

document.getElementById('form-registro').onsubmit = (e) => {
    e.preventDefault();
    enviarRegistro(document.getElementById('input-nombre').value);
};






