/**
 * guards.js — Page Access Guards
 * QMS Authentication System
 */

/**
 * Protect a page — redirect to login if no valid token.
 * Call at the top of every protected page's script.
 * @param {string[]} [requiredPermissions] — optional permission checks
 */
async function requireAuth(requiredPermissions = []) {
  const token = localStorage.getItem('access_token');
  if (!token) {
    redirectToLogin();
    return null;
  }

  // Fetch fresh user data
  try {
    const { data, ok, status } = await API.getMe();
    if (!ok) {
      redirectToLogin();
      return null;
    }

    // Update stored user
    localStorage.setItem('current_user', JSON.stringify(data));

    // Check permissions
    if (requiredPermissions.length > 0) {
      const userPerms = data.role?.permissions || [];
      const missing = requiredPermissions.filter(p => !userPerms.includes(p));
      if (missing.length > 0) {
        showToast('Access denied: insufficient permissions', 'error');
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
  clearAuthData();
  const current = window.location.pathname + window.location.search;
  window.location.href = `login.html?redirect=${encodeURIComponent(current)}`;
}

/**
 * If user is already logged in, redirect away from auth pages.
 */
function redirectIfAuthenticated(destination = '/dashboard.html') {
  const token = localStorage.getItem('access_token');
  if (token) {
    window.location.href = destination.replace(/^\//, '');
  }
}

/**
 * Check if user has a specific permission (client-side, cached).
 */
function hasPermission(permissionName) {
  const user = getCurrentUser();
  if (!user) return false;
  return (user.role?.permissions || []).includes(permissionName);
}

/**
 * Show/hide elements based on permissions.
 */
function applyPermissionVisibility() {
  document.querySelectorAll('[data-require-perm]').forEach(el => {
    const perm = el.dataset.requirePerm;
    if (!hasPermission(perm)) {
      el.style.display = 'none';
    }
  });
}

window.requireAuth = requireAuth;
window.redirectIfAuthenticated = redirectIfAuthenticated;
window.hasPermission = hasPermission;
window.applyPermissionVisibility = applyPermissionVisibility;
