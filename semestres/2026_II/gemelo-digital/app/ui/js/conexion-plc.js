/*
 * Conexión con el PLC del brazo XK-JS1-1.
 *
 * Dos modos:
 *  - "simulacion": la página mueve su propia simulación (sin hardware).
 *  - "planta": la página habla con la app del gemelo digital
 *    (semestres/2026_II/gemelo-digital/app/gemelo_brazo.py), que lee y escribe el S7-200
 *    por el cable USB-PPI. Si la página se abre desde la app (http://localhost:8050) el
 *    modo planta se activa solo.
 *
 * API de la app (JSON):
 *   GET  {url}/api/info            -> { conectado, perfil, ordenes: [...], mando, ... }
 *   GET  {url}/api/estado          -> { theta_deg, sX_mm, sY_mm, garra, referenciado, en_movimiento,
 *                                       estimado, pulsos, entradas: {"I0.0": bool, ...},
 *                                       salidas: {"Q0.0": bool, ...}, plc: {...}, conectado, mando }
 *   POST {url}/api/mando           { habilitado: bool }
 *   POST {url}/api/orden/<nombre>  homing | mover {theta, sX, sY} | detener | garra {cerrada}
 *                                  | velocidad {hz} | iniciar | emergencia | rearmar
 */
(function (raiz) {
  'use strict';

  const estado = { modo: 'simulacion', url: '', simulador: null, timeout: 4000 };

  async function http(metodo, ruta, cuerpo) {
    const ctrl = new AbortController();
    const t = setTimeout(() => ctrl.abort(), estado.timeout);
    try {
      const r = await fetch(estado.url.replace(/\/$/, '') + ruta, {
        method: metodo,
        headers: cuerpo ? { 'Content-Type': 'application/json' } : undefined,
        body: cuerpo ? JSON.stringify(cuerpo) : undefined,
        signal: ctrl.signal,
        cache: 'no-store'
      });
      const datos = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(datos.error || 'La app respondió ' + r.status);
      return datos;
    } catch (e) {
      throw new Error(e.name === 'AbortError' ? 'La app del gemelo no respondió a tiempo' : e.message);
    } finally {
      clearTimeout(t);
    }
  }

  function simulador() {
    if (!estado.simulador) throw new Error('No hay simulador registrado');
    return estado.simulador;
  }

  const ConexionPLC = {
    /** Cambia el modo ("simulacion" | "planta") y la URL de la app ('' = mismo servidor) */
    configurar(opciones) {
      Object.assign(estado, opciones || {});
      return { modo: estado.modo, url: estado.url };
    },
    get modo() { return estado.modo; },
    get url() { return estado.url; },

    /** La página registra aquí su simulación: { mover(q), estado(), homing() } */
    registrarSimulador(sim) { estado.simulador = sim; },

    /** ¿Hay una app del gemelo en esta URL? Devuelve su info o null */
    async detectar(url) {
      const previa = estado.url;
      if (url != null) estado.url = url;
      try {
        const i = await http('GET', '/api/info');
        return i && i.app === 'gemelo-brazo-xk-js1-1' ? i : null;
      } catch (e) {
        return null;
      } finally {
        if (url != null && estado.modo !== 'planta') estado.url = previa;
      }
    },
    info: () => http('GET', '/api/info'),
    mando: habilitado => http('POST', '/api/mando', { habilitado }),
    orden: (nombre, datos) => http('POST', '/api/orden/' + nombre, datos || {}),

    /** Ordena ir a una posición articular {theta, sX, sY, garra?} [°, mm, mm] */
    async enviarPosicion(q) {
      if (estado.modo === 'simulacion') return simulador().mover(q);
      return http('POST', '/api/orden/mover', { theta: q.theta, sX: q.sX, sY: q.sY });
    },

    /** Estado actual: posición, entradas y salidas del PLC */
    async leerEstado() {
      if (estado.modo === 'simulacion') return simulador().estado();
      return http('GET', '/api/estado');
    },

    /** Búsqueda de referencias: finales de carrera X/Y y sensor inductivo de la base */
    async homing() {
      if (estado.modo === 'simulacion') return simulador().homing();
      return http('POST', '/api/orden/homing', {});
    }
  };

  raiz.ConexionPLC = ConexionPLC;
})(typeof globalThis !== 'undefined' ? globalThis : this);
