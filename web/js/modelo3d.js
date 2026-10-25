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
const RUTA_GLB = 'global/modelo-3d/brazo_xk-js1-1.glb';
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
  dir: { Z: 0, X: 0, Y: 0 },
  aviso: '',
  traza: []
};

const velocidad = () => Number($('#m3d-velocidad').value);       // mm/s; la base va a 1.5 °/s por mm/s
function duracion(q0, q1, factor) {
  const v = velocidad() * (factor || 1);
  return Math.max(0.12, Math.abs(q1.theta - q0.theta) / (1.5 * v), Math.abs(q1.sX - q0.sX) / v, Math.abs(q1.sY - q0.sY) / v);
}

// Segmentos articulares de q0 a q1. Con el PTO compartido (Q0.1) X e Y van por turnos:
// si el brazo sube (sY baja) primero se mueve Y, si baja primero X. La base (Q0.0) va en paralelo.
function segmentosArticulares(q0, q1, factor) {
  if (!$('#m3d-pto').checked || Math.abs(q1.sX - q0.sX) < 1e-6 || Math.abs(q1.sY - q0.sY) < 1e-6) {
    return [{ desde: q0, hasta: q1, dur: duracion(q0, q1, factor) }];
  }
  const primeroY = q1.sY < q0.sY;
  const medio = { theta: q1.theta, sX: primeroY ? q0.sX : q1.sX, sY: primeroY ? q1.sY : q0.sY };
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
    sim.activos[ej] = Math.abs(v) > 1e-3;
    if (sim.activos[ej]) sim.dir[ej] = Math.sign(v);
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
  return ejecutar(segmentosArticulares(Object.assign({}, sim.q), destino, factor));
}

async function moverCartesiano(obj) {
  const fk = K.directa(sim.q);
  const pasos = Math.max(20, Math.round(Math.hypot(obj.X - fk.X, obj.Y - fk.Y, obj.Z - fk.Z) / 3));
  const tr = K.trayectoria(sim.q, obj, pasos);
  if (!tr.valida) return { valida: false, motivo: tr.motivo };
  visor.marcarObjetivo(obj);
  if ($('#m3d-pto').checked) {
    await moverArticular(tr.qFin);
    return { valida: true, nota: 'Con el PTO compartido X e Y se mueven por turnos: la trayectoria no es recta.' };
  }
  const ruta = [Object.assign({}, sim.q)].concat(tr.qs);
  await ejecutar([{ ruta, dur: Math.max(0.3, duracion(sim.q, tr.qFin) * 1.15) }]);
  return { valida: true, nota: tr.cartesiana ? 'Trayectoria recta en el espacio cartesiano.' : 'Algún punto intermedio era inalcanzable: se interpoló en el espacio articular.' };
}

function fijarGarra(cerrada) {
  sim.garra = !!cerrada;
  const b = $('#m3d-garra');
  b.setAttribute('aria-pressed', String(sim.garra));
  b.textContent = sim.garra ? 'Abrir garra' : 'Cerrar garra';
}

