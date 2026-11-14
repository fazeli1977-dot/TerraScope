import os, re

def read_safe(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        with open(path, "r", encoding="utf-16") as f:
            return f.read()

def write_safe(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)

# ---------------------------------------------------------
# 1. FIX index.html (Add Marked.js + MathJax & clean stray tag)
# ---------------------------------------------------------
index_path = os.path.join("frontend", "public", "index.html")
if os.path.exists(index_path):
    html = read_safe(index_path)
    
    if "</html>" in html:
        html = html.split("</html>")[0] + "</html>\n"

    ai_head_assets = """
    <!-- Markdown & LaTeX Scientific Rendering -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <script>
      window.MathJax = {
        tex: {
          inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
          displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']]
        },
        svg: { fontCache: 'global' }
      };
    </script>
    <script id="MathJax-script" async src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js"></script>
    <style>
      .ai-markdown-body { line-height: 1.75; font-size: 0.92rem; color: #e2e8f0; }
      .ai-markdown-body h1, .ai-markdown-body h2, .ai-markdown-body h3, .ai-markdown-body h4 {
        color: #38bdf8; margin-top: 12px; margin-bottom: 6px; font-weight: 700;
      }
      .ai-markdown-body p { margin-bottom: 8px; }
      .ai-markdown-body ul, .ai-markdown-body ol { padding-inline-start: 20px; margin-bottom: 10px; }
      .ai-markdown-body li { margin-bottom: 4px; }
      .ai-markdown-body strong { color: #f8fafc; font-weight: 700; }
      .ai-markdown-body table { width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 0.85rem; }
      .ai-markdown-body th, .ai-markdown-body td { border: 1px solid rgba(148,163,184,0.25); padding: 6px 8px; text-align: right; }
      .ai-markdown-body th { background: rgba(15,23,42,0.7); color: #38bdf8; }
      .ai-markdown-body code { background: rgba(15,23,42,0.8); padding: 2px 5px; border-radius: 4px; color: #fbbf24; font-family: monospace; }
    </style>
"""
    if "marked.min.js" not in html:
        html = html.replace("</head>", ai_head_assets + "\n</head>")

    write_safe(index_path, html)
    print("[SUCCESS] index.html updated with Marked.js, MathJax, and clean DOM.")

# ---------------------------------------------------------
# 2. FIX server.js (Fix Python child_process execution in /api/ai-analysis)
# ---------------------------------------------------------
server_path = os.path.join("backend", "server.js")
if os.path.exists(server_path):
    srv = read_safe(server_path)
    
    ai_route_pattern = r"app\.get\(['\"]/api/ai-analysis['\"][\s\S]*?(?=app\.listen)"
    clean_ai_route = """app.get('/api/ai-analysis', (req, res) => {
    const wetlandName = req.query.name || '';
    const lang = req.query.lang || 'fa';
    const { execFile } = require('child_process');
    const path = require('path');
    const pyExe = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
    const scriptPath = path.join(__dirname, '..', 'engine', 'ai_analyzer.py');
    const pythonCmd = require('fs').existsSync(pyExe) ? pyExe : 'python';

    execFile(pythonCmd, [scriptPath, wetlandName, lang], { encoding: 'utf8', maxBuffer: 1024 * 1024 * 5 }, (error, stdout, stderr) => {
        if (error) {
            return res.json({
                status: 'fallback',
                analysis: `### تحلیل هوشمند اکولوژیک (${wetlandName})\\n\\nبر اساس پایش طیف‌سنجی ماهواره‌ای Sentinel-2 و شاخص نرمال‌شده تفاوت آب ($NDWI = \\\\frac{G - NIR}{G + NIR}$)، وضعیت تالاب نیازمند پایش مستمر حقابه محیط‌زیستی و کنترل تنش تبخیری است.`
            });
        }
        try {
            const parsed = JSON.parse(stdout);
            res.json(parsed);
        } catch (e) {
            res.json({ status: 'success', analysis: stdout });
        }
    });
});

"""
    if re.search(ai_route_pattern, srv):
        srv = re.sub(ai_route_pattern, clean_ai_route, srv)
        write_safe(server_path, srv)
        print("[SUCCESS] server.js /api/ai-analysis route fixed.")

# ---------------------------------------------------------
# 3. FIX app.js (Fix fetch syntax error, exact GeoJSON rendering)
# ---------------------------------------------------------
app_path = os.path.join("frontend", "public", "app.js")
if os.path.exists(app_path):
    app_js = read_safe(app_path)

    app_js = re.sub(
        r"fetch\(\s*/api/ai-analysis\?name=\s*\+\s*encodeURIComponent\(wetlandName\)\s*\)",
        "fetch('/api/ai-analysis?name=' + encodeURIComponent(wetlandName))",
        app_js
    )

    helper_fn = """
function renderFormattedAI(targetEl, rawMarkdown) {
    if (!targetEl) return;
    targetEl.classList.add('ai-markdown-body');
    if (window.marked && typeof window.marked.parse === 'function') {
        targetEl.innerHTML = window.marked.parse(rawMarkdown || '');
    } else {
        targetEl.innerHTML = (rawMarkdown || '').replace(/\\n/g, '<br>');
    }
    if (window.MathJax && typeof window.MathJax.typesetPromise === 'function') {
        window.MathJax.typesetPromise([targetEl]).catch(err => console.warn('MathJax error:', err));
    }
}
"""
    if "function renderFormattedAI" not in app_js:
        app_js += "\n" + helper_fn

    marker_fn_pattern = r"function renderMapMarkers\s*\([^)]*\)\s*\{[\s\S]*?(?=\nfunction\s+\w+|\n// ===)"
    new_marker_fn = """function renderMapMarkers(wetlands) {
    markersLayer.clearLayers();
    const ColorMap = {
        0: { stroke: '#10b981', fill: '#10b981' },
        1: { stroke: '#f59e0b', fill: '#f59e0b' },
        2: { stroke: '#ef4444', fill: '#ef4444' }
    };

    const drawPolygons = (geoData) => {
        wetlands.forEach(w => {
            const c = ColorMap[w.status_code] || ColorMap[0];
            const isSelected = selectedWetland && selectedWetland.ramsar_id === w.ramsar_id;
            const name = currentLang === 'fa' ? w.name_fa : w.name_en;
            let layer = null;

            if (geoData && geoData.features) {
                const feat = geoData.features.find(f =>
                    Number(f.properties.ramsar_id) === Number(w.ramsar_id) ||
                    (f.properties.name_en && w.name_en && f.properties.name_en.toLowerCase() === w.name_en.toLowerCase())
                );
                if (feat) {
                    layer = L.geoJSON(feat, {
                        style: {
                            color: isSelected ? '#38bdf8' : c.stroke,
                            weight: isSelected ? 3 : 2,
                            fillColor: c.fill,
                            fillOpacity: isSelected ? 0.45 : 0.28
                        }
                    });
                }
            }

            if (!layer) {
                layer = L.circle([w.lat, w.lon], {
                    radius: Math.max(Math.sqrt((w.area_ha || 1500) * 10000 / Math.PI), 1500),
                    color: isSelected ? '#38bdf8' : c.stroke,
                    weight: isSelected ? 3 : 2,
                    fillColor: c.fill,
                    fillOpacity: isSelected ? 0.45 : 0.28
                });
            }

            const tooltipHtml = `<div style="font-family: inherit; text-align: ${currentLang === 'fa' ? 'right' : 'left'};">
                <strong>${name}</strong><br/>
                <span>Area: ${Number(w.area_ha || 0).toLocaleString()} ha</span>
            </div>`;

            layer.bindTooltip(tooltipHtml, { sticky: true, direction: 'top' });
            layer.on('click', () => {
                selectWetland(w);
                if (layer.getBounds) {
                    map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 12 });
                }
            });
            markersLayer.addLayer(layer);
        });
    };

    if (window.cachedBoundariesGeoJSON) {
        drawPolygons(window.cachedBoundariesGeoJSON);
    } else {
        fetch('/data/iran_ramsar_exact_boundaries.geojson')
            .then(r => r.ok ? r.json() : null)
            .then(data => {
                window.cachedBoundariesGeoJSON = data;
                drawPolygons(data);
            })
            .catch(err => {
                console.warn("Failed to load geojson boundaries:", err);
                drawPolygons(null);
            });
    }
}
"""
    if re.search(marker_fn_pattern, app_js):
        app_js = re.sub(marker_fn_pattern, new_marker_fn, app_js, count=1)

    app_js = re.sub(
        r"document\.getElementById\(['\"]aiAnalysisText['\"]\)\.(?:innerText|textContent|innerHTML)\s*=\s*([^;]+);",
        r"renderFormattedAI(document.getElementById('aiAnalysisText'), \1);",
        app_js
    )
    app_js = re.sub(
        r"aiBox\.(?:innerText|textContent|innerHTML)\s*=\s*([^;]+);",
        r"renderFormattedAI(aiBox, \1);",
        app_js
    )

    write_safe(app_path, app_js)
    print("[SUCCESS] app.js fixed successfully!")

