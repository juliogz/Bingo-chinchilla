const URL_BASE = 'https://bingo-backend-rdqx.onrender.com'; 
const socket = new WebSocket(URL_BASE.replace('https', 'wss') + '/ws');
const MIN_JUGADORES = 2; 

let miNombre = localStorage.getItem("nombreBingo");

window.onload = () => {
    if (miNombre) {
        enviarRegistro(miNombre);
    }
};

socket.onmessage = (event) => {
    const datos = JSON.parse(event.data);

    if (datos.tipo === "ACTUALIZACION_LOBBY") {
        const registro = document.getElementById('seccion-registro');
        if (miNombre && registro.innerHTML.includes("Esperando")) {
            registro.innerHTML = `⏳ Esperando a que se llene la sala (${datos.jugadores.length}/${datos.total_necesario})...`;
        }
    }

    if (datos.tipo === "FASE_ESCRITURA") {
        if (miNombre) mostrarSeccionEscritura(datos.jugadores);
    }

    if (datos.tipo === "EMPEZAR_JUEGO") {
        irATablero();
    }

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
                casilla.style.backgroundColor = "lightgreen";
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
            if (datos.fase === "TABLERO") {
                irATablero();
            } else if (datos.fase === "ESCRITURA") {
                if (datos.ya_listo) {
                    document.getElementById('seccion-registro').style.display = "none";
                    document.getElementById('seccion-casillas').style.display = "block";
                    document.getElementById('seccion-casillas').innerHTML = "⏳ Frases enviadas. Esperando al resto...";
                } else {
                    mostrarSeccionEscritura(datos.jugadores);
                }
            } else {
                document.getElementById('seccion-registro').innerHTML = 
                    `⏳ Esperando a que se llene la sala (${datos.jugadores.length}/${MIN_JUGADORES})...`;
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
    contenedor.innerHTML = ""; 
    const otros = jugadores.filter(j => j !== miNombre);
    otros.forEach(n => crearInputFrase(contenedor, `Sobre ${n}:`));
    crearInputFrase(contenedor, "General:");
    document.getElementById('btn-confirmar-frases').style.display = "block";
}

function crearInputFrase(padre, etiqueta) {
    const div = document.createElement('div');
    div.style.marginBottom = "10px";
    div.innerHTML = `<label style="display:block; color:white;">${etiqueta}</label>
                     <input class="input-frase" placeholder="Escribe algo..." style="width:80%">`;
    padre.appendChild(div);
}

document.getElementById('btn-confirmar-frases').onclick = () => {
    const frases = Array.from(document.querySelectorAll('.input-frase')).map(i => i.value).filter(v => v);
    localStorage.setItem("bingo_mis_frases", JSON.stringify(frases));
    fetch(`${URL_BASE}/listo-para-jugar`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: miNombre })
    });
    document.getElementById('seccion-casillas').innerHTML = "⏳ Frases enviadas. Esperando al resto...";
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
    if(btn) btn.classList.add('seleccionado');
    fetch(`${URL_BASE}/votar`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eleccion, nombre_jugador: miNombre})
    });
}

function resetearBotonesVoto() {
    const bSi = document.getElementById('btn-si');
    const bNo = document.getElementById('btn-no');
    if(bSi) bSi.classList.remove('seleccionado');
    if(bNo) bNo.classList.remove('seleccionado');
}

function actualizarMarcador(puntos) {
    const lista = document.getElementById('lista-puntos');
    if (!lista) return;
    lista.innerHTML = "";
    Object.entries(puntos).forEach(([n, p]) => {
        const li = document.createElement('li');
        li.innerText = `${n}: ${p}`;
        lista.appendChild(li);
    });
}

function mostrarPantallaFinal(ganador, puntuaciones) {
    document.getElementById('pantalla-juego').style.display = "none";
    let finalDiv = document.getElementById('pantalla-final');
    if (!finalDiv) {
        finalDiv = document.createElement('div');
        finalDiv.id = "pantalla-final";
        document.body.appendChild(finalDiv);
    }
    finalDiv.style.display = "block";
    
    const ranking = Object.entries(puntuaciones).sort((a,b)=>b[1]-a[1])
        .map(([n,p], i) => `<div>${i===0?'🥇':''} ${n}: ${p} pts</div>`).join("");
        
    finalDiv.innerHTML = `
        <div style="text-align:center; padding:50px; color:white; background:rgba(0,0,0,0.9); position:fixed; top:0; left:0; width:100%; height:100%; z-index:9999;">
            <h1>👑 ¡FIN DE LA PARTIDA! 👑</h1>
            <h2>Ha ganado: ${ganador}</h2>
            <div style="margin:20px 0; font-size:1.5rem;">${ranking}</div>
            <button onclick="reinicioMaestro()" style="padding:15px 30px; font-size:1.2rem; cursor:pointer;">Reiniciar Juego</button>
        </div>`;
}

function reinicioMaestro() {
    fetch(`${URL_BASE}/reset-total`, { method: 'POST' });
}

document.getElementById('form-registro').onsubmit = (e) => {
    e.preventDefault();
    enviarRegistro(document.getElementById('input-nombre').value);
};




