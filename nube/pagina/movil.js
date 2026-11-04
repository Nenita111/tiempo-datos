/* 4.19 (lo pidió Isa el 4 nov 2026): la página de la tele en un móvil de casa. La sirve la app de la tele (Movil.kt) en
   http://<tele>:8090/<clave>/ y este fichero va delante de index.html (solo ahí: en la tele no se carga).
   - Lo que en la tele hace la app (window.Android) aquí lo da el servidor de la tele: los datos (cada 20 s; si no han cambiado, nada),
     el mapa y las pantallas que salen y su orden (las de la tele).
   - «Añádele botones para avanzar a derecha o izquierda»: ◀ ▶ (y deslizar o las flechas del teclado); la rotación se para 1 minuto,
     como con el mando.
   - «Haz que pueda ampliar algunos apartados usando dos dedos»: se amplía con dos dedos; mientras está ampliada no cambia sola y
     deslizar mueve lo ampliado (no cambia de pantalla).
   - 4.21 («quiero que sea una dirección html que se pueda ver desde cualquier dispositivo»): lo mismo en internet
     (https://nenita111.github.io/tiempo-datos/, window.NUBE): los datos, de datos.json, que GitHub pone al día cada media hora con la
     misma parte de la app que baja los datos (NubeTest); se mira cada 5 minutos.
   - 4.22 (lo pidió Isa el 4 nov 2026: «elimina el selector de localidad»): sin el desplegable de municipios de 4.19 ni la lista al
     tocar el nombre de 4.21: la página es la del sitio de la tele (en internet, Adra). */
