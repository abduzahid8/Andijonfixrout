/* RoadPulse Admin Dashboard */
const params = new URLSearchParams(location.search);
const API = (params.get('api') || location.origin) + '/api/v1';

const map = L.map('map').setView([41.311081, 69.279562], 12);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map);
let heatLayer = null;
const markersLayer = L.layerGroup().addTo(map);

const sevColor = s => s === 'high' ? '#dc2626' : s === 'medium' ? '#ea580c' : '#ca8a04';
const sevWeight = s => s === 'high' ? 1.0 : s === 'medium' ? 0.6 : 0.35;
const prioStyle = p =>
  p === 'emergency' ? 'background:#7f1d1d;color:#fca5a5' :
  p === 'urgent' ? 'background:#7c2d12;color:#fdba74' :
  p === 'scheduled' ? 'background:#78350f;color:#fcd34d' :
  'background:#064e3b;color:#6ee7b7';
const statusBadge = s =>
  s === 'repaired' ? '<span class="badge bg-emerald-900 text-emerald-300">repaired</span>' :
  s === 'in_review' ? '<span class="badge bg-amber-900 text-amber-300">in_review</span>' :
  '<span class="badge bg-red-900 text-red-300">active</span>';

function absUrl(u) {
  return u && u.startsWith('http') ? u : location.origin + (u || '');
}

/** Heat intensity: emergency pits always burn brightest; otherwise severity
 *  weight plus boosts for crowded cells and urgent repairs. */
function heatIntensity(p) {
  if (p.repair_priority === 'emergency') return 1.0;
  const boost = Math.min(0.3, 0.1 * ((p.cluster_size || 1) - 1))
    + (p.repair_priority === 'urgent' ? 0.15 : 0);
  return Math.min(1, sevWeight(p.severity) + boost);
}

/** One-line pit grading for popups, e.g. "🕳️ large (~45×8 cm · urgent)". */
function pitLabel(p) {
  if (!p || !p.pit_category || p.pit_category === 'none') return '';
  const size = p.diameter_cm && p.depth_cm ? ` ~${p.diameter_cm}×${p.depth_cm} cm`
    : p.diameter_cm ? ` ~${p.diameter_cm} cm` : '';
  const prio = p.repair_priority ? ` · ${p.repair_priority}` : '';
  return `<br>🕳️ <b>${p.pit_category}</b>${size}${prio}`;
}

async function loadStats() {
  const r = await fetch(`${API}/admin/stats`);
  const s = await r.json();
  document.getElementById('statTotal').textContent = s.total_defects;
  document.getElementById('statHigh').textContent = s.high_risk_potholes;
  document.getElementById('statRepaired').textContent = s.repaired_count;
  document.getElementById('statReview').textContent = s.in_review_count ?? 0;
  document.getElementById('zones').innerHTML = (s.critical_zones || []).map((z, i) => `
    <div class="flex items-center justify-between bg-slate-800/70 rounded-xl px-3 py-2">
      <span><b class="${i === 0 ? 'text-red-400' : ''}">${i + 1}. ${z.street_name}</b></span>
      <span class="badge ${i === 0 ? 'bg-red-600' : 'bg-slate-700'}">${z.defect_count}</span>
    </div>`).join('') || '<p class="text-slate-500">no data</p>';
  document.getElementById('updatedAt').textContent = 'updated ' + new Date().toLocaleTimeString();
}

