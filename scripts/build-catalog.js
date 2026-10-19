/*
 * Genera web/data/catalogo.js a partir de las carpetas global/ y semestres/.
 *
 *   node scripts/build-catalog.js
 *
 * Cloudflare Pages (y GitHub Actions, .github/workflows/pages.yml) lo ejecutan
 * en cada push a main.
 * No necesita dependencias. Títulos, descripciones y subsistemas se corrigen en
 * config/archivos.json; los semestres y el equipo en config/semestres.json;
 * los videos de YouTube en config/videos.json.
 */

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const OUT_DIR = path.join(ROOT, 'web', 'data');
const REPO = 'GabAndGom/Brazo-de-4-grados-de-libertad';
const RAMA = 'main';
// Cloudflare Pages publica archivos de hasta 25 MB y GitHub Pages de hasta 100 MB.
// Los más grandes se descargan directamente desde GitHub.
const EN_CLOUDFLARE = !!process.env.CF_PAGES;
const LIMITE_PAGES = (EN_CLOUDFLARE ? 25 : 95) * 1024 * 1024;

const CARPETAS = ['global', 'semestres'];

// Subsistemas del brazo. Un archivo se asigna a un subsistema si su ruta
// (sin tildes y en minúsculas) contiene alguna de las claves.
const SUBSISTEMAS = [
  { id: 1, nombre: 'Ejes X-Y', detalle: 'Motores NEMA 23 y finales de carrera', claves: ['motor_xy', 'eje_x', 'eje_y', 'ejes_xy', 'final_de_carrera', 'v-156'] },
  { id: 2, nombre: 'Eje Z', detalle: 'Motor NEMA 17 y sensor inductivo', claves: ['motor_z', 'eje_z', 'sensor_inductivo', 'lj12a3'] },
  { id: 3, nombre: 'Garra', detalle: 'Efector final con solenoide 24 V', claves: ['garra', 'efector', 'solenoide'] },
  { id: 4, nombre: 'Potencia y mando', detalle: 'Drivers 2M542/2M530, fuente, relés y botonera', claves: ['driver', 'dm542', '2dm556', 'fuente', 'disyuntor', 'rele_', 'rele.', 'botonera'] },
  { id: 5, nombre: 'PLC S7-200', detalle: 'CPU 224 y librería MAP_SERV', claves: ['plc', 's7-200', 'cpu224', 'map_serv', 'kop', '.mwp', '.awl'] },
  { id: 6, nombre: 'Datos y HMI', detalle: 'Base de datos, interfaz y SCADA', claves: ['base-de-datos', 'hmi', 'interfaz', 'mockup', 'scada', 'erp', '.sql'] }
];

const CATEGORIAS = {
  guia: 'Guías',
  informe: 'Informes',
  pid: 'P&ID',
  electrico: 'Planos eléctricos',
  plano: 'Otros planos CAD',
  mockup: 'Mockups',
  diagrama: 'Diagramas',
  modelo3d: 'Modelos 3D',
  datasheet: 'Datasheets',
  manual: 'Manuales',
  normativa: 'Normativas',
  plantilla: 'Plantillas',
  presentacion: 'Presentaciones',
  datos: 'Datos y ensayos',
  enlace: 'Enlaces',
  otro: 'Otros',
  programa: 'Programas',
  basedatos: 'Base de datos',
  imagen: 'Imágenes',
  video: 'Videos'
};

// Tipo de programa, para el filtro de la sección Programas
const LENGUAJES = {
  awl: 'AWL (S7-200)',
  mwp: 'Micro/WIN',
  mwl: 'Librería Micro/WIN',
  st: 'Texto estructurado',
  py: 'Python',
  m: 'MATLAB', mlx: 'MATLAB',
  slx: 'Simulink',
  c: 'C/C++', cpp: 'C/C++', h: 'C/C++', hpp: 'C/C++', ino: 'Arduino',
  js: 'Web', html: 'Web', css: 'Web',
  sql: 'SQL',
  tex: 'LaTeX'
};

const EXT = {
  imagen: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'],
  modelo3d: ['sldprt', 'sldasm', 'slddrw', 'step', 'stp', 'stl', 'igs', 'iges', 'f3d', 'ipt', 'iam', 'obj', 'glb', '3mf'],
  plano: ['dwg', 'dxf'],
  presentacion: ['pptx', 'ppt'],
  datos: ['csv', 'xlsx', 'xlsm', 'xls'],
  video: ['mp4', 'webm', 'mov']
};

