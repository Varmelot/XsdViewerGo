import './style.css';
import { OpenFileDialog, LoadXSD } from '../wailsjs/go/main/App';
import { EventsOn } from '../wailsjs/runtime/runtime';

// Auto-load file passed as CLI argument
EventsOn('load-file', path => loadFile(path));

// ─── State ──────────────────────────────────────────────────────────────────
let allRows = [];       // flat list of {el, node, depth, childRows, collapsed}
let selectedRow = null;
let fontSize = 13;
let searchTerm = '';

// ─── DOM refs ────────────────────────────────────────────────────────────────
const treeBody   = document.getElementById('tree-body');
const legendBar  = document.getElementById('legend-bar');
const attrBody   = document.getElementById('attr-body');
const statusBar  = document.getElementById('statusbar');
const searchInput = document.getElementById('search-input');

// ─── Toolbar buttons ─────────────────────────────────────────────────────────
document.getElementById('btn-open').addEventListener('click', openFile);
document.getElementById('btn-expand').addEventListener('click', () => setAllCollapsed(false));
document.getElementById('btn-collapse').addEventListener('click', () => setAllCollapsed(true));
document.getElementById('btn-zoom-in').addEventListener('click', () => changeZoom(1));
document.getElementById('btn-zoom-out').addEventListener('click', () => changeZoom(-1));
document.getElementById('btn-zoom-reset').addEventListener('click', () => changeZoom(0));

const searchClear = document.getElementById('search-clear');
searchInput.addEventListener('input', e => {
  searchTerm = e.target.value;
  searchClear.style.display = searchTerm ? 'block' : 'none';
  applySearch();
});
searchClear.addEventListener('click', () => {
  searchInput.value = '';
  searchTerm = '';
  searchClear.style.display = 'none';
  applySearch();
  searchInput.focus();
});

// ─── Keyboard shortcuts ───────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  if (e.ctrlKey && e.key === '+') { e.preventDefault(); changeZoom(1); }
  if (e.ctrlKey && e.key === '-') { e.preventDefault(); changeZoom(-1); }
  if (e.ctrlKey && e.key === '0') { e.preventDefault(); changeZoom(0); }
  if (e.ctrlKey && e.key === 'f') { e.preventDefault(); searchInput.focus(); }
  if (e.key === 'F2') { copyNodeName(); }
});

// ─── Resizer drag ────────────────────────────────────────────────────────────
const resizer   = document.getElementById('resizer');
const treeArea  = document.getElementById('tree-area');
const sidebar   = document.getElementById('sidebar');
let resizing = false, resizeStartX = 0, resizeStartW = 0;

resizer.addEventListener('mousedown', e => {
  resizing = true; resizeStartX = e.clientX; resizeStartW = treeArea.offsetWidth;
  resizer.classList.add('active');
});
document.addEventListener('mousemove', e => {
  if (!resizing) return;
  const dx = e.clientX - resizeStartX;
  treeArea.style.flex = 'none';
  treeArea.style.width = Math.max(300, resizeStartW + dx) + 'px';
});
document.addEventListener('mouseup', () => { resizing = false; resizer.classList.remove('active'); });

// ─── Open file ───────────────────────────────────────────────────────────────
async function openFile() {
  const path = await OpenFileDialog();
  if (!path) return;
  await loadFile(path);
}

async function loadFile(path) {
  setStatus('Загрузка: ' + path);
  try {
    const result = await LoadXSD(path);
    if (result.error) { setStatus('Ошибка: ' + result.error); return; }
    renderAll(result);
    setStatus('Загружено: ' + path.split('/').pop());
  } catch(e) {
    setStatus('Ошибка: ' + e);
  }
}

// ─── Render ──────────────────────────────────────────────────────────────────
function renderAll(result) {
  treeBody.innerHTML = '';
  legendBar.innerHTML = '';
  attrBody.innerHTML = '';
  allRows = [];
  selectedRow = null;

  // legend
  (result.legend || []).forEach(item => {
    const chip = document.createElement('div');
    chip.className = 'legend-chip';
    chip.textContent = item.fileName;
    chip.style.backgroundColor = item.color;
    legendBar.appendChild(chip);
  });

  // build flat rows
  (result.nodes || []).forEach(node => buildRows(node, 0));

  // render all rows into DOM
  const frag = document.createDocumentFragment();
  allRows.forEach(r => frag.appendChild(r.el));
  treeBody.appendChild(frag);
}

