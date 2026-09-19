/* RoadPulse Telegram Mini App — native Telegram UI with browser fallback. */
const tg = window.Telegram?.WebApp || null;
const inTelegram = !!tg && !!tg.initData;

if (tg) {
  tg.ready();
  tg.expand();
  try { tg.disableVerticalSwipes?.(); } catch (e) { console.warn(e); }
}

// ---------- Identity ----------
const params = new URLSearchParams(location.search);
const API = (params.get('api') || location.origin) + '/api/v1';

const tgUser = tg?.initDataUnsafe?.user || {};
const USER_ID = Number(params.get('uid')) || tgUser.id || 123456789;
const USERNAME = tgUser.username || params.get('username') || null;
const FIRST_NAME = tgUser.first_name || params.get('first_name') || 'Road';

document.getElementById('userName').textContent = FIRST_NAME + (USERNAME ? ' @' + USERNAME : '');
if (tgUser.photo_url) {
  document.getElementById('avatar').innerHTML =
    `<img src="${tgUser.photo_url}" alt="" class="w-9 h-9 rounded-full object-cover"/>`;
} else {
  document.getElementById('avatar').textContent = (FIRST_NAME[0] || 'R').toUpperCase();
}

// ---------- Map ----------
const TASHKENT = [41.311081, 69.279562];
const LIGHT_TILES = 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
const DARK_TILES = 'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png';
const map = L.map('map', { zoomControl: false }).setView(TASHKENT, 13);
L.control.zoom({ position: 'topright' }).addTo(map);
let tileLayer = null;

const markersLayer = L.layerGroup().addTo(map);
let myLatLng = null;
let manualLatLng = null;
let picking = false;
let mapCentered = false;

// ---------- Theme (Telegram themeParams -> CSS vars + map tiles) ----------
function applyTheme() {
  const p = tg?.themeParams || {};
  const css = document.documentElement.style;
  css.setProperty('--app-bg', p.bg_color || '#0f172a');
  css.setProperty('--app-section', p.secondary_bg_color || '#16213a');
  css.setProperty('--app-text', p.text_color || '#ffffff');
  css.setProperty('--app-hint', p.hint_color || '#94a3b8');
  css.setProperty('--app-button', p.button_color || '#dc2626');
  css.setProperty('--app-button-text', p.button_text_color || '#ffffff');
  const scheme = tg?.colorScheme || 'dark';
  document.documentElement.style.colorScheme = scheme;
  try {
    tg?.setHeaderColor?.('secondary_bg_color');
    tg?.setBackgroundColor?.(p.bg_color || '#0f172a');
  } catch (e) { console.warn(e); }

  const wantDark = scheme === 'dark';
  if (tileLayer && tileLayer.options.dark !== wantDark) {
    map.removeLayer(tileLayer);
    tileLayer = null;
  }
  if (!tileLayer) {
    tileLayer = wantDark
      ? L.tileLayer(DARK_TILES, { maxZoom: 19, attribution: '© OpenStreetMap © CARTO', dark: true })
      : L.tileLayer(LIGHT_TILES, { maxZoom: 19, attribution: '© OpenStreetMap', dark: false });
    tileLayer.addTo(map);
  }
}
if (tg?.onEvent) tg.onEvent('themeChanged', applyTheme);

// ---------- Small UI helpers ----------
const $ = id => document.getElementById(id);
const pickModal = $('pickModal');
const historySheet = $('historySheet');
const fileInput = $('fileInput');

function toast(msg, ok = true) {
  const el = $('toast');
  el.textContent = msg;
  el.className = `fixed top-4 inset-x-4 z-[1200] rounded-xl px-4 py-3 text-sm font-semibold text-center ${ok ? 'bg-emerald-600 text-white' : 'bg-red-600 text-white'}`;
  el.classList.remove('hidden');
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add('hidden'), 4200);
}

