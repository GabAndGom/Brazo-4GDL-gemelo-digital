/*
 * Sección "Modelo 3D": simulación del brazo XK-JS1-1 y visor three.js.
 *
 * - La simulación (estado, movimientos, homing, E/S del PLC, secuencias) no
 *   depende de three.js y funciona desde que carga la página.
 * - three.js, GLTFLoader y OrbitControls se importan solo cuando la sección se
 *   acerca a la pantalla o al pulsar "Cargar visor 3D".
 * - La pose de cada pieza sale de la cinemática (web/js/cinematica.js): las
 *   bielas pasivas no se animan a mano.
 */
const K = window.Cinematica;
const PLC = window.ConexionPLC;
const $ = s => document.querySelector(s);
const P = K.parametros, T = K.transmision, D = K.derivados;
const RAD = Math.PI / 180, M = 0.001;
const RUTA_GLB = window.RUTA_GLB_BRAZO || 'global/modelo-3d/brazo_xk-js1-1.glb';   // la app de escritorio usa su copia
const CLAVE_SEQ = 'brazo-xk-js1-1-secuencia';
const LIMITES = {
  theta: [P.thetaMin, P.thetaMax],
  sX: [0, P.recorridoX],
  sY: [0, P.recorridoY]
};
const fmt = (v, d = 1) => (Math.abs(v) < 0.5 * 10 ** -d ? 0 : v).toFixed(d);
const limitar = (eje, v) => Math.min(LIMITES[eje][1], Math.max(LIMITES[eje][0], v));

// ================================================================== simulación
const sim = {
  q: { theta: 30, sX: 60, sY: 110 },   // posición al encender: desconocida para el PLC
  garra: false,
  referenciado: false,
  homing: false,
  plan: null,                          // { segmentos, i, t0, resolver }
  activos: { Z: false, X: false, Y: false },
  vel: { Z: 0, X: 0, Y: 0 },
  dir: { Z: 0, X: 0, Y: 0 },
  aviso: '',
  traza: []
};

const velocidad = () => Number($('#m3d-velocidad').value);       // mm/s; la base va a 1.5 °/s por mm/s
function duracion(q0, q1, factor) {
  const v = velocidad() * (factor || 1);
  return Math.max(0.12, Math.abs(q1.theta - q0.theta) / (1.5 * v), Math.abs(q1.sX - q0.sX) / v, Math.abs(q1.sY - q0.sY) / v);
}

// Segmentos articulares de q0 a q1. Con el PTO compartido (Q0.1 a los dos drivers por los relés
// K1 y K2, cada eje con su DIR) X e Y se mueven a la vez, pero reciben los mismos pulsos a la misma
// frecuencia: avanzan juntos a la misma velocidad durante el tramo común y, cuando el de menor
// recorrido llega, se abre su relé y el otro sigue solo. La base (Q0.0) va en paralelo.
function segmentosArticulares(q0, q1, factor) {
  const dX = q1.sX - q0.sX, dY = q1.sY - q0.sY;
  const comun = Math.min(Math.abs(dX), Math.abs(dY));
  if (!$('#m3d-pto').checked || comun < 1e-6 || Math.abs(Math.abs(dX) - Math.abs(dY)) < 1e-6) {
    return [{ desde: q0, hasta: q1, dur: duracion(q0, q1, factor) }];
  }
  const largo = Math.max(Math.abs(dX), Math.abs(dY));
  const medio = {
    theta: q0.theta + (q1.theta - q0.theta) * comun / largo,
    sX: q0.sX + Math.sign(dX) * comun,
    sY: q0.sY + Math.sign(dY) * comun
  };
  return [{ desde: q0, hasta: medio, dur: duracion(q0, medio, factor) }, { desde: medio, hasta: q1, dur: duracion(medio, q1, factor) }];
}

function ejecutar(segmentos) {
  cancelar();
  return new Promise(resolver => {
    sim.plan = { segmentos, i: 0, t0: performance.now(), resolver };
  });
}

function cancelar() {
  if (sim.plan) { const r = sim.plan.resolver; sim.plan = null; r({ detenido: true }); }
}

// Avance de la simulación en cada cuadro
let tPrev = performance.now();
function paso(ahora) {
  if (planta.activa) { sim.plan = null; seguirMuestras(ahora); }
  if (sim.plan) {
    const pl = sim.plan;
    let seg = pl.segmentos[pl.i];
    let t = (ahora - pl.t0) / 1000 / seg.dur;
    while (t >= 1 && pl.i < pl.segmentos.length - 1) {
      pl.t0 += seg.dur * 1000; pl.i++; seg = pl.segmentos[pl.i]; t = (ahora - pl.t0) / 1000 / seg.dur;
    }
    const tt = Math.min(1, t);
    let q;
    if (seg.ruta) {
      const x = tt * (seg.ruta.length - 1), k = Math.floor(x), f = x - k;
      const a = seg.ruta[k], b = seg.ruta[Math.min(k + 1, seg.ruta.length - 1)];
      q = { theta: a.theta + (b.theta - a.theta) * f, sX: a.sX + (b.sX - a.sX) * f, sY: a.sY + (b.sY - a.sY) * f };
    } else {
      q = K.interpolarQ(seg.desde, seg.hasta, tt);
    }
    fijarQ(q);
    if (t >= 1 && pl.i === pl.segmentos.length - 1) { sim.plan = null; pl.resolver({ detenido: false }); }
  }
  // Ejes activos y dirección (para Q0.0-Q0.6)
  const dt = Math.max(1e-3, (ahora - tPrev) / 1000); tPrev = ahora;
  for (const [ej, k] of [['Z', 'theta'], ['X', 'sX'], ['Y', 'sY']]) {
    const v = (sim.q[k] - (sim.qPrev ? sim.qPrev[k] : sim.q[k])) / dt;
    sim.vel[ej] = v;
    sim.activos[ej] = Math.abs(v) > 1e-3;
    if (sim.activos[ej]) sim.dir[ej] = Math.sign(v);
  }
  const real = planta.activa && planta.e && planta.e.salidas;
  if (real) {
    // Con el brazo real, los ejes activos y los sentidos salen de las salidas del PLC
    sim.activos = { Z: real['Q0.0'], X: real['Q0.1'] && real['Q0.5'], Y: real['Q0.1'] && real['Q0.6'] };
    sim.dir = { Z: real['Q0.2'] ? -1 : 1, X: real['Q0.3'] ? -1 : 1, Y: real['Q0.4'] ? -1 : 1 };
  }
  sim.qPrev = Object.assign({}, sim.q);
  visor.actualizar();
  telemetria(ahora);
  requestAnimationFrame(paso);
}

function fijarQ(q) {
  sim.q = { theta: limitar('theta', q.theta), sX: limitar('sX', q.sX), sY: limitar('sY', q.sY) };
}

