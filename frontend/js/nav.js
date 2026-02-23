/**
 * QMS Enterprise — Shared Navigation Injector
 * Include this script in every page to get consistent sidebar + topbar.
 * Usage: <script src="js/nav.js"></script>  (before closing </body>)
 */

(function() {
  'use strict';

  const PAGES = [
    { href: 'dashboard.html',       icon: 'fa-gauge-high',         label: 'Dashboard',      section: 'overview' },
    { href: 'analytics.html',       icon: 'fa-chart-mixed',        label: 'Analytics',      section: 'overview' },
    { href: 'defects.html',         icon: 'fa-bug',                label: 'Defect Records', section: 'overview' },
    { href: 'forms.html',           icon: 'fa-wpforms',            label: 'Form Builder',   section: 'overview' },
    { href: 'ai.html',              icon: 'fa-brain',              label: 'AI Intelligence',section: 'intelligence' },
    { href: 'reports.html',         icon: 'fa-file-chart-column',  label: 'Reports',        section: 'intelligence' },
    { href: 'spc.html',             icon: 'fa-wave-square',        label: 'SPC Charts',     section: 'intelligence' },
    { href: 'chatbot.html',         icon: 'fa-robot',              label: 'AI Chatbot',     section: 'intelligence' },
    { href: 'maintenance.html',     icon: 'fa-wrench',             label: 'Maintenance',    section: 'industrial' },
    { href: 'iot.html',             icon: 'fa-microchip',          label: 'IoT Monitor',    section: 'industrial' },
    { href: 'digital-twin.html',    icon: 'fa-cubes',              label: 'Digital Twin',   section: 'industrial' },
    { href: 'traceability.html',    icon: 'fa-route',              label: 'Traceability',   section: 'industrial' },
    { href: 'library.html',         icon: 'fa-book',               label: 'Quality Library',section: 'config' },
    { href: 'roles.html',           icon: 'fa-user-shield',        label: 'Roles',          section: 'config' },
    { href: 'profile.html',         icon: 'fa-user-circle',        label: 'Profile',        section: 'config' },
  ];

  const SECTIONS = {
    overview:     'Overview',
    intelligence: 'Intelligence',
    industrial:   'Industrial 4.0',
    config:       'Configuration',
  };

  const currentPage = window.location.pathname.split('/').pop() || 'index.html';

  // ── Build sidebar HTML ─────────────────────────────────────────
  function buildSidebar() {
    const groups = {};
    PAGES.forEach(p => {
      if (!groups[p.section]) groups[p.section] = [];
      groups[p.section].push(p);
    });

    let navHTML = '';
    Object.entries(groups).forEach(([sec, pages]) => {
      navHTML += `<div class="nav-section-label">${SECTIONS[sec]}</div>`;
      pages.forEach(p => {
        const active = p.href === currentPage ? ' active' : '';
        navHTML += `<a class="nav-link${active}" href="${p.href}">
          <i class="fas ${p.icon} nav-icon"></i> ${p.label}
        </a>`;
      });
    });

    return `
      <aside class="sidebar" id="qmsSidebar">
        <div class="sidebar-brand">
          <a href="index.html" style="display:flex;align-items:center;gap:.75rem;text-decoration:none;">
            <div class="brand-icon"><i class="fas fa-shield-halved"></i></div>
            <div>
              <div class="brand-text">QMS Enterprise</div>
              <div class="brand-sub" id="sb-factory">—</div>
            </div>
          </a>
        </div>
        <nav class="sidebar-nav">${navHTML}</nav>
        <div class="sidebar-footer">
          <div class="user-chip">
            <div class="user-ava" id="sb-avatar">?</div>
            <div>
              <div class="user-info-name" id="sb-name">Loading...</div>
              <div class="user-info-role" id="sb-role">—</div>
            </div>
          </div>
          <button onclick="if(typeof logout==='function')logout();else{localStorage.clear();window.location.href='login.html';}"
            style="margin-top:.75rem;width:100%;background:rgba(239,68,68,.1);border:1px solid rgba(239,68,68,.2);color:#ef4444;border-radius:7px;padding:.45rem;font-size:.775rem;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:.4rem;">
            <i class="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      </aside>`;
  }

  // ── Inject sidebar if page has sidebar placeholder or .main ────
  function injectSidebar() {
    // Skip auth/landing pages
    const skipPages = ['login.html','admin-register.html','register.html','forgot-password.html','reset-password.html','index.html',''];
    if (skipPages.includes(currentPage)) return;

    // If sidebar already exists, skip
    if (document.querySelector('.sidebar')) {
      populateSidebarUser();
      return;
    }

    // Inject before .main or body
    const main = document.querySelector('.main') || document.querySelector('main');
    if (main) {
      const sidebarEl = document.createElement('div');
      sidebarEl.innerHTML = buildSidebar();
      document.body.insertBefore(sidebarEl.firstElementChild, main);
      populateSidebarUser();
    }
  }

  // ── Populate user info in sidebar ─────────────────────────────
  function populateSidebarUser() {
    const userStr = localStorage.getItem('current_user');
    if (!userStr) return;
    try {
      const user = JSON.parse(userStr);
      const nameEl = document.getElementById('sb-name');
      const roleEl = document.getElementById('sb-role');
      const avaEl  = document.getElementById('sb-avatar');
      const facEl  = document.getElementById('sb-factory');
      if (nameEl) nameEl.textContent = user.name || '—';
      if (roleEl) roleEl.textContent = user.role?.name || '—';
      if (facEl)  facEl.textContent  = user.factory?.name || '—';
      if (avaEl)  avaEl.textContent  = (user.name || '?').slice(0,2).toUpperCase();
    } catch(e) {}
  }

  // ── Mobile sidebar toggle ──────────────────────────────────────
  window.toggleSidebar = function() {
    const sb = document.getElementById('qmsSidebar');
    if (sb) sb.classList.toggle('open');
  };

  // ── Run on DOMContentLoaded ────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', injectSidebar);
  } else {
    injectSidebar();
  }

  // Re-populate after requireAuth resolves
  window.addEventListener('qms:user:loaded', populateSidebarUser);
})();