function buildRows(node, depth) {
  const hasChildren = node.children && node.children.length > 0;
  const el = createRowEl(node, depth, hasChildren);
  const rowObj = { el, node, depth, childRows: [], collapsed: false };
  allRows.push(rowObj);

  if (hasChildren) {
    node.children.forEach(child => {
      const childRows = buildRows(child, depth + 1);
      rowObj.childRows.push(...childRows);
    });
  }
  return [rowObj, ...rowObj.childRows];
}

function createRowEl(node, depth, hasChildren) {
  const row = document.createElement('div');
  row.className = 'tree-row';
  row.style.backgroundColor = node.color || '#fff';

  // name cell
  const cellName = document.createElement('div');
  cellName.className = 'cell-name';

  const indent = document.createElement('span');
  indent.className = 'indent';
  indent.style.width = (depth * 20) + 'px';
  cellName.appendChild(indent);

  if (hasChildren) {
    const toggle = document.createElement('span');
    toggle.className = 'toggle-btn';
    toggle.textContent = '▼';
    toggle.addEventListener('click', e => { e.stopPropagation(); toggleRow(row); });
    cellName.appendChild(toggle);
  } else {
    const spacer = document.createElement('span');
    spacer.className = 'toggle-btn';
    spacer.textContent = '';
    cellName.appendChild(spacer);
  }

  const nameSpan = document.createElement('span');
  nameSpan.className = 'name-text';
  nameSpan.dataset.text = node.name || '';
  cellName.appendChild(nameSpan);

  // type cell
  const cellType = document.createElement('div');
  cellType.className = 'cell-type';
  const typeSpan = document.createElement('span');
  typeSpan.dataset.text = (node.typeInfo ? node.typeInfo + ' ' : '') + (node.occurs || '');
  cellType.appendChild(typeSpan);

  // annotation cell
  const cellAnno = document.createElement('div');
  cellAnno.className = 'cell-anno';
  const annoSpan = document.createElement('span');
  annoSpan.dataset.text = node.annotation || '';
  cellAnno.appendChild(annoSpan);

  row.appendChild(cellName);
  row.appendChild(cellType);
  row.appendChild(cellAnno);

  // click to select
  row.addEventListener('click', () => selectRow(row, node));

  // store node ref
  row._node = node;

  renderCellText(nameSpan, node.name || '');
  renderCellText(typeSpan, (node.typeInfo ? node.typeInfo + ' ' : '') + (node.occurs || ''));
  renderCellText(annoSpan, node.annotation || '');

  return row;
}

// ─── Text with search highlight ───────────────────────────────────────────────
function renderCellText(span, text) {
  if (!searchTerm || !text.toLowerCase().includes(searchTerm.toLowerCase())) {
    span.textContent = text;
    return;
  }
  span.innerHTML = '';
  const lower = text.toLowerCase();
  const st = searchTerm.toLowerCase();
  let pos = 0;
  while (pos < text.length) {
    const idx = lower.indexOf(st, pos);
    if (idx === -1) {
      span.appendChild(document.createTextNode(text.slice(pos)));
      break;
    }
    if (idx > pos) span.appendChild(document.createTextNode(text.slice(pos, idx)));
    const mark = document.createElement('span');
    mark.className = 'hl';
    mark.textContent = text.slice(idx, idx + searchTerm.length);
    span.appendChild(mark);
    pos = idx + searchTerm.length;
  }
}

// ─── Selection ────────────────────────────────────────────────────────────────
function selectRow(rowEl, node) {
  if (selectedRow) selectedRow.classList.remove('selected');
  rowEl.classList.add('selected');
  selectedRow = rowEl;
  renderSidebar(node.attributes || {});
}