function moverArticular(q, factor) {
  const destino = { theta: limitar('theta', q.theta), sX: limitar('sX', q.sX), sY: limitar('sY', q.sY) };
  if (planta.activa) return ordenPlanta('mover', destino).then(r => r.error ? { detenido: true, error: r.error } : esperarFin());
  return ejecutar(segmentosArticulares(Object.assign({}, sim.q), destino, factor));
}

async function moverCartesiano(obj) {
  const fk = K.directa(sim.q);
  const pasos = Math.max(20, Math.round(Math.hypot(obj.X - fk.X, obj.Y - fk.Y, obj.Z - fk.Z) / 3));
  const tr = K.trayectoria(sim.q, obj, pasos);
  if (!tr.valida) return { valida: false, motivo: tr.motivo };
  visor.marcarObjetivo(obj);
  if ($('#m3d-pto').checked || planta.activa) {
    const r = await moverArticular(tr.qFin);
    if (r.error) return { valida: false, motivo: r.error };
    return { valida: true, nota: 'Con el PTO compartido X e Y avanzan juntos a la misma velocidad hasta que el de menor recorrido termina: la trayectoria no es recta.' };
  }
  const ruta = [Object.assign({}, sim.q)].concat(tr.qs);
  await ejecutar([{ ruta, dur: Math.max(0.3, duracion(sim.q, tr.qFin) * 1.15) }]);
  return { valida: true, nota: tr.cartesiana ? 'Trayectoria recta en el espacio cartesiano.' : 'Algún punto intermedio era inalcanzable: se interpoló en el espacio articular.' };
}

// Punto alcanzable más cercano a un objetivo cartesiano (con el θ del objetivo): la zona que barren
// los carros es estrecha, así que un X, Y, Z escrito a mano suele quedar fuera
function puntoAlcanzable(obj) {
  const p = K.parametros;
  const iv = K.inversa(obj, { thetaActual: sim.q.theta });
  let theta = iv.soluciones && iv.soluciones.length ? iv.soluciones[0].q.theta : Math.atan2(obj.Y, obj.X) * 180 / Math.PI;
  theta = Math.min(p.thetaMax, Math.max(p.thetaMin, theta));
  let mejor = null;
  const probar = (sX, sY) => {
    if (sX < 0 || sY < 0 || sX > p.recorridoX || sY > p.recorridoY) return;
    const q = { theta, sX, sY }, fk = K.directa(q);
    if (fk.valida === false || K.colision(fk)) return;
    const d = Math.hypot(fk.X - obj.X, fk.Y - obj.Y, fk.Z - obj.Z);
    if (!mejor || d < mejor.d) mejor = { q, d, X: fk.X, Y: fk.Y, Z: fk.Z };
  };
  for (let sX = 0; sX <= p.recorridoX; sX += 2) for (let sY = 0; sY <= p.recorridoY; sY += 2) probar(sX, sY);
  if (mejor) {
    const c = mejor.q;
    for (let dx = -2; dx <= 2; dx += 0.25) for (let dy = -2; dy <= 2; dy += 0.25) probar(c.sX + dx, c.sY + dy);
  }
  return mejor;
}

function fijarGarra(cerrada) {
  sim.garra = !!cerrada;
  const b = $('#m3d-garra');
  b.setAttribute('aria-pressed', String(sim.garra));
  b.textContent = sim.garra ? 'Abrir garra' : 'Cerrar garra';
}

// Homing simulado, como el programa del PLC (subrutina Origen): los carros X e Y a la vez con
// K1 y K2 cerrados, X hacia atrás hasta su final (I0.1) e Y hacia abajo hasta su final (I0.3),
// y después la base hasta el sensor inductivo (I0.0), a velocidad reducida. Ahí los tres
// ejes quedan en 0 pulsos.
async function homing() {
  if (planta.activa) {
    const r = await ordenPlanta(planta.info.ordenes.includes('homing') ? 'homing' : 'iniciar');
    return r.error ? { ok: false, error: r.error } : esperarFin(240);
  }
  if (sim.homing) return { ok: false };
  sim.homing = true;
  try {
    for (const destino of [{ sX: 0, sY: 0 }, { theta: 0 }]) {
      const r = await moverArticular(Object.assign({}, sim.q, destino), 0.5);
      if (r.detenido) return { ok: false, detenido: true };
    }
    sim.referenciado = true;
    sim.traza = [];
    return { ok: true };
  } finally {
    sim.homing = false;
  }
}

function entradas() {
  if (planta.activa && planta.e && planta.e.entradas) return filtrarIO(planta.e.entradas, 'I');
  const q = sim.q;
  return {
    'I0.0': Math.abs(q.theta) < 0.5,
    'I0.1': q.sX <= 0.2,
    'I0.2': q.sX >= P.recorridoX - 0.2,
    'I0.3': q.sY <= 0.2,                    // final Y abajo (homing en el programa Origen)
    'I0.4': q.sY >= P.recorridoY - 0.2      // final Y arriba
  };
}
function salidas() {
  if (planta.activa && planta.e && planta.e.salidas) return filtrarIO(planta.e.salidas, 'Q');
  const a = sim.activos;
  return {
    'Q0.0': a.Z, 'Q0.1': a.X || a.Y, 'Q0.2': sim.dir.Z > 0, 'Q0.3': sim.dir.X > 0, 'Q0.4': sim.dir.Y > 0,
    'Q0.5': a.X, 'Q0.6': a.Y, 'Q0.7': sim.garra
  };
}
const NOMBRES_IO = {
  'I0.0': 'Inductivo θ = 0', 'I0.1': 'Final X atrás', 'I0.2': 'Final X adelante', 'I0.3': 'Final Y abajo', 'I0.4': 'Final Y arriba',
  'Q0.0': 'PTO base (Z)', 'Q0.1': 'PTO X/Y', 'Q0.2': 'DIR base', 'Q0.3': 'DIR X', 'Q0.4': 'DIR Y',
  'Q0.5': 'Relé K1 → X', 'Q0.6': 'Relé K2 → Y', 'Q0.7': 'Garra (K3)',
  'I0.5': 'Selector automático', 'I0.6': 'Paro / reset', 'I0.7': 'Garra / inicio',
  'I1.0': 'Base Q0.2 = 0', 'I1.1': 'Base Q0.2 = 1', 'I1.2': 'X adelante', 'I1.3': 'X atrás',
  'I1.4': 'Y arriba', 'I1.5': 'Y abajo'
};
function filtrarIO(obj, letra) {
  const r = {};
  for (const k of Object.keys(NOMBRES_IO)) if (k[0] === letra && k in obj) r[k] = !!obj[k];
  return r;
}

PLC.registrarSimulador({
  mover: q => { if (q.garra != null) fijarGarra(q.garra); return moverArticular(q); },
  estado: () => ({
    theta_deg: sim.q.theta, sX_mm: sim.q.sX, sY_mm: sim.q.sY, garra: sim.garra,
    referenciado: sim.referenciado, en_movimiento: !!sim.plan,
    pulsos: K.aPulsos(sim.q), entradas: entradas(), salidas: salidas()
  }),
  homing
});

