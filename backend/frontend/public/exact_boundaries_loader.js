// TerraScope - Exact Ramsar Polygon Boundary Renderer
window.loadExactRamsarBoundaries = async function(mapInstance) {
    const targetMap = mapInstance || window.map || window.leafletMap;
    if (!targetMap) {
        console.warn("[TerraScope] Map instance not found on window. Pass map object to loadExactRamsarBoundaries(map).");
        return;
    }

    try {
        const response = await fetch('/api/wetlands/boundaries');
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const geojsonData = await response.json();

        if (window.ramsarBoundaryLayer) {
            targetMap.removeLayer(window.ramsarBoundaryLayer);
        }

        window.ramsarBoundaryLayer = L.geoJSON(geojsonData, {
            style: function(feature) {
                const isExact = feature.properties.boundary_source && !feature.properties.boundary_source.includes('Buffer');
                return {
                    color: isExact ? '#00e5ff' : '#ff9800',
                    weight: 2.2,
                    opacity: 0.9,
                    fillColor: isExact ? '#00b4d8' : '#ffb703',
                    fillOpacity: 0.25,
                    dashArray: isExact ? null : '5, 5'
                };
            },
            onEachFeature: function(feature, layer) {
                const p = feature.properties || {};
                layer.on({
                    mouseover: function(e) {
                        const l = e.target;
                        l.setStyle({ weight: 3.5, fillOpacity: 0.45, color: '#ffffff' });
                        l.bringToFront();
                    },
                    mouseout: function(e) {
                        window.ramsarBoundaryLayer.resetStyle(e.target);
                    },
                    click: function(e) {
                        targetMap.fitBounds(e.target.getBounds(), { padding: [30, 30] });
                        if (typeof window.selectWetland === 'function' && p.ramsar_id) {
                            window.selectWetland(p.ramsar_id);
                        }
                    }
                });

                const popupHtml = `
                    <div style="font-family: Tahoma, sans-serif; direction: rtl; text-align: right; min-width: 210px;">
                        <h4 style="margin: 0 0 6px 0; color: #0077b6; border-bottom: 1px solid #ccc; padding-bottom: 4px;">
                            ${p.name_fa || p.name_en || 'تالاب رامسر'}
                        </h4>
                        <div style="font-size: 12px; line-height: 1.7;">
                            <b>نام انگلیسی:</b> ${p.name_en || '-'}<br>
                            <b>کد رامسر (Site ID):</b> #${p.ramsar_id || '-'}<br>
                            <b>استان:</b> ${p.province_fa || p.province || '-'}<br>
                            <b>مساحت رسمی:</b> ${p.area_ha ? Number(p.area_ha).toLocaleString() + ' هکتار' : '-'}<br>
                            <b>منبع مرز:</b> <span style="color: #006400; font-weight: bold;">${p.boundary_source || 'RSIS Exact Polygon'}</span>
                        </div>
                    </div>
                `;
                layer.bindPopup(popupHtml);
            }
        }).addTo(targetMap);

        console.log(`[TerraScope] Loaded ${geojsonData.features.length} exact wetland boundaries.`);
        return window.ramsarBoundaryLayer;
    } catch (err) {
        console.error("[TerraScope] Error loading exact boundaries:", err);
    }
};