function iconFor(p) {
  const size = p.severity === 'high' ? 26 : 18;
  let cls = 'dot-green';
  if (p.status === 'in_review') cls = 'dot-yellow';
  else if (p.severity === 'high') cls = 'pulse-red';
  else if (p.severity === 'medium') cls = 'dot-orange';
  else if (p.severity === 'low') cls = 'dot-yellow';
  return L.divIcon({ className: '', html: `<div class="${cls}" style="width:${size}px;height:${size}px"></div>`, iconSize: [size, size], iconAnchor: [size / 2, size / 2] });
}

function absUrl(u) {
  return u && u.startsWith('http') ? u : location.origin + (u || '');
}

/** One-line pit grading for popups, e.g. "🕳️ pit: large (~45×8 cm · urgent)". */
function pitLabel(p) {
  if (!p || !p.pit_category || p.pit_category === 'none') return '';
  const size = p.diameter_cm && p.depth_cm ? ` ~${p.diameter_cm}×${p.depth_cm} cm`
    : p.diameter_cm ? ` ~${p.diameter_cm} cm` : '';
  const prio = p.repair_priority ? ` · ${p.repair_priority}` : '';
  return `<br>🕳️ pit: <b>${p.pit_category}</b>${size}${prio}`;
}

// ---------- Overlays + native BackButton ----------
function overlayOpen() {
  return !pickModal.classList.contains('hidden') || !historySheet.classList.contains('hidden');
}
function syncBackButton() {
  if (!inTelegram) return;
  if (overlayOpen()) tg.BackButton.show();
  else tg.BackButton.hide();
}
function closeTopOverlay() {
  if (!historySheet.classList.contains('hidden')) historySheet.classList.add('hidden');
  else if (!pickModal.classList.contains('hidden')) pickModal.classList.add('hidden');
  picking = false;
  syncBackButton();
}
if (inTelegram) tg.BackButton.onClick(closeTopOverlay);
historySheet.addEventListener('click', e => { if (e.target === historySheet) closeTopOverlay(); });
$('historyClose').onclick = closeTopOverlay;
$('pickCancelBtn').onclick = closeTopOverlay;
$('pickModeBtn').onclick = () => {
  picking = true;
  pickModal.classList.add('hidden');
  syncBackButton();
  toast('Tap anywhere on the map to set location.');
};

// ---------- Native MainButton (Telegram) vs HTML button (browser) ----------
function startReportFlow() {
  tg?.HapticFeedback?.impactOccurred('light');
  const coords = manualLatLng || myLatLng;
  if (!coords) {
    pickModal.classList.remove('hidden');
    syncBackButton();
    return;
  }
  fileInput.click();
}
if (inTelegram) {
  document.body.classList.add('native');
  tg.MainButton.setText('📸 Take Photo / Report');
  tg.MainButton.show();
  tg.MainButton.onClick(startReportFlow);
} else {
  $('reportBtn').onclick = startReportFlow;
}

// ---------- Map data ----------
async function loadPoints() {
  try {
    const b = map.getBounds();
    const q = `?min_lat=${b.getSouth()}&max_lat=${b.getNorth()}&min_lng=${b.getWest()}&max_lng=${b.getEast()}`;
    const res = await fetch(`${API}/map/points${q}`);
    const data = await res.json();
    markersLayer.clearLayers();
    (data.points || []).forEach(p => {
      const crowded = (p.cluster_size || 1) > 3;
      const marker = L.marker([p.lat, p.lng], { icon: iconFor({ ...p, severity: crowded ? 'high' : p.severity }) });
      const statusColor = p.status === 'in_review' ? '#a16207' : '#15803d';
      marker.bindPopup(`<b>${p.defect_type}</b> · ${p.severity}${pitLabel(p)}<br><span style="color:${statusColor}">${p.status}</span><br><img src="${absUrl(p.image_url)}" width="180" style="border-radius:8px;margin-top:4px" onerror="this.remove()"/>`);
      marker.addTo(markersLayer);
    });
  } catch (e) { console.warn('map load failed', e); }
}

async function refreshPoints() {
  try {
    const res = await fetch(`${API}/users/${USER_ID}`);
    if (res.ok) {
      const u = await res.json();
      $('pointsBadge').textContent = `⭐️ ${u.points}`;
      const adminBtn = $('adminBtn');
      if (u.is_admin) {
        adminBtn.classList.remove('hidden');
        adminBtn.onclick = () => { location.href = location.origin + '/dashboard/'; };
      } else {
        adminBtn.classList.add('hidden');
      }
    }
  } catch (e) { console.warn('points refresh failed', e); }
}