// ================================================================== telemetría
let tTel = 0;
function telemetria(ahora) {
  if (ahora - tTel < 90) return;
  tTel = ahora;
  const fk = K.directa(sim.q);
  const jac = K.jacobiano(sim.q);
  const n = K.aPulsos(sim.q);
  const ent = entradas(), sal = salidas();
  const io = obj => Object.entries(obj).map(([k, v]) =>
    `<span class="${v ? 'on' : ''}" title="${NOMBRES_IO[k]}"><i></i>${k}<small>${NOMBRES_IO[k]}</small></span>`).join('');
  const dir = d => d > 0 ? '+ (1)' : d < 0 ? '− (0)' : '—';
  const pul = v => sim.referenciado ? v.toLocaleString('es-BO') : 'sin ref.';
  const errModelo = visor.errorModelo(fk);
  $('#m3d-telemetria').innerHTML = `
    <div class="m3d-tarjeta"><h3>Articulaciones</h3><dl>
      <dt>θ base</dt><dd>${fmt(sim.q.theta)} °</dd>
      <dt>Carro X</dt><dd>${fmt(sim.q.sX)} mm</dd>
      <dt>Carro Y</dt><dd>${fmt(sim.q.sY)} mm</dd>
      <dt>φ brazo 9</dt><dd>${fmt(fk.phi)} °</dd>
      <dt>Biela 12</dt><dd>${fmt(fk.angBiela)} °</dd>
      ${planta.activa ? `<dt>Origen</dt><dd>${planta.e && planta.e.estimado ? 'estimada (pulsos leídos)' : 'contada en el PLC'}</dd>` : ''}</dl></div>
    <div class="m3d-tarjeta"><h3>Posición de la garra (TCP)</h3><dl>
      <dt>X</dt><dd>${fmt(fk.X)} mm</dd><dt>Y</dt><dd>${fmt(fk.Y)} mm</dd><dt>Z</dt><dd>${fmt(fk.Z)} mm</dd>
      <dt>r · z</dt><dd>${fmt(fk.r)} · ${fmt(fk.z)}</dd>
      <dt>Garra Q0.7</dt><dd>${sim.garra ? 'cerrada (ON)' : 'abierta (OFF)'}</dd></dl></div>
    <div class="m3d-tarjeta"><h3>Pulsos desde el origen</h3><dl>
      <dt>Base (Q0.0)</dt><dd>${pul(n.nZ)}</dd><dt>DIR base Q0.2</dt><dd>${dir(sim.dir.Z)}</dd>
      <dt>X (Q0.1 + K1)</dt><dd>${pul(n.nX)}</dd><dt>DIR X Q0.3</dt><dd>${dir(sim.dir.X)}</dd>
      <dt>Y (Q0.1 + K2)</dt><dd>${pul(n.nY)}</dd><dt>DIR Y Q0.4</dt><dd>${dir(sim.dir.Y)}</dd>
      <dt>Resolución</dt><dd>${T.mmPorPulso} mm · ${T.gradosPorPulso}°</dd></dl></div>
    <div class="m3d-tarjeta"><h3>E/S del PLC (${planta.activa ? 'en vivo' : 'simuladas'})</h3>
      <div class="m3d-io">${io(ent)}${io(sal)}</div></div>
    <div class="m3d-tarjeta"><h3>Análisis</h3><dl>
      <dt>det J</dt><dd>${jac ? (jac.det / 1000).toFixed(1) + '·10³' : '—'}</dd>
      <dt>dφ/dsY</dt><dd>${jac ? jac.dphi_dsY.toFixed(3) + ' °/mm' : '—'}</dd>
      <dt>Transmisión</dt><dd>${jac ? fmt(jac.transmision) + ' °' : '—'}</dd>
      <dt>Modelo vs FK</dt><dd>${errModelo == null ? 'visor sin cargar' : errModelo.toFixed(3) + ' mm'}</dd>
      <dt>Referencia</dt><dd>${sim.referenciado ? 'sí (homing)' : 'no'}</dd></dl></div>`;

  // Indicadores
  const chips = chipsPlanta();
  if (!sim.referenciado) chips.push(['alerta', 'Sin referencia: haga homing']);
  if (sim.homing) chips.push(['', 'Homing en curso']);
  if (ent['I0.1'] || ent['I0.2']) chips.push(['alerta', 'Límite carro X']);
  if (ent['I0.3'] || ent['I0.4']) chips.push(['alerta', 'Límite carro Y']);
  if (Math.abs(sim.q.theta - P.thetaMin) < 0.3 || Math.abs(sim.q.theta - P.thetaMax) < 0.3) chips.push(['alerta', 'Límite θ base']);
  if (K.colision(fk)) chips.push(['alerta', 'Colisión con la mesa']);
  // Con un solo PTO, X e Y pueden moverse a la vez pero solo a la misma velocidad
  const vx = Math.abs(sim.vel.X), vy = Math.abs(sim.vel.Y);
  if (!planta.activa && sim.activos.X && sim.activos.Y && Math.abs(vx - vy) > 0.05 * Math.max(vx, vy)) {
    chips.push(['alerta', 'X e Y a distinta velocidad: el PLC real (un solo PTO) no puede']);
  }
  if (sim.plan || (planta.activa && planta.e && planta.e.en_movimiento)) chips.push(['ok', 'En movimiento']);
  const html = chips.map(([c, t]) => `<span class="m3d-chip ${c}">${t}</span>`).join('');
  if ($('#m3d-chips').innerHTML !== html) $('#m3d-chips').innerHTML = html;

  // Controles articulares sincronizados con el estado (sin pisar al usuario)
  for (const [eje, id] of [['theta', 'theta'], ['sX', 'sx'], ['sY', 'sy']]) {
    const r = $('#m3d-' + id), num = $('#m3d-' + id + '-num');
    if (document.activeElement !== r) r.value = sim.q[eje];
    if (document.activeElement !== num) num.value = fmt(sim.q[eje]);
  }
}

// ================================================================== visor (carga diferida)
const visor = {
  listo: false,
  actualizar() {},
  errorModelo() { return null; },
  marcarObjetivo() {}
};

let cargando = null;
function cargarVisor() {
  if (cargando) return cargando;
  $('#m3d-estado-carga').textContent = 'Cargando three.js y el modelo…';
  $('#m3d-cargar').disabled = true;
  cargando = iniciarVisor().catch(err => {
    console.error(err);
    $('#m3d-estado-carga').textContent = 'No se pudo cargar el visor 3D: ' + err.message;
    $('#m3d-cargar').disabled = false;
    cargando = null;
  });
  return cargando;
}