async function loadMap() {
  const r = await fetch(`${API}/map/points`);
  const d = await r.json();
  const pts = d.points || [];
  if (heatLayer) map.removeLayer(heatLayer);
  heatLayer = L.heatLayer(
    pts.map(p => [p.lat, p.lng, heatIntensity(p)]),
    { radius: 30, blur: 22, maxZoom: 17, gradient: { 0.2: '#22c55e', 0.45: '#eab308', 0.7: '#f97316', 0.9: '#dc2626' } }
  );
  if (document.getElementById('heatToggle').checked) heatLayer.addTo(map);
  markersLayer.clearLayers();
  if (document.getElementById('markerToggle').checked) {
    pts.forEach(p => {
      L.circleMarker([p.lat, p.lng], { radius: p.severity === 'high' ? 8 : 5, color: sevColor(p.severity), fillColor: sevColor(p.severity), fillOpacity: 0.85, weight: 1 })
        .bindPopup(`<b>${p.defect_type}</b> · ${p.severity}${pitLabel(p)}<br><img src="${absUrl(p.image_url)}" width="180" style="border-radius:8px" onerror="this.remove()"/>`)
        .addTo(markersLayer);
    });
  }
  renderSeverityMix(pts);
}

function renderSeverityMix(pts) {
  const mix = { high: 0, medium: 0, low: 0 };
  pts.forEach(p => { if (mix[p.severity] !== undefined) mix[p.severity]++; });
  const total = Math.max(1, pts.length);
  document.getElementById('severityMix').innerHTML = Object.entries(mix).map(([k, v]) => `
    <div><div class="flex justify-between text-xs mb-1"><span class="capitalize">${k}</span><span>${v}</span></div>
    <div class="h-2 rounded bg-slate-800"><div class="h-2 rounded" style="width:${(v / total * 100).toFixed(1)}%;background:${sevColor(k)}"></div></div></div>`).join('');
}

function reportRow(x) {
  const action = x.status !== 'repaired'
    ? `<button data-id="${x.id}" class="repairBtn px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-xs font-bold whitespace-nowrap">Repaired</button>`
    : '<span class="text-emerald-400 text-xs">✓ done</span>';
  return `
    <tr class="border-t border-slate-800 hover:bg-slate-800/40">
      <td class="p-2"><img class="thumb" src="${absUrl(x.image_url)}" loading="lazy" onerror="this.remove()"/></td>
      <td class="p-2 text-xs font-mono">${Number(x.lat).toFixed(5)}, ${Number(x.lng).toFixed(5)}</td>
      <td class="p-2">${x.defect_type}</td>
      <td class="p-2"><span class="badge" style="background:${sevColor(x.severity)}22;color:${sevColor(x.severity)}">${x.severity}</span></td>
      <td class="p-2 capitalize">${x.pit_category || '—'}${x.diameter_cm ? ` <span class="text-slate-400">~${x.diameter_cm}cm</span>` : ''}</td>
      <td class="p-2">${statusBadge(x.status)}</td>
      <td class="p-2"><span class="badge" style="${prioStyle(x.repair_priority)}">${x.repair_priority || ''}</span></td>
      <td class="p-2">${(x.confidence_score ?? 0).toFixed(2)}</td>
      <td class="p-2 text-xs text-slate-400">${(x.created_at || '').slice(0, 16).replace('T', ' ')}</td>
      <td class="p-2">${action}</td>
    </tr>`;
}

async function loadTable() {
  const status = document.getElementById('statusFilter').value;
  const r = await fetch(`${API}/admin/reports?limit=50${status ? '&status=' + status : ''}`);
  const d = await r.json();
  document.getElementById('rows').innerHTML = (d.reports || []).map(reportRow).join('');
  document.querySelectorAll('.repairBtn').forEach(b => b.onclick = async () => {
    b.disabled = true; b.textContent = '…';
    await fetch(`${API}/admin/reports/${b.dataset.id}`, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'repaired' })
    });
    refresh();
  });
}

async function refresh() {
  try { await Promise.all([loadStats(), loadMap(), loadTable()]); }
  catch (e) {
    console.warn('refresh failed', e);
    document.getElementById('updatedAt').textContent = 'backend unreachable — is it running?';
  }
}

document.getElementById('refreshBtn').onclick = refresh;
document.getElementById('statusFilter').onchange = loadTable;
document.getElementById('heatToggle').onchange = loadMap;
document.getElementById('markerToggle').onchange = loadMap;

refresh();
setInterval(refresh, 20000);
