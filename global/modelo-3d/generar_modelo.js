/*
 * Genera el modelo 3D articulado del brazo XK-JS1-1 a escala real (GLB).
 *
 *   node global/modelo-3d/generar_modelo.js
 *
 * Sin dependencias: construye la geometría con primitivas (cajas, cilindros y
 * prismas) a partir de las cotas de web/js/cinematica.js y escribe el glTF
 * binario a mano. Cada pieza móvil es un nodo con el origen en su eje de giro o
 * en su guía lineal; la jerarquía sigue el mecanismo:
 *
 *   brazo_xk_js1_1
 *   ├─ base_fija                       disco inferior 11 (fijo a la mesa)
 *   └─ base_giratoria      R  θ (eje Y del glTF)   disco superior, columna 7, bloque 2, NEMA 17
 *      └─ carro_x          P  sX (eje X)           placas 5 y 10, guías 16, husillos, NEMA 23
 *         ├─ carro_y       P  sY (eje X)           bloque 1, escuadra 6
 *         │  └─ biela_12   R  pasiva (pivote C)
 *         ├─ brazo_9       R  pasiva φ (pivote A)  brazo 9 + escuadra 8
 *         │  └─ pinza      R  -φ (pivote E: queda horizontal)
 *         │     ├─ mordaza_sup / mordaza_inf   garra ON/OFF
 *         │     └─ tcp     punto de trabajo
 *         └─ varilla_13    R  pasiva φ (pivote A')
 *
 * Las bielas pasivas no se animan a mano: la página calcula sus ángulos con la
 * cinemática (web/js/cinematica.js). Unidades del glTF: metros, Y hacia arriba,
 * X hacia adelante con θ = 0. Las cotas marcadas SUPUESTO están en cinematica.js.
 */
const fs = require('fs');
const path = require('path');
const K = require('../../web/js/cinematica.js');

const P = K.parametros, D = K.derivados;
const M = 0.001;   // mm -> m
const SALIDA = path.join(__dirname, 'brazo_xk-js1-1.glb');

// ------------------------------------------------------------------ materiales
const MATERIALES = [
  { name: 'aluminio', pbrMetallicRoughness: { baseColorFactor: [0.80, 0.82, 0.85, 1], metallicFactor: 0.55, roughnessFactor: 0.42 } },
  { name: 'acero', pbrMetallicRoughness: { baseColorFactor: [0.62, 0.65, 0.70, 1], metallicFactor: 0.9, roughnessFactor: 0.25 } },
  { name: 'motor', pbrMetallicRoughness: { baseColorFactor: [0.10, 0.10, 0.11, 1], metallicFactor: 0.3, roughnessFactor: 0.6 } },
  { name: 'acento', pbrMetallicRoughness: { baseColorFactor: [0.76, 0.38, 0.05, 1], metallicFactor: 0.1, roughnessFactor: 0.5 } },
  { name: 'sensor', pbrMetallicRoughness: { baseColorFactor: [0.85, 0.72, 0.30, 1], metallicFactor: 0.8, roughnessFactor: 0.35 } },
  { name: 'goma', pbrMetallicRoughness: { baseColorFactor: [0.18, 0.18, 0.2, 1], metallicFactor: 0, roughnessFactor: 0.9 } }
];
const MAT = Object.fromEntries(MATERIALES.map((m, i) => [m.name, i]));

// ------------------------------------------------------------------ geometría
// Cada pieza acumula triángulos por material: { mat: {pos:[], nor:[]} }
function nuevaGeo() { return {}; }
function tri(geo, mat, a, b, c, n) {
  const g = geo[mat] || (geo[mat] = { pos: [], nor: [] });
  if (!n) {
    const u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]], v = [c[0] - a[0], c[1] - a[1], c[2] - a[2]];
    n = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]];
    const l = Math.hypot(...n) || 1; n = n.map(x => x / l);
  }
  for (const p of [a, b, c]) { g.pos.push(p[0] * M, p[1] * M, p[2] * M); }
  const ns = Array.isArray(n[0]) ? n : [n, n, n];
  for (const x of ns) g.nor.push(...x);
}
function quad(geo, mat, a, b, c, d) { tri(geo, mat, a, b, c); tri(geo, mat, a, c, d); }

