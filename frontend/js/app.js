/**
 * QMS Enterprise — Shared Navigation & App Shell
 * Inject sidebar + topbar, handle auth, page routing
 */

const NAV_LINKS = [
  { section: 'CORE', links: [
    { href: 'dashboard.html',  icon: 'fa-gauge',           label: 'Dashboard' },
    { href: 'analytics.html',  icon: 'fa-chart-area',      label: 'Analytics' },
    { href: 'defects.html',    icon: 'fa-bug',             label: 'Defect Records' },
    { href: 'forms.html',      icon: 'fa-wpforms',         label: 'Form Builder' },
  ]},
  { section: 'QUALITY 4.0', links: [
    { href: 'iot.html',         icon: 'fa-microchip',      label: 'IoT & Sensors' },
    { href: 'spc.html',         icon: 'fa-chart-gantt',    label: 'SPC Control' },
    { href: 'maintenance.html', icon: 'fa-wrench',         label: 'Predictive Maint.' },
    { href: 'traceability.html',icon: 'fa-sitemap',        label: 'Traceability' },
    { href: 'digital-twin.html',icon: 'fa-cube',           label: 'Digital Twin' },
  ]},
  { section: 'INTELLIGENCE', links: [
    { href: 'ai.html',          icon: 'fa-brain',          label: 'AI Predictions' },
    { href: 'chatbot.html',     icon: 'fa-comments',       label: 'Quality Chatbot' },
    { href: 'reports.html',     icon: 'fa-file-chart-column', label: 'Reports' },
    { href: 'library.html',     icon: 'fa-book',           label: 'Quality Library' },
  ]},
  { section: 'ADMIN', links: [
    { href: 'roles.html',      icon: 'fa-user-shield',    label: 'Roles' },
    { href: 'profile.html',    icon: 'fa-user-circle',    label: 'Profile' },
  ]},
];

function buildSidebar(user) {
  const currentPage = window.location.pathname.split('/').pop() || 'dashboard.html';

  const sectionsHtml = NAV_LINKS.map(section => `
    <div class="nav-section">
      <div class="nav-section-title">${section.section}</div>
      ${section.links.map(link => {
        const active = link.href === currentPage ? ' active' : '';
        return `<a class="nav-item${active}" href="${link.href}">
          <i class="fas ${link.icon} nav-icon"></i>${link.label}
        </a>`;
      }).join('')}
    </div>
  `).join('');

  return `
    <div class="sidebar-header">
      <div class="brand-mark"><span class="brand-q">Q</span></div>
      <div>
        <div class="sidebar-title">QMS Enterprise</div>
        <div class="sidebar-subtitle" id="factoryNameSidebar">${user?.factory_name || '—'}</div>
      </div>
    </div>
    <nav class="sidebar-nav">${sectionsHtml}</nav>
    <div class="sidebar-footer">
      <div class="user-chip">
        <div class="user-avatar">${(user?.name || 'U')[0].toUpperCase()}</div>
        <div>
          <div class="user-name">${user?.name || '—'}</div>
          <div class="user-role">${user?.role_name || ''}</div>
        </div>
      </div>
      <button class="nav-item logout-btn" onclick="appLogout()">
        <i class="fas fa-sign-out-alt nav-icon"></i>Sign Out
      </button>
    </div>
  `;
}

function initAppShell(pageTitle = '') {
  const user = getStoredUser();
  if (!user) {
    window.location.href = 'login.html';
    return null;
  }

  const sidebar = document.getElementById('appSidebar');
  const topbarTitle = document.getElementById('topbarTitle');
  const topbarFactory = document.getElementById('topbarFactory');

  if (sidebar) sidebar.innerHTML = buildSidebar(user);
  if (topbarTitle && pageTitle) topbarTitle.textContent = pageTitle;
  if (topbarFactory) topbarFactory.textContent = user.factory_name || '';

  return user;
}

