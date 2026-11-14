let allWetlands = [];
let allDocs = [];
let selectedWetland = null;
let currentLang = 'fa';
let map = null;
let markersLayer = null;
let bboxLayer = null;
let boundariesLayer = null;
let surfaceChartInstance = null;
let spectralChartInstance = null;

const BOUNDARY_STYLE = { color: '#2ecc71', weight: 2, opacity: 0.9, fillColor: '#2ecc71', fillOpacity: 0.2 };
const BOUNDARY_SELECTED_STYLE = { color: '#a7f3d0', weight: 3, opacity: 1, fillColor: '#2ecc71', fillOpacity: 0.35 };

document.addEventListener('DOMContentLoaded', async () => {
  initMap();
  bindEvents();
  await Promise.all([loadInitialData(), loadBoundaries()]);
  highlightBoundary();
});

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`${url} responded with HTTP ${response.status}`);
  return response.json();
}

function getFeatureRamsarId(feature) {
  const props = (feature && feature.properties) || {};
  const id = Number(props.ramsar_id ?? props.ramsarid);
  return Number.isFinite(id) ? id : null;
}

function getBoundaryLabel(feature) {
  const props = (feature && feature.properties) || {};
  const ramsarId = getFeatureRamsarId(feature);
  const wetland = allWetlands.find(w => Number(w.ramsar_id) === ramsarId) || {};
  const nameFa = wetland.name_fa || props.name_fa;
  const nameEn = wetland.name_en || props.name_en || props.officialname || props.officialna;
  const title = (currentLang === 'fa' ? (nameFa || nameEn) : (nameEn || nameFa)) || 'Ramsar Site';
  const area = Number(wetland.area_ha ?? props.area_ha ?? props.area_off);
  const areaText = Number.isFinite(area) && area > 0 ? ` | ${area.toLocaleString('en-US')} ha` : '';
  return `<b>${title}</b><br/>${ramsarId ? 'Ramsar #' + ramsarId : 'Ramsar'}${areaText}`;
}

async function loadBoundaries() {
  if (!map) return;
  try {
    const geojson = await fetchJson('/api/wetlands/boundaries');
    const features = Array.isArray(geojson && geojson.features) ? geojson.features.filter(f => f && f.geometry) : [];
    if (boundariesLayer) map.removeLayer(boundariesLayer);

    boundariesLayer = L.geoJSON({ type: 'FeatureCollection', features }, {
      style: () => BOUNDARY_STYLE,
      onEachFeature: (feature, layer) => {
        layer.bindTooltip(() => getBoundaryLabel(feature), { sticky: true });
        layer.on('click', () => {
          const ramsarId = getFeatureRamsarId(feature);
          if (ramsarId) selectWetland(ramsarId);
        });
      }
    }).addTo(map);

    boundariesLayer.bringToBack();
  } catch (err) {
    console.error('Error loading wetland boundaries:', err);
  }
}

function highlightBoundary() {
  if (!boundariesLayer) return;
  const selectedId = selectedWetland ? Number(selectedWetland.ramsar_id) : null;
  boundariesLayer.eachLayer(layer => {
    const isSelected = selectedId !== null && getFeatureRamsarId(layer.feature) === selectedId;
    layer.setStyle(isSelected ? BOUNDARY_SELECTED_STYLE : BOUNDARY_STYLE);
  });
}

function initMap() {
  const mapEl = document.getElementById('mapContainer');
  if (!mapEl) return;

  map = L.map('mapContainer', { zoomControl: true }).setView([32.4279, 53.6880], 5);

  const darkBase = L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap & CartoDB | TerraScope',
    maxZoom: 18
  });

  const esriSat = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
    attribution: 'Tiles &copy; Esri &mdash; Sentinel-2 / World Imagery',
    maxZoom: 18
  });

  esriSat.addTo(map);
  L.control.layers({ "تصویر ماهواره‌ای (Satellite)": esriSat, "نقشه تاریک (Dark GIS)": darkBase }).addTo(map);

  markersLayer = L.layerGroup().addTo(map);
  bboxLayer = L.layerGroup().addTo(map);
}