// Caja centrada en (cx, cy, cz) con lados (sx, sy, sz) [mm]
function caja(geo, mat, cx, cy, cz, sx, sy, sz) {
  const x0 = cx - sx / 2, x1 = cx + sx / 2, y0 = cy - sy / 2, y1 = cy + sy / 2, z0 = cz - sz / 2, z1 = cz + sz / 2;
  quad(geo, mat, [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1]);
  quad(geo, mat, [x1, y0, z0], [x0, y0, z0], [x0, y1, z0], [x1, y1, z0]);
  quad(geo, mat, [x1, y0, z1], [x1, y0, z0], [x1, y1, z0], [x1, y1, z1]);
  quad(geo, mat, [x0, y0, z0], [x0, y0, z1], [x0, y1, z1], [x0, y1, z0]);
  quad(geo, mat, [x0, y1, z1], [x1, y1, z1], [x1, y1, z0], [x0, y1, z0]);
  quad(geo, mat, [x0, y0, z0], [x1, y0, z0], [x1, y0, z1], [x0, y0, z1]);
}

// Cilindro de radio r entre los puntos a y b (normales suaves en el manto)
function cilindro(geo, mat, a, b, r, seg) {
  const n = seg || 24;
  const eje = [b[0] - a[0], b[1] - a[1], b[2] - a[2]];
  const L = Math.hypot(...eje); const w = eje.map(x => x / L);
  const t = Math.abs(w[1]) < 0.9 ? [0, 1, 0] : [1, 0, 0];
  let u = [w[1] * t[2] - w[2] * t[1], w[2] * t[0] - w[0] * t[2], w[0] * t[1] - w[1] * t[0]];
  const lu = Math.hypot(...u); u = u.map(x => x / lu);
  const v = [w[1] * u[2] - w[2] * u[1], w[2] * u[0] - w[0] * u[2], w[0] * u[1] - w[1] * u[0]];
  const dir = k => { const ang = 2 * Math.PI * k / n; return [0, 1, 2].map(i => Math.cos(ang) * u[i] + Math.sin(ang) * v[i]); };
  for (let k = 0; k < n; k++) {
    const d0 = dir(k), d1 = dir(k + 1);
    const p = (base, d) => [0, 1, 2].map(i => base[i] + r * d[i]);
    const a0 = p(a, d0), a1 = p(a, d1), b0 = p(b, d0), b1 = p(b, d1);
    tri(geo, mat, a0, a1, b1, [d0, d1, d1]);
    tri(geo, mat, a0, b1, b0, [d0, d1, d0]);
    tri(geo, mat, b, b0, b1, w);
    tri(geo, mat, a, a1, a0, w.map(x => -x));
  }
}

// Prisma: polígono convexo en el plano XY [[x, y], ...] (antihorario), extruido de z0 a z1
function prisma(geo, mat, poli, z0, z1) {
  const n = poli.length;
  for (let i = 1; i < n - 1; i++) {
    tri(geo, mat, [poli[0][0], poli[0][1], z1], [poli[i][0], poli[i][1], z1], [poli[i + 1][0], poli[i + 1][1], z1]);
    tri(geo, mat, [poli[0][0], poli[0][1], z0], [poli[i + 1][0], poli[i + 1][1], z0], [poli[i][0], poli[i][1], z0]);
  }
  for (let i = 0; i < n; i++) {
    const p = poli[i], q = poli[(i + 1) % n];
    quad(geo, mat, [p[0], p[1], z0], [q[0], q[1], z0], [q[0], q[1], z1], [p[0], p[1], z1]);
  }
}

// Barra plana con extremos redondeados entre (0,0) y (L,0), ancho w, en z ∈ [z0, z1]
function barra(geo, mat, L, w, z0, z1) {
  const poli = [], r = w / 2, s = 10;
  for (let k = 0; k <= s; k++) { const a = -Math.PI / 2 + Math.PI * k / s; poli.push([L + r * Math.cos(a), r * Math.sin(a)]); }
  for (let k = 0; k <= s; k++) { const a = Math.PI / 2 + Math.PI * k / s; poli.push([r * Math.cos(a), r * Math.sin(a)]); }
  prisma(geo, mat, poli, z0, z1);
}

const pasador = (geo, u, h, z0, z1) => cilindro(geo, 'acero', [u, h, z0], [u, h, z1], 4.5, 16);

// ------------------------------------------------------------------ piezas
const nodos = [];
function nodo(nombre, padre, opciones) {
  const n = Object.assign({ nombre, padre, geo: nuevaGeo(), t: [0, 0, 0], extras: null }, opciones || {});
  nodos.push(n); return n;
}

// Ejes locales: x = adelante (radial), y = arriba, z = lateral
const raiz = nodo('brazo_xk_js1_1', null);

