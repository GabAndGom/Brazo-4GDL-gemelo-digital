/* Brazo 4 GDL - lógica del sitio. Los datos vienen de web/data/catalogo.js */
(function () {
  'use strict';

  const C = window.CATALOGO;
  const $ = (sel, raiz = document) => raiz.querySelector(sel);

  if (!C) {
    $('#app').innerHTML = '<div class="vacio" style="margin-top:40px">No se encontró <span class="codigo-inline">web/data/catalogo.js</span>. ' +
      'Ejecute <span class="codigo-inline">node scripts/build-catalog.js</span> en la carpeta del repositorio.</div>';
    return;
  }

  // ---------------------------------------------------------------- utilidades
  const LIBS = {
    marked: 'https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js',
    purify: 'https://cdnjs.cloudflare.com/ajax/libs/dompurify/3.1.6/purify.min.js'
  };
  const cargados = {};
  function cargar(src) {
    if (!cargados[src]) {
      cargados[src] = new Promise((ok, mal) => {
        const s = document.createElement('script');
        s.src = src; s.onload = ok; s.onerror = () => mal(new Error('No se pudo cargar ' + src));
        document.head.appendChild(s);
      });
    }
    return cargados[src];
  }

  async function markdownAHtml(texto, base) {
    await Promise.all([cargar(LIBS.marked), cargar(LIBS.purify)]);
    const html = window.DOMPurify.sanitize(window.marked.parse(texto));
    const div = document.createElement('div');
    div.innerHTML = html;
    // Rutas relativas de imágenes y enlaces dentro del README
    div.querySelectorAll('img[src], a[href]').forEach(el => {
      const attr = el.tagName === 'IMG' ? 'src' : 'href';
      const v = el.getAttribute(attr);
      if (v && !/^([a-z]+:|#|\/)/i.test(v)) el.setAttribute(attr, (base ? base + '/' : '') + v);
      if (el.tagName === 'A' && /^https?:/.test(el.getAttribute('href'))) { el.target = '_blank'; el.rel = 'noopener'; }
    });
    return div.innerHTML;
  }

  const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const norm = s => String(s || '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const urlDe = ruta => ruta.split('/').map(encodeURIComponent).join('/');
  const urlArchivo = a => a.github || urlDe(a.ruta);
  const carpetaDe = ruta => ruta.includes('/') ? ruta.slice(0, ruta.lastIndexOf('/')) : '';
  const nombreCarpeta = n => C.carpetas[n] || n.replace(/[_-]+/g, ' ').replace(/^./, c => c.toUpperCase());

  function tamano(b) {
    if (b < 1024) return b + ' B';
    if (b < 1048576) return Math.round(b / 1024) + ' KB';
    return (b / 1048576).toFixed(1) + ' MB';
  }

  const etiquetaSem = id => {
    if (id === 'global') return 'General';
    const s = C.semestres.find(x => x.id === id);
    return s ? s.etiqueta : id;
  };
  const subsistema = id => C.subsistemas.find(s => s.id === id);

  const ICONO = {
    carpeta: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>',
    archivo: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"><path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5"/></svg>'
  };

  // Programa con el que se abre cada formato que la página no puede mostrar
  const PROGRAMA_PARA = {
    dwg: 'AutoCAD o DWG TrueView', dxf: 'AutoCAD o LibreCAD',
    mwp: 'STEP 7-Micro/WIN', mwl: 'STEP 7-Micro/WIN',
    pptx: 'PowerPoint o LibreOffice Impress', ppt: 'PowerPoint o LibreOffice Impress',
    docx: 'Word o LibreOffice Writer', doc: 'Word o LibreOffice Writer',
    xlsx: 'Excel o LibreOffice Calc', xls: 'Excel o LibreOffice Calc',
    slx: 'MATLAB / Simulink', mlx: 'MATLAB'
  };

  const visibles = C.archivos.filter(a => !a.oculto);
  const CAT_NO_DOC = new Set(['programa', 'basedatos', 'imagen', 'video']);
  const documentos = visibles.filter(a => !CAT_NO_DOC.has(a.categoria));
  const programas = visibles.filter(a => a.categoria === 'programa' || a.categoria === 'basedatos');
  const imagenes = visibles.filter(a => a.categoria === 'imagen' || a.categoria === 'video');

  const ordenSem = id => id === 'global' ? '0' : id;
  function ordenar(lista) {
    return lista.slice().sort((a, b) =>
      (a.orden ?? 999) - (b.orden ?? 999) ||
      ordenSem(b.semestre).localeCompare(ordenSem(a.semestre)) ||
      a.titulo.localeCompare(b.titulo, 'es', { numeric: true }));
  }

  function coincide(a, q) {
    if (!q) return true;
    const texto = norm([a.titulo, a.descripcion, a.nombre, a.ruta, C.categorias[a.categoria], a.lenguaje].join(' '));
    return norm(q).split(/\s+/).every(p => texto.includes(p));
  }

  // ---------------------------------------------------------------- cifras
  function renderCifras() {
    const datos = [
      [C.semestres.length, 'Semestres'],
      [visibles.length, 'Archivos'],
      [programas.length, 'Programas'],
      [visibles.filter(a => a.categoria === 'datasheet' || a.categoria === 'manual').length, 'Datasheets y manuales']
    ];
    $('#cifras').innerHTML = datos.map(([n, t]) => `<div class="cifra"><strong>${n}</strong><span>${t}</span></div>`).join('');
  }

  // ---------------------------------------------------------------- planta
  function renderHardware() {
    const fotos = ordenar(visibles.filter(a => a.ruta.startsWith('global/fotos-planta/') && a.categoria === 'imagen'));
    $('#planta').hidden = !fotos.length;
    $('#hardware').innerHTML = fotos.map((a, i) => `
      <button class="hardware" data-ver="${esc(a.ruta)}">
        <div class="hardware-img"><img src="${esc(urlArchivo(a))}" alt="${esc(a.titulo)}" loading="lazy"></div>
        <div class="hardware-texto">
          <span>${String(i + 1).padStart(2, '0')}</span>
          <h3>${esc(a.titulo)}</h3>
          ${a.descripcion ? `<p>${esc(a.descripcion)}</p>` : ''}
        </div>
      </button>`).join('');
  }

  // ---------------------------------------------------------------- subsistemas
  function renderSubsistemas() {
    $('#subsistemas').innerHTML = C.subsistemas.map(s => {
      const n = visibles.filter(a => a.subsistemas.includes(s.id)).length;
      const activa = filtros.subsistema === String(s.id) ? ' activa' : '';
      return `<button class="tarjeta${activa}" data-subsistema="${s.id}">
        <span class="tarjeta-num">${s.id}</span>
        <h3>${esc(s.nombre)}</h3>
        <p>${esc(s.detalle)}</p>
        <span class="conteo">${n} archivo${n === 1 ? '' : 's'}</span>
      </button>`;
    }).join('');
  }

  // ---------------------------------------------------------------- semestres
  function renderSemestres() {
    $('#semestres').innerHTML = C.semestres.map(s => `
      <div class="semestre">
        <div class="semestre-id">${esc(s.etiqueta)}${s.id === C.actual ? '<em>EN CURSO</em>' : ''}</div>
        <p>${esc(s.resumen || 'Sin resumen. Agréguelo en config/semestres.json.')}</p>
        <div class="semestre-acciones">
          <span>${s.archivos} archivos</span>
          <button class="boton boton-chico" data-ver-semestre="${esc(s.id)}">Documentos</button>
          <button class="boton boton-chico" data-ir-carpeta="semestres/${esc(s.id)}">Carpeta</button>
        </div>
      </div>`).join('');
  }

  // ---------------------------------------------------------------- tarjetas de archivo
  function tarjetaArchivo(a) {
    const subs = a.subsistemas.map(id => subsistema(id)).filter(Boolean).map(s => s.nombre);
    const verBtn = a.vista
      ? `<button class="boton boton-chico boton-primario" data-ver="${esc(a.ruta)}">Ver</button>`
      : `<button class="boton boton-chico" data-ver="${esc(a.ruta)}">Detalles</button>`;
    return `<div class="archivo">
      <div class="ext ${esc(a.ext)}">${esc(a.ext || '?')}</div>
      <div class="archivo-info">
        <h4>${esc(a.titulo)}</h4>
        ${a.descripcion ? `<p>${esc(a.descripcion)}</p>` : ''}
        <div class="meta">
          <span class="sem">${esc(etiquetaSem(a.semestre))}</span>
          ${a.lenguaje ? `<span>${esc(a.lenguaje)}</span>` : ''}
          <span>${tamano(a.tam)}</span>
          ${subs.length && subs.length < C.subsistemas.length - 1 ? `<span>${esc(subs.join(' · '))}</span>` : ''}
        </div>
      </div>
      <div class="archivo-acciones">
        ${verBtn}
        <a class="boton boton-chico" href="${esc(urlArchivo(a))}" download="${esc(a.nombre)}">Descargar</a>
      </div>
    </div>`;
  }

  // ---------------------------------------------------------------- documentos
  const filtros = { q: '', semestre: '', categoria: '', subsistema: '' };

  function llenarSelect(sel, opciones, todas) {
    sel.innerHTML = `<option value="">${todas}</option>` +
      opciones.map(([v, t]) => `<option value="${esc(v)}">${esc(t)}</option>`).join('');
  }

  function prepararFiltrosDocs() {
    const sems = [...new Set(documentos.map(a => a.semestre))].sort((a, b) => ordenSem(b).localeCompare(ordenSem(a)));
    llenarSelect($('#filtro-semestre'), sems.map(s => [s, etiquetaSem(s)]), 'Todos los semestres');
    const cats = Object.keys(C.categorias).filter(k => documentos.some(a => a.categoria === k));
    llenarSelect($('#filtro-categoria'), cats.map(k => [k, C.categorias[k]]), 'Todas las categorías');
    llenarSelect($('#filtro-subsistema'), C.subsistemas.map(s => [String(s.id), s.nombre]), 'Todos los subsistemas');

    $('#buscar-docs').addEventListener('input', e => { filtros.q = e.target.value; renderDocumentos(); });
    [['#filtro-semestre', 'semestre'], ['#filtro-categoria', 'categoria'], ['#filtro-subsistema', 'subsistema']].forEach(([sel, k]) =>
      $(sel).addEventListener('change', e => { filtros[k] = e.target.value; renderDocumentos(); renderSubsistemas(); }));
  }

  function sincronizarSelects() {
    $('#buscar-docs').value = filtros.q;
    $('#filtro-semestre').value = filtros.semestre;
    $('#filtro-categoria').value = filtros.categoria;
    $('#filtro-subsistema').value = filtros.subsistema;
  }

  function renderDocumentos() {
    const lista = documentos.filter(a =>
      (!filtros.semestre || a.semestre === filtros.semestre) &&
      (!filtros.categoria || a.categoria === filtros.categoria) &&
      (!filtros.subsistema || a.subsistemas.includes(Number(filtros.subsistema))) &&
      coincide(a, filtros.q));

    const chips = [];
    if (filtros.semestre) chips.push(['semestre', etiquetaSem(filtros.semestre)]);
    if (filtros.categoria) chips.push(['categoria', C.categorias[filtros.categoria]]);
    if (filtros.subsistema) chips.push(['subsistema', subsistema(Number(filtros.subsistema)).nombre]);
    if (filtros.q) chips.push(['q', `“${filtros.q}”`]);
    $('#filtros-activos').innerHTML = chips.map(([k, t]) => `<button class="chip" data-quitar="${k}">${esc(t)} ✕</button>`).join('') +
      (chips.length > 1 ? '<button class="chip" data-quitar="todo">Quitar filtros</button>' : '');

    if (!lista.length) {
      $('#lista-documentos').innerHTML = '<div class="vacio">No hay documentos con esos filtros.</div>';
      return;
    }
    const grupos = Object.keys(C.categorias)
      .map(k => [k, ordenar(lista.filter(a => a.categoria === k))])
      .filter(([, l]) => l.length);
    $('#lista-documentos').innerHTML = grupos.map(([k, l]) => `
      <div class="grupo">
        <div class="grupo-titulo">${esc(C.categorias[k])} <span>${l.length}</span></div>
        <div class="archivos">${l.map(tarjetaArchivo).join('')}</div>
      </div>`).join('');
  }

  function filtrarDocumentos(cambios) {
    Object.assign(filtros, { q: '', semestre: '', categoria: '', subsistema: '' }, cambios);
    sincronizarSelects();
    renderDocumentos();
    renderSubsistemas();
    $('#documentos').scrollIntoView();
  }

  // ---------------------------------------------------------------- programas
  const filtrosProg = { q: '', lenguaje: '' };

  function prepararProgramas() {
    const lenguajes = [...new Set(programas.map(a => a.lenguaje))].sort();
    llenarSelect($('#filtro-lenguaje'), lenguajes.map(l => [l, l]), 'Todos los lenguajes');
    $('#buscar-prog').addEventListener('input', e => { filtrosProg.q = e.target.value; renderProgramas(); });
    $('#filtro-lenguaje').addEventListener('change', e => { filtrosProg.lenguaje = e.target.value; renderProgramas(); });
  }

  function renderProgramas() {
    const lista = ordenar(programas.filter(a =>
      (!filtrosProg.lenguaje || a.lenguaje === filtrosProg.lenguaje) && coincide(a, filtrosProg.q)));
    $('#lista-programas').innerHTML = lista.length
      ? `<div class="archivos">${lista.map(tarjetaArchivo).join('')}</div>`
      : `<div class="vacio">${programas.length ? 'No hay programas con esos filtros.' :
        'Todavía no hay programas. Súbalos a <span class="codigo-inline">semestres/' + esc(C.actual) + '/programas-plc/</span>.'}</div>`;
  }

  // ---------------------------------------------------------------- galería
  let pestanaGaleria = 'todo';

  function idYoutube(url) {
    const m = /(?:youtu\.be\/|v=|embed\/|shorts\/)([\w-]{11})/.exec(url);
    return m ? m[1] : null;
  }

  function renderGaleria() {
    const carpetas = [...new Set(imagenes.map(a => carpetaDe(a.ruta).split('/').pop()))];
    const pestanas = [['todo', 'Todo']].concat(carpetas.map(c => [c, nombreCarpeta(c)]));
    if (C.videos.length) pestanas.push(['videos', 'Videos']);
    $('#pestanas-galeria').innerHTML = pestanas.map(([k, t]) =>
      `<button class="pestana" role="tab" aria-selected="${k === pestanaGaleria}" data-pestana="${esc(k)}">${esc(t)}</button>`).join('');

    const fotos = pestanaGaleria === 'videos' ? [] : imagenes.filter(a =>
      pestanaGaleria === 'todo' || carpetaDe(a.ruta).split('/').pop() === pestanaGaleria);
    const videos = pestanaGaleria === 'todo' || pestanaGaleria === 'videos' ? C.videos : [];

    const html = ordenar(fotos).map(a => `
      <button class="foto" data-ver="${esc(a.ruta)}">
        <div class="foto-img${a.categoria === 'video' ? ' video' : ''}">
          ${a.categoria === 'video' ? '▶' : `<img src="${esc(urlArchivo(a))}" alt="${esc(a.titulo)}" loading="lazy">`}
        </div>
        <div class="pie-foto">${esc(a.titulo)}<small>${esc(etiquetaSem(a.semestre))}</small></div>
      </button>`).concat(videos.map((v, i) => {
        const id = idYoutube(v.url);
        return `<button class="foto" data-video="${i}">
          <div class="foto-img video">${id ? `<img src="https://i.ytimg.com/vi/${id}/hqdefault.jpg" alt="" loading="lazy">` : '▶'}</div>
          <div class="pie-foto">${esc(v.titulo)}<small>${esc(etiquetaSem(v.semestre))} · YouTube</small></div>
        </button>`;
      })).join('');
    $('#lista-galeria').innerHTML = html || '<div class="vacio">No hay imágenes todavía.</div>';
  }

  // ---------------------------------------------------------------- explorador
  let carpetaActual = '';

  function contenidoDe(dir) {
    const prefijo = dir ? dir + '/' : '';
    const carpetas = new Map();
    const archivos = [];
    for (const a of C.archivos) {
      if (!a.ruta.startsWith(prefijo)) continue;
      const resto = a.ruta.slice(prefijo.length);
      if (resto.includes('/')) {
        const c = resto.split('/')[0];
        carpetas.set(c, (carpetas.get(c) || 0) + 1);
      } else archivos.push(a);
    }
    return { carpetas, archivos };
  }

  async function renderExplorador() {
    const partes = carpetaActual ? carpetaActual.split('/') : [];
    $('#ruta-explorador').innerHTML = '<button data-ir-carpeta="">raíz</button>' + partes.map((p, i) =>
      `<span>/</span><button data-ir-carpeta="${esc(partes.slice(0, i + 1).join('/'))}">${esc(p)}</button>`).join('');

    const { carpetas, archivos } = contenidoDe(carpetaActual);
    const prefijo = carpetaActual ? carpetaActual + '/' : '';
    const filas = [];
    if (carpetaActual) {
      filas.push(`<li class="carpeta"><button data-ir-carpeta="${esc(carpetaDe(carpetaActual))}">${ICONO.carpeta}<span>..</span><small></small></button></li>`);
    }
    [...carpetas.keys()].sort().forEach(c => {
      const etiqueta = C.carpetas[c] ? ` <small>· ${esc(C.carpetas[c])}</small>` : '';
      filas.push(`<li class="carpeta"><button data-ir-carpeta="${esc(prefijo + c)}">${ICONO.carpeta}<span>${esc(c)}${etiqueta}</span><small>${carpetas.get(c)}</small></button></li>`);
    });
    archivos.sort((a, b) => a.nombre.localeCompare(b.nombre, 'es', { numeric: true })).forEach(a => {
      filas.push(`<li><button data-ver="${esc(a.ruta)}">${ICONO.archivo}<span>${esc(a.nombre)}</span><small>${tamano(a.tam)}</small></button></li>`);
    });
    $('#arbol').innerHTML = filas.join('') || '<li class="vacio">Carpeta vacía</li>';

    // README de la carpeta (en la raíz, el README.md del repositorio)
    const leeme = $('#leeme');
    const rutaLeeme = carpetaActual ? (archivos.find(a => a.nombre.toLowerCase() === 'readme.md') || {}).ruta : 'README.md';
    leeme.hidden = true;
    if (!rutaLeeme) return;
    const pedida = carpetaActual;
    try {
      const r = await fetch(urlDe(rutaLeeme));
      if (!r.ok) return;
      const html = await markdownAHtml(await r.text(), carpetaDe(rutaLeeme));
      if (pedida !== carpetaActual) return;
      leeme.innerHTML = `<div class="markdown">${html}</div>`;
      leeme.hidden = false;
    } catch (e) { /* sin README */ }
  }

  function irACarpeta(dir, desplazar) {
    carpetaActual = dir;
    renderExplorador();
    if (desplazar) $('#explorador').scrollIntoView();
  }

  // ---------------------------------------------------------------- equipo
  function renderEquipo() {
    const conEquipo = C.semestres.filter(s => s.equipo.length);
    $('#equipo').hidden = !conEquipo.length;
    $('#lista-equipo').innerHTML = conEquipo.map(s => `
      <div class="equipo">
        <h3>${esc(s.etiqueta)}</h3>
        ${s.docente ? `<p class="docente">Docente: ${esc(s.docente)}</p>` : ''}
        ${s.equipo.map(g => `<h4>${esc(g.grupo)}</h4><ul>${g.integrantes.map(n => `<li>${esc(n)}</li>`).join('')}</ul>`).join('')}
      </div>`).join('');
  }

  // ---------------------------------------------------------------- visor
  const visor = $('#visor');
  let foco = null;

  function abrirVisor(titulo, ruta, url, html) {
    foco = document.activeElement;
    $('#visor-titulo').textContent = titulo;
    $('#visor-ruta').textContent = ruta;
    const desc = $('#visor-descargar');
    const abrir = $('#visor-abrir');
    desc.hidden = !url; abrir.hidden = !url;
    if (url) {
      desc.href = url; desc.setAttribute('download', ruta.split('/').pop());
      abrir.href = url;
    }
    $('#visor-cuerpo').innerHTML = html;
    visor.hidden = false;
    document.body.style.overflow = 'hidden';
    $('[data-cerrar].boton-icono', visor).focus();
  }

  function cerrarVisor() {
    visor.hidden = true;
    $('#visor-cuerpo').innerHTML = '';
    document.body.style.overflow = '';
    if (location.hash.startsWith('#ver=')) history.replaceState(null, '', location.pathname + location.search);
    if (foco) foco.focus();
  }

  async function verArchivo(ruta) {
    const a = C.archivos.find(x => x.ruta === ruta);
    if (!a) return;
    const url = urlArchivo(a);
    history.replaceState(null, '', '#ver=' + encodeURIComponent(ruta));

    const cargando = '<div class="centrado">Cargando…</div>';
    switch (a.vista) {
      case 'pdf':
        abrirVisor(a.titulo, a.ruta, url, `<iframe src="${esc(url)}#view=FitH" title="${esc(a.titulo)}"></iframe>`);
        return;
      case 'imagen':
        abrirVisor(a.titulo, a.ruta, url, `<div class="centrado"><img src="${esc(url)}" alt="${esc(a.titulo)}"></div>`);
        return;
      case 'video':
        abrirVisor(a.titulo, a.ruta, url, `<div class="centrado"><video src="${esc(url)}" controls></video></div>`);
        return;
      case 'md':
      case 'texto': {
        abrirVisor(a.titulo, a.ruta, url, cargando);
        try {
          const r = await fetch(url);
          if (!r.ok) throw new Error(r.status);
          const texto = await r.text();
          $('#visor-cuerpo').innerHTML = a.vista === 'md'
            ? `<div class="markdown">${await markdownAHtml(texto, carpetaDe(a.ruta))}</div>`
            : `<pre>${esc(texto)}</pre>`;
        } catch (e) {
          $('#visor-cuerpo').innerHTML = '<div class="centrado">No se pudo cargar el archivo. Use “Descargar”.</div>';
        }
        return;
      }
      default: {
        const programa = PROGRAMA_PARA[a.ext];
        abrirVisor(a.titulo, a.ruta, url, `<div class="centrado"><div class="sin-vista">
          <div class="ext ${esc(a.ext)}">${esc(a.ext || '?')}</div>
          ${a.descripcion ? `<p>${esc(a.descripcion)}</p>` : ''}
          <p>Este formato no se puede mostrar en el navegador${programa ? `; se abre con <strong>${esc(programa)}</strong>` : ''}.</p>
          <a class="boton boton-primario" href="${esc(url)}" download="${esc(a.nombre)}">Descargar (${tamano(a.tam)})</a>
        </div></div>`);
      }
    }
  }

  function verVideo(i) {
    const v = C.videos[i];
    const id = idYoutube(v.url);
    abrirVisor(v.titulo, v.descripcion || etiquetaSem(v.semestre), null, id
      ? `<iframe src="https://www.youtube-nocookie.com/embed/${id}" title="${esc(v.titulo)}" allow="accelerometer; encrypted-media; picture-in-picture" allowfullscreen></iframe>`
      : `<div class="centrado"><a class="boton boton-primario" href="${esc(v.url)}" target="_blank" rel="noopener">Abrir video ↗</a></div>`);
  }

  // ---------------------------------------------------------------- eventos
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-ver], [data-video], [data-subsistema], [data-ver-semestre], [data-ir-carpeta], [data-quitar], [data-pestana], [data-cerrar]');
    if (!el) return;
    const d = el.dataset;
    if (d.ver != null) verArchivo(d.ver);
    else if (d.video != null) verVideo(Number(d.video));
    else if (d.subsistema) filtrarDocumentos(filtros.subsistema === d.subsistema ? {} : { subsistema: d.subsistema });
    else if (d.verSemestre) filtrarDocumentos({ semestre: d.verSemestre });
    else if (d.irCarpeta != null) irACarpeta(d.irCarpeta, !el.closest('#explorador'));
    else if (d.pestana) { pestanaGaleria = d.pestana; renderGaleria(); }
    else if (d.cerrar != null) cerrarVisor();
    else if (d.quitar) {
      if (d.quitar === 'todo') Object.assign(filtros, { q: '', semestre: '', categoria: '', subsistema: '' });
      else filtros[d.quitar] = '';
      sincronizarSelects(); renderDocumentos(); renderSubsistemas();
    }
  });

  document.addEventListener('keydown', e => { if (e.key === 'Escape' && !visor.hidden) cerrarVisor(); });

  // Enlaces #ver=... pegados en la barra de direcciones, y menú con el visor abierto
  window.addEventListener('hashchange', () => {
    if (location.hash.startsWith('#ver=')) verArchivo(decodeURIComponent(location.hash.slice(5)));
    else if (!visor.hidden) cerrarVisor();
  });

  $('#cambiar-tema').addEventListener('click', () => {
    const oscuro = document.documentElement.dataset.theme
      ? document.documentElement.dataset.theme === 'dark'
      : matchMedia('(prefers-color-scheme: dark)').matches;
    const nuevo = oscuro ? 'light' : 'dark';
    document.documentElement.dataset.theme = nuevo;
    try { localStorage.setItem('tema', nuevo); } catch (err) { /* sin almacenamiento */ }
  });

  const menu = $('#menu');
  $('#abrir-menu').addEventListener('click', () => {
    const abierto = menu.classList.toggle('abierto');
    $('#abrir-menu').setAttribute('aria-expanded', abierto);
  });
  menu.addEventListener('click', e => { if (e.target.closest('a')) menu.classList.remove('abierto'); });

  // Resalta en el menú la sección visible
  const enlaces = [...menu.querySelectorAll('a')];
  const observador = new IntersectionObserver(entradas => {
    entradas.forEach(en => {
      if (en.isIntersecting) enlaces.forEach(a => a.classList.toggle('activo', a.getAttribute('href') === '#' + en.target.id));
    });
  }, { rootMargin: '-40% 0px -55% 0px' });
  enlaces.forEach(a => { const s = $(a.getAttribute('href')); if (s) observador.observe(s); });

  // ---------------------------------------------------------------- inicio
  $('#enlace-github').href = `https://github.com/${C.repo}`;
  $('#pie-meta').innerHTML = `<a href="https://github.com/${esc(C.repo)}" target="_blank" rel="noopener">github.com/${esc(C.repo)}</a><br>` +
    `Actualizado: ${new Date(C.generado).toLocaleDateString('es-BO', { day: 'numeric', month: 'long', year: 'numeric' })}`;

  renderCifras();
  renderHardware();
  renderSubsistemas();
  renderSemestres();
  prepararFiltrosDocs();
  renderDocumentos();
  prepararProgramas();
  renderProgramas();
  renderGaleria();
  renderExplorador();
  renderEquipo();

  if (location.hash.startsWith('#ver=')) verArchivo(decodeURIComponent(location.hash.slice(5)));
})();
