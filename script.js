const socket = new WebSocket('wss://bingo-backend-rdqx.onrender.com/ws');
let miNombre = localStorage.getItem("nombreBingo");

socket.onmessage = (event) => {
    const datos = JSON.parse(event.data);

    if (datos.tipo === "FASE_ESCRITURA") {
        // Si el usuario ya está registrado, le pintamos las cajas
        if (miNombre) {
            document.getElementById('seccion-registro').style.display = "none";
            document.getElementById('seccion-casillas').style.display = "block";
            generarCamposEscritura(datos.jugadores);
        }
    }

    if (datos.tipo === "EMPEZAR_JUEGO") {
        document.getElementById('pantalla-lobby').style.display = "none";
        document.getElementById('pantalla-juego').style.display = "block";
        dibujarTableroBingo();
    }
    
    if (datos.tipo === "RESET_GLOBAL") {
        localStorage.clear();
        location.reload();
    }
};

async function enviarRegistro(nombre) {
    miNombre = nombre;
    localStorage.setItem("nombreBingo", nombre);
    
    const respuesta = await fetch('https://bingo-backend-rdqx.onrender.com/unirse', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ nombre: nombre })
    });
    
    document.getElementById('seccion-registro').innerHTML = "⏳ Esperando a que se llene la sala...";
}

function generarCamposEscritura(jugadores) {
    const contenedor = document.getElementById('contenedor-inputs-casillas');
    
    // LA LIMPIEZA MÁGICA:
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

// ... Mantén tus funciones de votar e iniciar-votacion igual que las tenías ...



