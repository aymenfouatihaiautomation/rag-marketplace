// ── Auth helpers ──────────────────────────────────────────────────────────────
const Auth = {
  save(token, user_id, username) {
    localStorage.setItem('token',    token);
    localStorage.setItem('user_id',  user_id);
    localStorage.setItem('username', username);
  },
  token()    { return localStorage.getItem('token'); },
  userId()   { return localStorage.getItem('user_id'); },
  username() { return localStorage.getItem('username'); },
  clear()    { localStorage.removeItem('token'); localStorage.removeItem('user_id'); localStorage.removeItem('username'); },
  guard()    { if (!Auth.token()) { window.location.href = '/login.html'; return false; } return true; }
};

// ── API wrapper ───────────────────────────────────────────────────────────────
const API = {
  async call(method, path, body = null) {
    const opts = {
      method,
      headers: {
        'Content-Type':  'application/json',
        'Authorization': `Bearer ${Auth.token()}`
      }
    };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(path, opts);
    if (res.status === 401) { Auth.clear(); window.location.href = '/login.html'; return; }
    return res.json();
  },
  get(path)         { return API.call('GET',    path); },
  post(path, body)  { return API.call('POST',   path, body); },
  del(path)         { return API.call('DELETE', path); }
};

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type = 'success') {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.className   = `show ${type}`;
  setTimeout(() => { t.className = ''; }, 3000);
}

// ── Logout ────────────────────────────────────────────────────────────────────
async function logout() {
  try { await API.post('/logout'); } catch (_) {}
  Auth.clear();
  window.location.href = '/login.html';
}

// ── Fill navbar user info ─────────────────────────────────────────────────────
function fillNavUser() {
  const name = Auth.username() || '?';
  const el   = document.getElementById('nav-username');
  const av   = document.getElementById('nav-avatar');
  if (el) el.textContent = name;
  if (av) av.textContent = name.charAt(0).toUpperCase();
}