// Cómo se abre cada extensión en la página; lo que no está aquí se descarga
const VISTAS = {
  pdf: 'pdf',
  md: 'md',
  png: 'imagen', jpg: 'imagen', jpeg: 'imagen', gif: 'imagen', bmp: 'imagen', webp: 'imagen', svg: 'imagen',
  mp4: 'video', webm: 'video',
  awl: 'texto', st: 'texto', py: 'texto', m: 'texto', sql: 'texto', txt: 'texto', json: 'texto', csv: 'texto',
  js: 'texto', css: 'texto', c: 'texto', cpp: 'texto', h: 'texto', hpp: 'texto', ino: 'texto', xml: 'texto', tex: 'texto'
};

const IGNORAR = new Set(['.git', 'node_modules', '.DS_Store', 'Thumbs.db', 'desktop.ini', '.gitignore', '.gitkeep']);

const normalizar = t => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

function leerJson(rel, porDefecto) {
  const archivo = path.join(ROOT, rel);
  if (!fs.existsSync(archivo)) return porDefecto;
  try {
    return JSON.parse(fs.readFileSync(archivo, 'utf8'));
  } catch (err) {
    console.error(`\nERROR: ${rel} no es un JSON válido.\n${err.message}\n` +
      'Revise comas y comillas. Puede validarlo en https://jsonlint.com\n');
    process.exit(1);
  }
}

function recorrer(dirRel, lista) {
  const dirAbs = path.join(ROOT, dirRel);
  if (!fs.existsSync(dirAbs)) return;
  for (const e of fs.readdirSync(dirAbs, { withFileTypes: true })) {
    if (IGNORAR.has(e.name) || e.name.startsWith('~$')) continue;
    const rel = `${dirRel}/${e.name}`;
    if (e.isDirectory()) recorrer(rel, lista);
    else if (e.isFile()) lista.push({ rel, tam: fs.statSync(path.join(ROOT, rel)).size });
  }
}

// "2026_II" -> "II-2026"
function etiquetaSemestre(id) {
  const m = /^(\d{4})_(I{1,2})$/.exec(id);
  return m ? `${m[2]}-${m[1]}` : id.replace(/_/g, ' ');
}