async function iniciarVisor() {
  const THREE = await import('three');
  const { OrbitControls } = await import('three/addons/controls/OrbitControls.js');
  const { GLTFLoader } = await import('three/addons/loaders/GLTFLoader.js');

  const lienzo = $('#m3d-lienzo');
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  // Mapeo de tonos: evita que las caras de aluminio iluminadas desde arriba salgan blancas
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.05;
  renderer.domElement.setAttribute('aria-label', 'Vista 3D del brazo; arrastre para girar la cámara');
  renderer.domElement.setAttribute('role', 'img');

  const escena = new THREE.Scene();
  const camara = new THREE.PerspectiveCamera(40, 1, 0.01, 20);
  const controles = new OrbitControls(camara, renderer.domElement);
  controles.enableDamping = true;
  controles.target.set(0.3, 0.2, 0);
  controles.maxPolarAngle = Math.PI * 0.495;
  controles.minDistance = 0.3;
  controles.maxDistance = 4;

  escena.add(new THREE.HemisphereLight(0xffffff, 0x8a8f98, 1.6));
  const sol = new THREE.DirectionalLight(0xffffff, 2.0);
  sol.position.set(0.35, 2.2, 0.45);     // casi cenital: la sombra cae debajo del brazo
  sol.castShadow = true;
  sol.shadow.mapSize.set(2048, 2048);
  sol.shadow.radius = 4;
  Object.assign(sol.shadow.camera, { left: -0.9, right: 0.9, top: 0.9, bottom: -0.9, near: 0.1, far: 4 });
  escena.add(sol);

  // Mesa (900 × 640 mm según el manual), con el brazo al centro, y rejilla de 50 mm
  const matMesa = new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0.1 });
  const mesa = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.64), matMesa);
  mesa.rotation.x = -Math.PI / 2;
  mesa.position.set(0, 0, 0);
  mesa.receiveShadow = true;
  escena.add(mesa);
  const rejilla = new THREE.GridHelper(1.8, 36);
  rejilla.position.y = 0.0005;
  rejilla.material.transparent = true;
  rejilla.material.opacity = 0.35;
  escena.add(rejilla);

  function aplicarTema() {
    const css = getComputedStyle(document.documentElement);
    escena.background = new THREE.Color(css.getPropertyValue('--superficie-2').trim() || '#eef0f3');
    const oscuro = escena.background.getHSL({}).l < 0.4;
    matMesa.color.set(oscuro ? '#3a414c' : '#d9dde3');
    rejilla.material.color.set(oscuro ? '#5b6472' : '#9aa3b2');
    sucio = true;
  }
  new MutationObserver(aplicarTema).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', aplicarTema);

  const gltf = await new GLTFLoader().loadAsync(RUTA_GLB);
  const modelo = gltf.scene;
  modelo.traverse(o => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
  escena.add(modelo);
  const nodo = n => { const o = modelo.getObjectByName(n); if (!o) throw new Error('Falta el nodo ' + n + ' en el GLB'); return o; };
  const N = {
    giro: nodo('base_giratoria'), carroX: nodo('carro_x'), carroY: nodo('carro_y'), biela: nodo('biela_12'),
    brazo: nodo('brazo_9'), pinza: nodo('pinza'), varilla: nodo('varilla_13'),
    mordIzq: nodo('mordaza_izq'), mordDer: nodo('mordaza_der'), tcp: nodo('tcp')
  };
  const base = Object.fromEntries(Object.entries(N).map(([k, o]) => [k, o.position.clone()]));

  // Capa: espacio de trabajo (contorno r-z girado en el rango de θ)
  const contorno = K.contorno(40).map(p => new THREE.Vector2(p.r * M, p.z * M));
  const espacio = new THREE.Mesh(
    new THREE.LatheGeometry(contorno, 72, (P.thetaMin + 90) * RAD, (P.thetaMax - P.thetaMin) * RAD),
    new THREE.MeshBasicMaterial({ color: 0xf08a24, transparent: true, opacity: 0.08, side: THREE.DoubleSide, depthWrite: false })
  );
  espacio.visible = false;
  escena.add(espacio);

  // Capa: trayectoria del TCP y marcador del objetivo
  const MAXT = 800;
  const geoTraza = new THREE.BufferGeometry();
  geoTraza.setAttribute('position', new THREE.BufferAttribute(new Float32Array(MAXT * 3), 3));
  geoTraza.setDrawRange(0, 0);
  const traza = new THREE.Line(geoTraza, new THREE.LineBasicMaterial({ color: 0xc2620c }));
  escena.add(traza);
  const objetivo = new THREE.Mesh(new THREE.SphereGeometry(0.006, 16, 12), new THREE.MeshBasicMaterial({ color: 0x2f7fc1 }));
  objetivo.visible = false;
  escena.add(objetivo);

  // Robot (X adelante, Y izquierda, Z arriba) -> glTF (x, y arriba, -z)
  const aEscena = (X, Y, Z) => new THREE.Vector3(X * M, Z * M, -Y * M);

  let sucio = true, visible = true, qDibujada = null;
  const v = new THREE.Vector3();

  function aplicarPose() {
    const fk = K.directa(sim.q);
    if (!fk.valida) return;
    N.giro.rotation.y = sim.q.theta * RAD;
    N.carroX.position.x = base.carroX.x + sim.q.sX * M;
    N.carroY.position.x = base.carroY.x + fk.posBloque1 * M;   // el bloque 1 retrocede al subir el brazo
    N.biela.rotation.z = fk.angBiela * RAD;
    N.brazo.rotation.z = fk.phi * RAD;
    N.pinza.rotation.z = -fk.phi * RAD;        // paralelogramo: la pinza queda horizontal
    N.varilla.rotation.z = fk.phi * RAD;
    // Garra: los dedos giran en el plano horizontal sobre sus pasadores verticales.
    // Cerrada (Q0.7 ON) quedan paralelos; abierta se separan 25° cada uno (SUPUESTO).
    const apertura = sim.garra ? 0 : 25 * RAD;
    N.mordDer.rotation.y = -apertura;   // dedo en +z: girar en -y lo lleva hacia afuera
    N.mordIzq.rotation.y = apertura;
    modelo.updateMatrixWorld(true);
    // Traza
    if ($('#m3d-ver-traza').getAttribute('aria-pressed') === 'true') {
      N.tcp.getWorldPosition(v);
      const ult = sim.traza[sim.traza.length - 1];
      if (!ult || ult.distanceTo(v) > 0.002) {
        sim.traza.push(v.clone());
        if (sim.traza.length > MAXT) sim.traza.shift();
        const arr = geoTraza.attributes.position.array;
        sim.traza.forEach((p, i) => { arr[i * 3] = p.x; arr[i * 3 + 1] = p.y; arr[i * 3 + 2] = p.z; });
        geoTraza.attributes.position.needsUpdate = true;
        geoTraza.setDrawRange(0, sim.traza.length);
      }
    }
  }

  visor.actualizar = () => {
    const clave = sim.q.theta + ',' + sim.q.sX + ',' + sim.q.sY + ',' + sim.garra;
    if (clave !== qDibujada) { qDibujada = clave; aplicarPose(); sucio = true; }
  };
  // Validación: TCP del modelo 3D frente a la cinemática directa
  visor.errorModelo = fk => {
    N.tcp.getWorldPosition(v);
    const e = aEscena(fk.X, fk.Y, fk.Z);
    return v.distanceTo(e) / M;
  };
  visor.marcarObjetivo = obj => { objetivo.position.copy(aEscena(obj.X, obj.Y, obj.Z)); objetivo.visible = true; sucio = true; };
  visor.borrarTraza = () => { sim.traza = []; geoTraza.setDrawRange(0, 0); sucio = true; };
  // Imagen PNG de la vista actual (para informes)
  visor.captura = () => { renderer.render(escena, camara); return renderer.domElement.toDataURL('image/png'); };
  // Cámara libre (depuración): posición y objetivo en metros
  visor.camara = (pos, obj) => {
    anim = null;
    camara.position.set(...pos);
    controles.target.set(...obj);
    controles.update();
    sucio = true;
  };

  // Vistas rápidas con transición suave
  const VISTAS = {
    iso: [1.05, 0.8, 0.95], frontal: [1.45, 0.35, 0.0], lateral: [0.3, 0.3, 1.4], superior: [0.1, 1.4, 0.001]
  };
  let anim = null;
  function irAVista(nombre) {
    const destino = new THREE.Vector3(...VISTAS[nombre]);
    const objetivo = nombre === 'superior' ? new THREE.Vector3(0.1, 0, 0) : new THREE.Vector3(0.3, 0.2, 0);
    anim = { desde: camara.position.clone(), hasta: destino, t0: performance.now(), tDesde: controles.target.clone(), objetivo };
  }
  document.querySelectorAll('[data-vista]').forEach(b => b.addEventListener('click', () => irAVista(b.dataset.vista)));
  camara.position.set(...VISTAS.iso);

  $('#m3d-ver-espacio').addEventListener('click', e => {
    espacio.visible = !espacio.visible;
    e.currentTarget.setAttribute('aria-pressed', String(espacio.visible));
    sucio = true;
  });
  $('#m3d-ver-traza').addEventListener('click', e => {
    const on = e.currentTarget.getAttribute('aria-pressed') !== 'true';
    e.currentTarget.setAttribute('aria-pressed', String(on));
    traza.visible = on;
    if (!on) visor.borrarTraza();
    sucio = true;
  });

  controles.addEventListener('change', () => { sucio = true; });
  function ajustar() {
    const w = lienzo.clientWidth, h = lienzo.clientHeight;
    renderer.setSize(w, h, false);
    camara.aspect = w / h;
    camara.updateProjectionMatrix();
    sucio = true;
  }
  new ResizeObserver(ajustar).observe(lienzo);
  new IntersectionObserver(e => { visible = e[0].isIntersecting; }).observe(lienzo);

  $('#m3d-carga').remove();
  lienzo.appendChild(renderer.domElement);
  aplicarTema();
  ajustar();
  aplicarPose();
  visor.listo = true;

  (function dibujar(ahora) {
    if (anim) {
      const t = Math.min(1, (ahora - anim.t0) / 600), w = t * t * (3 - 2 * t);
      camara.position.lerpVectors(anim.desde, anim.hasta, w);
      controles.target.lerpVectors(anim.tDesde, anim.objetivo, w);
      if (t >= 1) anim = null;
      sucio = true;
    }
    controles.update();
    if (sucio && visible) { renderer.render(escena, camara); sucio = false; }
    requestAnimationFrame(dibujar);
  })(performance.now());
}