// Base fija: disco inferior y buje
const baseFija = nodo('base_fija', raiz);
cilindro(baseFija.geo, 'aluminio', [0, 0, 0], [0, P.hDiscoInf, 0], P.rDisco, 48);
cilindro(baseFija.geo, 'acero', [0, P.hDiscoInf, 0], [0, P.hDiscoInf + P.hEntreDiscos, 0], 30, 32);

// Base giratoria (θ)
const hSup = P.hDiscoInf + P.hEntreDiscos;                 // cara inferior del disco superior
const hCol = hSup + P.hDiscoSup;                          // pie de la columna
const giro = nodo('base_giratoria', raiz, { extras: { articulacion: 'revoluta', eje: 'y', variable: 'theta' } });
cilindro(giro.geo, 'aluminio', [0, hSup, 0], [0, hCol, 0], P.rDisco, 48);
// Columna 7 en H: dos patas y travesaño (SUPUESTO de forma)
caja(giro.geo, 'aluminio', 0, hCol + P.hColumna / 2, 38.5, 71, P.hColumna, 23);
caja(giro.geo, 'aluminio', 0, hCol + P.hColumna / 2, -38.5, 71, P.hColumna, 23);
caja(giro.geo, 'aluminio', 0, hCol + P.hColumna - 7.5, 0, 71, 15, 100);
caja(giro.geo, 'aluminio', 0, hCol + 5, 0, 90, 10, 120);
// Bloque 2 (fijo) con la tuerca del husillo inferior
caja(giro.geo, 'aluminio', 0, D.hEjeX, 0, P.largoBloque, P.hBloque2, P.anchoBloque);
cilindro(giro.geo, 'motor', [P.largoBloque / 2, D.hEjeX, 0], [P.largoBloque / 2 + 8, D.hEjeX, 0], 24, 24);
// Motor NEMA 17 delante de la columna (fotos f11, f13) con su acople hacia el engranaje, y sensor inductivo
caja(giro.geo, 'motor', 62, hCol + 30, 0, 42, 48, 42);
cilindro(giro.geo, 'acero', [62, hCol, 0], [62, hCol + 6, 0], 13, 20);
cilindro(giro.geo, 'sensor', [-45, hCol, 58], [-45, hCol + 45, 58], 6, 16);

// Bastidor = carro X. Origen: eje del husillo inferior, en la cara interior de la placa 5
const cx = nodo('carro_x', giro, { t: [D.u5_0, D.hEjeX, 0], extras: { articulacion: 'prismatica', eje: 'x', variable: 'sX' } });
const xp10 = -(P.largoGuias - 2 * P.espesorPlaca);        // cara interior de la placa 10
const yPlaca = P.sepNiveles / 2;
caja(cx.geo, 'aluminio', P.espesorPlaca / 2, yPlaca, 0, P.espesorPlaca, 120, 110);
caja(cx.geo, 'aluminio', xp10 - P.espesorPlaca / 2, yPlaca, 0, P.espesorPlaca, 120, 110);
for (const y of [0, P.sepNiveles]) {
  for (const z of [-49, 49]) cilindro(cx.geo, 'acero', [xp10 - P.espesorPlaca, y, z], [P.espesorPlaca, y, z], 8, 20);
  cilindro(cx.geo, 'acero', [xp10 - P.espesorPlaca, y, 0], [P.espesorPlaca, y, 0], 8, 20);   // husillo
}
// Motores NEMA 23 con adaptadores 3 (arriba Y, abajo X); separados para que no se crucen (SUPUESTO)
const xm = xp10 - P.espesorPlaca;
for (const [y, nombre] of [[-8, 'X'], [P.sepNiveles + 8, 'Y']]) {
  caja(cx.geo, 'aluminio', xm - 25, y, 0, 50, 57, 57);
  caja(cx.geo, 'motor', xm - 50 - 38, y, 0, 76, 56, 56);
  caja(cx.geo, 'acero', xm - 50 - 77, y, 0, 2, 38, 38);     // tapa trasera del motor
}
// Barras de finales de carrera en las placas 5 y 10 (dos interruptores cada una)
for (const x of [P.espesorPlaca / 2, xp10 - P.espesorPlaca / 2]) {
  caja(cx.geo, 'aluminio', x, yPlaca, -62, 16, 110, 8);
  for (const y of [0, P.sepNiveles]) caja(cx.geo, 'motor', x + (x > 0 ? -12 : 12), y, -62, 12, 18, 10);
}
// Horquilla 17 en la cara delantera de la placa 5 (pivote A, a la altura del husillo superior)
const xH = P.espesorPlaca, largoH = P.uA - P.espesorPlaca + 12;
caja(cx.geo, 'aluminio', xH + largoH / 2, P.dhA, -24, largoH, 34, 6);
caja(cx.geo, 'aluminio', xH + largoH / 2, P.dhA, 24, largoH, 34, 6);
pasador(cx.geo, P.uA, P.dhA, -32, 32);
// Soporte sobre la placa 5 y poste 14 del pivote A' (paralelogramo)
const yTopPlaca = P.sepNiveles / 2 + 60;
caja(cx.geo, 'aluminio', (P.uA + 6) / 2, yTopPlaca + 5, 40, P.uA + 6, 10, 20);
cilindro(cx.geo, 'acero', [P.uA, yTopPlaca + 10, 40], [P.uA, P.dhA + P.L14, 40], 5, 16);

