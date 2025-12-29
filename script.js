const socket = new WebSocket('wss://bingo-backend-rdqx.onrender.com/ws');
let miNombre = localStorage.getItem("nombreBingo");
const panelVoto = document.getElementById('panel-voto');

socket.onmessage = (event) => {
    const datos = JSON.parse(event.data);

    if (datos.tipo === "FASE_ESCRITURA") {
        document.getElementById('seccion-registro').style.display = "none";
        document.getElementById('seccion-casillas').style.display = "block";
        // Pasamos la lista de jugadores para saber a quién etiquetar
        generarCamposEscritura(datos.jugadores);
    }

    if (datos.tipo === "EMPEZAR_JUEGO") {
        document.getElementById('pantalla-lobby').style.display = "none";
        document.getElementById('pantalla-juego').style.display = "block";
        dibujarTableroBingo();
    }

    if (datos.tipo === "NUEVA_VOTACION") {
        panelVoto.style.display = "block";
        document.getElementById('texto-voto').innerText = `¿Ha pasado: "${datos.texto}"? (Punto para ${datos.nombre})`;
        resetearBotonesVoto();
    }

    if (datos.tipo === "RESULTADO_FINAL") {
        panelVoto.style.display = "none";
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

    if (datos.tipo === "FIN_TIEMPO") {
        const ordenados = Object.entries(datos.puntuaciones).sort((a, b) => b[1] - a[1]);
        mostrarPantallaFinal(ordenados[0][0], datos.puntuaciones, "¡Tiempo agotado! ⏰");
    }

    if (datos.tipo === "ACTUALIZACION_MARCADOR") actualizarMarcador(datos.puntuaciones);
    if (datos.tipo === "RESET_GLOBAL") { localStorage.clear(); location.reload(); }
};

async function enviarRegistro(nombre) {
    const respuesta = await fetch('https://bingo-backend-rdqx.onrender.com/unirse', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nombre })
    });
    const datos = await respuesta.json();
    if (datos.status === "error") alert(datos.mensaje);
    else {
        miNombre = nombre;
        localStorage.setItem("nombreBingo", miNombre);
        document.getElementById('seccion-registro').innerHTML = "⏳ Esperando a que se llene la sala...";
    }
}

document.getElementById('form-registro').onsubmit = (e) => {
    e.preventDefault();
    if (socket.readyState !== 1) return alert("Conectando...");
    enviarRegistro(document.getElementById('input-nombre').value);
};

function generarCamposEscritura(jugadores) {
    const contenedor = document.getElementById('contenedor-inputs-casillas');
    contenedor.innerHTML = "";
    
    // Filtramos para que no aparezca nuestro nombre
    const otrosJugadores = jugadores.filter(j => j !== miNombre);
    
    // Creamos un input por cada compañero
    otrosJugadores.forEach(nombre => {
        crearInputFrase(contenedor, `Sobre ${nombre}:`);
    });

    // Añadimos el "General"
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
    fetch('https://bingo-backend-rdqx.onrender.com/listo-para-jugar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: miNombre })
    });
    document.getElementById('seccion-casillas').innerHTML = "⏳ Esperando al resto...";
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
                fetch('https://bingo-backend-rdqx.onrender.com/iniciar-votacion', {
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
    document.getElementById(idBtn).classList.add('seleccionado');
    fetch('https://bingo-backend-rdqx.onrender.com/votar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({eleccion, nombre_jugador: miNombre})
    });
}

function resetearBotonesVoto() {
    document.getElementById('btn-si').classList.remove('seleccionado');
    document.getElementById('btn-no').classList.remove('seleccionado');
}

function actualizarMarcador(puntos) {
    const lista = document.getElementById('lista-puntos');
    lista.innerHTML = "";
    Object.entries(puntos).forEach(([n, p]) => {
        const li = document.createElement('li');
        li.innerText = `${n}: ${p}`;
        lista.appendChild(li);
    });
}

function mostrarPantallaFinal(ganador, puntuaciones, titulo = "👑 ¡Fin de la partida! 👑") {
    document.getElementById('pantalla-juego').style.display = "none";
    let finalDiv = document.getElementById('pantalla-final') || document.createElement('div');
    finalDiv.id = "pantalla-final";
    const ranking = Object.entries(puntuaciones).sort((a,b)=>b[1]-a[1])
        .map(([n,p], i) => `<div>${i===0?'🥇':''} ${n}: ${p} pts</div>`).join("");
    finalDiv.innerHTML = `<h1>${titulo}</h1><h2>Ganador: ${ganador}</h2><div class="ranking">${ranking}</div>
                          <button onclick="reinicioMaestro()">Reiniciar Todo</button>`;
    document.body.appendChild(finalDiv);
    confetti();
}

function reinicioMaestro() {
    fetch('https://bingo-backend-rdqx.onrender.com/reset-total', { method: 'POST' });

}
