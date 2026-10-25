/*
 * Pruebas de la cinemática (web/js/cinematica.js) y exportación de parámetros.
 *
 *   node semestres/2026_II/modelo-3d/cinematica/pruebas_cinematica.js
 *
 * 1. Directa -> inversa -> directa en una rejilla de carreras (error en mm).
 * 2. Jacobiano analítico frente a diferencias finitas.
 * 3. Rangos de φ, r, z, singularidades y ángulo de transmisión.
 * 4. Escribe parametros.json (lo leen los scripts de Python y MATLAB) y
 *    tabla_cinematica.csv (para validar contra la planta).
 */
const fs = require('fs');
const path = require('path');
const K = require('../../../../web/js/cinematica.js');

const p = K.parametros;
let fallos = 0;
const ok = (cond, msg) => { if (!cond) { fallos++; console.log('  FALLA: ' + msg); } };

// ------------------------------------------------------------------ 1. ida y vuelta
let errMax = 0, n = 0;
for (let i = 0; i <= 20; i++) {
  for (let j = 0; j <= 20; j++) {
    for (const theta of [-150, -30, 0, 45, 170]) {
      const q = { theta, sX: p.recorridoX * i / 20, sY: p.recorridoY * j / 20 };
      const fk = K.directa(q);
      ok(fk.valida, 'directa no válida en ' + JSON.stringify(q));
      const ik = K.inversa({ X: fk.X, Y: fk.Y, Z: fk.Z }, { thetaActual: theta });
      // La IK puede rechazar por colisión; se compara con la solución de la rama real
      const sol = ik.soluciones.find(s => s.rama === 'adelante' && Math.abs(s.q.theta - theta) < 1e-6);
      ok(!!sol, 'inversa sin solución en ' + JSON.stringify(q));
      if (!sol) continue;
      const e = Math.max(Math.abs(sol.q.sX - q.sX), Math.abs(sol.q.sY - q.sY), Math.abs(sol.q.theta - q.theta));
      errMax = Math.max(errMax, e); n++;
    }
  }
}
console.log(`1. Ida y vuelta: ${n} puntos, error máximo en articulaciones = ${errMax.toExponential(2)}`);
ok(errMax < 1e-6, 'error de ida y vuelta demasiado grande');

// ------------------------------------------------------------------ 2. jacobiano
let errJ = 0;
const h = 1e-4;
for (const q of [{ theta: 20, sX: 50, sY: 30 }, { theta: -60, sX: 120, sY: 100 }, { theta: 90, sX: 10, sY: 160 }]) {
  const J = K.jacobiano(q).J;
  const vars = [['theta', Math.PI / 180], ['sX', 1], ['sY', 1]];
  vars.forEach(([v, esc], c) => {
    const qa = Object.assign({}, q), qb = Object.assign({}, q);
    qa[v] += h; qb[v] -= h;
    const fa = K.directa(qa), fb = K.directa(qb);
    const num = ['X', 'Y', 'Z'].map(k => (fa[k] - fb[k]) / (2 * h) / esc);
    num.forEach((x, f) => { errJ = Math.max(errJ, Math.abs(x - J[f][c])); });
  });
}
console.log(`2. Jacobiano analítico vs numérico: error máximo = ${errJ.toExponential(2)}`);
ok(errJ < 1e-4, 'jacobiano no coincide');

// ------------------------------------------------------------------ 3. rangos
const pts = K.espacioTrabajo(60);
const rango = k => [Math.min(...pts.map(x => x[k])), Math.max(...pts.map(x => x[k]))];
const phis = [0, p.recorridoY].map(sY => K.directa({ theta: 0, sX: 0, sY }).phi);
const jacs = [];
for (let j = 0; j <= 100; j++) jacs.push(K.jacobiano({ theta: 0, sX: 0, sY: p.recorridoY * j / 100 }));
const dets = jacs.map(x => Math.abs(x.det));
const mus = jacs.map(x => x.transmision);
const choques = pts.filter(x => x.choca).length;
console.log('3. Rangos:');
console.log(`   φ brazo:  ${phis[0].toFixed(1)}° (sY = 0) a ${phis[1].toFixed(1)}° (sY = ${p.recorridoY})`);
console.log(`   r TCP:    ${rango('r').map(v => v.toFixed(1)).join(' a ')} mm`);
console.log(`   z TCP:    ${rango('z').map(v => v.toFixed(1)).join(' a ')} mm`);
console.log(`   |det J| mínimo: ${Math.min(...dets).toFixed(0)} mm²/rad (sin singularidades si > 0)`);
console.log(`   transmisión biela 12: ${Math.min(...mus).toFixed(1)}° a ${Math.max(...mus).toFixed(1)}°`);
console.log(`   puntos con choque con la mesa: ${choques} de ${pts.length}`);
console.log(`   resolución: ${K.transmision.mmPorPulso} mm/pulso (X, Y), ${K.transmision.gradosPorPulso} °/pulso (base)`);
ok(Math.min(...dets) > 1, 'hay una singularidad dentro del recorrido');

// ------------------------------------------------------------------ 4. archivos
const dir = __dirname;
fs.writeFileSync(path.join(dir, 'parametros.json'), JSON.stringify({
  nota: 'Generado por pruebas_cinematica.js desde web/js/cinematica.js. No editar a mano.',
  parametros: p, derivados: K.derivados, transmision: K.transmision, supuestos: K.supuestos
}, null, 2) + '\n');

const filas = ['sX_mm,sY_mm,phi_deg,r_mm,z_mm,pulsos_X,pulsos_Y'];
for (let i = 0; i <= 4; i++) {
  for (let j = 0; j <= 4; j++) {
    const q = { theta: 0, sX: p.recorridoX * i / 4, sY: p.recorridoY * j / 4 };
    const f = K.directa(q), np = K.aPulsos(q);
    filas.push([q.sX, q.sY, f.phi.toFixed(2), f.r.toFixed(1), f.z.toFixed(1), np.nX, np.nY].join(','));
  }
}
fs.writeFileSync(path.join(dir, 'tabla_cinematica.csv'), filas.join('\n') + '\n');
console.log('4. Escritos parametros.json y tabla_cinematica.csv');

console.log(fallos ? `\n${fallos} prueba(s) fallaron` : '\nTodas las pruebas pasaron');
process.exit(fallos ? 1 : 0);
