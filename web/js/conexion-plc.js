/*
 * Conexión con el PLC del brazo XK-JS1-1.
 *
 * Interfaz única para la página: enviarPosicion(), leerEstado() y homing().
 * Hoy actúa sobre la simulación (modo "simulacion"). Para la planta real se usa
 * el modo "middleware", que habla por HTTP con la capa de aplicación de la
 * arquitectura de 3 capas del README (Node-RED o un script en Python), y esa
 * capa escribe y lee la memoria V del S7-200 (PPI, o Modbus RTU con la librería
 * MBUS_SLAVE en el puerto 0).
 *
 * Contrato propuesto con el middleware (JSON):
 *   POST {url}/posicion   { theta_deg, sX_mm, sY_mm, garra, pulsos: { nZ, nX, nY } }
 *                         -> { ok: true }   (el PLC mueve con PTO Q0.0 y Q0.1 + relés K1/K2)
 *   GET  {url}/estado     -> { theta_deg, sX_mm, sY_mm, garra, referenciado, en_movimiento,
 *                              entradas: { "I0.0": bool, ... }, salidas: { "Q0.0": bool, ... } }
 *   POST {url}/homing     -> { ok: true }
 * Propuesta de mapeo en el PLC (por acordar con ETN-1034): VD100/VD104/VD108 =
 * pulsos objetivo Z/X/Y, V112.0 = garra, V112.1 = orden de mover, V112.2 = homing.
 */
(function (raiz) {
  'use strict';

  const estado = { modo: 'simulacion', url: 'http://localhost:1880/brazo', simulador: null, timeout: 4000 };

  async function http(metodo, ruta, cuerpo) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), estado.timeout);
    try {
      const r = await fetch(estado.url.replace(/\/$/, '') + ruta, {
        method: metodo,
        headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
        body: cuerpo ? JSON.stringify(cuerpo) : undefined,
        signal: ctrl.signal
      });
      if (!r.ok) throw new Error('El middleware respondió ' + r.status);
      return await r.json();
    } catch (e) {
      throw new Error(e.name === 'AbortError' ? 'El middleware no respondió a tiempo' : e.message);
    } finally {
      clearTimeout(t);
    }
  }

  function simulador() {
    if (!estado.simulador) throw new Error('No hay simulador registrado');
    return estado.simulador;
  }

  const ConexionPLC = {
    /** Cambia el modo ("simulacion" | "middleware") y la URL del middleware */
    configurar(opciones) {
      Object.assign(estado, opciones || {});
      return { modo: estado.modo, url: estado.url };
    },
    get modo() { return estado.modo; },
    get url() { return estado.url; },

    /** La página registra aquí su simulación: { mover(q), estado(), homing() } */
    registrarSimulador(sim) { estado.simulador = sim; },

    /**
     * Ordena ir a una posición articular.
     * @param {{theta:number, sX:number, sY:number, garra?:boolean}} q  [°, mm, mm]
     * @returns {Promise<object>}
     */
    async enviarPosicion(q) {
      if (estado.modo === 'simulacion') return simulador().mover(q);
      const K = raiz.Cinematica;
      return http('POST', '/posicion', {
        theta_deg: q.theta, sX_mm: q.sX, sY_mm: q.sY, garra: !!q.garra,
        pulsos: K ? K.aPulsos(q) : undefined
      });
    },

    /** Estado actual: posición estimada, entradas y salidas del PLC */
    async leerEstado() {
      if (estado.modo === 'simulacion') return simulador().estado();
      return http('GET', '/estado');
    },

    /** Búsqueda de referencias: finales de carrera X/Y y sensor inductivo de la base */
    async homing() {
      if (estado.modo === 'simulacion') return simulador().homing();
      return http('POST', '/homing', {});
    }
  };

  raiz.ConexionPLC = ConexionPLC;
})(typeof globalThis !== 'undefined' ? globalThis : this);