// Homing simulado: Y hasta su final superior (I0.3), X hasta el trasero (I0.1)
// y la base hasta el sensor inductivo (I0.0), a velocidad reducida como pide el manual.
async function homing() {
  if (sim.homing) return { ok: false };
  sim.homing = true;
  try {
    for (const destino of [{ sY: 0 }, { sX: 0 }, { theta: 0 }]) {
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
  const q = sim.q;
  return {
    'I0.0': Math.abs(q.theta) < 0.5,
    'I0.1': q.sX <= 0.2,
    'I0.2': q.sX >= P.recorridoX - 0.2,
    'I0.3': q.sY <= 0.2,
    'I0.4': q.sY >= P.recorridoY - 0.2
  };
}
function salidas() {
  const a = sim.activos;
  return {
    'Q0.0': a.Z, 'Q0.1': a.X || a.Y, 'Q0.2': sim.dir.Z > 0, 'Q0.3': sim.dir.X > 0, 'Q0.4': sim.dir.Y > 0,
    'Q0.5': a.X, 'Q0.6': a.Y, 'Q0.7': sim.garra
  };
}
const NOMBRES_IO = {
  'I0.0': 'Inductivo θ = 0', 'I0.1': 'Final X atrás', 'I0.2': 'Final X adelante', 'I0.3': 'Final Y arriba', 'I0.4': 'Final Y abajo',
  'Q0.0': 'PTO base (Z)', 'Q0.1': 'PTO X/Y', 'Q0.2': 'DIR base', 'Q0.3': 'DIR X', 'Q0.4': 'DIR Y',
  'Q0.5': 'Relé K1 → X', 'Q0.6': 'Relé K2 → Y', 'Q0.7': 'Garra (K3)'
};

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
      <dt>Biela 12</dt><dd>${fmt(fk.angBiela)} °</dd></dl></div>
    <div class="m3d-tarjeta"><h3>Posición de la garra (TCP)</h3><dl>
      <dt>X</dt><dd>${fmt(fk.X)} mm</dd><dt>Y</dt><dd>${fmt(fk.Y)} mm</dd><dt>Z</dt><dd>${fmt(fk.Z)} mm</dd>
      <dt>r · z</dt><dd>${fmt(fk.r)} · ${fmt(fk.z)}</dd>
      <dt>Garra Q0.7</dt><dd>${sim.garra ? 'cerrada (ON)' : 'abierta (OFF)'}</dd></dl></div>
    <div class="m3d-tarjeta"><h3>Pulsos desde el origen</h3><dl>
      <dt>Base (Q0.0)</dt><dd>${pul(n.nZ)}</dd><dt>DIR base Q0.2</dt><dd>${dir(sim.dir.Z)}</dd>
      <dt>X (Q0.1 + K1)</dt><dd>${pul(n.nX)}</dd><dt>DIR X Q0.3</dt><dd>${dir(sim.dir.X)}</dd>
      <dt>Y (Q0.1 + K2)</dt><dd>${pul(n.nY)}</dd><dt>DIR Y Q0.4</dt><dd>${dir(sim.dir.Y)}</dd>
      <dt>Resolución</dt><dd>${T.mmPorPulso} mm · ${T.gradosPorPulso}°</dd></dl></div>
    <div class="m3d-tarjeta"><h3>E/S del PLC (simuladas)</h3>
      <div class="m3d-io">${io(ent)}${io(sal)}</div></div>
    <div class="m3d-tarjeta"><h3>Análisis</h3><dl>
      <dt>det J</dt><dd>${jac ? (jac.det / 1000).toFixed(1) + '·10³' : '—'}</dd>
      <dt>dφ/dsY</dt><dd>${jac ? jac.dphi_dsY.toFixed(3) + ' °/mm' : '—'}</dd>
      <dt>Transmisión</dt><dd>${jac ? fmt(jac.transmision) + ' °' : '—'}</dd>
      <dt>Modelo vs FK</dt><dd>${errModelo == null ? 'visor sin cargar' : errModelo.toFixed(3) + ' mm'}</dd>
      <dt>Referencia</dt><dd>${sim.referenciado ? 'sí (homing)' : 'no'}</dd></dl></div>`;

  // Indicadores
  const chips = [];
  if (!sim.referenciado) chips.push(['alerta', 'Sin referencia: haga homing']);
  if (sim.homing) chips.push(['', 'Homing en curso']);
  if (ent['I0.1'] || ent['I0.2']) chips.push(['alerta', 'Límite carro X']);
  if (ent['I0.3'] || ent['I0.4']) chips.push(['alerta', 'Límite carro Y']);
  if (Math.abs(sim.q.theta - P.thetaMin) < 0.3 || Math.abs(sim.q.theta - P.thetaMax) < 0.3) chips.push(['alerta', 'Límite θ base']);
  if (K.colision(fk)) chips.push(['alerta', 'Colisión con la mesa']);
  if (sim.activos.X && sim.activos.Y) chips.push(['alerta', 'X e Y a la vez: no posible con un solo PTO']);
  if (sim.plan) chips.push(['ok', 'En movimiento']);
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
  const sol = new THREE.DirectionalLight(0xffffff, 2.2);
  sol.position.set(0.9, 1.6, 1.1);
  sol.castShadow = true;
  sol.shadow.mapSize.set(2048, 2048);
  sol.shadow.radius = 4;
  Object.assign(sol.shadow.camera, { left: -0.9, right: 0.9, top: 0.9, bottom: -0.9, near: 0.1, far: 4 });
  escena.add(sol);

  // Mesa (900 × 640 mm según el manual) y rejilla de 50 mm
  const matMesa = new THREE.MeshStandardMaterial({ roughness: 0.85, metalness: 0.1 });
  const mesa = new THREE.Mesh(new THREE.PlaneGeometry(0.9, 0.64), matMesa);
  mesa.rotation.x = -Math.PI / 2;
  mesa.position.set(0.2, 0, 0);
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
    mordSup: nodo('mordaza_sup'), mordInf: nodo('mordaza_inf'), tcp: nodo('tcp')
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
    N.carroY.position.x = base.carroY.x + sim.q.sY * M;
    N.biela.rotation.z = fk.angBiela * RAD;
    N.brazo.rotation.z = fk.phi * RAD;
    N.pinza.rotation.z = -fk.phi * RAD;        // paralelogramo: la pinza queda horizontal
    N.varilla.rotation.z = fk.phi * RAD;
    const cierre = sim.garra ? 6 * M : 0;
    N.mordSup.position.y = base.mordSup.y - cierre;
    N.mordInf.position.y = base.mordInf.y + cierre;
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
    iso: [1.05, 0.8, 0.95], frontal: [1.45, 0.35, 0.0], lateral: [0.3, 0.3, 1.4], superior: [0.3, 1.55, 0.001]
  };
  let anim = null;
  function irAVista(nombre) {
    const destino = new THREE.Vector3(...VISTAS[nombre]);
    anim = { desde: camara.position.clone(), hasta: destino, t0: performance.now(), tDesde: controles.target.clone() };
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
      controles.target.lerpVectors(anim.tDesde, new THREE.Vector3(0.3, 0.2, 0), w);
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
    r.addEventListener('input', () => { cancelar(); fijarQ(Object.assign({}, sim.q, { [eje]: Number(r.value) })); });
    num.addEventListener('change', () => {
      const val = Number(num.value);
      if (!isFinite(val)) return;
      moverArticular(Object.assign({}, sim.q, { [eje]: val }));
    });
  }
  $('#m3d-garra').addEventListener('click', () => fijarGarra(!sim.garra));
  $('#m3d-homing').addEventListener('click', () => PLC.homing());
  $('#m3d-detener').addEventListener('click', () => { detenerSecuencia = true; cancelar(); });
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
    if (!r.valida) { msg.className = 'm3d-mensaje error'; msg.textContent = r.motivo; msg.setAttribute('role', 'alert'); return; }
    msg.setAttribute('role', 'status');
    msg.className = 'm3d-mensaje ok';
    const fk = K.directa(sim.q);
    msg.textContent = `${r.nota} Llegó a X ${fmt(fk.X)}, Y ${fmt(fk.Y)}, Z ${fmt(fk.Z)} mm.`;
  });

  // Conexión
  $('#m3d-modo').addEventListener('change', e => PLC.configurar({ modo: e.target.value }));
  $('#m3d-url').addEventListener('change', e => PLC.configurar({ url: e.target.value }));
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

// Tabla de pulsos/dirección por eje para programar el PLC (DIR = 1 en sentido positivo: SUPUESTO)
function csvPulsos() {
  const filas = [['paso', 'theta_deg', 'carro_x_mm', 'carro_y_mm', 'garra_Q0.7',
    'pulsos_abs_base', 'pulsos_abs_x', 'pulsos_abs_y',
    'dpulsos_base_Q0.0', 'dir_base_Q0.2', 'dpulsos_x_Q0.1_K1', 'dir_x_Q0.3', 'dpulsos_y_Q0.1_K2', 'dir_y_Q0.4',
    'X_mm', 'Y_mm', 'Z_mm']];
  let prev = { nZ: 0, nX: 0, nY: 0 };
  secuencia.forEach((p, i) => {
    const n = K.aPulsos(p), fk = K.directa(p);
    const d = { Z: n.nZ - prev.nZ, X: n.nX - prev.nX, Y: n.nY - prev.nY };
    filas.push([i + 1, fmt(p.theta, 2), fmt(p.sX, 2), fmt(p.sY, 2), p.garra ? 1 : 0, n.nZ, n.nX, n.nY,
      Math.abs(d.Z), d.Z >= 0 ? 1 : 0, Math.abs(d.X), d.X >= 0 ? 1 : 0, Math.abs(d.Y), d.Y >= 0 ? 1 : 0,
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
    fijarGarra(secuencia[i].garra);
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
    if (b.dataset.ir != null) { const p = secuencia[+b.dataset.ir]; moverArticular(p).then(() => fijarGarra(p.garra)); }
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

// ================================================================== inicio
prepararControles();
fijarGarra(false);
requestAnimationFrame(paso);
$('#m3d-cargar').addEventListener('click', cargarVisor);
new IntersectionObserver((e, obs) => {
  if (e[0].isIntersecting) { obs.disconnect(); cargarVisor(); }
}, { rootMargin: '250px' }).observe($('#modelo3d'));

// Acceso para depuración y pruebas desde la consola
window.__brazo = { sim, K, homing, moverArticular, moverCartesiano, visor };