function renderSidebar(attrs) {
  attrBody.innerHTML = '';
  const entries = Object.entries(attrs).sort((a, b) => a[0].localeCompare(b[0]));
  entries.forEach(([k, v]) => {
    const tr = document.createElement('tr');
    const td1 = document.createElement('td'); td1.textContent = k;
    const td2 = document.createElement('td'); td2.textContent = v;
    tr.appendChild(td1); tr.appendChild(td2);
    attrBody.appendChild(tr);
  });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────
function getDirectChildren(rowObj) {
  return rowObj.childRows.filter(cr => cr.depth === rowObj.depth + 1);
}

function setToggleBtn(rowObj, collapsed) {
  if (rowObj.childRows.length === 0) return;
  const btn = rowObj.el.querySelector('.toggle-btn');
  if (btn) btn.textContent = collapsed ? '▶' : '▼';
}

// ─── Expand / Collapse ────────────────────────────────────────────────────────
function toggleRow(rowEl) {
  const rowObj = allRows.find(r => r.el === rowEl);
  if (!rowObj) return;
  rowObj.collapsed = !rowObj.collapsed;
  setToggleBtn(rowObj, rowObj.collapsed);
  setDescendantsHidden(rowObj, rowObj.collapsed);
}

function setDescendantsHidden(rowObj, hidden) {
  if (hidden) {
    rowObj.childRows.forEach(child => child.el.classList.add('hidden'));
  } else {
    getDirectChildren(rowObj).forEach(child => {
      child.el.classList.remove('hidden');
      if (!child.collapsed) setDescendantsHidden(child, false);
    });
  }
}

function setAllCollapsed(collapsed) {
  allRows.forEach(r => {
    r.collapsed = collapsed && r.childRows.length > 0;
    setToggleBtn(r, r.collapsed);
    if (r.depth === 0) r.el.classList.remove('hidden');
    else r.el.classList.toggle('hidden', collapsed);
  });
  if (!collapsed) allRows.forEach(r => r.el.classList.remove('hidden'));
}

// Expand the path from any root down to targetObj, keeping everything else collapsed.
function expandPathTo(targetObj) {
  const ancestors = allRows.filter(r => r.childRows.includes(targetObj));
  const ancestorSet = new Set(ancestors);

  ancestors.forEach(ancestor => {
    ancestor.collapsed = false;
    ancestor.el.classList.remove('hidden');
    setToggleBtn(ancestor, false);

    // Show direct children; siblings of the path stay collapsed
    getDirectChildren(ancestor).forEach(child => {
      child.el.classList.remove('hidden');
      if (!ancestorSet.has(child) && child !== targetObj) {
        if (child.childRows.length > 0) {
          child.collapsed = true;
          setToggleBtn(child, true);
        }
      }
    });
  });

  targetObj.el.classList.remove('hidden');
  targetObj.el.scrollIntoView({ block: 'center', behavior: 'smooth' });
}

// ─── Search ───────────────────────────────────────────────────────────────────
function applySearch() {
  const st = searchTerm.toLowerCase();

  // re-render all text spans with highlight
  allRows.forEach(rowObj => {
    const node = rowObj._node || rowObj.el._node;
    const spans = rowObj.el.querySelectorAll('[data-text]');
    spans.forEach(span => {
      renderCellText(span, span.dataset.text);
    });
  });

  if (!st) {
    // Collapse everything to top-level
    allRows.forEach(r => {
      const hasKids = r.childRows.length > 0;
      r.collapsed = hasKids;
      setToggleBtn(r, r.collapsed);
      r.el.classList.toggle('hidden', r.depth > 0);
    });
    // Restore path to the selected row so the user doesn't lose their place
    if (selectedRow) {
      const selObj = allRows.find(r => r.el === selectedRow);
      if (selObj) expandPathTo(selObj);
    }
    return;
  }

  // determine which rows match
  allRows.forEach(r => {
    const node = r.el._node;
    const text = [node.name, node.typeInfo, node.occurs, node.annotation]
      .filter(Boolean).join(' ').toLowerCase();
    r._matches = text.includes(st);
  });

  // propagate: if a row matches, all ancestors must be visible
  function hasMatchingDescendant(rowObj) {
    if (rowObj._matches) return true;
    return rowObj.childRows.some(hasMatchingDescendant);
  }

  allRows.forEach(rowObj => {
    const visible = rowObj._matches || hasMatchingDescendant(rowObj);
    rowObj.el.classList.toggle('hidden', !visible);
    if (visible) {
      rowObj.collapsed = false;
      const btn = rowObj.el.querySelector('.toggle-btn');
      if (btn && rowObj.childRows.length > 0) btn.textContent = '▼';
    }
  });
}

// ─── Copy node name (F2) ─────────────────────────────────────────────────────
function copyNodeName() {
  if (!selectedRow) return;
  const node = selectedRow._node;
  if (!node) return;
  let name = (node.name || '').replace(/^● /, '').split(' (')[0].replace(/^@/, '');
  navigator.clipboard.writeText(name).then(() => setStatus('Скопировано: ' + name, 4000));
}

// ─── Zoom ────────────────────────────────────────────────────────────────────
function changeZoom(delta) {
  if (delta === 0) fontSize = 13;
  else fontSize = Math.max(8, Math.min(40, fontSize + delta));
  document.body.style.fontSize = fontSize + 'px';
}

// ─── Status ──────────────────────────────────────────────────────────────────
let statusTimer = null;
function setStatus(msg, timeout) {
  statusBar.textContent = msg;
  if (statusTimer) clearTimeout(statusTimer);
  if (timeout) statusTimer = setTimeout(() => { statusBar.textContent = ''; }, timeout);
}