// Carro Y: bloque 1 con la escuadra 6. Origen: cara delantera del bloque 1 sobre el eje inferior
const xBloque1_0 = -(D.carreraLibre - P.holgura);
const cyN = nodo('carro_y', cx, { t: [xBloque1_0, 0, 0], extras: { articulacion: 'prismatica', eje: 'x', variable: 'sY' } });
caja(cyN.geo, 'aluminio', -P.largoBloque / 2, P.sepNiveles, 0, P.largoBloque, P.hBloque1, P.anchoBloque);
cilindro(cyN.geo, 'motor', [0, P.sepNiveles, 0], [8, P.sepNiveles, 0], 24, 24);
const yTop1 = P.hBloque2 / 2 + P.hBloque1;            // cara superior del bloque 1 (relativa al eje inferior)
const hCrel = D.hCabs - D.hEjeX;                       // pivote C (relativo al eje inferior)
for (const z0 of [-17, 6]) {
  prisma(cyN.geo, 'aluminio', [[P.uCBloque - 24.5, yTop1], [P.uCBloque + 24.5, yTop1],
    [P.uCBloque + 12, yTop1 + P.hC], [P.uCBloque - 12, yTop1 + P.hC]], z0, z0 + 11);
}
pasador(cyN.geo, P.uCBloque, hCrel, -20, 20);

// Biela 12: origen en C, a lo largo de +x hasta B
const biela = nodo('biela_12', cyN, { t: [P.uCBloque, hCrel, 0], extras: { articulacion: 'revoluta', eje: 'z', pasiva: true } });
barra(biela.geo, 'aluminio', P.L12, 24, -5.5, 5.5);

// Brazo 9 + escuadra 8: origen en A, brazo a lo largo de +x
const brazo = nodo('brazo_9', cx, { t: [P.uA, P.dhA, 0], extras: { articulacion: 'revoluta', eje: 'z', pasiva: true, variable: 'phi' } });
barra(brazo.geo, 'aluminio', P.L9, 46, -5, 5);
const bU = P.a * Math.cos(P.beta * Math.PI / 180), bH = P.a * Math.sin(P.beta * Math.PI / 180);
for (const z0 of [-17, 6]) prisma(brazo.geo, 'aluminio', [[20, 0], [125, 0], [bU + 12, bH], [bU - 12, bH]], z0, z0 + 11);
pasador(brazo.geo, bU, bH, -20, 20);
pasador(brazo.geo, P.L9, 0, -32, 32);

// Pinza: origen en E, contrarrota -φ para quedar horizontal
const pinza = nodo('pinza', brazo, { t: [P.L9, 0, 0], extras: { articulacion: 'revoluta', eje: 'z', pasiva: true, nota: 'rotación = -phi (paralelogramo)' } });
// Cuerpo 4: E en su parte trasera, a media altura (sube hCuerpo - pinzaBajoE y baja pinzaBajoE)
const yCuerpo = (P.hCuerpoPinza - 2 * P.pinzaBajoE) / 2;
caja(pinza.geo, 'aluminio', 35, yCuerpo, 0, 80, P.hCuerpoPinza, 55);
cilindro(pinza.geo, 'motor', [10, yCuerpo, 28], [60, yCuerpo, 28], 13, 20);   // solenoide
const yTopCuerpo = P.hCuerpoPinza - P.pinzaBajoE;
caja(pinza.geo, 'aluminio', 0, yTopCuerpo + 5, 34, 16, 10, 20);
cilindro(pinza.geo, 'acero', [0, yTopCuerpo, 40], [0, P.L14, 40], 5, 16);
const largoMordaza = 2 * (P.dg - 75);
for (const [nombre, s] of [['mordaza_sup', 1], ['mordaza_inf', -1]]) {
  const m = nodo(nombre, pinza, { t: [75, -P.hg + s * 14, 0], extras: { articulacion: 'garra', abierta_mm: s * 8 } });
  caja(m.geo, 'aluminio', largoMordaza / 2, 0, 0, largoMordaza, 8, 30);
  caja(m.geo, 'goma', largoMordaza - 12, -s * 5, 0, 24, 3, 30);
}
nodo('tcp', pinza, { t: [P.dg, -P.hg, 0] });

