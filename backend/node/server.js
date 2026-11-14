/**
 * TerraScope Phase 2, 3, 4 & 5: High-Speed Backend Server, RAM Cache, Processing Queue & PDF Reporting
 * Uses Node.js v22 native node:sqlite (DatabaseSync) for zero-overhead queries.
 */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');
const { DatabaseSync } = require('node:sqlite');

const PORT = process.env.PORT ? parseInt(process.env.PORT, 10) : 5000;
const ROOT_DIR = path.resolve(__dirname, '..', '..');
const DB_PATH = path.join(ROOT_DIR, 'data', 'database', 'terrascope.db');
const PUBLIC_DIR = path.join(ROOT_DIR, 'frontend', 'public');
const DOCS_DIR = path.join(ROOT_DIR, 'data', 'raw_documents');
const PYTHON_EXE = path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe');

const db = new DatabaseSync(DB_PATH);

const ramCache = {
  overview: null,
  documents: null,
  lastUpdated: 0,
  TTL_MS: 30000
};

function invalidateCache() {
  ramCache.overview = null;
  ramCache.documents = null;
  ramCache.lastUpdated = 0;
}

class ProcessingQueue {
  constructor() {
    this.queue = [];
    this.activeJob = null;
    this.history = [];
  }

  enqueue(jobType, params) {
    const existing = this.queue.find(j => j.jobType === jobType && JSON.stringify(j.params) === JSON.stringify(params));
    if (existing) return existing;
    if (this.activeJob && this.activeJob.jobType === jobType && JSON.stringify(this.activeJob.params) === JSON.stringify(params)) {
      return this.activeJob;
    }
    const job = {
      id: 'job_' + Date.now() + '_' + Math.random().toString(36).slice(2, 6),
      jobType,
      params,
      status: 'queued',
      createdAt: new Date().toISOString()
    };
    this.queue.push(job);
    this.processNext();
    return job;
  }

  processNext() {
    if (this.activeJob || this.queue.length === 0) return;
    this.activeJob = this.queue.shift();
    this.activeJob.status = 'running';
    this.activeJob.startedAt = new Date().toISOString();

    const job = this.activeJob;
    let args = [];
    if (job.jobType === 'eo_fetch') {
      const eoScript = path.join(ROOT_DIR, 'backend', 'python', 'data_engine', 'eo_engine.py');
      args = [eoScript, '--ramsar-id', String(job.params.ramsar_id), '--years', ...(job.params.years || [2020, 2022, 2024]).map(String)];
    } else if (job.jobType === 'ai_refresh') {
      const aiScript = path.join(ROOT_DIR, 'backend', 'python', 'ai_engine', 'eco_ai_engine.py');
      args = [aiScript];
    }

    const proc = spawn(PYTHON_EXE, args, { cwd: ROOT_DIR });
    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', d => { stdout += d.toString(); });
    proc.stderr.on('data', d => { stderr += d.toString(); });

    proc.on('close', code => {
      job.status = code === 0 ? 'completed' : 'failed';
      job.finishedAt = new Date().toISOString();
      job.exitCode = code;
      job.output = stdout.slice(-1500);
      if (stderr) job.error = stderr.slice(-1000);

      if (job.jobType === 'eo_fetch' && code === 0) {
        const aiScript = path.join(ROOT_DIR, 'backend', 'python', 'ai_engine', 'eco_ai_engine.py');
        const aiProc = spawn(PYTHON_EXE, [aiScript], { cwd: ROOT_DIR });
        aiProc.on('close', () => {
          invalidateCache();
          this.finishActiveJob();
        });
      } else {
        invalidateCache();
        this.finishActiveJob();
      }
    });
  }

  finishActiveJob() {
    if (this.activeJob) {
      this.history.unshift(this.activeJob);
      if (this.history.length > 25) this.history.pop();
      this.activeJob = null;
    }
    this.processNext();
  }

  getStatus() {
    return {
      activeJob: this.activeJob,
      queuedCount: this.queue.length,
      queue: this.queue,
      recentHistory: this.history.slice(0, 10)
    };
  }
}

const jobQueue = new ProcessingQueue();