async function loadInitialData() {
  try {
    const [wRes, dRes] = await Promise.all([
      fetchJson('/api/wetlands'),
      fetchJson('/api/documents').catch(err => {
        console.error('Error loading documents:', err);
        return { data: [] };
      })
    ]);

    const wetlandRows = Array.isArray(wRes) ? wRes : (wRes && (wRes.data || wRes.wetlands));
    const docRows = Array.isArray(dRes) ? dRes : (dRes && (dRes.data || dRes.documents));
    allWetlands = Array.isArray(wetlandRows) ? wetlandRows : [];
    allDocs = Array.isArray(docRows) ? docRows : [];

    updateKPIs();
    renderWetlandList();
    renderMapMarkers();
    renderCompareModal();
    renderArchiveModal();

    if (allWetlands.length > 0) {
      const defaultSite = allWetlands.find(w => Number(w.ramsar_id) === 38) || allWetlands[0];
      selectWetland(defaultSite.ramsar_id);
    }
  } catch (err) {
    console.error('Error loading TerraScope data:', err);
  }
}

function getStatusCode(w) {
  const risk = Number(w.risk_score || 0);
  if (risk >= 70 || Number(w.montreux_listed) === 1) return 'CRITICAL';
  if (risk >= 50) return 'STRESSED';
  if (risk >= 35) return 'MODERATE';
  return 'STABLE';
}

function getRiskColor(risk) {
  const r = Number(risk || 0);
  if (r >= 70) return '#f43f5e';
  if (r >= 50) return '#f59e0b';
  if (r >= 35) return '#3b82f6';
  return '#10b981';
}

function getStatusLabel(w) {
  if (currentLang === 'fa') {
    return w.status_fa || (getStatusCode(w) === 'CRITICAL' ? 'بحرانی (ماده ۳.۲)' : getStatusCode(w) === 'STRESSED' ? 'تنش بالا' : 'پایدار نسبی');
  }
  return w.status_en || getStatusCode(w);
}

function updateKPIs() {
  const totalArea = allWetlands.reduce((sum, w) => sum + Number(w.area_ha || 0), 0);
  const criticalCount = allWetlands.filter(w => getStatusCode(w) === 'CRITICAL').length;

  const elSites = document.getElementById('kpiValSites');
  const elArea = document.getElementById('kpiSubArea');
  const elCrit = document.getElementById('kpiValCritical');
  const elLive = document.getElementById('kpiValLiveEO');
  const elDocs = document.getElementById('kpiValDocs');

  if (elSites) elSites.textContent = allWetlands.length;
  if (elArea) {
    elArea.textContent = currentLang === 'fa'
      ? `مساحت کل: ${totalArea.toLocaleString('fa-IR')} هکتار`
      : `Total Area: ${totalArea.toLocaleString('en-US')} ha`;
  }
  if (elCrit) elCrit.textContent = criticalCount;
  if (elLive) elLive.textContent = `${allWetlands.length} / 28`;
  if (elDocs && allDocs.length > 0) elDocs.textContent = allDocs.length;
}

