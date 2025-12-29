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
    document.getElementById('pantalla-juego').style.display = "none";
    let finalDiv = document.getElementById('pantalla-final') || document.createElement('div');
    finalDiv.id = "pantalla-final";
    document.body.appendChild(finalDiv);
    
    const ranking = Object.entries(puntuaciones).sort((a,b)=>b[1]-a[1])
        .map(([n,p], i) => `
            <div style="display:flex; justify-content:space-between; padding:10px; background:rgba(255,255,255,0.1); margin:5px; border-radius:10px; font-size:1.2rem;">
                <span>${i===0?'🥇':(i===1?'🥈':(i===2?'🥉':''))} ${n}</span>
                <strong>${p} pts</strong>
            </div>`).join("");
        
    finalDiv.innerHTML = `
        <div style="position:fixed; top:0; left:0; width:100%; height:100%; background:linear-gradient(135deg, #2c3e50, #000); color:white; z-index:10000; display:flex; flex-direction:column; align-items:center; justify-content:center; font-family:sans-serif; overflow-y:auto; padding:20px;">
            <h1 style="font-size:3rem; margin:0; color:#f1c40f; text-shadow: 0 0 20px #f1c40f;">BINGO! 🥂</h1>
            <h2 style="font-size:1.5rem; margin-bottom:30px;">¡${ganador} ha ganado la noche!</h2>
            <div style="width:100%; max-width:400px; background:rgba(0,0,0,0.5); padding:20px; border-radius:20px; border:1px solid #f1c40f; margin-bottom:30px;">
                <h3 style="text-align:center; border-bottom:1px solid #333; padding-bottom:10px;">RANKING FINAL</h3>
                ${ranking}
            </div>
            <button onclick="reinicioMaestro()" style="background:#f1c40f; color:black; border:none; padding:15px 40px; font-size:1.2rem; font-weight:bold; border-radius:50px; cursor:pointer; box-shadow: 0 10px 0 #b7950b;">NUEVA PARTIDA</button>
        </div>`;
}

function reinicioMaestro() { fetch(`${URL_BASE}/reset-total`, { method: 'POST' }); }

document.getElementById('form-registro').onsubmit = (e) => {
    e.preventDefault();
    enviarRegistro(document.getElementById('input-nombre').value);
};





