// نقشه پایه
const map = L.map('map').setView([32.4279, 53.6836], 5);
L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 18,
    attribution: ' TerraScope | Ramsar Wetlands'
}).addTo(map);

// فراخوانی مرز تالاب‌ها
fetch('/api/wetlands/boundaries')
    .then(response => response.json())
    .then(data => {
        if(data && data.features && data.features.length > 0) {
            L.geoJSON(data, {
                style: { color: '#0078A8', weight: 2, fillOpacity: 0.4 },
                onEachFeature: function (feature, layer) {
                    layer.on('click', function() {
                        const wetlandName = feature.properties.name || feature.properties.Site_Name || 'Unknown';
                        document.getElementById('ai-content').innerText = 'در حال پردازش هوش مصنوعی...';
                        
                        // درخواست تحلیل به بک‌اند
                        fetch(`/api/ai-analysis?name=${encodeURIComponent(wetlandName)}`)
                            .then(res => res.json())
                            .then(aiData => {
                                document.getElementById('ai-content').innerText = aiData.analysis;
                            })
                            .catch(err => {
                                document.getElementById('ai-content').innerText = 'خطا در دریافت تحلیل.';
                            });
                    });
                    
                    if (feature.properties.Site_Name) {
                        layer.bindPopup(`<b>${feature.properties.Site_Name}</b><br>کلیک کنید تا تحلیل هوش مصنوعی بارگذاری شود.`);
                    }
                }
            }).addTo(map);
        } else {
            console.warn('داده GeoJSON خالی است یا یافت نشد.');
        }
    })
    .catch(err => console.error('Error loading geojson:', err));