function renderWetlandList() {
  const container = document.getElementById('wetlandListContainer');
  const badge = document.getElementById('wetlandCountBadge');
  if (!container) return;

  const q = (document.getElementById('searchInput')?.value || '').trim().toLowerCase();
  const statusFilter = document.getElementById('statusFilter')?.value || 'ALL';

  const filtered = allWetlands.filter(w => {
    const matchText = !q ||
      (w.name_fa && w.name_fa.toLowerCase().includes(q)) ||
      (w.name_en && w.name_en.toLowerCase().includes(q)) ||
      (w.province_fa && w.province_fa.toLowerCase().includes(q)) ||
      (w.province_en && w.province_en.toLowerCase().includes(q)) ||
      String(w.ramsar_id).includes(q);

    const code = getStatusCode(w);
    const matchStatus =
      statusFilter === 'ALL' ||
      statusFilter === 'LIVE_EO' ||
      statusFilter === code;

    return matchText && matchStatus;
  });

  if (badge) badge.textContent = filtered.length;
  container.innerHTML = '';

  filtered.forEach(w => {
    const code = getStatusCode(w);
    const color = getRiskColor(w.risk_score);
    const isSelected = selectedWetland && Number(selectedWetland.ramsar_id) === Number(w.ramsar_id);

    const card = document.createElement('div');
    card.className = `wetland-item ${isSelected ? 'active' : ''}`;
    card.style.cssText = `
      padding: 0.75rem;
      margin-bottom: 0.5rem;
      border-radius: 8px;
      background: ${isSelected ? 'rgba(56, 189, 248, 0.14)' : 'rgba(30, 41, 59, 0.65)'};
      border: 1px solid ${isSelected ? '#38bdf8' : 'rgba(148, 163, 184, 0.18)'};
      border-right: 4px solid ${color};
      cursor: pointer;
      transition: all 0.15s ease;
    `;

    const title = currentLang === 'fa' ? w.name_fa : w.name_en;
    const prov = currentLang === 'fa' ? w.province_fa : w.province_en;

    card.innerHTML = `
      <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem;">
        <strong style="font-size:0.88rem; color:#f8fafc;">${title}</strong>
        <span class="badge badge-${code}" style="background:${color}22; color:${color}; border:1px solid ${color}; padding:2px 6px; border-radius:4px; font-size:0.72rem;">
          Risk: ${w.risk_score ?? '-'}
        </span>
      </div>
      <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:#94a3b8; margin-top:0.35rem;">
        <span>📍 ${prov} | #${w.ramsar_id}</span>
        <span>💧 ${w.water_ratio_pct ?? '-'}% | 🌿 ${w.veg_ratio_pct ?? '-'}%</span>
      </div>
    `;

    card.addEventListener('click', () => selectWetland(w.ramsar_id));
    container.appendChild(card);
  });
}

function renderMapMarkers() {
  if (!map || !markersLayer) return;
  markersLayer.clearLayers();

  allWetlands.forEach(w => {
    const lat = Number(w.latitude);
    const lon = Number(w.longitude);
    if (isNaN(lat) || isNaN(lon)) return;

    const color = getRiskColor(w.risk_score);
    const marker = L.circleMarker([lat, lon], {
      radius: 8,
      fillColor: color,
      color: '#ffffff',
      weight: 2,
      opacity: 1,
      fillOpacity: 0.9
    });

    const title = currentLang === 'fa' ? w.name_fa : w.name_en;
    marker.bindTooltip(`<b>${title || '-'}</b><br/>Ramsar #${w.ramsar_id} | Risk: ${w.risk_score ?? '-'}`, {
      direction: 'top'
    });

    marker.on('click', () => selectWetland(w.ramsar_id));
    markersLayer.addLayer(marker);
  });
}

