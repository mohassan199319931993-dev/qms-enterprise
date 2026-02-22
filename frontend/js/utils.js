/**
 * utils.js — Utilities: Validation, Toast, Helpers
 * QMS Authentication System
 */

// ── Toast Notifications ──────────────────────────────────────

let _toastContainer = null;

function getToastContainer() {
  if (!_toastContainer) {
    _toastContainer = document.createElement('div');
    _toastContainer.className = 'toast-container';
    document.body.appendChild(_toastContainer);
  }
  return _toastContainer;
}

/**
 * Show a toast notification.
 * @param {string} message
 * @param {'success'|'error'|'warning'|'info'} type
 * @param {number} duration - ms
 */
function showToast(message, type = 'info', duration = 3500) {
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' };
  const container = getToastContainer();

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span><span>${message}</span>`;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'slideIn .3s reverse';
    setTimeout(() => toast.remove(), 280);
  }, duration);
}

// ── Form Validation ──────────────────────────────────────────

const Validators = {
  required: (v) => v && v.trim().length > 0 ? null : 'This field is required',
  email:    (v) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? null : 'Enter a valid email address',
  minLen:   (n) => (v) => v && v.length >= n ? null : `Must be at least ${n} characters`,
  maxLen:   (n) => (v) => !v || v.length <= n ? null : `Must be ${n} characters or fewer`,
  match:    (other) => (v) => v === other ? null : 'Passwords do not match',
  password: (v) => {
    if (!v || v.length < 8) return 'Password must be at least 8 characters';
    if (!/[A-Z]/.test(v)) return 'Must contain at least one uppercase letter';
    if (!/[0-9]/.test(v)) return 'Must contain at least one number';
    return null;
  }
};

/**
 * Validate a form field.
 * @param {HTMLElement} input
 * @param {function[]} rules
 * @returns {boolean} valid
 */
function validateField(input, rules) {
  const value = input.value;
  const errorEl = input.closest('.form-group')?.querySelector('.field-error');

  for (const rule of rules) {
    const err = rule(value);
    if (err) {
      input.classList.add('error');
      input.classList.remove('success');
      if (errorEl) { errorEl.textContent = err; errorEl.classList.add('show'); }
      return false;
    }
  }

  input.classList.remove('error');
  input.classList.add('success');
  if (errorEl) errorEl.classList.remove('show');
  return true;
}

/**
 * Show global form-level error message.
 */
function showFormError(containerId, message) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.textContent = message;
  el.className = 'alert alert-danger';
  el.style.display = 'flex';
}

function hideFormError(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.style.display = 'none';
}

// ── Password Strength ────────────────────────────────────────

function getPasswordStrength(password) {
  let score = 0;
  if (password.length >= 8) score++;
  if (password.length >= 12) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;
  if (/[^A-Za-z0-9]/.test(password)) score++;
  if (score <= 1) return { level: 'weak', score };
  if (score <= 3) return { level: 'medium', score };
  return { level: 'strong', score };
}

function updateStrengthBar(inputEl, barContainerId) {
  const container = document.getElementById(barContainerId);
  if (!container) return;
  const { level, score } = getPasswordStrength(inputEl.value);
  const segments = container.querySelectorAll('.strength-segment');
  const label = container.querySelector('.strength-label');
  segments.forEach((s, i) => {
    s.className = `strength-segment${i < score ? ' ' + level : ''}`;
  });
  if (label) {
    label.textContent = inputEl.value ? `Strength: ${level}` : '';
    label.style.color = level === 'weak' ? 'var(--danger)' : level === 'medium' ? 'var(--warning)' : 'var(--success)';
  }
}

// ── URL Params ───────────────────────────────────────────────

function getUrlParam(name) {
  return new URLSearchParams(window.location.search).get(name);
}

// ── Toggle password visibility ───────────────────────────────

function togglePasswordVisibility(inputId, btnId) {
  const input = document.getElementById(inputId);
  const btn = document.getElementById(btnId);
  if (!input) return;
  const isText = input.type === 'text';
  input.type = isText ? 'password' : 'text';
  if (btn) btn.innerHTML = `<i class="fas fa-eye${isText ? '' : '-slash'}"></i>`;
}

// ── Button Loading State ─────────────────────────────────────

function setButtonLoading(btn, loading) {
  if (loading) {
    btn.classList.add('loading');
    btn.disabled = true;
  } else {
    btn.classList.remove('loading');
    btn.disabled = false;
  }
}

// ── Format Date ──────────────────────────────────────────────

function formatDate(isoString) {
  if (!isoString) return '—';
  return new Date(isoString).toLocaleDateString('en-US', {
    year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
  });
}

// ── Avatar Initials ──────────────────────────────────────────

function getInitials(name) {
  return (name || '?')
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map(w => w[0].toUpperCase())
    .join('');
}

// Expose
window.showToast = showToast;
window.Validators = Validators;
window.validateField = validateField;
window.showFormError = showFormError;
window.hideFormError = hideFormError;
window.getPasswordStrength = getPasswordStrength;
window.updateStrengthBar = updateStrengthBar;
window.getUrlParam = getUrlParam;
window.togglePasswordVisibility = togglePasswordVisibility;
window.setButtonLoading = setButtonLoading;
window.formatDate = formatDate;
window.getInitials = getInitials;