// ================================================================== controles
function prepararControles() {
  for (const [eje, id] of [['theta', 'theta'], ['sX', 'sx'], ['sY', 'sy']]) {
    const r = $('#m3d-' + id), num = $('#m3d-' + id + '-num');
    for (const el of [r, num]) { el.min = LIMITES[eje][0]; el.max = LIMITES[eje][1]; }
    // Deslizador: movimiento directo (jog). Número: movimiento animado al soltar.
    r.addEventListener('input', () => { if (planta.activa) return; cancelar(); fijarQ(Object.assign({}, sim.q, { [eje]: Number(r.value) })); });
    r.addEventListener('change', () => { if (planta.activa) moverArticular(Object.assign({}, sim.q, { [eje]: Number(r.value) })); });
    num.addEventListener('change', () => {
      const val = Number(num.value);
      if (!isFinite(val)) return;
      moverArticular(Object.assign({}, sim.q, { [eje]: val }));
    });
  }
  $('#m3d-garra').addEventListener('click', () => garra(!sim.garra));
  $('#m3d-homing').addEventListener('click', () => homing());
  $('#m3d-detener').addEventListener('click', () => {
    detenerSecuencia = true; cancelar();
    if (planta.activa) ordenPlanta(planta.info.ordenes.includes('detener') ? 'detener' : 'emergencia');
  });
  const vel = $('#m3d-velocidad');
  vel.addEventListener('input', () => { $('#m3d-velocidad-txt').textContent = vel.value + ' mm/s'; });

  // Pestañas (con flechas del teclado)
  const tabs = [...document.querySelectorAll('#modelo3d [role="tab"]')];
  function activar(tab) {
    tabs.forEach(t => {
      const sel = t === tab;
      t.setAttribute('aria-selected', String(sel));
      t.tabIndex = sel ? 0 : -1;
      document.getElementById(t.getAttribute('aria-controls')).hidden = !sel;
    });
    if (tab.id === 'tab-cartesiano') usarActual(false);
  }
  tabs.forEach((t, i) => {
    t.addEventListener('click', () => activar(t));
    t.addEventListener('keydown', e => {
      const d = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!d) return;
      const sig = tabs[(i + d + tabs.length) % tabs.length];
      sig.focus(); activar(sig); e.preventDefault();
    });
  });

  // Cartesiano
  function usarActual(siempre) {
    const fk = K.directa(sim.q);
    for (const k of ['x', 'y', 'z']) {
      const el = $('#m3d-' + k);
      if (siempre || el.value === '') el.value = fmt(fk[k.toUpperCase()], 0);
    }
  }
  $('#m3d-usar-actual').addEventListener('click', () => usarActual(true));
  $('#m3d-form-xyz').addEventListener('submit', async e => {
    e.preventDefault();
    const obj = { X: Number($('#m3d-x').value), Y: Number($('#m3d-y').value), Z: Number($('#m3d-z').value) };
    const msg = $('#m3d-msg-xyz');
    msg.className = 'm3d-mensaje'; msg.textContent = 'Moviendo…';
    const r = await moverCartesiano(obj);
    if (!r.valida) {
      msg.className = 'm3d-mensaje error'; msg.setAttribute('role', 'alert');
      msg.textContent = r.motivo;
      const c = /Inalcanzable/.test(r.motivo) && puntoAlcanzable(obj);
      if (c) {
        msg.textContent += ` El punto alcanzable más cercano es X ${fmt(c.X, 0)}, Y ${fmt(c.Y, 0)}, Z ${fmt(c.Z, 0)} mm (a ${fmt(c.d, 0)} mm). `;
        const b = document.createElement('button');
        b.type = 'button'; b.className = 'boton boton-chico'; b.textContent = 'Usar ese punto';
        b.addEventListener('click', () => {
          $('#m3d-x').value = fmt(c.X, 0); $('#m3d-y').value = fmt(c.Y, 0); $('#m3d-z').value = fmt(c.Z, 0);
          msg.textContent = ''; msg.className = 'm3d-mensaje';
        });
        msg.appendChild(b);
      }
      return;
    }
    msg.setAttribute('role', 'status');
    msg.className = 'm3d-mensaje ok';
    const fk = K.directa(sim.q);
    msg.textContent = `${r.nota} Llegó a X ${fmt(fk.X)}, Y ${fmt(fk.Y)}, Z ${fmt(fk.Z)} mm.`;
  });

  // Conexión
  $('#m3d-modo').addEventListener('change', async e => {
    if (e.target.value === 'planta') {
      try { await activarPlanta($('#m3d-url').value.trim()); }
      catch (err) { e.target.value = 'simulacion'; mensajePlanta(err.message, true); }
    } else desactivarPlanta();
  });
  $('#m3d-url').addEventListener('change', e => { if (!planta.activa) PLC.configurar({ url: e.target.value.trim() }); });
  $('#m3d-mando').addEventListener('change', async e => {
    const si = e.target.checked;
    if (si && !confirm('Va a mandar el brazo REAL desde esta página. ¿Hay alguien junto a la parada de emergencia y el área está despejada?')) { e.target.checked = false; return; }
    try { await PLC.mando(si); mensajePlanta(si ? 'Mando habilitado.' : 'Mando deshabilitado.'); }
    catch (err) { e.target.checked = false; mensajePlanta(err.message, true); }
  });
  $('#m3d-planta-ordenes').addEventListener('click', e => {
    const b = e.target.closest('button[data-orden]');
    if (b) ordenPlanta(b.dataset.orden);
  });
  $('#m3d-cal-btn').addEventListener('click', async () => {
    const ang = Number($('#m3d-cal-ang').value);
    if (!isFinite(ang) || !ang) return mensajePlanta('Escriba el ángulo medido de la base', true);
    try {
      const r = await PLC.calibrarBase(ang);
      mensajePlanta(`Base calibrada: ${r.pulsosPorGrado.toFixed(2)} pulsos/° (reducción ≈ ${r.reduccion.toFixed(1)}:1). Se guardó en calibracion.json.`);
      planta.info = await PLC.info(); renderPlanta();
    } catch (err) { mensajePlanta(err.message, true); }
  });
  const hz = $('#m3d-hz');
  const txtHz = () => { $('#m3d-hz-txt').textContent = `${hz.value} Hz · ${fmt(hz.value / (1 / T.mmPorPulso), 0)} mm/s`; };
  hz.addEventListener('input', txtHz);
  hz.addEventListener('change', () => ordenPlanta('velocidad', { hz: Number(hz.value) }));
  txtHz();
  $('#m3d-probar').addEventListener('click', async () => {
    const out = $('#m3d-respuesta');
    try { out.textContent = JSON.stringify(await PLC.leerEstado(), (k, v) => typeof v === 'number' ? Math.round(v * 1000) / 1000 : v, 2); }
    catch (err) { out.textContent = 'Error: ' + err.message; }
  });

  prepararSecuencias();
}