function selectWetland(ramsarId) {
  const w = allWetlands.find(item => Number(item.ramsar_id) === Number(ramsarId));
  if (!w) return;
  selectedWetland = w;

  renderWetlandList();
  highlightBoundary();

  // Map flyTo and BBox
  if (map && w.latitude && w.longitude) {
    map.flyTo([Number(w.latitude), Number(w.longitude)], 9, { duration: 1.1 });
    bboxLayer.clearLayers();

    if (w.bbox_json) {
      try {
        const bbox = typeof w.bbox_json === 'string' ? JSON.parse(w.bbox_json) : w.bbox_json;
        if (Array.isArray(bbox) && bbox.length === 4) {
          const [minLon, minLat, maxLon, maxLat] = bbox;
          const bounds = [[minLat, minLon], [maxLat, maxLon]];
          L.rectangle(bounds, {
            color: '#a855f7',
            weight: 2,
            dashArray: '6, 4',
            fillColor: '#a855f7',
            fillOpacity: 0.12
          }).bindTooltip(`Sentinel-2 STAC Monitoring Frame (#${w.ramsar_id})`).addTo(bboxLayer);
        }
      } catch (e) {}
    }
  }

  // Update Coordinates Label
  const coordsLbl = document.getElementById('selectedCoordsLabel');
  if (coordsLbl) {
    coordsLbl.textContent = `WGS84: ${Number(w.latitude).toFixed(4)}°N, ${Number(w.longitude).toFixed(4)}°E | Scene: ${w.scene_id || 'S2B_MSIL2A'}`;
  }

  // Update Factsheet Link
  const btnPdf = document.getElementById('btnDownloadFactsheet');
  if (btnPdf) {
    btnPdf.href = `/files/IR${w.ramsar_id}RIS.pdf`;
  }

  // Update AI Panel
  const color = getRiskColor(w.risk_score);
  const statusBadge = document.getElementById('aiStatusBadge');
  if (statusBadge) {
    statusBadge.textContent = getStatusLabel(w);
    statusBadge.style.background = `${color}25`;
    statusBadge.style.color = color;
    statusBadge.style.border = `1px solid ${color}`;
  }

  document.getElementById('selectedWetlandTitle').textContent = currentLang === 'fa' ? w.name_fa : w.name_en;
  document.getElementById('selectedWetlandSub').textContent = currentLang === 'fa'
    ? `استان ${w.province_fa} | کد رامسر: #${w.ramsar_id} | آخرین رصد: ${w.observation_date || '2026-11'}`
    : `${w.province_en} Province | Ramsar #${w.ramsar_id} | Observed: ${w.observation_date || '2026-11'}`;

  const riskCircle = document.getElementById('aiRiskCircle');
  if (riskCircle) {
    riskCircle.textContent = w.risk_score ?? '--';
    riskCircle.style.borderColor = color;
    riskCircle.style.color = color;
  }

  document.getElementById('valMetricWater').textContent = `${w.water_ratio_pct ?? '-'}%`;
  document.getElementById('valMetricVeg').textContent = `${w.veg_ratio_pct ?? '-'}%`;
  document.getElementById('valMetricNdwi').textContent = `${w.ndwi_mean ?? '-'} / ${w.ndvi_mean ?? '-'}`;

  document.getElementById('aiSummaryText').textContent =
    currentLang === 'fa' ? (w.analysis_fa || '-') : (w.analysis_en || '-');

  document.getElementById('aiRecText').textContent =
    currentLang === 'fa' ? (w.recommendation_fa || '-') : (w.recommendation_en || '-');

  // Update RIS Metadata Table
  document.getElementById('mValId').textContent = `#${w.ramsar_id} (IR${w.ramsar_id}RIS)`;
  document.getElementById('mValProv').textContent = currentLang === 'fa' ? w.province_fa : w.province_en;
  document.getElementById('mValArea').textContent = Number(w.area_ha || 0).toLocaleString(currentLang === 'fa' ? 'fa-IR' : 'en-US') + (currentLang === 'fa' ? ' هکتار' : ' ha');
  document.getElementById('mValDate').textContent = w.designation_date || '1975-06-23';
  document.getElementById('mValElev').textContent = w.elevation_min != null && w.elevation_max != null
    ? `${w.elevation_min} - ${w.elevation_max} m`
    : (w.elevation_m || '-');
  document.getElementById('mValMontreux').innerHTML = Number(w.montreux_listed) === 1
    ? `<span style="color:#f43f5e; font-weight:bold;">${currentLang === 'fa' ? 'ثبت‌شده در فهرست مونترو (ماده ۳.۲)' : 'Listed in Montreux Record (Art. 3.2)'}</span>`
    : `<span style="color:#10b981;">${currentLang === 'fa' ? 'عادی (خارج از مونترو)' : 'Normal Status'}</span>`;
  document.getElementById('mValMgmt').textContent = currentLang === 'fa'
    ? (w.management_plan || 'دارای برنامه مدیریت زیست‌بومی و پایش ماهواره‌ای')
    : 'Active CEPA & Ecosystem Management Plan';
  document.getElementById('mValThreats').textContent =
    (currentLang === 'fa' ? w.threats_fa : w.threats_en) || (Number(w.risk_score) >= 65
      ? (currentLang === 'fa' ? 'کاهش حقابه، خشکسالی، برداشت بی‌رویه آب و کانون گردوغبار' : 'Water diversion, severe drought, dust emission hazard')
      : (currentLang === 'fa' ? 'نوسانات فصلی دما، زهاب کشاورزی و فشار کاربری اراضی' : 'Seasonal water fluctuation, agricultural runoff'));

  renderSiteDocs(w);
  renderCharts(w);
}

