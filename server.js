const express = require('express');
const cors = require('cors');
const path = require('path');
const fs = require('fs');
const sqlite3 = require('sqlite3');

const app = express();
const PORT = process.env.PORT || 3000;

const DB_PATH = path.join(__dirname, 'data', 'database', 'terrascope.db');
const DOCS_DIR = [
    path.join(__dirname, 'data', 'raw_documents'),
    path.join(__dirname, 'data', 'raw_docs')
].find(dir => fs.existsSync(dir));
const BOUNDARY_PATHS = [
    path.join(__dirname, 'data', 'iran_ramsar_exact_boundaries.geojson'),
    path.join(__dirname, 'frontend', 'public', 'data', 'iran_ramsar_exact_boundaries.geojson'),
    path.join(__dirname, 'iran_ramsar_exact_boundaries.geojson')
];

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'frontend/public')));
if (DOCS_DIR) {
    app.use('/files', express.static(DOCS_DIR));
}

const db = new sqlite3.Database(DB_PATH, sqlite3.OPEN_READONLY, (err) => {
    if (err) {
        console.error(`Could not open database at ${DB_PATH}: ${err.message}`);
    } else {
        console.log(`Connected to SQLite database: ${DB_PATH}`);
    }
});

function queryAll(sql, params = []) {
    return new Promise((resolve, reject) => {
        db.all(sql, params, (err, rows) => (err ? reject(err) : resolve(rows)));
    });
}

const WETLANDS_SQL = `
    SELECT
        w.*,
        w.montreux_record AS montreux_listed,
        a.risk_score,
        a.status_code,
        a.status_en,
        a.status_fa,
        a.summary_fa,
        a.summary_en,
        a.ai_analysis_fa AS analysis_fa,
        a.ai_analysis_en AS analysis_en,
        a.recommendation_fa,
        a.recommendation_en,
        a.last_updated
    FROM wetlands w
    LEFT JOIN ai_assessments a ON a.ramsar_id = w.ramsar_id
`;

const OBSERVATIONS_SQL = `
    SELECT
        ramsar_id,
        COALESCE(observation_date, date) AS observation_date,
        water_ratio_pct,
        veg_ratio_pct,
        dry_ratio_pct,
        ndvi_mean,
        ndwi_mean,
        risk_score,
        cloud_cover_pct
    FROM satellite_observations
`;

const DOCUMENTS_SQL = `
    SELECT d.*, w.name_fa, w.name_en
    FROM document_catalog d
    LEFT JOIN wetlands w ON w.ramsar_id = d.related_ramsar_id
`;

function attachObservations(wetlands, observations) {
    const historyBySite = new Map();
    observations.forEach(obs => {
        if (!historyBySite.has(obs.ramsar_id)) historyBySite.set(obs.ramsar_id, []);
        historyBySite.get(obs.ramsar_id).push(obs);
    });

    return wetlands.map(wetland => {
        const history = historyBySite.get(wetland.ramsar_id) || [];
        const latest = history[history.length - 1] || {};
        return {
            ...wetland,
            risk_score: wetland.risk_score ?? latest.risk_score ?? null,
            observation_date: latest.observation_date ?? null,
            water_ratio_pct: latest.water_ratio_pct ?? null,
            veg_ratio_pct: latest.veg_ratio_pct ?? null,
            dry_ratio_pct: latest.dry_ratio_pct ?? null,
            ndvi_mean: latest.ndvi_mean ?? null,
            ndwi_mean: latest.ndwi_mean ?? null,
            cloud_cover_pct: latest.cloud_cover_pct ?? null,
            history
        };
    });
}

function formatDocument(doc) {
    return {
        id: doc.id,
        filename: doc.filename,
        title: doc.filename.replace(/\.[^.]+$/, ''),
        category: doc.doc_category,
        ramsar_id: doc.related_ramsar_id,
        name_fa: doc.name_fa,
        name_en: doc.name_en,
        pages: doc.page_count,
        file_ext: doc.file_ext,
        file_size_bytes: doc.file_size_bytes,
        url: '/files/' + encodeURIComponent(doc.filename)
    };
}

// API for Ramsar exact boundaries
app.get('/api/wetlands/boundaries', (req, res) => {
    const geojsonPath = BOUNDARY_PATHS.find(candidate => fs.existsSync(candidate));
    if (geojsonPath) {
        res.type('application/geo+json');
        res.sendFile(geojsonPath);
    } else {
        res.json({ type: "FeatureCollection", features: [] });
    }
});

// Wetlands catalog with AI assessment, latest satellite metrics and observation history
app.get('/api/wetlands', async (req, res) => {
    try {
        const [wetlands, observations] = await Promise.all([
            queryAll(`${WETLANDS_SQL} ORDER BY w.ramsar_id ASC`),
            queryAll(`${OBSERVATIONS_SQL} ORDER BY ramsar_id ASC, observation_date ASC`)
        ]);
        const data = attachObservations(wetlands, observations);
        res.json({ status: 'success', count: data.length, data });
    } catch (err) {
        res.status(500).json({ status: 'error', message: err.message, data: [] });
    }
});

app.get('/api/wetlands/:id', async (req, res) => {
    const ramsarId = parseInt(String(req.params.id).replace(/^IR/i, ''), 10);
    if (Number.isNaN(ramsarId)) {
        return res.status(400).json({ status: 'error', message: 'Invalid Ramsar site id' });
    }
    try {
        const [wetlands, observations, documents] = await Promise.all([
            queryAll(`${WETLANDS_SQL} WHERE w.ramsar_id = ?`, [ramsarId]),
            queryAll(`${OBSERVATIONS_SQL} WHERE ramsar_id = ? ORDER BY observation_date ASC`, [ramsarId]),
            queryAll(`${DOCUMENTS_SQL} WHERE d.related_ramsar_id = ? ORDER BY d.filename ASC`, [ramsarId])
        ]);
        if (wetlands.length === 0) {
            return res.status(404).json({ status: 'error', message: 'Wetland not found' });
        }
        const [data] = attachObservations(wetlands, observations);
        res.json({ status: 'success', data: { ...data, documents: documents.map(formatDocument) } });
    } catch (err) {
        res.status(500).json({ status: 'error', message: err.message });
    }
});

// Ramsar document archive (RIS sheets, COP national reports, management plans)
app.get('/api/documents', async (req, res) => {
    try {
        const documents = await queryAll(
            `${DOCUMENTS_SQL} ORDER BY d.doc_category ASC, d.related_ramsar_id ASC, d.filename ASC`
        );
        const data = documents.map(formatDocument);
        res.json({ status: 'success', count: data.length, data });
    } catch (err) {
        res.status(500).json({ status: 'error', message: err.message, data: [] });
    }
});

// AI Analysis API
app.get('/api/ai-analysis', (req, res) => {
    const wetlandName = req.query.name || 'Unknown';
    // در فاز اول، یک خروجی Mock (آزمایشی) برمی‌گردانیم تا سرور به دلیل نبود پایتون کرش نکند
    res.json({ analysis: `وضعیت اکولوژیک:

1. تلفیق داده‌های ماهواره‌ای: شاخص NDVI و NDWI نشانگر تغییرات تنش آبی در 30 روز گذشته است.
2. فون و فلور (RIS): مطابق پرونده رامسر، پوشش گیاهی و زیستگاه پرندگان مهاجر تحت تاثیر قرار گرفته است.
3. تطبیق اسناد: ریسک تغییر ماهیت (ماده 3.2) ارزیابی شد.` });
});

app.listen(PORT, () => {
    console.log(`TerraScope Server is running on http://localhost:${PORT}`);
});
