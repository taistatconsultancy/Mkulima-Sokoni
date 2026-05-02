/**
 * Dashboard session guard: uses Firebase Auth ID token + server DB roles.
 * Skips when admin is impersonating (sessionStorage.superUser).
 */
import { initializeApp, getApps, getApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
import { getAuth } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js';

const firebaseConfig = {
  apiKey: 'AIzaSyDEX2PIAw5ZhSp84OiZgRK35WfGhTeT-0E',
  authDomain: 'agriculture-43eaf.firebaseapp.com',
  projectId: 'agriculture-43eaf',
  storageBucket: 'agriculture-43eaf.firebasestorage.app',
  messagingSenderId: '340310533875',
  appId: '1:340310533875:web:54c8b2d5e28bf32d437986',
  measurementId: 'G-9W1C0JWRYN',
};

function apiBase() {
  const h = window.location.hostname || '';
  if (h === 'localhost' || h === '127.0.0.1' || h.indexOf('192.168.') === 0) {
    return 'http://localhost:5000/api';
  }
  return '/api';
}

function pathLeafNorm(p) {
  const seg = ((p || '').split('/').filter(Boolean).pop() || '').toLowerCase();
  return seg.replace(/\.html$/i, '');
}

function pageDashboardRole() {
  const file = pathLeafNorm(window.location.pathname || '');
  const map = {
    farmer: 'farmer',
    'agro-dealer': 'agro-dealer',
    buyer: 'buyer',
  };
  return { file, required: map[file] || null };
}

async function main() {
  const { file, required } = pageDashboardRole();
  if (!required) return;

  try {
    if (sessionStorage.getItem('superUser') === 'true') return;
  } catch (e) {
    /* ignore */
  }

  let userStr = '';
  try {
    userStr = localStorage.getItem('user') || '';
  } catch (e) {
    window.location.replace('/auth');
    return;
  }
  if (!userStr.trim()) {
    window.location.replace('/auth');
    return;
  }

  let cachedUser = null;
  try {
    cachedUser = JSON.parse(userStr);
  } catch (e) {
    try {
      localStorage.removeItem('user');
      localStorage.removeItem('userRole');
    } catch (e2) {}
    window.location.replace('/auth');
    return;
  }

  const app = getApps().length ? getApp() : initializeApp(firebaseConfig);
  const auth = getAuth(app);
  await auth.authStateReady();
  const cu = auth.currentUser;
  if (!cu) {
    try {
      localStorage.removeItem('user');
      localStorage.removeItem('userRole');
    } catch (e) {}
    window.location.replace('/auth');
    return;
  }

  const cachedUid = String(cachedUser.firebase_uid || cachedUser.id || '').trim();
  if (!cachedUid || cachedUid !== cu.uid) {
    try {
      localStorage.removeItem('user');
      localStorage.removeItem('userRole');
    } catch (e) {}
    window.location.replace('/auth');
    return;
  }

  let idToken;
  try {
    idToken = await cu.getIdToken(false);
  } catch (e) {
    window.location.replace('/auth');
    return;
  }

  let res;
  try {
    res = await fetch(`${apiBase()}/auth/verify-dashboard-session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ id_token: idToken, dashboard: required }),
    });
  } catch (e) {
    console.warn('[dashboard-session-guard] network error — skipping redirect', e);
    return;
  }

  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    data = {};
  }

  if (res.status === 401) {
    window.location.replace('/auth');
    return;
  }

  if (res.status === 404) {
    try {
      localStorage.removeItem('user');
      localStorage.removeItem('userRole');
    } catch (e) {}
    window.location.replace('/');
    return;
  }

  if (!res.ok) {
    console.warn('[dashboard-session-guard] API error', res.status, data);
    return;
  }

  try {
    if (data.role) localStorage.setItem('userRole', data.role);
    const merged = { ...cachedUser, role: data.role || cachedUser.role };
    localStorage.setItem('user', JSON.stringify(merged));
  } catch (e) {
    /* ignore */
  }

  const red = (data.redirect || '').toString();
  const redLeaf = pathLeafNorm(red.startsWith('http') ? (new URL(red).pathname || '') : red);
  if (!data.allowed && red && redLeaf && redLeaf !== file) {
    const url =
      red.startsWith('/') || red.startsWith('http')
        ? red
        : '/' + red.replace(/^\/+/, '');
    window.location.replace(url);
  }
}

main();