map.on('moveend', loadPoints);
map.on('click', e => {
  if (!picking) return;
  manualLatLng = { lat: e.latlng.lat, lng: e.latlng.lng };
  picking = false;
  pickModal.classList.add('hidden');
  syncBackButton();
  toast(`Location set: ${manualLatLng.lat.toFixed(5)}, ${manualLatLng.lng.toFixed(5)} — now choose a photo.`);
  fileInput.click();
});

// ---------- GPS ----------
const gpsHint = $('gpsHint');
if (navigator.geolocation) {
  navigator.geolocation.watchPosition(
    pos => {
      myLatLng = { lat: pos.coords.latitude, lng: pos.coords.longitude };
      gpsHint.textContent = `📍 ${myLatLng.lat.toFixed(4)}, ${myLatLng.lng.toFixed(4)}`;
      if (!mapCentered) { map.setView([myLatLng.lat, myLatLng.lng], 15); mapCentered = true; }
    },
    () => { gpsHint.textContent = 'GPS off — tap 📸 to pick on map'; },
    { enableHighAccuracy: true }
  );
} else {
  gpsHint.textContent = 'Geolocation not supported';
}

// ---------- My reports sheet ----------
function statusStyle(s) {
  if (s === 'repaired') return 'background:#064e3b;color:#6ee7b7';
  if (s === 'in_review') return 'background:#78350f;color:#fcd34d';
  return 'background:#7f1d1d;color:#fca5a5';
}

function historyRow(x) {
  const reward = x.status === 'active' ? '+10 ⭐️' : x.status === 'repaired' ? '✓ done' : '⏳ review';
  const date = (x.created_at || '').slice(0, 16).replace('T', ' ');
  return `
    <div class="flex items-center gap-3 bg-black/20 rounded-2xl p-2.5">
      <img class="hist-thumb" src="${absUrl(x.image_url)}" loading="lazy" onerror="this.remove()"/>
      <div class="min-w-0 flex-1">
        <div class="text-sm font-bold capitalize truncate">${x.defect_type} · ${x.severity}</div>
        <div class="text-xs opacity-70">${date} · 🕳️ ${x.pit_category || '—'} · ${x.repair_priority || ''}</div>
      </div>
      <div class="text-right shrink-0">
        <div class="text-xs font-bold rounded-full px-2 py-0.5 mb-1" style="${statusStyle(x.status)}">${x.status}</div>
        <div class="text-xs font-bold">${reward}</div>
      </div>
    </div>`;
}

async function openHistory() {
  tg?.HapticFeedback?.impactOccurred('light');
  $('sheetTitle').textContent = '📋 My reports';
  historySheet.classList.remove('hidden');
  syncBackButton();
  const list = $('historyList');
  list.innerHTML = '<p class="text-sm opacity-60 text-center py-6">Loading…</p>';
  try {
    const res = await fetch(`${API}/users/${USER_ID}/reports?limit=20`);
    if (res.status === 404 || !res.ok) {
      list.innerHTML = '<p class="text-sm opacity-60 text-center py-6">No reports yet — tap 📸 to file the first one.</p>';
      return;
    }
    const { reports } = await res.json();
    list.innerHTML = reports.length
      ? reports.map(historyRow).join('')
      : '<p class="text-sm opacity-60 text-center py-6">No reports yet — tap 📸 to file the first one.</p>';
  } catch (e) {
    console.warn('history failed', e);
    list.innerHTML = '<p class="text-sm opacity-60 text-center py-6">Offline — could not load reports.</p>';
  }
}
$('historyBtn').onclick = openHistory;
$('leadersBtn').onclick = openLeaders;

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function leaderRow(l, i) {
  const medal = ['🥇', '🥈', '🥉'][i] || `${i + 1}.`;
  const name = esc((l.first_name || 'Road') + (l.username ? ' @' + l.username : '') + (l.id === USER_ID ? ' · you' : ''));
  return `
    <div class="flex items-center gap-3 bg-black/20 rounded-2xl p-2.5">
      <div class="text-xl w-8 text-center shrink-0">${medal}</div>
      <div class="text-sm font-bold truncate flex-1">${name}</div>
      <div class="text-sm font-bold shrink-0">⭐️ ${l.points}</div>
    </div>`;
}