function sendJson(res, statusCode, payload) {
  const body = JSON.stringify(payload);
  res.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Cache-Control': 'no-store'
  });
  res.end(body);
}

function parseBody(req) {
  return new Promise((resolve) => {
    let raw = '';
    req.on('data', chunk => { raw += chunk; });
    req.on('end', () => {
      try { resolve(raw ? JSON.parse(raw) : {}); }
      catch (e) { resolve({}); }
    });
  });
}

function getOverviewData() {
  const now = Date.now();
  if (ramCache.overview && (now - ramCache.lastUpdated < ramCache.TTL_MS)) {
    return ramCache.overview;
  }

  const wetlands = db.prepare(`
    SELECT
      w.*,
      a.status_code,
      a.risk_score,
      a.trend_direction,
      a.summary_fa,
      a.summary_en,
      a.recommendation_fa,
      a.recommendation_en,
      a.key_drivers_json,
      (SELECT COUNT(*) FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id) AS eo_count,
      (SELECT s.water_Ratio_pct FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_water_pct,
      (SELECT s.vegetation_ratio_pct FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_veg_pct,
      (SELECT s.dry_or_barren_ratio_pct FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_dry_pct,
      (SELECT s.mean_ndwi FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_ndwi,
      (SELECT s.mean_ndvi FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_ndvi,
      (SELECT s.acquisition_date FROM satellite_observations s WHERE s.ramsar_id = w.ramsar_id ORDER BY s.target_year DESC LIMIT 1) AS latest_eo_date
    FROM wetlands w
    LEFT JOIN ai_assessments a ON w.ramsar_id = a.ramsar_id
    ORDER BY a.risk_score DESC, w.area_ha DESC
  `).all();

  const stats = db.prepare(`
    SELECT
      (SELECT COUNT(*) FROM wetlands) AS total_wetlands,
      (SELECT SUM(area_ha) FROM wetlands) AS total_area_ha,
      (SELECT COUNT(*) FROM wetlands WHERE montreux_currently_listed = 'Yes') AS montreux_listed_count,
      (SELECT COUNT(*) FROM document_catalog) AS total_documents,
      (SELECT COUNT(*) FROM satellite_observations) AS total_eo_records,
      (SELECT ROUND(AVG(risk_score), 1) FROM ai_assessments) AS avg_national_risk
  `).get();

  const result = { stats, wetlands };
  ramCache.overview = result;
  ramCache.lastUpdated = now;
  return result;
}

const MIME_TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'application/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.pdf': 'application/pdf',
  '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon'
};