// Varilla 13: origen en A', paralela al brazo
const varilla = nodo('varilla_13', cx, { t: [P.uA, P.dhA + P.L14, 40], extras: { articulacion: 'revoluta', eje: 'z', pasiva: true } });
cilindro(varilla.geo, 'aluminio', [0, 0, 0], [P.L9, 0, 0], 5.5, 16);
cilindro(varilla.geo, 'acero', [0, 0, -6], [0, 0, 6], 7, 16);
cilindro(varilla.geo, 'acero', [P.L9, 0, -6], [P.L9, 0, 6], 7, 16);

// ------------------------------------------------------------------ glTF binario
function escribirGlb() {
  const gltf = {
    asset: { version: '2.0', generator: 'generar_modelo.js (Brazo 4 GDL, UMSA)' },
    scene: 0, scenes: [{ name: 'brazo', nodes: [0] }],
    nodes: [], meshes: [], materials: MATERIALES, accessors: [], bufferViews: [], buffers: []
  };
  const trozos = []; let largo = 0;
  function vista(arr, target) {
    const buf = Buffer.from(arr.buffer, arr.byteOffset, arr.byteLength);
    const relleno = (4 - (largo % 4)) % 4;
    if (relleno) { trozos.push(Buffer.alloc(relleno)); largo += relleno; }
    gltf.bufferViews.push({ buffer: 0, byteOffset: largo, byteLength: buf.length, target });
    trozos.push(buf); largo += buf.length;
    return gltf.bufferViews.length - 1;
  }
  nodos.forEach((n, i) => {
    const g = { name: n.nombre };
    if (n.t.some(v => v)) g.translation = n.t.map(v => v * M);
    if (n.extras) g.extras = n.extras;
    const hijos = nodos.map((x, j) => x.padre === n ? j : -1).filter(j => j >= 0);
    if (hijos.length) g.children = hijos;
    const prims = [];
    for (const [mat, data] of Object.entries(n.geo)) {
      const pos = new Float32Array(data.pos), nor = new Float32Array(data.nor);
      const min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
      for (let k = 0; k < pos.length; k += 3) for (let c = 0; c < 3; c++) { min[c] = Math.min(min[c], pos[k + c]); max[c] = Math.max(max[c], pos[k + c]); }
      gltf.accessors.push({ bufferView: vista(pos, 34962), componentType: 5126, count: pos.length / 3, type: 'VEC3', min, max });
      const ip = gltf.accessors.length - 1;
      gltf.accessors.push({ bufferView: vista(nor, 34962), componentType: 5126, count: nor.length / 3, type: 'VEC3' });
      prims.push({ attributes: { POSITION: ip, NORMAL: ip + 1 }, material: MAT[mat] });
    }
    if (prims.length) { gltf.meshes.push({ name: n.nombre, primitives: prims }); g.mesh = gltf.meshes.length - 1; }
    gltf.nodes.push(g);
  });
  const bin = Buffer.concat(trozos);
  gltf.buffers.push({ byteLength: bin.length });
  let json = Buffer.from(JSON.stringify(gltf), 'utf8');
  json = Buffer.concat([json, Buffer.alloc((4 - json.length % 4) % 4, 0x20)]);
  const binPad = Buffer.concat([bin, Buffer.alloc((4 - bin.length % 4) % 4)]);
  const cab = Buffer.alloc(12);
  cab.writeUInt32LE(0x46546C67, 0); cab.writeUInt32LE(2, 4);
  cab.writeUInt32LE(12 + 8 + json.length + 8 + binPad.length, 8);
  const c1 = Buffer.alloc(8); c1.writeUInt32LE(json.length, 0); c1.writeUInt32LE(0x4E4F534A, 4);
  const c2 = Buffer.alloc(8); c2.writeUInt32LE(binPad.length, 0); c2.writeUInt32LE(0x004E4942, 4);
  fs.writeFileSync(SALIDA, Buffer.concat([cab, c1, json, c2, binPad]));
  const tris = nodos.reduce((s, n) => s + Object.values(n.geo).reduce((t, d) => t + d.pos.length / 9, 0), 0);
  console.log(`${path.basename(SALIDA)}: ${nodos.length} nodos, ${tris} triángulos, ${(fs.statSync(SALIDA).size / 1024).toFixed(0)} KB`);
}

escribirGlb();
