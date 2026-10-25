/*
 * Cinemática del brazo XK-JS1-1 (4 GDL). Módulo sin dependencias.
 *
 * Se usa desde la página (window.Cinematica), desde Node (require) y es la
 * fuente única de parámetros para el generador del modelo 3D y los scripts de
 * gráficas (ver semestres/2026_II/modelo-3d/cinematica/).
 *
 * Nomenclatura:
 *   θ base        giro de la base [°]
 *   carro X (sX)  carrera del husillo inferior [mm]: desplaza todo el bastidor
 *                 respecto al bloque 2 (fijo a la columna)
 *   carro Y (sY)  carrera del husillo superior [mm]: desplaza el bloque 1
 *                 respecto al bastidor y, por la biela 12, hace girar el brazo 9.
 *                 sY = 0 en su final de carrera inferior (homing: brazo abajo,
 *                 bloque 1 adelante); sY positivo sube el brazo (el bloque 1 va
 *                 hacia atrás). Así los pulsos cuentan igual que en el PLC.
 *   carro X (sX)  sX = 0 en su final trasero (homing); positivo hacia la garra.
 *   posición de la garra (X, Y, Z): TCP en coordenadas cartesianas [mm],
 *                 origen en el eje de giro a nivel de la mesa, Z hacia arriba,
 *                 X hacia adelante con θ = 0 (sensor inductivo)
 *
 * Plano del brazo (r, z): r horizontal desde el eje de giro, z desde la mesa.
 * Todas las cotas en mm salvo que se indique.
 */