const server = http.createServer(async (req, res) => {
  if (req.method === 'OPTIONS') {
    res.writeHead(204, {
      'Access-Control-Allow-Origin': '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type'
    });
    return res.end();
  }

  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  const pathname = decodeURIComponent(parsedUrl.pathname);

  try {
    if (pathname === '/api/health' && req.method === 'GET') {
      return sendJson(res, 200, {
        status: 'ok',
        service: 'TerraScope Ramsar Observatory Backend',
        nodeVersion: process.version,
        queue: jobQueue.getStatus()
      });
    }

    if (pathname === '/api/wetlands' && req.method === 'GET') {
      return sendJson(res, 200, getOverviewData());
    }

    const wetMatch = pathname.match(/^\/api\/wetlands\/(\d+)$/);
    if (wetMatch && req.method === 'GET') {
      const ramsarId = parseInt(wetMatch[1], 10);
      const wetland = db.prepare(`SELECT * FROM wetlands WHERE ramsar_id = ?`).get(ramsarId);
      if (!wetland) return sendJson(res, 404, { error: 'Wetland not found' });

      const ai = db.prepare(`SELECT * FROM ai_assessments WHERE ramsar_id = ?`).get(ramsarId);
      const observations = db.prepare(`
        SELECT * FROM satellite_observations
        WHERE ramsar_id = ?
        ORDER BY target_year ASC
      `).all(ramsarId);
      const docs = db.prepare(`
        SELECT * FROM document_catalog
        WHERE related_ramsar_id = ? OR doc_category IN ('Summary', 'COP_National_Report')
        ORDER BY related_ramsar_id DESC, doc_category ASC
      `).all(ramsarId);

      return sendJson(res, 200, { wetland, ai, observations, documents: docs });
    }

    if (pathname === '/api/documents' && req.method === 'GET') {
      if (!ramCache.documents) {
        ramCache.documents = db.prepare(`
          SELECT d.*, w.name_fa, w.name_en
          FROM document_catalog d
          LEFT JOIN wetlands w ON d.related_ramsar_id = w.ramsar_id
          ORDER BY d.doc_category ASC, d.related_ramsar_id ASC, d.filename ASC
        `).all();
      }
      return sendJson(res, 200, { count: ramCache.documents.length, documents: ramCache.documents });
    }

    if (pathname.startsWith('/raw_documents/') && req.method === 'GET') {
      const filename = path.basename(pathname.replace('/raw_documents/', ''));
      const filePath = path.join(DOCS_DIR, filename);
      if (!fs.existsSync(filePath)) return sendJson(res, 404, { error: 'Document file not found' });
      const ext = path.extname(filePath).toLowerCase();
      res.writeHead(200, {
        'Content-Type': MIME_TYPES[ext] || 'application/octet-stream',
        'Content-Disposition': `inline; filename="${filename}"`
      });
      return fs.createReadStream(filePath).pipe(res);
    }

    const repMatch = pathname.match(/^\/api\/report\/(\d+)$/);
    if (repMatch && req.method === 'GET') {
      const ramsarId = parseInt(repMatch[1], 10);
      const pdfPath = path.join(ROOT_DIR, 'reports', 'factsheets', `TerraScope_Ramsar_${ramsarId}_Factsheet.pdf`);
      const reportScript = path.join(ROOT_DIR, 'backend', 'python', 'reporting', 'factsheet_generator.py');
      const proc = spawn(PYTHON_EXE, [reportScript, String(ramsarId)], { cwd: ROOT_DIR });
      proc.on('close', () => {
        if (fs.existsSync(pdfPath)) {
          res.writeHead(200, {
            'Content-Type': 'application/pdf',
            'Content-Disposition': `inline; filename="TerraScope_Ramsar_${ramsarId}_Factsheet.pdf"`
          });
          fs.createReadStream(pdfPath).pipe(res);
        } else {
          sendJson(res, 500, { ok: false, error: 'Failed to generate PDF factsheet' });
        }
      });
      return;
    }

    if (pathname === '/api/eo/trigger' && req.method === 'POST') {
      const body = await parseBody(req);
      const ramsarId = parseInt(body.ramsar_id, 10);
      if (!ramsarId) return sendJson(res, 400, { error: 'Valid ramsar_id required' });
      const years = Array.isArray(body.years) ? body.years : [2020, 2022, 2024];
      const job = jobQueue.enqueue('eo_fetch', { ramsar_id: ramsarId, years });
      return sendJson(res, 202, { message: 'EO processing job queued', job, queueStatus: jobQueue.getStatus() });
    }

    if (pathname === '/api/queue' && req.method === 'GET') {
      return sendJson(res, 200, jobQueue.getStatus());
    }

    // Static Dashboard Serving (Windows-safe path resolution)
    const cleanRel = (pathname === '/' ? 'index.html' : pathname).replace(/^[/\\]+/, '');
    const safePath = path.join(PUBLIC_DIR, path.normalize(cleanRel));
    if (safePath.startsWith(PUBLIC_DIR) && fs.existsSync(safePath) && fs.statSync(safePath).isFile()) {
      const ext = path.extname(safePath).toLowerCase();
      res.writeHead(200, { 'Content-Type': MIME_TYPES[ext] || 'text/plain; charset=utf-8' });
      return fs.createReadStream(safePath).pipe(res);
    }

    return sendJson(res, 404, { error: 'Endpoint or resource not found', path: pathname });
  } catch (err) {
    console.error('[SERVER ERROR]', err);
    return sendJson(res, 500, { error: err.message });
  }
});

server.listen(PORT, () => {
  console.log('==============================================================');
  console.log(` TerraScope Backend & Dashboard Server listening on port ${PORT}`);
  console.log(` URL: http://localhost:${PORT}`);
  console.log('==============================================================');
});