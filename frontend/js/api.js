/**
 * QMS Enterprise — Unified API Client v3.1
 * Central HTTP + WebSocket client for all pages.
 */

const API_BASE = window.QMS_API_BASE || 'http://localhost:5000/api';
const WS_BASE  = window.QMS_WS_BASE  || 'http://localhost:5000';

// ─────────────────────────────────────────────────────────────────
// CORE HTTP
// ─────────────────────────────────────────────────────────────────
async function apiRequest(endpoint, method = 'GET', body = null, skipAuth = false) {
  const token = localStorage.getItem('access_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token && !skipAuth) headers['Authorization'] = `Bearer ${token}`;

  const opts = { method, headers };
  if (body) opts.body = JSON.stringify(body);

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, opts);

    if (response.status === 401 && !skipAuth) {
      const refreshed = await _tryRefreshToken();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${localStorage.getItem('access_token')}`;
        const retry = await fetch(`${API_BASE}${endpoint}`, { ...opts, headers });
        const retryData = await retry.json().catch(() => ({}));
        return { data: retryData, status: retry.status, ok: retry.ok };
      } else {
        clearAuthData();
        window.location.href = 'login.html';
        return { data: null, status: 401, ok: false };
      }
    }

    const data = await response.json().catch(() => ({}));
    return { data, status: response.status, ok: response.ok };

  } catch (err) {
    console.error(`API Error [${method} ${endpoint}]:`, err);
    return { data: { error: err.message }, status: 0, ok: false };
  }
}

async function _tryRefreshToken() {
  const rt = localStorage.getItem('refresh_token');
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: rt }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem('access_token', data.access_token);
    if (data.refresh_token) localStorage.setItem('refresh_token', data.refresh_token);
    return true;
  } catch { return false; }
}

function clearAuthData() {
  ['access_token', 'refresh_token', 'current_user'].forEach(k => localStorage.removeItem(k));
}

// ─────────────────────────────────────────────────────────────────
// WEBSOCKET
// ─────────────────────────────────────────────────────────────────
let _socket = null;
const _wsHandlers = {};

function initWebSocket(factoryId) {
  if (typeof io === 'undefined' || (_socket && _socket.connected)) return;
  _socket = io(WS_BASE, { transports: ['websocket', 'polling'] });
  _socket.on('connect', () => {
    if (factoryId) _socket.emit('subscribe_kpi', { factory_id: factoryId });
  });
  ['kpi_update', 'model_trained', 'high_risk_prediction', 'anomaly_alert'].forEach(evt => {
    _socket.on(evt, (d) => (_wsHandlers[evt] || []).forEach(fn => fn(d)));
  });
}

function onWsEvent(event, handler) {
  if (!_wsHandlers[event]) _wsHandlers[event] = [];
  _wsHandlers[event].push(handler);
}

// ─────────────────────────────────────────────────────────────────
// UNIFIED API
// ─────────────────────────────────────────────────────────────────
const API = {
  get:        (ep)       => apiRequest(ep, 'GET'),
  post:       (ep, body) => apiRequest(ep, 'POST', body),
  put:        (ep, body) => apiRequest(ep, 'PUT',  body),
  delete:     (ep)       => apiRequest(ep, 'DELETE'),
  postPublic: (ep, body) => apiRequest(ep, 'POST', body, true),

  // Auth
  login:          (d) => API.postPublic('/auth/login', d),
  register:       (d) => API.postPublic('/auth/register', d),
  adminRegister:  (d) => API.postPublic('/auth/admin-register', d),
  forgotPassword: (d) => API.postPublic('/auth/forgot-password', d),
  resetPassword:  (d) => API.postPublic('/auth/reset-password', d),

  // Users
  getMe:          ()     => API.get('/users/me'),
  updateMe:       (d)    => API.put('/users/me', d),
  getUsers:       ()     => API.get('/users/'),
  toggleUser:     (id)   => API.put(`/users/${id}/toggle-active`),
  changePassword: (d)    => API.put('/users/me/password', d),

  // Roles
  getRoles:       ()        => API.get('/roles/'),
  createRole:     (d)       => API.post('/roles/', d),
  updateRole:     (id, d)   => API.put(`/roles/${id}`, d),
  deleteRole:     (id)      => API.delete(`/roles/${id}`),
  getPermissions: ()        => API.get('/roles/permissions'),

  // Factories
  getFactories: () => API.get('/factories/'),
  getMyFactory: () => API.get('/factories/mine'),

  // Quality
  getDefects:     (p='')     => API.get(`/quality/defects${p}`),
  createDefect:   (d)        => API.post('/quality/defects', d),
  updateDefect:   (id, d)    => API.put(`/quality/defects/${id}`, d),
  deleteDefect:   (id)       => API.delete(`/quality/defects/${id}`),
  getKPIs:        (days=30)  => API.get(`/quality/kpis?days=${days}`),
  getDefectCodes: ()         => API.get('/quality/defect-codes'),
  getMachines:    ()         => API.get('/quality/machines'),

  // AI
  trainModel:           ()         => API.post('/ai/train', {}),
  predictDefect:        (d)        => API.post('/ai/predict', d),
  getAnomalies:         (days=30)  => API.get(`/ai/anomalies?days=${days}`),
  recommend:            (d)        => API.post('/ai/recommend', d),
  getForecast:          (days=7)   => API.get(`/ai/forecast?days=${days}`),
  getModelInfo:         ()         => API.get('/ai/model-info'),
  getModelVersions:     ()         => API.get('/ai/versions'),
  rcaPredict:           (d)        => API.post('/ai/rca/predict', d),
  rcaClusters:          (days=30)  => API.get(`/ai/rca/clusters?days=${days}`),
  rcaFeatureImportance: ()         => API.get('/ai/rca/feature-importance'),

  // Q40 KPIs
  getQ40KPIs: (days=30) => API.get(`/q40/kpis?days=${days}`),

  // IoT
  getDevices:        (mid)   => API.get(`/q40/iot/devices${mid ? '?machine_id=' + mid : ''}`),
  createDevice:      (d)     => API.post('/q40/iot/devices', d),
  ingestSensor:      (d)     => API.post('/q40/iot/ingest', d),
  getSensorSummary:  (h=1)   => API.get(`/q40/iot/summary?hours=${h}`),
  getSensorTimeseries:(devId, metric, h) =>
    API.get(`/q40/iot/timeseries?device_id=${devId}&metric=${metric}&hours=${h}`),

  // SPC
  getCpk:          (mid, m, usl, lsl, days) =>
    API.get(`/q40/spc/cpk?machine_id=${mid}&metric=${m}&usl=${usl}&lsl=${lsl}&days=${days}`),
  getControlChart: (mid, m, ss, days) =>
    API.get(`/q40/spc/control-chart?machine_id=${mid}&metric=${m}&sample_size=${ss}&days=${days}`),
  detectShift:     (mid, m, days) =>
    API.get(`/q40/spc/shift-detect?machine_id=${mid}&metric=${m}&days=${days}`),
  getStability:    (days=30) => API.get(`/q40/spc/stability?days=${days}`),

  // Maintenance
  getMTBF:              (mid)  => API.get(`/q40/maintenance/mtbf?machine_id=${mid}`),
  predictFailure:       (mid)  => API.get(`/q40/maintenance/predict?machine_id=${mid}`),
  getSchedule:          ()     => API.get('/q40/maintenance/schedule'),
  getRiskScores:        ()     => API.get('/q40/maintenance/risk-scores'),
  generateRiskScores:   ()     => API.post('/q40/maintenance/risk-scores/generate', {}),
  getMaintenanceEvents: (mid)  =>
    API.get(`/q40/maintenance/events${mid ? '?machine_id=' + mid : ''}`),
  createMaintenanceEvent: (d)  => API.post('/q40/maintenance/events', d),

  // Chatbot
  chatQuery:      (q)      => API.post('/q40/chatbot/query', { question: q }),
  getChatHistory: (lim=20) => API.get(`/q40/chatbot/history?limit=${lim}`),

  // Traceability
  getBatches:    (s)   => API.get(`/q40/batches${s ? '?status=' + s : ''}`),
  createBatch:   (d)   => API.post('/q40/batches', d),
  getBatchTrace: (id)  => API.get(`/q40/batches/${id}/trace`),

  // Digital Twin
  getDigitalAssets:   ()  => API.get('/q40/digital-twin/assets'),
  createDigitalAsset: (d) => API.post('/q40/digital-twin/assets', d),

  // Operator Performance
  getOperatorPerformance: (days=30) => API.get(`/q40/operators/performance?days=${days}`),

  // Reports
  getReports:     ()  => API.get('/reports/'),
  generateReport: (d) => API.post('/reports/generate', d),

  // Library
  getLibraryDocs:   ()    => API.get('/library/'),
  getLibraryDoc:    (id)  => API.get(`/library/${id}`),
  createLibraryDoc: (d)   => API.post('/library/', d),

  // Forms
  getForms:   ()      => API.get('/forms/'),
  getForm:    (id)    => API.get(`/forms/${id}`),
  createForm: (d)     => API.post('/forms/', d),
  submitForm: (id, d) => API.post(`/forms/${id}/submit`, d),
};

window.API           = API;
window.apiRequest    = apiRequest;
window.clearAuthData = clearAuthData;
window.initWebSocket = initWebSocket;
window.onWsEvent     = onWsEvent;