function renderSiteDocs(w) {
  const container = document.getElementById('siteDocsContainer');
  if (!container) return;

  const siteDocs = allDocs.filter(d =>
    Number(d.ramsar_id) === Number(w.ramsar_id) ||
    (d.filename && d.filename.toUpperCase().includes(`IR${w.ramsar_id}RIS`))
  );

  // Add default RIS link if not returned by /api/documents scan
  if (siteDocs.length === 0) {
    siteDocs.push({
      filename: `IR${w.ramsar_id}RIS.pdf`,
      category: 'Ramsar Information Sheet (RIS)',
      url: `/files/IR${w.ramsar_id}RIS.pdf`
    });
  }

  container.innerHTML = siteDocs.map(doc => {
    const fileUrl = doc.url || `/files/${doc.filename}`;
    return `
      <div style="display:flex; justify-content:space-between; align-items:center; padding:0.45rem 0.6rem; margin-bottom:0.35rem; background:rgba(30,41,59,0.6); border-radius:6px; font-size:0.78rem;">
        <span>📄 ${doc.filename}</span>
        <a href="${fileUrl}" target="_blank" class="btn" style="padding:2px 8px; font-size:0.72rem; text-decoration:none;">
          ${currentLang === 'fa' ? 'مشاهده PDF' : 'Open PDF'}
        </a>
      </div>
    `;
  }).join('');
}

function renderCharts(w) {
  const history = Array.isArray(w.history) && w.history.length > 0 ? w.history : [w];
  const labels = history.map(h => (h.observation_date || '').slice(0, 7));
  const waterData = history.map(h => Number(h.water_ratio_pct || 0));
  const vegData = history.map(h => Number(h.veg_ratio_pct || 0));
  const dryData = history.map(h => Number(h.dry_ratio_pct || 0));
  const ndwiData = history.map(h => Number(h.ndwi_mean || 0));
  const ndviData = history.map(h => Number(h.ndvi_mean || 0));
  const riskData = history.map(h => Number(h.risk_score || 0));

  const ctx1 = document.getElementById('surfaceChart')?.getContext('2d');
  if (ctx1) {
    if (surfaceChartInstance) surfaceChartInstance.destroy();
    surfaceChartInstance = new Chart(ctx1, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: currentLang === 'fa' ? 'پهنه آبی (%)' : 'Open Water (%)', data: waterData, borderColor: '#38bdf8', backgroundColor: 'rgba(56,189,248,0.18)', fill: true, tension: 0.35 },
          { label: currentLang === 'fa' ? 'پوشش گیاهی (%)' : 'Vegetation (%)', data: vegData, borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.15)', fill: true, tension: 0.35 },
          { label: currentLang === 'fa' ? 'بستر خشک (%)' : 'Dry Bed (%)', data: dryData, borderColor: '#f43f5e', backgroundColor: 'rgba(244,63,94,0.1)', fill: false, borderDash: [4, 4], tension: 0.35 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#cbd5e1', font: { family: 'Vazirmatn, Inter' } } } },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
          y: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' }, min: 0, max: 100 }
        }
      }
    });
  }

  const ctx2 = document.getElementById('spectralChart')?.getContext('2d');
  if (ctx2) {
    if (spectralChartInstance) spectralChartInstance.destroy();
    spectralChartInstance = new Chart(ctx2, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'NDWI (شاخص آب)', data: ndwiData, borderColor: '#38bdf8', yAxisID: 'y', tension: 0.35 },
          { label: 'NDVI (شاخص گیاهی)', data: ndviData, borderColor: '#34d399', yAxisID: 'y', tension: 0.35 },
          { label: 'Risk Score (0-100)', data: riskData, borderColor: '#f59e0b', yAxisID: 'y1', borderDash: [3, 3], tension: 0.35 }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#cbd5e1', font: { family: 'Vazirmatn, Inter' } } } },
        scales: {
          x: { ticks: { color: '#94a3b8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
          y: { type: 'linear', position: 'left', min: -0.5, max: 0.8, ticks: { color: '#38bdf8' }, grid: { color: 'rgba(148,163,184,0.1)' } },
          y1: { type: 'linear', position: 'right', min: 0, max: 100, ticks: { color: '#f59e0b' }, grid: { drawOnChartArea: false } }
        }
      }
    });
  }
}