function getStoredUser() {
  try {
    const token = localStorage.getItem('access_token');
    if (!token) return null;
    const payload = JSON.parse(atob(token.split('.')[1]));
    return {
      id: payload.sub || payload.user_id,
      name: payload.name || localStorage.getItem('user_name') || 'User',
      email: payload.email,
      role_name: payload.role_name || localStorage.getItem('user_role') || '',
      factory_id: payload.factory_id || localStorage.getItem('factory_id'),
      factory_name: payload.factory_name || localStorage.getItem('factory_name') || 'Factory',
    };
  } catch {
    return null;
  }
}

function appLogout() {
  localStorage.clear();
  window.location.href = 'login.html';
}

// ── Unified API helper ───────────────────────────────────────────
async function qmsApi(path, method = 'GET', body = null) {
  const token = localStorage.getItem('access_token');
  const opts = {
    method,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
  };
  if (body) opts.body = JSON.stringify(body);
  const res = await fetch(path, opts);
  if (res.status === 401) { appLogout(); return null; }
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ── Formatting helpers ───────────────────────────────────────────
function fmt(v, decimals = 0) {
  if (v == null || v === '') return '—';
  return Number(v).toLocaleString(undefined, { maximumFractionDigits: decimals });
}
function fmtPct(v, decimals = 2) {
  if (v == null || v === '') return '—';
  return Number(v).toFixed(decimals) + '%';
}
function fmtDate(v) {
  if (!v) return '—';
  return new Date(v).toLocaleDateString();
}
function riskColor(level) {
  return { critical: '#ef4444', high: '#f97316', medium: '#f59e0b', low: '#22d3ee' }[level] || '#94a3b8';
}
function riskEmoji(level) {
  return { critical: '🔴', high: '🟠', medium: '🟡', low: '🟢' }[level] || '⚪';
}

// ── Toast notifications ──────────────────────────────────────────
function showToast(msg, type = 'info') {
  const colors = { info: '#22d3ee', success: '#34d399', error: '#ef4444', warn: '#f59e0b' };
  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed;bottom:1.5rem;right:1.5rem;z-index:9999;
    background:#0d1929;border:1px solid ${colors[type]};
    color:#e2e8f0;padding:.75rem 1.25rem;border-radius:8px;
    font-family:'IBM Plex Sans',sans-serif;font-size:.85rem;
    box-shadow:0 4px 20px rgba(0,0,0,.5);
    animation:slideIn .3s ease;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3500);
}

// ── Auto-refresh support ─────────────────────────────────────────
function startAutoRefresh(fn, intervalMs = 30000) {
  fn();
  return setInterval(fn, intervalMs);
}

// CSS animation for toast
const style = document.createElement('style');
style.textContent = `@keyframes slideIn{from{transform:translateX(100%);opacity:0}to{transform:translateX(0);opacity:1}}`;
document.head.appendChild(style);

// ─────────────────────────────────────────────────────────────────
// REAL-TIME KPI UPDATES (WebSocket polling fallback)
// ─────────────────────────────────────────────────────────────────

/**
 * Initialize real-time dashboard updates.
 * Uses WebSocket if Socket.IO loaded, else falls back to 30s polling.
 */
function initRealTimeKPI(updateFn, intervalMs = 30000) {
  const user = getStoredUser();
  const factoryId = user?.factory_id;

  // Try WebSocket first
  if (typeof io !== 'undefined' && factoryId) {
    initWebSocket(factoryId);
    onWsEvent('kpi_update', (data) => {
      updateFn(data);
      const el = document.getElementById('lastRefresh');
      if (el) el.textContent = 'Live · ' + new Date().toLocaleTimeString();
    });
    console.log('[App] Real-time via WebSocket');
  } else {
    // Fallback: polling
    updateFn();
    setInterval(() => {
      updateFn();
      const el = document.getElementById('lastRefresh');
      if (el) el.textContent = 'Updated · ' + new Date().toLocaleTimeString();
    }, intervalMs);
    console.log(`[App] Real-time via polling every ${intervalMs / 1000}s`);
  }
}

window.initRealTimeKPI = initRealTimeKPI;