async function openLeaders() {
  tg?.HapticFeedback?.impactOccurred('light');
  $('sheetTitle').textContent = '🏆 Top reporters';
  historySheet.classList.remove('hidden');
  syncBackButton();
  const list = $('historyList');
  list.innerHTML = '<p class="text-sm opacity-60 text-center py-6">Loading…</p>';
  try {
    const res = await fetch(`${API}/users/leaderboard?limit=10`);
    const { leaders } = await res.json();
    list.innerHTML = leaders.length
      ? leaders.map(leaderRow).join('')
      : '<p class="text-sm opacity-60 text-center py-6">No reporters yet.</p>';
  } catch (e) {
    console.warn('leaders failed', e);
    list.innerHTML = '<p class="text-sm opacity-60 text-center py-6">Offline — could not load.</p>';
  }
}

// Downscale huge photos before upload (slow networks, 10 MB server limit).
async function preparePhoto(file) {
  try {
    const bitmap = await createImageBitmap(file);
    const maxDim = 1600;
    const scale = Math.min(1, maxDim / Math.max(bitmap.width, bitmap.height));
    if (scale === 1 && file.size <= 2 * 1024 * 1024) { bitmap.close(); return file; }
    const canvas = document.createElement('canvas');
    canvas.width = Math.round(bitmap.width * scale);
    canvas.height = Math.round(bitmap.height * scale);
    canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
    bitmap.close();
    const blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg', 0.85));
    return blob ? new File([blob], 'road.jpg', { type: 'image/jpeg' }) : file;
  } catch (e) { console.warn('compression skipped', e); return file; }
}

// ---------- Upload ----------
fileInput.onchange = async () => {
  const file = fileInput.files[0];
  if (!file) return;
  const coords = manualLatLng || myLatLng;
  if (!coords) { toast('No location. Enable GPS or pick on map.', false); fileInput.value = ''; return; }

  $('loader').classList.remove('hidden');
  if (inTelegram) tg.MainButton.showProgress();
  try {
    const photo = await preparePhoto(file);
    const fd = new FormData();
    fd.append('photo', photo, 'road.jpg');
    fd.append('latitude', coords.lat);
    fd.append('longitude', coords.lng);
    fd.append('telegram_user_id', USER_ID);
    if (USERNAME) fd.append('username', USERNAME);
    fd.append('first_name', FIRST_NAME);

    const headers = {};
    if (tg?.initData) headers['X-Telegram-Init-Data'] = tg.initData;
    const res = await fetch(`${API}/reports`, { method: 'POST', headers, body: fd });
    const data = await res.json();
    if (res.status === 201 && data.status === 'success') {
      const d = data.data;
      toast(`✅ ${d.message} (+${d.points_awarded} pts · ${d.pit_category} pit)`);
      manualLatLng = null;
      loadPoints(); refreshPoints();
      tg?.HapticFeedback?.notificationOccurred('success');
    } else if (res.status === 422) {
      toast(`❌ Rejected: ${data.reason || 'no defect detected'}`, false);
      tg?.HapticFeedback?.notificationOccurred('error');
    } else {
      toast(`❌ Upload failed: ${data.detail || res.status}`, false);
      tg?.HapticFeedback?.notificationOccurred('error');
    }
  } catch (e) {
    console.warn('upload failed', e);
    toast('❌ Network error. Is the backend running?', false);
  } finally {
    if (inTelegram) tg.MainButton.hideProgress();
    $('loader').classList.add('hidden');
    fileInput.value = '';
  }
};

// ---------- Boot ----------
applyTheme();
loadPoints();
refreshPoints();
setInterval(() => { loadPoints(); refreshPoints(); }, 30000);
