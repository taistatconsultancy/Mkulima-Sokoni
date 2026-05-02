/**
 * Firebase sign-in for /admin-support; exposes token for Bearer API calls.
 */
import { initializeApp } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js';
import { getAuth, signInWithEmailAndPassword, onAuthStateChanged, signOut } from 'https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js';

const firebaseConfig = {
  apiKey: 'AIzaSyDEX2PIAw5ZhSp84OiZgRK35WfGhTeT-0E',
  authDomain: 'agriculture-43eaf.firebaseapp.com',
  projectId: 'agriculture-43eaf',
  storageBucket: 'agriculture-43eaf.firebasestorage.app',
  messagingSenderId: '340310533875',
  appId: '1:340310533875:web:54c8b2d5e28bf32d437986',
  measurementId: 'G-9W1C0JWRYN'
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

function apiBase() {
  const h = window.location.hostname || '';
  if (h === 'localhost' || h === '127.0.0.1' || h.indexOf('192.168.') === 0) {
    return 'http://localhost:5000/api';
  }
  return '/api';
}

function showAdminDashboard() {
  document.getElementById('loginGate').classList.add('hidden');
  document.getElementById('adminPage').style.display = '';
  if (typeof window.__bootstrapAdminDashboard === 'function') {
    window.__bootstrapAdminDashboard();
  }
}

function hideAdminDashboard() {
  document.getElementById('loginGate').classList.remove('hidden');
  document.getElementById('adminPage').style.display = 'none';
  window.__adminSupportCenterInitialized = false;
}

async function verifyAdminOnBackend(user) {
  const token = await user.getIdToken();
  const res = await fetch(apiBase() + '/auth/admin/stats', {
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/json' },
  });
  return res.ok;
}

window.__getAdminIdToken = function () {
  return auth.currentUser ? auth.currentUser.getIdToken() : Promise.resolve(null);
};

window.__adminSignOut = function () {
  return signOut(auth);
};

document.getElementById('adminLoginForm').addEventListener('submit', async function (e) {
  e.preventDefault();
  var form = e.target;
  var submitBtn = form.querySelector('button[type="submit"]') || form.querySelector('.login-btn');
  var idleLabel = submitBtn ? submitBtn.textContent : '';
  if (submitBtn && submitBtn.disabled) return;
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = 'Signing in…';
  }
  var errEl = document.getElementById('loginError');
  errEl.style.display = 'none';
  var email = document.getElementById('admin-email').value.trim();
  var pass = document.getElementById('admin-password').value;
  try {
    await signInWithEmailAndPassword(auth, email, pass);
  } catch (err) {
    errEl.textContent = (err && err.message) ? err.message : 'Sign-in failed.';
    errEl.style.display = 'block';
    setTimeout(function () { errEl.style.display = 'none'; }, 5000);
  } finally {
    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.textContent = idleLabel;
    }
  }
});

onAuthStateChanged(auth, async function (user) {
  window.__adminUserEmail = user && user.email ? user.email : '';
  if (!user) {
    hideAdminDashboard();
    return;
  }
  try {
    const allowed = await verifyAdminOnBackend(user);
    if (!allowed) {
      await signOut(auth);
      var errEl = document.getElementById('loginError');
      errEl.textContent = 'You do not have admin access.';
      errEl.style.display = 'block';
      hideAdminDashboard();
      return;
    }
    showAdminDashboard();
  } catch (e) {
    console.warn('[admin-support] admin verification failed', e);
    try {
      await signOut(auth);
    } catch (e2) { /* ignore */ }
    hideAdminDashboard();
  }
});