function tituloDesdeNombre(nombre) {
  const t = nombre.replace(/\.[^.]+$/, '').replace(/[_]+/g, ' ').replace(/\s{2,}/g, ' ').trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

function detectarSubsistemas(rel) {
  const texto = normalizar(rel);
  return SUBSISTEMAS.filter(s => s.claves.some(c => texto.includes(c))).map(s => s.id);
}

function clasificar(partes, ext) {
  const ruta = normalizar(partes.join('/'));
  const nombre = normalizar(partes[partes.length - 1]);
  const carpeta = partes[1];

  if (partes[0] === 'global') {
    if (carpeta === 'datasheets') return 'datasheet';
    if (carpeta === 'manuales') return 'manual';
    if (carpeta === 'normativas') return 'normativa';
    if (carpeta === 'plantillas') return 'plantilla';
  }
  if (ext === 'sql') return 'basedatos';
  if (EXT.modelo3d.includes(ext)) return 'modelo3d';
  if (EXT.imagen.includes(ext)) return 'imagen';
  if (EXT.video.includes(ext)) return 'video';
  if (ext === 'drawio') return 'diagrama';

  const esCad = EXT.plano.includes(ext);
  if (esCad || ['pdf', 'docx', 'doc', 'md'].includes(ext)) {
    if (/mockup/.test(ruta)) return 'mockup';
    if (/electric/.test(nombre) || /\/electrico\//.test(ruta)) return 'electrico';
    if (/guia/.test(nombre)) return 'guia';
    if (/informe/.test(nombre)) return 'informe';
    if (/p&id|p_id|(^|[_\-. ])pid([_\-. ]|$)/.test(nombre) || /\/pid\//.test(ruta)) return 'pid';
    if (esCad) return 'plano';
    if (/diagrama|grafcet|bloques|petri|flujo/.test(nombre)) return 'diagrama';
    if (/manual|datasheet/.test(nombre)) return 'manual';
    return 'informe';
  }
  if (LENGUAJES[ext]) return 'programa';
  if (EXT.presentacion.includes(ext)) return 'presentacion';
  if (EXT.datos.includes(ext)) return 'datos';
  return 'otro';
}

function construir() {
  const semConfig = leerJson('config/semestres.json', { semestres: {} });
  const archConfig = leerJson('config/archivos.json', {});
  const vidConfig = leerJson('config/videos.json', { videos: [] });
  const carpetas = leerJson('config/carpetas.json', {});

  const lista = [];
  for (const c of CARPETAS) recorrer(c, lista);

  // Claves que terminan en "/" se aplican a toda la carpeta (de la más general a la más específica)
  const porCarpeta = Object.entries(archConfig)
    .filter(([k]) => k.endsWith('/'))
    .sort((a, b) => a[0].length - b[0].length);

  const grandes = [];
  const archivos = lista.map(({ rel, tam }) => {
    const partes = rel.split('/');
    const nombre = partes[partes.length - 1];
    const ext = nombre.includes('.') ? nombre.split('.').pop().toLowerCase() : '';
    const semestre = partes[0] === 'semestres' && partes.length > 2 ? partes[1] : 'global';

    const extra = {};
    for (const [k, v] of porCarpeta) if (rel.startsWith(k)) Object.assign(extra, v);
    Object.assign(extra, archConfig[rel] || {});

    const auto = clasificar(partes, ext);
    // Una categoría puesta para toda una carpeta no saca a las imágenes de la galería
    const categoria = extra.categoria && auto !== 'imagen' ? extra.categoria : auto;
    // Los README.md de cada carpeta se ven en el explorador, no en las listas
    const oculto = typeof extra.oculto === 'boolean' ? extra.oculto : nombre.toLowerCase() === 'readme.md';

    const item = {
      ruta: rel,
      nombre,
      ext,
      titulo: extra.titulo || tituloDesdeNombre(nombre),
      semestre,
      categoria,
      subsistemas: extra.subsistemas || detectarSubsistemas(rel),
      tam
    };
    if (extra.descripcion) item.descripcion = extra.descripcion;
    if (extra.orden != null) item.orden = extra.orden;
    if (oculto) item.oculto = true;
    if (categoria === 'programa' || categoria === 'basedatos') item.lenguaje = LENGUAJES[ext] || ext.toUpperCase();
    if (VISTAS[ext]) item.vista = VISTAS[ext];
    if (tam > LIMITE_PAGES) {
      item.github = `https://github.com/${REPO}/raw/${RAMA}/${rel.split('/').map(encodeURIComponent).join('/')}`;
      delete item.vista;
      grandes.push(rel);
    }
    return item;
  });

  const dirSem = path.join(ROOT, 'semestres');
  const ids = fs.existsSync(dirSem)
    ? fs.readdirSync(dirSem, { withFileTypes: true }).filter(d => d.isDirectory()).map(d => d.name)
    : [];
  const semestres = ids.sort().reverse().map(id => {
    const cfg = semConfig.semestres[id] || {};
    return {
      id,
      etiqueta: etiquetaSemestre(id),
      resumen: cfg.resumen || '',
      equipo: cfg.equipo || [],
      docente: cfg.docente || '',
      archivos: archivos.filter(a => a.semestre === id && !a.oculto).length
    };
  });

  const videos = (vidConfig.videos || []).filter(v => v && v.url).map(v => ({
    titulo: v.titulo || 'Video',
    url: v.url,
    semestre: v.semestre || semConfig.actual || 'global',
    subsistemas: v.subsistemas || [],
    descripcion: v.descripcion || ''
  }));

  const catalogo = {
    generado: new Date().toISOString(),
    repo: REPO,
    rama: RAMA,
    actual: semConfig.actual || (semestres[0] && semestres[0].id),
    subsistemas: SUBSISTEMAS.map(({ claves, ...s }) => s),
    categorias: CATEGORIAS,
    carpetas,
    semestres,
    videos,
    archivos
  };

  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.writeFileSync(path.join(OUT_DIR, 'catalogo.js'),
    `// Archivo generado por scripts/build-catalog.js. No editar a mano.\nwindow.CATALOGO = ${JSON.stringify(catalogo)};\n`);

  console.log(`Catálogo: ${archivos.length} archivos, ${semestres.length} semestres, ${videos.length} videos.`);
  if (grandes.length) {
    console.log(`Archivos demasiado grandes para el hosting (se descargan desde GitHub):\n  ${grandes.join('\n  ')}`);
    // Si se publicaran, Cloudflare rechazaría el despliegue completo
    if (EN_CLOUDFLARE) {
      for (const rel of grandes) fs.unlinkSync(path.join(ROOT, rel));
      console.log('Quitados de la copia que se publica en Cloudflare.');
    }
  }

  const sinConfig = Object.keys(archConfig).filter(k => !k.endsWith('/') && !archivos.some(a => a.ruta === k));
  if (sinConfig.length) console.log(`Aviso: config/archivos.json menciona archivos que no existen:\n  ${sinConfig.join('\n  ')}`);
}

construir();
