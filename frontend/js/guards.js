/**
 * guards.js — Page Access Guards
 * QMS Enterprise v3.1
 */

/**
 * Protect a page — redirect to login if no valid token.
 * @param {string[]} [requiredPermissions]
 */
async function requireAuth(requiredPermissions = []) {
  const token = localStorage.getItem('access_token');
  if (!token) {
    redirectToLogin();
    return null;
  }

  try {
    const { data, ok } = await API.getMe();
    if (!ok) {
      redirectToLogin();
      return null;
    }

    localStorage.setItem('current_user', JSON.stringify(data));

    if (requiredPermissions.length > 0) {
      const userPerms = data.role?.permissions || [];
      const missing = requiredPermissions.filter(p => !userPerms.includes(p));
      if (missing.length > 0) {
        if (typeof showToast === 'function') showToast('Access denied: insufficient permissions', 'error');
        window.location.href = 'dashboard.html';
        return null;
      }
    }

    return data;
  } catch {
    redirectToLogin();
    return null;
  }
}

/**
 * Redirect to login, preserving the intended destination.
 */
function redirectToLogin() {
  if (typeof clearAuthData === 'function') clearAuthData();
  else {
    ['access_token','refresh_token','current_user'].forEach(k => localStorage.removeItem(k));
  }
  const current = window.location.pathname.split('/').pop() + window.location.search;
  window.location.href = 'login.html' + (current ? '?redirect=' + encodeURIComponent(current) : '');
}

/**
 * If user is already authenticated, redirect to destination.
 */
function redirectIfAuthenticated(destination) {
  destination = destination || 'dashboard.html';
  // Strip leading slash for Railway / file:// compatibility
  destination = destination.replace(/^\//, '');

  const token = localStorage.getItem('access_token');
  if (!token) return;

  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (payload.exp * 1000 > Date.now()) {
      window.location.href = destination;
    }
  } catch {
    localStorage.removeItem('access_token');
  }
}

/**
 * Check if user has a specific permission (client-side, cached).
 */
function hasPermission(permissionName) {
  const user = typeof getCurrentUser === 'function' ? getCurrentUser() : null;
  if (!user) return false;
  return (user.role?.permissions || []).includes(permissionName);
}

/**
 * Show/hide elements based on permissions.
 */
function applyPermissionVisibility() {
  document.querySelectorAll('[data-require-perm]').forEach(el => {
    const perm = el.dataset.requirePerm;
    if (!hasPermission(perm)) el.style.display = 'none';
  });
}

window.requireAuth               = requireAuth;
window.redirectIfAuthenticated   = redirectIfAuthenticated;
window.redirectToLogin           = redirectToLogin;
window.hasPermission             = hasPermission;
window.applyPermissionVisibility = applyPermissionVisibility;