(function () {
  "use strict";
  window.MOVIL = true;
  const NUBE = !!window.NUBE;
  const sync = u => { try { const x = new XMLHttpRequest(); x.open("GET", u, false); x.send(); return x.status === 200 ? x.responseText : ""; } catch (e) { return ""; } };
  const zoom = () => (window.visualViewport ? visualViewport.scale : 1);
  let etag = null, espera = null, mv = null, ultimo = "";
  try { localStorage.removeItem("tiempo.municipio"); } catch (e) {}   // lo que se eligió con el selector de 4.21

  /* ---------- los datos, del servidor de la tele ---------- */
  function pedirDatos(ms) { clearTimeout(espera); espera = setTimeout(traer, ms || 0); }
  async function traer() {
    if (NUBE) return traerNube();
    let luego = document.hidden ? 60000 : 20000;
    try {
      const r = await fetch("estado.json", {cache: "no-store", headers: etag ? {"If-None-Match": etag} : {}});
      if (r.status === 200) {
        const j = await r.json();
        etag = r.headers.get("ETag");
        aviso(null);
        if (window.app) app.actualizar(j);
      } else if (r.status === 304) aviso(null);
      else if (r.status === 503) { aviso("La tele está preparando los datos…"); luego = 2000; }
      else { aviso("La tele no da la página: vuelve a abrir el enlace del menú ≡ de la tele"); luego = 30000; }
    } catch (e) { aviso("Sin conexión con la tele: tiene que estar encendida y el móvil, en la misma wifi"); luego = 5000; }
    pedirDatos(luego);
  }
  // en internet: datos.json (GitHub Pages lo sirve con su ETag: si no ha cambiado, el navegador no lo vuelve a bajar)
  async function traerNube() {
    let luego = 5 * 60000;
    try {
      const r = await fetch("datos.json", {cache: "no-cache"});
      if (!r.ok) throw new Error(r.status);
      const t = await r.text();
      aviso(null);
      if (t !== ultimo) { ultimo = t; if (window.app) app.actualizar(JSON.parse(t)); }
    } catch (e) { aviso(ultimo ? null : "No se han podido cargar los datos: se vuelve a probar en un momento"); luego = 30000; }
    pedirDatos(luego);
  }
  window.Android = {
    mapa: () => sync("mapa.txt"),
    ajustes: () => (NUBE ? "" : sync("ajustes.json")) || "{}",   // las de la tele (aquí no se cambian); en internet, las de siempre
    guardarAjustes() {}, menu() {}, pantalla() {}, cambiarSitio() {},
    listo() { pedirDatos(0); },
  };
  document.addEventListener("visibilitychange", () => { if (!document.hidden) pedirDatos(0); });

  /* ---------- cambiar de pantalla ---------- */
  function mover(d) { if (!window.app) return; app.tecla(); app.pagina(d); }
  addEventListener("keydown", e => { if (e.key === "ArrowRight") mover(1); else if (e.key === "ArrowLeft") mover(-1); });
  let t0 = null, dedos = 0;
  addEventListener("touchstart", e => {
    dedos = Math.max(dedos, e.touches.length);
    if (e.touches.length === 1) { dedos = 1; const t = e.touches[0]; t0 = {x: t.clientX, y: t.clientY, t: Date.now()}; }
  }, {passive: true});
  addEventListener("touchend", e => {
    if (e.touches.length) return;
    const a = t0; t0 = null;
    if (!a || dedos > 1 || zoom() > 1.05 || (e.target.closest && e.target.closest("#mv"))) return;   // ampliada: deslizar la mueve
    const t = e.changedTouches[0], dx = t.clientX - a.x, dy = t.clientY - a.y;
    if (Math.abs(dx) > 50 && Math.abs(dx) > 1.5 * Math.abs(dy) && Date.now() - a.t < 900) mover(dx < 0 ? 1 : -1);
  }, {passive: true});
  // ampliada con dos dedos: quieta (como si se usara el mando) y sin los botones encima
  // los bordes, del color de fondo de la página (claro u oscuro según el sol)
  function tema() { try { const c = getComputedStyle(document.body).getPropertyValue("--bg").trim(); if (c) document.documentElement.style.background = c; } catch (e) {} }
  function ampliada() {
    tema();
    const z = zoom() > 1.05;
    if (mv) mv.classList.toggle("zoom", z);
    if (z && window.app) app.tecla();
  }
  if (window.visualViewport) { visualViewport.addEventListener("resize", ampliada); visualViewport.addEventListener("scroll", ampliada); }
  setInterval(ampliada, 5000);


  /* ---------- los controles (fuera de la página escalada) ---------- */
  function aviso(t) {
    if (!mv) return;
    const a = mv.querySelector(".mv-aviso");
    a.textContent = t || ""; a.hidden = !t;
  }
  function crear() {
    const st = document.createElement("style");
    st.textContent = `
html{touch-action:pan-x pan-y pinch-zoom}footer .pista{display:none}
#mv{position:fixed;inset:0;pointer-events:none;z-index:100;font:600 16px/1.2 Atkinson,system-ui,sans-serif;color:#e8eef7;-webkit-tap-highlight-color:transparent}
#mv.zoom .mv-b,#mv.zoom .mv-c{opacity:0;pointer-events:none}
#mv button{pointer-events:auto;position:absolute;border:0;color:inherit;font:inherit;background:rgba(20,30,44,.72);
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.14),0 6px 18px -8px rgba(0,0,0,.8);border-radius:16px;touch-action:manipulation;cursor:pointer;
  display:flex;align-items:center;justify-content:center;gap:6px;transition:opacity .2s;-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}
#mv .mv-b{font-size:26px}#mv button:active{background:rgba(60,90,130,.85)}
#mv .mv-aviso{position:absolute;left:50%;top:10px;transform:translateX(-50%);max-width:calc(100% - 24px);background:rgba(20,30,44,.9);
  border-radius:12px;padding:8px 14px;font-size:14px;text-align:center;box-shadow:0 6px 18px -8px rgba(0,0,0,.8)}
#mv .mv-gira{position:absolute;left:0;right:0;text-align:center;font-size:14px;color:#9fb0c4}
#mv .mv-gira[hidden],#mv .mv-aviso[hidden]{display:none}`;
    document.head.appendChild(st);
    mv = document.createElement("div"); mv.id = "mv";
    mv.innerHTML = `<button class="mv-b mv-izq" type="button" aria-label="Pantalla anterior">◀</button>
      <button class="mv-b mv-der" type="button" aria-label="Pantalla siguiente">▶</button>
      <button class="mv-c" type="button" aria-label="Pantalla completa">⛶</button>
      <div class="mv-gira" hidden>Gira el móvil para verla más grande · con dos dedos se amplía</div>
      <div class="mv-aviso">${NUBE ? "Cargando…" : "Conectando con la tele…"}</div>`;
    document.documentElement.appendChild(mv);   // fuera del body (que va escalado): los botones, a su tamaño
    mv.querySelector(".mv-izq").addEventListener("click", () => mover(-1));
    mv.querySelector(".mv-der").addEventListener("click", () => mover(1));
    const fs = mv.querySelector(".mv-c"), de = document.documentElement;
    if (!(de.requestFullscreen || de.webkitRequestFullscreen)) fs.remove();
    else fs.addEventListener("click", () => {
      try { if (document.fullscreenElement || document.webkitFullscreenElement) (document.exitFullscreen || document.webkitExitFullscreen).call(document);
            else (de.requestFullscreen || de.webkitRequestFullscreen).call(de); } catch (e) {}
    });
    if (window.escalar) escalar();
  }
  /* dónde va cada cosa: con hueco a los lados (móvil en horizontal), a los lados; en vertical, debajo de la página; si no, encima */
  window.colocarMovil = function (w, h, s) {
    if (!mv) return;
    tema();
    const pw = 1920 * s, ph = 1080 * s, x = (w - pw) / 2, y = (h - ph) / 2;
    const pon = (sel, l, t, an, al) => { const e = mv.querySelector(sel); if (e) Object.assign(e.style, {left: l + "px", top: t + "px", width: an + "px", height: al + "px"}); };
    const gira = mv.querySelector(".mv-gira");
    mv.classList.remove("lado", "abajo", "encima");
    if (h - ph >= 150) {   // en vertical: debajo
      mv.classList.add("abajo");
      const t = y + ph + 14, al = 56, g = 10, b = (w - 24 - g) / 2;
      pon(".mv-izq", 12, t, b, al); pon(".mv-der", w - 12 - b, t, b, al);
      pon(".mv-c", w / 2 - 28, t + al + 12, 56, 44);
      gira.hidden = false; gira.style.top = (t + al + (mv.querySelector(".mv-c") ? 68 : 14)) + "px";
    } else if (x >= 52) {   // en horizontal, con hueco a los lados
      mv.classList.add("lado");
      const an = Math.min(x - 10, 84);
      pon(".mv-izq", (x - an) / 2, h / 2 - 60, an, 120); pon(".mv-der", w - x + (x - an) / 2, h / 2 - 60, an, 120);
      pon(".mv-c", w - x + (x - an) / 2, 12, an, 52);
      gira.hidden = true;
    } else {   // sin hueco: encima, en los bordes
      mv.classList.add("encima");
      pon(".mv-izq", 6, h / 2 - 50, 48, 100); pon(".mv-der", w - 54, h / 2 - 50, 48, 100);
      pon(".mv-c", w - 54, h - 52, 48, 44);
      gira.hidden = true;
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", crear); else crear();
})();