// ================================================================== secuencias pick & place
let secuencia = [];
let detenerSecuencia = false;

function guardarSecuencia() {
  try { localStorage.setItem(CLAVE_SEQ, JSON.stringify(secuencia)); } catch (e) { /* sin almacenamiento */ }
}
function cargarSecuencia() {
  try { secuencia = JSON.parse(localStorage.getItem(CLAVE_SEQ) || '[]').filter(p => isFinite(p.theta) && isFinite(p.sX) && isFinite(p.sY)); }
  catch (e) { secuencia = []; }
}

function renderSecuencia(activo) {
  const ol = $('#m3d-lista');
  if (!secuencia.length) { ol.innerHTML = '<li class="vacio-lista">Sin puntos. Mueva el brazo y pulse “Grabar punto”.</li>'; return; }
  ol.innerHTML = secuencia.map((p, i) => `<li class="${i === activo ? 'activo' : ''}">
      <span class="n">${i + 1}</span>
      <span>θ ${fmt(p.theta)}° · X ${fmt(p.sX)} · Y ${fmt(p.sY)} · ${p.garra ? 'cierra' : 'abre'}</span>
      <span class="m3d-vistas">
        <button type="button" class="boton boton-chico" data-ir="${i}" aria-label="Ir al punto ${i + 1}">Ir</button>
        <button type="button" class="boton boton-chico" data-quitar-punto="${i}" aria-label="Quitar el punto ${i + 1}">✕</button>
      </span></li>`).join('');
}

