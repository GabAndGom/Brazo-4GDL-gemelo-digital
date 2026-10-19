const CONFIG = {
  user: 'GabAndGom',
  repo: 'Brazo-de-4-grados-de-libertad',
  branch: 'main' // Si tu rama es 'master', el script lo detecta automáticamente abajo
};

let RAW_BASE = '';
let allFiles = [];

// Extensiones reconocidas para cada sección
const EXT_DOCS = ['pdf', 'doc', 'docx', 'ppt', 'pptx', 'xls', 'xlsx', 'txt', 'md'];
const EXT_CODE = [
  'awl', 'mwp', 's7p',           // PLC Siemens S7-200
  'c', 'cpp', 'h', 'ino', 'pbp', // Microcontroladores (ESP32, Arduino, PIC)
  'm', 'slx', 'mdl',             // MATLAB / Simulink
  'py', 'sh', 'sql', 'json',     // Scripts y datos
  'dxf', 'dwg', 'stl', 'step',   // Planos CAD y modelos 3D del brazo
  'pdsprj', 'dsn', 'sch', 'kicad_pcb' // Proteus / KiCad
];
const EXT_IMG = ['png', 'jpg', 'jpeg', 'webp', 'gif', 'svg'];

async function initPortal() {
  try {
    // 1. Obtener información del repositorio para saber si usa 'main' o 'master'
    const repoInfoRes = await fetch(`https://api.github.com/repos/${CONFIG.user}/${CONFIG.repo}`);
    if (repoInfoRes.ok) {
      const repoInfo = await repoInfoRes.json();
      CONFIG.branch = repoInfo.default_branch || 'main';
    }

    RAW_BASE = `https://raw.githubusercontent.com/${CONFIG.user}/${CONFIG.repo}/${CONFIG.branch}/`;
    const treeUrl = `https://api.github.com/repos/${CONFIG.user}/${CONFIG.repo}/git/trees/${CONFIG.branch}?recursive=1`;

    const res = await fetch(treeUrl);
    const data = await res.json();

    // Excluir los propios archivos de la interfaz web
    allFiles = (data.tree || []).filter(item =>
      !item.path.startsWith('web/') && item.path !== 'index.html'
    );

    populateFilters(allFiles);
    updateCounters(allFiles);
    renderDocs();
    renderCode();
    renderGallery(allFiles);
    renderRepoExplorer('');
    loadReadme('README.md');
  } catch (err) {
    console.error('Error al conectar con GitHub:', err);
  }
}

function getExt(path) {
  const parts = path.split('.');
  return parts.length > 1 ? parts.pop().toLowerCase() : '';
}

function getTopFolder(path) {
  const parts = path.split('/');
  return parts.length > 1 ? parts[0] : 'Raíz';
}

function updateCounters(files) {
  const blobs = files.filter(f => f.type === 'blob');
  document.getElementById('count-docs').textContent = blobs.filter(f => EXT_DOCS.includes(getExt(f.path))).length;
  document.getElementById('count-code').textContent = blobs.filter(f => EXT_CODE.includes(getExt(f.path))).length;
  document.getElementById('count-img').textContent  = blobs.filter(f => EXT_IMG.includes(getExt(f.path))).length;
}

function populateFilters(files) {
  const blobs = files.filter(f => f.type === 'blob');

  // Carpetas para documentos
  const folders = [...new Set(blobs.map(f => getTopFolder(f.path)))].sort();
  const folderSelect = document.getElementById('filter-docs-folder');
  folders.forEach(folder => {
    const opt = document.createElement('option');
    opt.value = folder;
    opt.textContent = `Carpeta: ${folder}`;
    folderSelect.appendChild(opt);
  });

  // Extensiones para programas
  const codeExts = [...new Set(blobs.map(f => getExt(f.path)).filter(ext => EXT_CODE.includes(ext)))].sort();
  const extSelect = document.getElementById('filter-code-ext');
  codeExts.forEach(ext => {
    const opt = document.createElement('option');
    opt.value = ext;
    opt.textContent = `.${ext.toUpperCase()}`;
    extSelect.appendChild(opt);
  });
}

function renderDocs() {
  const query = document.getElementById('search-docs').value.toLowerCase();
  const folder = document.getElementById('filter-docs-folder').value;
  const container = document.getElementById('docs-grid');

  const docs = allFiles.filter(f => {
    if (f.type !== 'blob' || !EXT_DOCS.includes(getExt(f.path))) return false;
    if (folder && getTopFolder(f.path) !== folder) return false;
    return f.path.toLowerCase().includes(query);
  });

  container.innerHTML = docs.length ? docs.map(f => `
    <div class="card">
      <div>
        <span class="badge">${getExt(f.path).toUpperCase()}</span>
        <h4>${f.path.split('/').pop()}</h4>
        <small>${f.path}</small>
      </div>
      <button class="btn btn-outline btn-sm" onclick="openPreview('${f.path}')">Abrir documento</button>
    </div>
  `).join('') : '<p>No se encontraron documentos con ese filtro.</p>';
}

function renderCode() {
  const query = document.getElementById('search-code').value.toLowerCase();
  const extFilter = document.getElementById('filter-code-ext').value;
  const container = document.getElementById('code-grid');

  const codes = allFiles.filter(f => {
    const ext = getExt(f.path);
    if (f.type !== 'blob' || !EXT_CODE.includes(ext)) return false;
    if (extFilter && ext !== extFilter) return false;
    return f.path.toLowerCase().includes(query);
  });

  container.innerHTML = codes.length ? codes.map(f => `
    <div class="card">
      <div>
        <span class="badge">.${getExt(f.path).toUpperCase()}</span>
        <h4>${f.path.split('/').pop()}</h4>
        <small>${f.path}</small>
      </div>
      <button class="btn btn-outline btn-sm" onclick="openPreview('${f.path}')">Ver / Descargar</button>
    </div>
  `).join('') : '<p>No hay programas con ese criterio.</p>';
}

