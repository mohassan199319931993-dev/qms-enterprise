/**
 * auth.js — Authentication Logic
 * QMS Authentication System
 */

/** Save auth tokens and user data to localStorage */
function saveAuthData(tokens, user) {
  localStorage.setItem('access_token', tokens.access_token);
  localStorage.setItem('refresh_token', tokens.refresh_token);
  localStorage.setItem('current_user', JSON.stringify(user));
}

/** Get stored user object */
function getCurrentUser() {
  try {
    return JSON.parse(localStorage.getItem('current_user') || 'null');
  } catch {
    return null;
  }
}

/** Logout: clear storage and redirect */
function logout() {
  clearAuthData();
  window.location.href = 'login.html';
}

// ── Login ────────────────────────────────────────────────────
async function handleLogin(email, password) {
  const { data, ok } = await API.login({ email, password });
  if (!ok) throw new Error(data.error || 'Login failed');
  saveAuthData(data, data.user);
  return data.user;
}

// ── Register (user in existing factory) ─────────────────────
async function handleRegister(name, email, password, confirmPassword, factoryId) {
  if (password !== confirmPassword) throw new Error('Passwords do not match');
  const { data, ok } = await API.register({ name, email, password, confirm_password: confirmPassword, factory_id: factoryId });
  if (!ok) throw new Error(data.error || 'Registration failed');
  saveAuthData(data, data.user);
  return data.user;
}

// ── Admin Register (create factory + admin) ──────────────────
async function handleAdminRegister(payload) {
  if (payload.password !== payload.confirm_password) throw new Error('Passwords do not match');
  const { data, ok } = await API.adminRegister(payload);
  if (!ok) throw new Error(data.error || 'Registration failed');
  saveAuthData(data, data.user);
  return data;
}

// ── Forgot Password ──────────────────────────────────────────
async function handleForgotPassword(email) {
  const { data, ok } = await API.forgotPassword({ email });
  if (!ok) throw new Error(data.error || 'Request failed');
  return data;
}

// ── Reset Password ───────────────────────────────────────────
async function handleResetPassword(token, password, confirmPassword) {
  if (password !== confirmPassword) throw new Error('Passwords do not match');
  const { data, ok } = await API.resetPassword({ token, password, confirm_password: confirmPassword });
  if (!ok) throw new Error(data.error || 'Reset failed');
  return data;
}

// Expose
window.logout = logout;
window.getCurrentUser = getCurrentUser;
window.handleLogin = handleLogin;
window.handleRegister = handleRegister;
window.handleAdminRegister = handleAdminRegister;
window.handleForgotPassword = handleForgotPassword;
window.handleResetPassword = handleResetPassword;