(function (raiz, fabrica) {
  'use strict';
  const mod = fabrica();
  if (typeof module === 'object' && module.exports) module.exports = mod;
  else raiz.Cinematica = mod;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const RAD = Math.PI / 180;

  // ------------------------------------------------------------------ parámetros
  // Origen de cada dato: leida (boceto), estimada (foto), fabricante (manual) o SUPUESTO.
  // Ver semestres/2026_II/modelo-3d/levantamiento/levantamiento_medidas.md
  const PARAMETROS = {
    // Base giratoria
    hDiscoInf: 15,        // leida: disco 11, Ø165 × 15
    hEntreDiscos: 21,     // SUPUESTO: separación entre discos
    hDiscoSup: 15,        // leida
    rDisco: 82.5,         // leida: Ø165
    hColumna: 120,        // leida: pieza 7
    hBloque2: 40,         // leida: pieza 2
    hBloque1: 50,         // leida: pieza 1
    largoBloque: 100,     // leida: bloques 1 y 2 a lo largo de las guías
    anchoBloque: 130,     // leida
    sepNiveles: 45,       // leida: ejes de los husillos separados ~44-45 mm
    // Bastidor
    largoGuias: 300,      // leida: piezas 16, Ø16 × 300
    espesorPlaca: 13,     // leida: placas 5 y 10
    anchoPlaca: 120,      // leida (f02, f04): 12.06 cm; agujeros a 22, 57 y 97 mm de un borde
    altoPlaca: 110,       // leida: 11.03 cm
    zGuias: 37.5,         // leida (f02): guías a ±37.5 mm del husillo (97 - 22 = 75 entre centros)
    holgura: 2,           // SUPUESTO: distancia bloque-placa al pisar el final de carrera
    // Recorridos útiles (entre finales de carrera)
    recorridoX: 120,      // SUPUESTO: ficha del fabricante "adelante-atrás 0-120 mm" (el manual dice 200,
                          // pero entre placas caben como máximo 300 - 2·13 - 100 - 2·2 = 170)
    recorridoY: 170,      // SUPUESTO: máximo geométrico entre placas (fabricante: vertical 0-400 mm de la garra)
    thetaMin: -175,       // SUPUESTO: el manual dice 360°; se limita por los cables
    thetaMax: 175,        // SUPUESTO
    // Mecanismo de bielas (cotas entre centros de pasadores). Las estimadas se ajustaron
    // con la foto de perfil del manual (fig. 1.3.3 A) y la foto f13: el modelo reproduce
    // esa pose con menos de 5 mm de diferencia en B y C.
    uA: 20,               // estimada: pivote A casi sobre la cara delantera de la placa 5 (placa 13 + 7)
    dhA: 45,              // estimada: pivote A a la altura del husillo superior (mitad del bloque 1)
    hC: 110,              // leida: altura de la escuadra 6
    dhC: -10,             // SUPUESTO: pivote C 10 mm bajo la punta de la escuadra 6
    uCBloque: -60,        // estimada: la escuadra 6 está hacia atrás del bloque 1 (desde su cara delantera)
    L12: 235,             // estimada: boceto pieza 12 = 24 cm de largo total; entre pivotes ≈ 235
    a: 145,               // estimada (manual): distancia A-B del balancín 8+9
    beta: 50,             // estimada (manual): ángulo entre A-B y el brazo A-E [°]
    L9: 300,              // estimada: igual a la varilla 13 (leida 300) por ser paralelogramo
    L14: 70,              // estimada: A-A' y E-E' (postes 14 de 46 mm + soportes)
    // Pinza (desde el pivote E hasta el centro de las mordazas = TCP)
    dg: 135,              // estimada (manual): E queda en la parte trasera del cuerpo 4, a media altura
    hg: 20,               // estimada: las mordazas van un poco por debajo de E
    hCuerpoPinza: 55,     // leida
    pinzaBajoE: 35,       // estimada: el cuerpo 4 baja 35 mm desde E (y sube 20)
    // Transmisión
    pasoHusillo: 5,       // SUPUESTO [mm/rev]: husillo de bolas tipo SFU1605
    pasosMotor: 200,      // fabricante: 1.8°/paso
    micropasosXY: 8,      // SUPUESTO: DIP 2M542 SW4-SW7 = 0 0 1 1 -> 1600 pulsos/rev
    micropasosZ: 8,       // SUPUESTO: 2M530 a 1600 pulsos/rev
    reduccionBase: 5,     // SUPUESTO: engranaje de la base 5:1 (manual: "gear drive")
    fMaxPTO: 20000        // fabricante: PTO de la CPU 224 hasta 20 kHz
  };

  // Supuestos y estimaciones de foto: deben medirse en la planta
  const SUPUESTOS = ['hEntreDiscos', 'holgura', 'recorridoX', 'recorridoY', 'thetaMin', 'thetaMax', 'uA', 'dhA',
    'dhC', 'uCBloque', 'L12', 'a', 'beta', 'L9', 'L14', 'dg', 'hg', 'pinzaBajoE',
    'pasoHusillo', 'micropasosXY', 'micropasosZ', 'reduccionBase'];

  // ------------------------------------------------------------------ geometría derivada
  function derivar(p) {
    const hEjeX = p.hDiscoInf + p.hEntreDiscos + p.hDiscoSup + p.hColumna + p.hBloque2 / 2;
    const hEjeY = hEjeX + p.sepNiveles;
    const uBloque2 = p.largoBloque / 2;          // cara delantera del bloque 2 (centrado en el eje θ)
    const carreraLibre = p.largoGuias - 2 * p.espesorPlaca - p.largoBloque;
    const u5_0 = uBloque2 + p.holgura;           // cara interior de la placa 5 con sX = 0
    const hA = hEjeX + p.dhA;
    const hCabs = hEjeX + p.hBloque2 / 2 + p.hBloque1 + p.hC + p.dhC;
    // C respecto a A (en el bastidor) con el bloque 1 atrás del todo (posición geométrica g = 0)
    const cu0 = -(carreraLibre - p.holgura) + p.uCBloque - p.uA;
    return { hEjeX, hEjeY, uBloque2, carreraLibre, u5_0, hA, hCabs, cu0, ch: hCabs - hA };
  }

  const norm180 = g => ((g + 180) % 360 + 360) % 360 - 180;

  function crear(sobrescribir) {
    const p = Object.assign({}, PARAMETROS, sobrescribir || {});
    const d = derivar(p);
    const beta = p.beta * RAD;

    // Posición geométrica del bloque 1 desde su tope trasero: g = recorridoY - sY
    // (sY se mide desde el final inferior, que es el homing).
    const gY = sY => p.recorridoY - sY;

    // Lazo A-B-C: ángulo ψ del segmento A-B para una posición geométrica g del bloque 1.
    // Rama de montaje real: B queda por debajo de la recta A-C.
    function psiDe(g) {
      const cx = g + d.cu0, cz = d.ch;
      const dist = Math.hypot(cx, cz);
      const cosg = (p.a * p.a + dist * dist - p.L12 * p.L12) / (2 * p.a * dist);
      if (cosg < -1 || cosg > 1) return NaN;
      return Math.atan2(cz, cx) - Math.acos(cosg);
    }

    // dψ/dg analítico, de f = |a·e(ψ) - C|² - L12² = 0  (dψ/dsY = -dψ/dg)
    function dpsi(g, psi) {
      const vx = p.a * Math.cos(psi) - (g + d.cu0);
      const vz = p.a * Math.sin(psi) - d.ch;
      return vx / (p.a * (-vx * Math.sin(psi) + vz * Math.cos(psi)));
    }

    // ---------------------------------------------------------------- directa
    function directa(q) {
      const theta = q.theta || 0, sX = q.sX || 0, sY = q.sY || 0;
      const g = gY(sY);
      const psi = psiDe(g);
      if (!isFinite(psi)) return { valida: false, motivo: 'El lazo de bielas no cierra para esa carrera del carro Y.' };
      const phi = psi - beta;
      const uA = d.u5_0 + sX + p.uA;
      const A = { u: uA, h: d.hA };
      const B = { u: uA + p.a * Math.cos(psi), h: d.hA + p.a * Math.sin(psi) };
      const C = { u: uA + g + d.cu0, h: d.hCabs };
      const E = { u: uA + p.L9 * Math.cos(phi), h: d.hA + p.L9 * Math.sin(phi) };
      const r = E.u + p.dg, z = E.h - p.hg;
      const th = theta * RAD;
      return {
        valida: true, theta, sX, sY, garra: !!q.garra,
        posBloque1: g,      // desplazamiento del bloque 1 desde su tope trasero (para el modelo 3D)
        phi: phi / RAD, psi: psi / RAD,
        angBiela: Math.atan2(B.h - C.h, B.u - C.u) / RAD,
        r, z, X: r * Math.cos(th), Y: r * Math.sin(th), Z: z,
        puntos: { A, B, C, E, A2: { u: A.u, h: A.h + p.L14 }, E2: { u: E.u, h: E.h + p.L14 } },
        hPinzaMin: E.h - p.pinzaBajoE
      };
    }

    // ---------------------------------------------------------------- límites y colisión
    function limites(q) {
      const av = [];
      if (q.sX < -1e-6 || q.sX > p.recorridoX + 1e-6) av.push('carro X fuera de recorrido');
      if (q.sY < -1e-6 || q.sY > p.recorridoY + 1e-6) av.push('carro Y fuera de recorrido');
      if (q.theta < p.thetaMin - 1e-6 || q.theta > p.thetaMax + 1e-6) av.push('θ base fuera de rango');
      return av;
    }

    // Colisión simple con la mesa (z = 0): cuerpo de la pinza y mordazas
    function colision(fk) {
      return !!fk.valida && (fk.hPinzaMin < 0 || fk.z - 15 < 0);
    }

    // ---------------------------------------------------------------- inversa
    // obj = {X, Y, Z}; opciones.thetaActual elige entre θ y θ ± 360°
    function inversa(obj, opciones) {
      const op = opciones || {};
      const r = Math.hypot(obj.X, obj.Y);
      const soluciones = [];
      if (r < 1) return { valida: false, motivo: 'El objetivo está sobre el eje de giro.', soluciones };

      const th0 = Math.atan2(obj.Y, obj.X) / RAD;
      const actual = op.thetaActual != null ? op.thetaActual : 0;
      let thetas = [th0 - 360, th0, th0 + 360]
        .filter(t => t >= p.thetaMin - 1e-9 && t <= p.thetaMax + 1e-9)
        .sort((x, y) => Math.abs(x - actual) - Math.abs(y - actual));
      if (!thetas.length) thetas = [th0];

      const s = (obj.Z + p.hg - d.hA) / p.L9;
      if (Math.abs(s) > 1) return { valida: false, motivo: 'Altura inalcanzable: el brazo no llega a esa Z.', soluciones };

      // Ramas del brazo: hacia adelante (cos φ > 0) y hacia atrás
      const ramas = [['adelante', Math.asin(s)], ['atrás', Math.PI - Math.asin(s)]];
      for (const [rama, phi] of ramas) {
        const sX = r - p.dg - p.L9 * Math.cos(phi) - d.u5_0 - p.uA;
        const psi = phi + beta;
        const bx = p.a * Math.cos(psi), bz = p.a * Math.sin(psi);
        const disc = p.L12 * p.L12 - (d.ch - bz) * (d.ch - bz);
        if (disc < 0) continue;
        for (const sgn of [-1, 1]) {
          const g = bx + sgn * Math.sqrt(disc) - d.cu0;
          const sY = gY(g);
          // Solo vale la que corresponde a la rama de montaje real
          const psiReal = psiDe(g);
          if (!isFinite(psiReal) || Math.abs(norm180((psiReal - psi) / RAD)) > 1e-6) continue;
          for (const theta of thetas) {
            const q = { theta, sX, sY };
            const avisos = limites(q);
            if (colision(directa(q))) avisos.push('colisión con la mesa');
            soluciones.push({ q, rama, avisos, valida: !avisos.length });
          }
        }
      }
      const buena = soluciones.find(x => x.valida);
      if (buena) return { valida: true, q: buena.q, soluciones };
      const motivo = soluciones.length
        ? 'Inalcanzable: ' + [...new Set(soluciones.flatMap(x => x.avisos))].join(', ') + '.'
        : 'Inalcanzable: el lazo de bielas no cierra para esa posición.';
      return { valida: false, motivo, soluciones };
    }

    // ---------------------------------------------------------------- jacobiano
    // J = ∂(X, Y, Z) / ∂(θ [rad], sX, sY)
    function jacobiano(q) {
      const fk = directa(q);
      if (!fk.valida) return null;
      const th = fk.theta * RAD, phi = fk.phi * RAD;
      const dphi = -dpsi(fk.posBloque1, fk.psi * RAD);
      const drY = -p.L9 * Math.sin(phi) * dphi;
      const dzY = p.L9 * Math.cos(phi) * dphi;
      const c = Math.cos(th), s = Math.sin(th);
      const J = [
        [-fk.r * s, c, c * drY],
        [fk.r * c, s, s * drY],
        [0, 0, dzY]
      ];
      const det = fk.r * dzY;   // desarrollando por la última fila
      // Ángulo de transmisión entre la biela 12 y el segmento A-B (ideal 90°)
      const P = fk.puntos;
      const v1 = [P.C.u - P.B.u, P.C.h - P.B.h], v2 = [P.A.u - P.B.u, P.A.h - P.B.h];
      const mu = Math.acos((v1[0] * v2[0] + v1[1] * v2[1]) / (Math.hypot(v1[0], v1[1]) * Math.hypot(v2[0], v2[1]))) / RAD;
      return { J, det, dphi_dsY: dphi / RAD, transmision: mu };
    }

    // ---------------------------------------------------------------- motor -> articulación
    const pulsosRevXY = p.pasosMotor * p.micropasosXY;
    const pulsosRevZ = p.pasosMotor * p.micropasosZ;
    const transmision = {
      pulsosRevXY, pulsosRevZ,
      mmPorPulso: p.pasoHusillo / pulsosRevXY,
      pulsosPorMm: pulsosRevXY / p.pasoHusillo,
      gradosPorPulso: 360 / (pulsosRevZ * p.reduccionBase),
      pulsosPorGrado: pulsosRevZ * p.reduccionBase / 360,
      vMaxXY: p.fMaxPTO * p.pasoHusillo / pulsosRevXY,
      wMaxBase: p.fMaxPTO * 360 / (pulsosRevZ * p.reduccionBase)
    };
    function aPulsos(q) {
      return {
        nZ: Math.round(q.theta * transmision.pulsosPorGrado),
        nX: Math.round(q.sX * transmision.pulsosPorMm),
        nY: Math.round(q.sY * transmision.pulsosPorMm)
      };
    }
    function dePulsos(n) {
      return { theta: n.nZ / transmision.pulsosPorGrado, sX: n.nX / transmision.pulsosPorMm, sY: n.nY / transmision.pulsosPorMm };
    }

    // ---------------------------------------------------------------- espacio de trabajo
    function espacioTrabajo(n) {
      const N = n || 35, pts = [];
      for (let i = 0; i <= N; i++) {
        for (let j = 0; j <= N; j++) {
          const fk = directa({ theta: 0, sX: p.recorridoX * i / N, sY: p.recorridoY * j / N });
          if (fk.valida) pts.push({ sX: fk.sX, sY: fk.sY, r: fk.r, z: fk.z, choca: colision(fk) });
        }
      }
      return pts;
    }
    // Contorno del corte r-z: imagen del borde del rectángulo de carreras
    function contorno(n) {
      const N = n || 60, borde = [];
      const add = (sX, sY) => { const f = directa({ theta: 0, sX, sY }); if (f.valida) borde.push({ r: f.r, z: f.z }); };
      for (let i = 0; i <= N; i++) add(p.recorridoX * i / N, 0);
      for (let i = 0; i <= N; i++) add(p.recorridoX, p.recorridoY * i / N);
      for (let i = N; i >= 0; i--) add(p.recorridoX * i / N, p.recorridoY);
      for (let i = N; i >= 0; i--) add(0, p.recorridoY * i / N);
      return borde;
    }

    // ---------------------------------------------------------------- trayectorias
    // Recta en el espacio cartesiano con perfil suave; si algún punto intermedio
    // no es alcanzable, se interpola en el espacio articular.
    function trayectoria(qIni, objetivo, pasos) {
      const N = Math.max(2, pasos || 60);
      const ini = directa(qIni);
      const fin = inversa(objetivo, { thetaActual: qIni.theta });
      if (!ini.valida || !fin.valida) return { valida: false, motivo: fin.motivo || ini.motivo };
      const qs = [];
      let cartesiana = true, thPrev = qIni.theta;
      for (let k = 1; k <= N; k++) {
        const t = k / N, w = t * t * (3 - 2 * t);
        const ik = inversa({
          X: ini.X + (objetivo.X - ini.X) * w,
          Y: ini.Y + (objetivo.Y - ini.Y) * w,
          Z: ini.Z + (objetivo.Z - ini.Z) * w
        }, { thetaActual: thPrev });
        if (!ik.valida) { cartesiana = false; break; }
        qs.push(ik.q); thPrev = ik.q.theta;
      }
      if (!cartesiana) {
        qs.length = 0;
        for (let k = 1; k <= N; k++) qs.push(interpolarQ(qIni, fin.q, k / N));
      }
      return { valida: true, cartesiana, qs, qFin: fin.q };
    }
    function interpolarQ(q0, q1, t) {
      const w = t * t * (3 - 2 * t);
      return {
        theta: q0.theta + (q1.theta - q0.theta) * w,
        sX: q0.sX + (q1.sX - q0.sX) * w,
        sY: q0.sY + (q1.sY - q0.sY) * w
      };
    }

    return {
      parametros: p, derivados: d, supuestos: SUPUESTOS.slice(), transmision,
      directa, inversa, jacobiano, limites, colision, aPulsos, dePulsos,
      espacioTrabajo, contorno, trayectoria, interpolarQ,
      _psiDe: psiDe
    };
  }

  const base = crear();
  base.crear = crear;
  base.PARAMETROS = PARAMETROS;
  return base;
});