function renderGallery(files) {
  const container = document.getElementById('gallery-grid');
  const imgs = files.filter(f => f.type === 'blob' && EXT_IMG.includes(getExt(f.path)));

  container.innerHTML = imgs.length ? imgs.map(f => `
    <div class="gallery-item" onclick="openPreview('${f.path}')">
      <img src="${RAW_BASE + encodeURI(f.path)}" alt="${f.path}" loading="lazy">
      <span>${f.path.split('/').pop()}</span>
    </div>
  `).join('') : '<p>Sube imágenes (.png, .jpg) a tu repositorio para verlas aquí automáticamente.</p>';
}

function renderRepoExplorer(currentDir) {
  document.getElementById('breadcrumb').textContent = '/ ' + currentDir;
  const list = document.getElementById('repo-tree');
  const itemsInDir = new Map();

  allFiles.forEach(item => {
    if (!item.path.startsWith(currentDir)) return;
    const relative = item.path.slice(currentDir.length);
    const parts = relative.split('/').filter(Boolean);

    if (parts.length === 1) {
      itemsInDir.set(parts[0], { name: parts[0], path: item.path, isDir: item.type === 'tree' });
    } else if (parts.length > 1) {
      const folderName = parts[0];
      if (!itemsInDir.has(folderName)) {
        itemsInDir.set(folderName, { name: folderName, path: currentDir + folderName + '/', isDir: true });
      }
    }
  });

  let html = '';
  if (currentDir !== '') {
    const parent = currentDir.split('/').filter(Boolean).slice(0, -1).join('/');
    const parentPath = parent ? parent + '/' : '';
    html += `<li onclick="renderRepoExplorer('${parentPath}')"><strong>⬅ .. (Subir nivel)</strong><small>Carpeta</small></li>`;
  }

  Array.from(itemsInDir.values())
    .sort((a, b) => b.isDir - a.isDir || a.name.localeCompare(b.name))
    .forEach(item => {
      if (item.isDir) {
        html += `<li onclick="renderRepoExplorer('${item.path}')"><span>📁 ${item.name}</span><small>Carpeta</small></li>`;
      } else {
        html += `<li onclick="openPreview('${item.path}')"><span>📄 ${item.name}</span><small>${getExt(item.name).toUpperCase()}</small></li>`;
      }
    });

  list.innerHTML = html || '<li>Carpeta vacía</li>';

  // Si la carpeta tiene su propio README.md, mostrarlo abajo
  const folderReadme = currentDir + 'README.md';
  if (allFiles.some(f => f.path.toLowerCase() === folderReadme.toLowerCase())) {
    loadReadme(folderReadme);
  }
}

async function loadReadme(path) {
  const viewer = document.getElementById('readme-viewer');
  try {
    const res = await fetch(RAW_BASE + encodeURI(path));
    if (!res.ok) throw new Error();
    const md = await res.text();
    viewer.innerHTML = marked.parse(md);
  } catch {
    viewer.innerHTML = '<p>No se encontró un archivo README.md en esta ubicación.</p>';
  }
}

async function openPreview(path) {
  const modal = document.getElementById('preview-modal');
  const body = document.getElementById('modal-body');
  const ext = getExt(path);
  const rawUrl = RAW_BASE + encodeURI(path);

  document.getElementById('modal-title').textContent = path.split('/').pop();
  document.getElementById('modal-path').textContent = path;
  document.getElementById('modal-download').href = rawUrl;
  document.getElementById('modal-external').href = rawUrl;
  modal.hidden = false;
  body.innerHTML = '<pre>Cargando vista previa...</pre>';

  if (ext === 'pdf') {
    body.innerHTML = `<iframe src="https://docs.google.com/viewer?url=${encodeURIComponent(rawUrl)}&embedded=true"></iframe>`;
  } else if (EXT_IMG.includes(ext)) {
    body.innerHTML = `<div style="display:flex;justify-content:center;align-items:center;height:100%;padding:1rem;"><img src="${rawUrl}" style="max-width:100%;max-height:78vh;border-radius:6px;"></div>`;
  } else if (ext === 'md') {
    const text = await (await fetch(rawUrl)).text();
    body.innerHTML = `<div style="background:#fff;color:#0f172a;padding:1.5rem;height:100%;overflow:auto;">${marked.parse(text)}</div>`;
  } else if (['awl', 'c', 'cpp', 'h', 'ino', 'py', 'm', 'sql', 'txt', 'json', 'sh', 'pbp'].includes(ext)) {
    const text = await (await fetch(rawUrl)).text();
    const escaped = text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    body.innerHTML = `<pre><code>${escaped}</code></pre>`;
  } else {
    body.innerHTML = `
      <div style="padding:3rem;text-align:center;">
        <p style="margin-bottom:1rem;">Este formato de ingeniería (<strong>.${ext.toUpperCase()}</strong>) es binario y requiere abrirse en su software original (Micro/WIN, Simulink, CAD, Proteus, etc.).</p>
        <a href="${rawUrl}" download class="btn btn-primary">Descargar archivo (${path.split('/').pop()})</a>
      </div>`;
  }
}

document.getElementById('modal-close').onclick = () => {
  document.getElementById('preview-modal').hidden = true;
};
document.getElementById('search-docs').oninput = renderDocs;
document.getElementById('filter-docs-folder').onchange = renderDocs;
document.getElementById('search-code').oninput = renderCode;
document.getElementById('filter-code-ext').onchange = renderCode;

initPortal();