function renderCompareModal() {
  const tbody = document.getElementById('compareTableBody');
  if (!tbody) return;
  tbody.innerHTML = allWetlands.map(w => {
    const color = getRiskColor(w.risk_score);
    return `
      <tr style="cursor:pointer;" onclick="document.getElementById('compareModal').classList.remove('active'); document.getElementById('compareModal').style.display='none'; selectWetland(${w.ramsar_id});">
        <td><b>#${w.ramsar_id}</b></td>
        <td>${(currentLang === 'fa' ? w.name_fa : w.name_en) || '-'}</td>
        <td>${(currentLang === 'fa' ? w.province_fa : w.province_en) || '-'}</td>
        <td>${Number(w.area_ha || 0).toLocaleString()}</td>
        <td><b style="color:${color};">${w.risk_score ?? '-'}</b></td>
        <td><span style="color:${color};">${getStatusLabel(w)}</span></td>
        <td>${w.water_ratio_pct ?? '-'}%</td>
        <td>${w.veg_ratio_pct ?? '-'}%</td>
      </tr>
    `;
  }).join('');
}

function renderArchiveModal(filterText = '') {
  const tbody = document.getElementById('archiveTableBody');
  if (!tbody) return;
  const q = filterText.trim().toLowerCase();

  const filteredDocs = allDocs.filter(d =>
    !q ||
    (d.filename && d.filename.toLowerCase().includes(q)) ||
    (d.category && d.category.toLowerCase().includes(q)) ||
    String(d.ramsar_id || '').includes(q)
  );

  tbody.innerHTML = filteredDocs.map((d, idx) => {
    const url = d.url || `/files/${d.filename}`;
    return `
      <tr>
        <td>${idx + 1}</td>
        <td style="direction:ltr; text-align:left;">${d.filename}</td>
        <td>${d.category || 'Official Document'}</td>
        <td>${d.ramsar_id ? '#' + d.ramsar_id : 'National / COP'}</td>
        <td>${d.pages || '-'}</td>
        <td><a href="${url}" target="_blank" class="btn" style="padding:2px 8px; font-size:0.75rem; text-decoration:none;">📥 مشاهده / دانلود</a></td>
      </tr>
    `;
  }).join('');
}

function bindEvents() {
  document.getElementById('searchInput')?.addEventListener('input', renderWetlandList);
  document.getElementById('statusFilter')?.addEventListener('change', renderWetlandList);

  const archiveModal = document.getElementById('archiveModal');
  const compareModal = document.getElementById('compareModal');

  document.getElementById('btnOpenArchive')?.addEventListener('click', () => {
    if (archiveModal) { archiveModal.classList.add('active'); archiveModal.style.display = 'flex'; }
  });
  document.getElementById('btnCloseArchive')?.addEventListener('click', () => {
    if (archiveModal) { archiveModal.classList.remove('active'); archiveModal.style.display = 'none'; }
  });

  document.getElementById('btnOpenCompare')?.addEventListener('click', () => {
    if (compareModal) { compareModal.classList.add('active'); compareModal.style.display = 'flex'; }
  });
  document.getElementById('btnCloseCompare')?.addEventListener('click', () => {
    if (compareModal) { compareModal.classList.remove('active'); compareModal.style.display = 'none'; }
  });

  document.getElementById('docSearchInput')?.addEventListener('input', (e) => {
    renderArchiveModal(e.target.value);
  });

  document.getElementById('btnTriggerEO')?.addEventListener('click', async () => {
    const btn = document.getElementById('lblRefreshBtn');
    if (btn) btn.textContent = currentLang === 'fa' ? 'در حال دریافت استریم ماهواره‌ای...' : 'Syncing Sentinel-2 STAC...';
    await loadInitialData();
    if (btn) btn.textContent = currentLang === 'fa' ? 'به‌روزرسانی زنده ماهواره‌ای تالاب' : 'Live Satellite EO Sync';
  });

  document.getElementById('btnLangToggle')?.addEventListener('click', () => {
    currentLang = currentLang === 'fa' ? 'en' : 'fa';
    document.body.dir = currentLang === 'fa' ? 'rtl' : 'ltr';
    document.documentElement.lang = currentLang;

    document.getElementById('uiAppTitle').textContent = currentLang === 'fa'
      ? 'TerraScope | دیده‌بان تالاب‌های ایران در کنوانسیون رامسر'
      : 'TerraScope | Iran’s Ramsar Wetlands Observatory';

    updateKPIs();
    renderWetlandList();
    renderMapMarkers();
    renderCompareModal();
    if (selectedWetland) selectWetland(selectedWetland.ramsar_id);
  });
}