function descargar(nombre, tipo, texto) {
  const url = URL.createObjectURL(new Blob([texto], { type: tipo }));
  const a = document.createElement('a');
  a.href = url; a.download = nombre;
  document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Tabla de pulsos/dirección por eje para programar el PLC (DIR = 1 en sentido positivo: SUPUESTO).
// X e Y comparten el PTO de Q0.1: primero un tramo común con K1 y K2 cerrados (los dos ejes reciben
// los mismos pulsos) y luego un tramo con solo el relé del eje de mayor recorrido.
function csvPulsos() {
  const filas = [['paso', 'theta_deg', 'carro_x_mm', 'carro_y_mm', 'garra_Q0.7',
    'pulsos_abs_base', 'pulsos_abs_x', 'pulsos_abs_y',
    'dpulsos_base_Q0.0', 'dir_base_Q0.2', 'dpulsos_x', 'dir_x_Q0.3', 'dpulsos_y', 'dir_y_Q0.4',
    'Q0.1_tramo_comun_K1+K2', 'Q0.1_tramo_solo_K1_x', 'Q0.1_tramo_solo_K2_y',
    'X_mm', 'Y_mm', 'Z_mm']];
  let prev = { nZ: 0, nX: 0, nY: 0 };
  secuencia.forEach((p, i) => {
    const n = K.aPulsos(p), fk = K.directa(p);
    const d = { Z: n.nZ - prev.nZ, X: n.nX - prev.nX, Y: n.nY - prev.nY };
    filas.push([i + 1, fmt(p.theta, 2), fmt(p.sX, 2), fmt(p.sY, 2), p.garra ? 1 : 0, n.nZ, n.nX, n.nY,
      Math.abs(d.Z), d.Z >= 0 ? 1 : 0, Math.abs(d.X), d.X >= 0 ? 1 : 0, Math.abs(d.Y), d.Y >= 0 ? 1 : 0,
      Math.min(Math.abs(d.X), Math.abs(d.Y)),
      Math.max(0, Math.abs(d.X) - Math.abs(d.Y)), Math.max(0, Math.abs(d.Y) - Math.abs(d.X)),
      fmt(fk.X), fmt(fk.Y), fmt(fk.Z)]);
    prev = n;
  });
  return filas.map(f => f.join(',')).join('\r\n') + '\r\n';
}

async function reproducir() {
  if (!secuencia.length) return;
  detenerSecuencia = false;
  const msg = $('#m3d-msg-seq');
  for (let i = 0; i < secuencia.length; i++) {
    if (detenerSecuencia) break;
    renderSecuencia(i);
    msg.textContent = `Punto ${i + 1} de ${secuencia.length}`;
    const r = await PLC.enviarPosicion({ theta: secuencia[i].theta, sX: secuencia[i].sX, sY: secuencia[i].sY });
    if (r && r.detenido) break;
    await garra(secuencia[i].garra);
    await new Promise(ok => setTimeout(ok, 350));
  }
  renderSecuencia();
  msg.textContent = detenerSecuencia ? 'Secuencia detenida.' : 'Secuencia terminada.';
}

function prepararSecuencias() {
  cargarSecuencia();
  renderSecuencia();
  $('#m3d-grabar').addEventListener('click', () => {
    secuencia.push({ theta: +sim.q.theta.toFixed(2), sX: +sim.q.sX.toFixed(2), sY: +sim.q.sY.toFixed(2), garra: sim.garra });
    guardarSecuencia(); renderSecuencia();
    $('#m3d-msg-seq').textContent = `Punto ${secuencia.length} grabado.`;
  });
  $('#m3d-reproducir').addEventListener('click', reproducir);
  $('#m3d-borrar').addEventListener('click', () => {
    if (secuencia.length && !confirm('¿Borrar todos los puntos de la secuencia?')) return;
    secuencia = []; guardarSecuencia(); renderSecuencia();
  });
  $('#m3d-lista').addEventListener('click', e => {
    const b = e.target.closest('button');
    if (!b) return;
    if (b.dataset.ir != null) { const p = secuencia[+b.dataset.ir]; moverArticular(p).then(r => { if (!r.detenido) garra(p.garra); }); }
    if (b.dataset.quitarPunto != null) { secuencia.splice(+b.dataset.quitarPunto, 1); guardarSecuencia(); renderSecuencia(); }
  });
  $('#m3d-exp-json').addEventListener('click', () => descargar('secuencia_brazo.json', 'application/json', JSON.stringify({
    formato: 'brazo-xk-js1-1/secuencia', version: 1, generado: new Date().toISOString(),
    transmision: { mmPorPulso: T.mmPorPulso, gradosPorPulso: T.gradosPorPulso, supuesto: true },
    puntos: secuencia
  }, null, 2)));
  $('#m3d-exp-csv').addEventListener('click', () => descargar('secuencia_brazo_pulsos.csv', 'text/csv', csvPulsos()));
  $('#m3d-imp-json').addEventListener('change', async e => {
    const f = e.target.files[0];
    if (!f) return;
    try {
      const datos = JSON.parse(await f.text());
      const puntos = (Array.isArray(datos) ? datos : datos.puntos || [])
        .filter(p => isFinite(p.theta) && isFinite(p.sX) && isFinite(p.sY))
        .map(p => ({ theta: limitar('theta', +p.theta), sX: limitar('sX', +p.sX), sY: limitar('sY', +p.sY), garra: !!p.garra }));
      if (!puntos.length) throw new Error('el archivo no tiene puntos válidos');
      secuencia = puntos; guardarSecuencia(); renderSecuencia();
      $('#m3d-msg-seq').textContent = `${puntos.length} puntos importados.`;
    } catch (err) {
      $('#m3d-msg-seq').textContent = 'No se pudo importar: ' + err.message;
    }
    e.target.value = '';
  });
}

// ================================================================== planta (brazo real)
// La app del gemelo (Python) lee el PLC; aquí se sondea su estado y el modelo lo sigue.
// Mandar el brazo REAL solo se permite desde la app del gemelo (su plantilla pone
// window.GEMELO_CONTROL = true). Desde la página publicada el brazo real solo se observa;
// la simulación sigue teniendo todos los controles.
const CONTROL_REAL = window.GEMELO_CONTROL === true;
const planta = { activa: false, info: null, e: null, sondeo: null, mensaje: '', muestras: [], retardo: 0.25 };

// El PLC se lee unas 8 veces por segundo: el modelo se dibuja un poco en el pasado
// (retardo = intervalo medio entre lecturas) interpolando entre las dos lecturas vecinas,
// así se mueve continuo en vez de a saltos.
function guardarMuestra(q) {
  const m = planta.muestras, t = performance.now();
  m.push({ t, q });
  while (m.length > 12) m.shift();
  if (m.length > 3) {
    const medio = (m[m.length - 1].t - m[0].t) / (m.length - 1) / 1000;
    planta.retardo = Math.min(0.5, Math.max(0.1, medio * 1.3));
  }
}
function seguirMuestras(ahora) {
  const m = planta.muestras;
  if (!m.length) return;
  const t = ahora - planta.retardo * 1000;
  if (t <= m[0].t) return fijarQ(m[0].q);
  for (let i = m.length - 1; i > 0; i--) {
    if (m[i - 1].t <= t) {
      const a = m[i - 1], b = m[i];
      if (t >= b.t) return fijarQ(b.q);
      const f = (t - a.t) / (b.t - a.t);
      return fijarQ({ theta: a.q.theta + (b.q.theta - a.q.theta) * f, sX: a.q.sX + (b.q.sX - a.q.sX) * f, sY: a.q.sY + (b.q.sY - a.q.sY) * f });
    }
  }
}
const dormir = ms => new Promise(ok => setTimeout(ok, ms));

async function activarPlanta(url) {
  const info = await PLC.detectar(url);
  if (!info) throw new Error('No se encontró la app del gemelo en ' + (url || location.origin) + '. ¿Está corriendo gemelo_brazo.py?');
  cancelar();
  PLC.configurar({ modo: 'planta', url: url || '' });
  planta.activa = true;
  planta.info = info;
  $('#m3d-modo').value = 'planta';
  $('#m3d-mando').checked = !!info.mando;
  sondear();
  renderPlanta();
}

function desactivarPlanta() {
  planta.activa = false;
  planta.e = null;
  planta.muestras = [];
  $('#m3d-garra').disabled = false;
  clearTimeout(planta.sondeo);
  PLC.configurar({ modo: 'simulacion' });
  renderPlanta();
}

async function sondear() {
  if (!planta.activa) return;
  try {
    const e = await PLC.leerEstado();
    planta.e = e;
    if (e.theta_deg != null) guardarMuestra({ theta: e.theta_deg, sX: e.sX_mm, sY: e.sY_mm });
    if (e.garra != null && e.garra !== sim.garra) fijarGarra(e.garra);
    sim.referenciado = !!e.referenciado;
    const yo = window.GEMELO_USUARIO ? window.GEMELO_USUARIO.usuario : 'local';
    const propio = !!e.mando && (!e.mando_de || e.mando_de === yo);
    if (propio !== $('#m3d-mando').checked) $('#m3d-mando').checked = propio;
    if (e.perfil && planta.info && e.perfil !== planta.info.perfil) { planta.info = await PLC.info(); renderPlanta(); }
    if (!planta.info.conectado && e.conectado) { planta.info = await PLC.info(); renderPlanta(); }
  } catch (err) {
    planta.e = Object.assign({}, planta.e, { conectado: false, error: 'la app del gemelo no responde' });
    planta.sondeo = setTimeout(sondear, 1500);     // sin app: reintenta despacio
    return;
  }
  planta.sondeo = setTimeout(sondear, 120);
}

// Espera a que el PLC empiece y termine el movimiento pedido
async function esperarFin(maxS = 120) {
  detenerSecuencia = false;
  const t0 = performance.now();
  let visto = false;
  while (performance.now() - t0 < maxS * 1000) {
    await dormir(150);
    if (!planta.activa || detenerSecuencia) return { detenido: true };
    const e = planta.e || {};
    if (e.en_movimiento) visto = true;
    else if (visto || performance.now() - t0 > 900) return { detenido: false };
  }
  return { detenido: true };
}

async function ordenPlanta(nombre, datos) {
  if (!CONTROL_REAL) {
    mensajePlanta('Vista de solo lectura: el brazo real se manda desde la app del gemelo en la PC del laboratorio', true);
    return { error: 'solo lectura' };
  }
  try {
    const r = await PLC.orden(nombre, datos);
    mensajePlanta('Orden enviada: ' + nombre);
    return r;
  } catch (err) {
    mensajePlanta(err.message, true);
    return { error: err.message };
  }
}

async function garra(cerrada) {
  if (!planta.activa) return fijarGarra(cerrada);
  if (!CONTROL_REAL || !planta.info.ordenes.includes('garra')) return mensajePlanta('El programa del PLC no deja mover la garra desde la PC', true);
  await ordenPlanta('garra', { cerrada });
  await dormir(600);
}

function mensajePlanta(texto, error) {
  const m = $('#m3d-msg-planta');
  m.className = 'm3d-mensaje' + (error ? ' error' : ' ok');
  m.textContent = texto;
}

// Con un programa del PLC que no acepta posiciones libres, los controles de posición solo muestran
function bloquearMover(si) {
  const ids = ['#m3d-theta', '#m3d-sx', '#m3d-sy', '#m3d-theta-num', '#m3d-sx-num', '#m3d-sy-num',
    '#m3d-form-xyz button[type="submit"]', '#m3d-reproducir'];
  for (const id of ids) { const el = $(id); if (el) el.disabled = si; }
  const aviso = $('#m3d-aviso-mover');
  if (aviso) aviso.hidden = !si;
}

function renderPlanta() {
  $('#m3d-planta').hidden = !planta.activa;
  // Con el PLC (real o simulado por la app) el tren compartido de X e Y ya lo reproduce el PLC:
  // la casilla solo tiene sentido en la simulación de la página
  const pto = $('#m3d-pto');
  if (pto) pto.closest('label').hidden = planta.activa;
  if (!planta.activa) {
    bloquearMover(false);
    for (const id of ['#m3d-homing', '#m3d-detener']) $(id).disabled = false;
    return;
  }
  const i = planta.info || {};
  $('#m3d-planta-info').textContent = i.conectado
    ? `PLC ${i.simulado ? 'SIMULADO' : 'en ' + i.puerto + ', dirección PPI ' + i.direccion} · programa: ${i.descripcion}`
    : 'La app está corriendo pero todavía no hay conexión con el PLC' + (i.error ? ': ' + i.error : '');
  const ordenes = CONTROL_REAL ? (i.ordenes || []) : [];
  for (const el of ['#m3d-mando-fila', '#m3d-planta-ordenes', '#m3d-cal-base']) $(el).hidden = !CONTROL_REAL;
  $('#m3d-solo-lectura').hidden = CONTROL_REAL;
  for (const id of ['#m3d-homing', '#m3d-detener']) $(id).disabled = !CONTROL_REAL;
  for (const b of document.querySelectorAll('#m3d-planta-ordenes [data-orden]')) b.hidden = !ordenes.includes(b.dataset.orden);
  bloquearMover(!ordenes.includes('mover'));
  const aviso = $('#m3d-aviso-mover');
  if (aviso) {
    if (!aviso.dataset.programa) aviso.dataset.programa = aviso.textContent;
    aviso.textContent = CONTROL_REAL ? aviso.dataset.programa
      : (window.GEMELO_USUARIO ? 'Su usuario es observador: ve el brazo real en vivo pero no puede moverlo.'
        : 'Esta página solo muestra el brazo real. Para probar movimientos vuelva al modo Simulación en la pestaña Conexión.');
  }
  $('#m3d-garra').disabled = !ordenes.includes('garra');
  $('#m3d-planta-vel').hidden = !ordenes.includes('velocidad');
}

function chipsPlanta() {
  if (!planta.activa) return [];
  const e = planta.e || {};
  const c = [];
  if (!e.conectado) c.push(['alerta', 'Sin conexión con el PLC' + (e.error ? ': ' + e.error : '')]);
  else c.push(['ok', 'Brazo real' + (planta.info && planta.info.simulado ? ' (simulado)' : '') + ' · ' + (e.perfil || '')]);
  if (e.conectado && e.estimado) c.push(['alerta', 'Posición estimada']);
  if (e.conectado && planta.info && planta.info.transmision && !planta.info.transmision.base_calibrada) c.push(['alerta', 'Base sin calibrar: el ángulo es aproximado']);
  if (!CONTROL_REAL) c.push(['', 'Solo lectura']);
  else if (e.conectado && !e.mando) c.push(['', 'Mando desde la PC deshabilitado']);
  else if (e.conectado && e.mando_de && window.GEMELO_USUARIO && e.mando_de !== window.GEMELO_USUARIO.usuario) c.push(['alerta', 'Mando en uso por ' + e.mando_de + ': usted solo puede dar paro']);
  if (e.conectado && e.modo_auto === false) c.push(['alerta', 'Selector en manual (I0.5): mando desde el panel']);
  if (e.plc && e.plc.error) c.push(['alerta', 'PLC: ' + e.plc.error]);
  if (e.plc && e.plc.falla_homing) c.push(['alerta', 'Falla de homing: use Rearmar']);
  if (e.plc && e.plc.en_curso && e.plc.en_curso !== 'reposo') c.push(['ok', 'PLC: ' + e.plc.en_curso]);
  return c;
}

// ================================================================== inicio
prepararControles();
fijarGarra(false);
requestAnimationFrame(paso);
$('#m3d-cargar').addEventListener('click', cargarVisor);
new IntersectionObserver((e, obs) => {
  if (e[0].isIntersecting) { obs.disconnect(); cargarVisor(); }
}, { rootMargin: '250px' }).observe($('#modelo3d'));

// Abierta desde la app del gemelo (localhost): modo planta automático
if (/^(localhost|127\.0\.0\.1)$/.test(location.hostname)) {
  PLC.detectar('').then(i => { if (i) activarPlanta('').catch(() => {}); });
}

// Acceso para depuración y pruebas desde la consola
window.__brazo = { sim, K, homing, moverArticular, moverCartesiano, visor, planta };
