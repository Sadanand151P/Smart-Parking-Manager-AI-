/* SmartPark India — API client + shared UI helpers */

const API_BASE = "/api";

function getToken() { return localStorage.getItem("sp_token"); }
function setToken(t) { localStorage.setItem("sp_token", t); }
function clearToken() { localStorage.removeItem("sp_token"); localStorage.removeItem("sp_user"); }
function getUser() { const u = localStorage.getItem("sp_user"); return u ? JSON.parse(u) : null; }
function setUser(u) { localStorage.setItem("sp_user", JSON.stringify(u)); }

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && getToken()) headers["Authorization"] = "Bearer " + getToken();

  const res = await fetch(API_BASE + path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try { data = await res.json(); } catch (e) { /* empty body */ }

  if (!res.ok) {
    const err = new Error((data && data.error) || `Request failed (${res.status})`);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

function toast(message, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = message;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add("show"));
  setTimeout(() => {
    el.classList.remove("show");
    setTimeout(() => el.remove(), 300);
  }, 3800);
}

function requireAuth(allowedRoles) {
  const user = getUser();
  if (!getToken() || !user) {
    window.location.href = "login.html";
    return null;
  }
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    window.location.href = "index.html";
    return null;
  }
  return user;
}

function renderNavbar(containerId = "navbar") {
  const user = getUser();
  const el = document.getElementById(containerId);
  if (!el) return;
  let links = `<a href="index.html">Find Parking</a>`;
  if (user) {
    if (user.role === "customer") links += `<a href="my-bookings.html">My Bookings</a>`;
    if (user.role === "owner") links += `<a href="owner.html">Owner Dashboard</a>`;
    if (user.role === "admin") links += `<a href="admin.html">Admin</a>`;
    links += `<a href="#" id="logoutLink">Logout (${user.name.split(" ")[0]})</a>`;
  } else {
    links += `<a href="login.html">Login</a><a href="register.html">Register</a>`;
  }
  el.innerHTML = `
    <div class="container">
      <a class="brand" href="index.html">🅿️ SmartPark <span class="plate">INDIA</span></a>
      <nav>${links}</nav>
    </div>`;
  const logout = document.getElementById("logoutLink");
  if (logout) logout.addEventListener("click", (e) => { e.preventDefault(); clearToken(); window.location.href = "index.html"; });
}

/** Renders a live painted-bay grid: N cells, `occupiedCount` shown as occupied. */
function renderBayGrid(container, total, occupied, cells = 24) {
  const shownCells = Math.min(cells, Math.max(total, 1));
  const occupiedRatio = total > 0 ? occupied / total : 0;
  const occupiedShown = Math.round(occupiedRatio * shownCells);
  let html = "";
  for (let i = 0; i < shownCells; i++) {
    const isOccupied = i < occupiedShown;
    html += `<div class="bay ${isOccupied ? "occupied" : "free"}">${isOccupied ? "X" : ""}</div>`;
  }
  container.innerHTML = html;
}

function scoreTagClass(score) {
  if (score >= 70) return "tag-green";
  if (score >= 45) return "tag-yellow";
  return "tag-red";
}
