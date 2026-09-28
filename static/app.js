const state = {
  user: null,
  cameras: [],
  events: [],
  alerts: [],
  watchlist: [],
  stats: null,
  activity: [],
  gap: null,
  maps: { overview: null, main: null },
  markerLayers: { overview: [], main: [] },
  routeLayer: null,
  socket: null,
  reconnectTimer: null,
  activeView: "overview",
  mapConfig: null,
  mapTileErrorShown: false,
};

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[character]));

const formatDate = (value, includeSeconds = false) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", ...(includeSeconds ? { second: "2-digit" } : {}) }).format(date);
};

const formatTime = (value) => {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(date);
};

const timeAgo = (value) => {
  if (!value) return "never";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 45) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
};

const titleCase = (value) => String(value ?? "").replaceAll("_", " ").toLowerCase().replace(/(^|\s)\S/g, (letter) => letter.toUpperCase());
const statusClass = (value) => String(value || "offline").toLowerCase();
const severityClass = (value) => String(value || "medium").toLowerCase();
const initials = (value) => String(value || "U").slice(0, 1).toUpperCase();

async function api(path, options = {}) {
  const request = { credentials: "include", ...options, headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(options.headers || {}) } };
  const response = await fetch(path, request);
  if (response.status === 401 && state.user) {
    state.user = null;
    showLogin();
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" ? payload.detail : payload;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return payload;
}

const defaultMapConfig = Object.freeze({
  tile_url: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap contributors</a> · <a href="https://www.openstreetmap.org/fixthemap" target="_blank" rel="noopener">Report a map issue</a>',
  max_zoom: 19,
  referrer_policy: "strict-origin-when-cross-origin",
});

async function loadMapConfig() {
  try {
    state.mapConfig = await api("/api/v1/system/map-config");
  } catch (error) {
    console.warn("Map configuration unavailable; using the documented default", error);
  }
}

function showToast(message, type = "info", duration = 4200) {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.innerHTML = `<span class="toast-symbol">${type === "success" ? "✓" : type === "error" ? "!" : "i"}</span><span>${escapeHtml(message)}</span>`;
  $("#toast-stack").appendChild(toast);
  window.setTimeout(() => toast.remove(), duration);
}

function showLogin() {
  $("#login-view").classList.remove("hidden");
  $("#app-view").classList.add("hidden");
}

async function showApp() {
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  const name = state.user?.display_name || "Operator";
  $("#welcome-name").textContent = name.split(" ")[0];
  const hour = new Date().getHours();
  $("#greeting").textContent = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  if (/Mac|iPhone|iPad/.test(navigator.platform)) $("#search-kbd").textContent = "⌘ K";
  $("#sidebar-user").innerHTML = `<span class="avatar">${escapeHtml(initials(name))}</span><div><strong>${escapeHtml(name)}</strong><small>${escapeHtml(state.user?.role || "operator")}</small></div>`;
  await loadMapConfig();
  initializeMaps();
  refreshAll();
  connectRealtime();
}

function switchView(view) {
  state.activeView = view;
  $$(".view").forEach((section) => section.classList.toggle("active-view", section.id === `view-${view}`));
  $$(".nav-item[data-view]").forEach((item) => item.classList.toggle("active", item.dataset.view === view));
  const title = view.charAt(0).toUpperCase() + view.slice(1);
  $("#page-title").textContent = title === "Gis" ? "GIS & movement" : title;
  if (view === "map") {
    initializeMaps();
    window.setTimeout(() => state.maps.main?.invalidateSize(), 50);
  }
}

function setViewFromTarget(target) {
  switchView(target);
}

async function refreshAll() {
  await Promise.all([loadStats(), loadCameras(), loadEvents(), loadAlerts(), loadWatchlist(), loadActivity(), loadGap()]);
  renderAll();
}

async function loadStats() {
  try { state.stats = await api("/api/v1/dashboard/stats"); } catch (error) { console.warn(error); }
}

async function loadCameras() {
  const params = new URLSearchParams();
  const search = $("#camera-search")?.value.trim();
  const status = $("#camera-status-filter")?.value;
  const protocol = $("#camera-protocol-filter")?.value;
  if (search) params.set("q", search);
  if (status) params.set("status", status);
  if (protocol) params.set("protocol", protocol);
  params.set("page_size", "500");
  try {
    const payload = await api(`/api/v1/cameras?${params.toString()}`);
    state.cameras = payload.items || [];
  } catch (error) { showToast(error.message, "error"); }
}

async function loadEvents() {
  const params = new URLSearchParams({ page_size: "500" });
  const search = $("#event-search")?.value.trim();
  const type = $("#event-type-filter")?.value;
  if (search) params.set("q", search);
  if (type) params.set("event_type", type);
  try {
    const payload = await api(`/api/v1/events?${params.toString()}`);
    state.events = payload.items || [];
  } catch (error) { showToast(error.message, "error"); }
}

async function loadAlerts() {
  const params = new URLSearchParams({ page_size: "500" });
  const status = $("#alert-status-filter")?.value;
  if (status) params.set("status", status);
  try {
    const payload = await api(`/api/v1/alerts?${params.toString()}`);
    state.alerts = payload.items || [];
  } catch (error) { showToast(error.message, "error"); }
}

async function loadWatchlist() {
  const params = new URLSearchParams();
  const search = $("#watchlist-search")?.value.trim();
  const type = $("#watchlist-type-filter")?.value;
  if (search) params.set("q", search);
  if (type) params.set("entity_type", type);
  try { state.watchlist = await api(`/api/v1/watchlist?${params.toString()}`); } catch (error) { showToast(error.message, "error"); }
}

async function loadActivity() {
  try { state.activity = await api("/api/v1/dashboard/activity?limit=12"); } catch (error) { console.warn(error); }
}

async function loadGap() {
  try { state.gap = await api("/api/v1/cameras/gap-analysis"); } catch (error) { console.warn(error); }
}

function renderAll() {
  renderStats();
  renderLiveGrid();
  renderOverviewAlerts();
  renderActivity();
  renderLatestDetection();
  renderCameraTable();
  renderEventTable();
  renderAlertTable();
  renderWatchlistTable();
  renderRegistrySummary();
  renderMaps();
}

function renderStats() {
  const stats = state.stats;
  if (!stats) return;
  $("#metric-cameras").textContent = stats.total_cameras;
  $("#metric-online").textContent = `${stats.online_cameras} online`;
  $("#metric-alerts").textContent = stats.open_alerts;
  $("#metric-critical").textContent = `${stats.critical_alerts} critical`;
  $("#metric-events").textContent = stats.events_today;
  $("#metric-sources").textContent = `${stats.active_sources} sources`;
  $("#metric-watchlist").textContent = stats.watchlist_entries;
  $("#metric-last-event").textContent = timeAgo(stats.last_event_at);
  $("#camera-health-bar").style.width = `${stats.total_cameras ? Math.round((stats.online_cameras / stats.total_cameras) * 100) : 0}%`;
  $("#camera-nav-count").textContent = stats.total_cameras;
  $("#event-nav-count").textContent = stats.total_events;
  $("#alert-nav-count").textContent = stats.open_alerts;
  $("#last-sync").textContent = `SYNCED ${formatTime(new Date().toISOString())}`;
}

function renderRegistrySummary() {
  const stats = state.stats;
  const online = state.cameras.filter((camera) => camera.status === "ONLINE").length;
  const protocols = new Set(state.cameras.map((camera) => camera.source_protocol)).size;
  $("#registry-total").textContent = stats?.total_cameras ?? state.cameras.length;
  $("#registry-online").textContent = online;
  $("#registry-sources").textContent = protocols;
  $("#registry-gap").textContent = state.gap?.uncovered_zones?.length ?? "—";
}

function renderLiveGrid() {
  const grid = $("#live-grid");
  const cameras = state.cameras.filter((camera) => camera.enabled).slice(0, 4);
  if (!cameras.length) { grid.innerHTML = '<div class="feed-placeholder">No enabled camera sources</div>'; return; }
  grid.innerHTML = cameras.map((camera) => `<div class="live-tile"><img loading="lazy" src="/api/v1/cameras/${encodeURIComponent(camera.camera_id)}/stream?t=${Date.now()}" alt="${escapeHtml(camera.name)} simulated feed"><div class="live-tile-overlay"><div><strong>${escapeHtml(camera.name)}</strong><small>${escapeHtml(camera.camera_id)} · ${escapeHtml(camera.zone)}</small></div><span class="tile-status ${statusClass(camera.status)}">${titleCase(camera.status)}</span></div></div>`).join("");
}

function renderOverviewAlerts() {
  const container = $("#overview-alerts");
  const alerts = state.alerts.filter((alert) => alert.status !== "RESOLVED").slice(0, 4);
  if (!alerts.length) { container.innerHTML = '<div class="empty-table">No open alerts. Network is quiet.</div>'; return; }
  container.innerHTML = alerts.map((alert) => `<div class="compact-row"><i class="severity-bar ${severityClass(alert.severity)}"></i><div class="compact-main"><strong>${escapeHtml(alert.matched_identifier)} · ${escapeHtml(alert.camera_name || alert.camera_id)}</strong><small>${escapeHtml(alert.message)}</small></div><span class="compact-time">${timeAgo(alert.created_at)}</span></div>`).join("");
}

function renderActivity() {
  const container = $("#activity-list");
  if (!state.activity.length) { container.innerHTML = '<div class="empty-table">No activity yet.</div>'; return; }
  container.innerHTML = state.activity.slice(0, 6).map((entry) => `<div class="activity-row"><span class="activity-icon">${entry.action.includes("alert") ? "!" : entry.action.includes("camera") ? "▣" : entry.action.includes("auth") ? "⌁" : "◈"}</span><div class="activity-copy"><strong>${escapeHtml(titleCase(entry.action.replaceAll(".", " ")))}</strong><small>${escapeHtml(entry.actor)} · ${escapeHtml(entry.resource_type)}</small></div><span class="compact-time">${timeAgo(entry.created_at)}</span></div>`).join("");
}

function renderLatestDetection() {
  const event = state.events[0];
  const container = $("#latest-detection");
  if (!event) { container.innerHTML = '<div class="detection-empty">Waiting for an analytics event…</div>'; return; }
  container.innerHTML = `<div class="detection-plate"><strong>${escapeHtml(event.entity_identifier || "UNIDENTIFIED")}</strong><span class="tag ${event.alert_id ? "red" : "green"}">${event.alert_id ? "MATCHED" : "CLEAR"}</span></div><div class="detection-meta"><div><span>Camera</span><b>${escapeHtml(event.camera_id)}</b></div><div><span>Confidence</span><b>${event.confidence == null ? "—" : `${Math.round(event.confidence * 100)}%`}</b></div><div><span>Event</span><b>${escapeHtml(event.event_type)}</b></div><div><span>Observed</span><b>${formatTime(event.occurred_at)}</b></div></div>`;
}

function renderCameraTable() {
  const table = $("#camera-table");
  if (!state.cameras.length) { table.innerHTML = '<div class="empty-table">No camera sources match these filters.</div>'; return; }
  const canManage = state.user?.role === "admin";
  const head = `<div class="data-row data-head"><span>Camera ID</span><span>Source / department</span><span>Zone</span><span>Health</span><span>Protocol</span><span>Actions</span></div>`;
  const rows = state.cameras.map((camera) => `<div class="data-row"><div class="cell"><strong class="id-chip">${escapeHtml(camera.camera_id)}</strong><small>${escapeHtml(camera.coverage_area || "Coverage not specified")}</small></div><div class="cell"><strong>${escapeHtml(camera.name)}</strong><small>${escapeHtml(camera.department)} · ${escapeHtml(camera.camera_type)}</small></div><div class="cell">${escapeHtml(camera.zone)}<small>${camera.latitude.toFixed(4)}, ${camera.longitude.toFixed(4)}</small></div><div class="cell"><span class="status-pill ${statusClass(camera.status)}">${titleCase(camera.status)}</span><small>${timeAgo(camera.last_heartbeat)}</small></div><div class="cell"><strong>${escapeHtml(camera.source_protocol)}</strong><small>${escapeHtml(camera.adapter?.mode || "simulated")}</small></div><div class="row-actions">${canManage ? `<button class="small-button" data-edit-camera="${escapeHtml(camera.camera_id)}">Edit</button><button class="small-button danger" data-disable-camera="${escapeHtml(camera.camera_id)}">Disable</button>` : '<span class="cell">View only</span>'}</div></div>`).join("");
  table.innerHTML = head + rows;
}

function renderEventTable() {
  const table = $("#event-table");
  if (!state.events.length) { table.innerHTML = '<div class="empty-table">No analytics events match these filters.</div>'; return; }
  const head = `<div class="data-row data-head"><span>Entity</span><span>Camera</span><span>Event</span><span>Confidence</span><span>Observed</span><span>Correlation</span></div>`;
  const rows = state.events.map((event) => `<div class="data-row"><div class="cell"><strong>${escapeHtml(event.entity_identifier || "Unidentified")}</strong><small>${escapeHtml(event.entity_type || "entity")} · ${escapeHtml(event.source)}</small></div><div class="cell"><strong>${escapeHtml(event.camera_id)}</strong><small>${escapeHtml(event.vehicle_type || "—")}</small></div><div class="cell"><strong>${escapeHtml(event.event_type)}</strong><small>${escapeHtml(event.event_key)}</small></div><div class="cell"><strong>${event.confidence == null ? "—" : `${Math.round(event.confidence * 100)}%`}</strong><small>${event.speed_kph == null ? "speed n/a" : `${event.speed_kph} km/h`}</small></div><div class="cell">${formatDate(event.occurred_at, true)}<small>${timeAgo(event.occurred_at)}</small></div><div class="cell">${event.alert_id ? `<span class="status-pill open">MATCHED</span>` : '<span class="status-pill resolved">CLEAR</span>'}</div></div>`).join("");
  table.innerHTML = head + rows;
}

function renderAlertTable() {
  const table = $("#alert-table");
  const open = state.alerts.filter((alert) => alert.status === "OPEN").length;
  const critical = state.alerts.filter((alert) => alert.status === "OPEN" && alert.severity === "CRITICAL").length;
  const acknowledged = state.alerts.filter((alert) => alert.status === "ACKNOWLEDGED").length;
  const resolved = state.alerts.filter((alert) => alert.status === "RESOLVED").length;
  $("#alert-kpi-open").textContent = open;
  $("#alert-kpi-critical").textContent = critical;
  $("#alert-kpi-ack").textContent = acknowledged;
  $("#alert-kpi-resolved").textContent = resolved;
  if (!state.alerts.length) { table.innerHTML = '<div class="empty-table">No alerts match this filter.</div>'; return; }
  const head = `<div class="data-row data-head"><span>Match</span><span>Camera / location</span><span>Severity</span><span>Status</span><span>Observed</span><span>Response</span></div>`;
  const rows = state.alerts.map((alert) => `<div class="data-row"><div class="cell"><strong>${escapeHtml(alert.matched_identifier)}</strong><small>${escapeHtml(alert.entity_name || "Watchlist entity")} · ${alert.confidence == null ? "—" : `${Math.round(alert.confidence * 100)}%`}</small></div><div class="cell"><strong>${escapeHtml(alert.camera_name || alert.camera_id)}</strong><small>${escapeHtml(alert.zone || "Unknown zone")}</small></div><div class="cell"><span class="tag ${severityClass(alert.severity)}">${titleCase(alert.severity)}</span></div><div class="cell"><span class="status-pill ${statusClass(alert.status)}">${titleCase(alert.status)}</span></div><div class="cell">${formatDate(alert.created_at, true)}<small>${timeAgo(alert.created_at)}</small></div><div class="row-actions">${alert.status !== "RESOLVED" ? `<button class="small-button" data-ack-alert="${escapeHtml(alert.id)}">Acknowledge</button><button class="small-button danger" data-resolve-alert="${escapeHtml(alert.id)}">Resolve</button>` : '<span class="cell">Closed</span>'}</div></div>`).join("");
  table.innerHTML = head + rows;
}

function renderWatchlistTable() {
  const table = $("#watchlist-table");
  if (!state.watchlist.length) { table.innerHTML = '<div class="empty-table">No watchlist records match these filters.</div>'; return; }
  const head = `<div class="data-row data-head"><span>Identifier</span><span>Entity</span><span>Reason</span><span>Severity</span><span>State</span><span>Source</span></div>`;
  const rows = state.watchlist.map((entry) => `<div class="data-row"><div class="cell"><strong class="id-chip">${escapeHtml(entry.identifier)}</strong><small>${escapeHtml(entry.entity_type)}</small></div><div class="cell"><strong>${escapeHtml(entry.display_name)}</strong><small>${escapeHtml(entry.department || "No department")}</small></div><div class="cell"><strong>${escapeHtml(entry.reason)}</strong><small>${escapeHtml(entry.extra_data?.case_reference || "No case reference")}</small></div><div class="cell"><span class="tag ${severityClass(entry.severity)}">${titleCase(entry.severity)}</span></div><div class="cell"><span class="status-pill ${entry.active ? "online" : "offline"}">${entry.active ? "Active" : "Inactive"}</span></div><div class="cell">${escapeHtml(entry.extra_data?.source || "manual")}</div></div>`).join("");
  table.innerHTML = head + rows;
}

function cameraAlertState(camera) {
  if (camera.active_alert_count > 0) return camera.highest_alert_severity || "MEDIUM";
  const activeAlerts = state.alerts.filter((alert) => alert.camera_id === camera.camera_id && alert.status !== "RESOLVED");
  if (!activeAlerts.length) return null;
  const rank = { LOW: 1, MEDIUM: 2, HIGH: 3, CRITICAL: 4 };
  return activeAlerts.sort((left, right) => (rank[right.severity] || 0) - (rank[left.severity] || 0))[0]?.severity || "MEDIUM";
}

function markerIcon(status, alertSeverity = null) {
  const statusColors = { ONLINE: "#35d07f", DEGRADED: "#f0b34b", OFFLINE: "#eb6470" };
  const alertColors = { LOW: "#a18bff", MEDIUM: "#62a7ff", HIGH: "#f0b34b", CRITICAL: "#eb6470" };
  const color = alertSeverity ? alertColors[alertSeverity] || alertColors.MEDIUM : statusColors[status] || statusColors.OFFLINE;
  const alertClass = alertSeverity ? " has-alert" : "";
  return L.divIcon({ className: "camera-marker-wrap", html: `<span class="camera-marker${alertClass}" style="--marker:${color}"></span>`, iconSize: [18, 18], iconAnchor: [9, 9] });
}

function mapTileSettings() {
  const config = { ...defaultMapConfig, ...(state.mapConfig || {}) };
  return {
    tileUrl: config.tile_url || defaultMapConfig.tile_url,
    attribution: config.attribution || defaultMapConfig.attribution,
    maxZoom: Number(config.max_zoom) || defaultMapConfig.max_zoom,
    referrerPolicy: config.referrer_policy || defaultMapConfig.referrer_policy,
  };
}

function addMapTiles(map) {
  const config = mapTileSettings();
  const tiles = L.tileLayer(config.tileUrl, {
    maxZoom: config.maxZoom,
    attribution: config.attribution,
    referrerPolicy: config.referrerPolicy,
  });
  tiles.on("tileerror", () => {
    if (state.mapTileErrorShown) return;
    state.mapTileErrorShown = true;
    showToast("Base map tiles are unavailable. Check MAP_TILE_URL or the configured provider; camera markers remain available.", "error", 7000);
  });
  tiles.addTo(map);
}

function initializeMaps() {
  if (!window.L) return;
  if (!state.maps.overview && $("#overview-map")) {
    state.maps.overview = L.map("overview-map", { zoomControl: false, attributionControl: true }).setView([22.99, 72.55], 10);
    addMapTiles(state.maps.overview);
  }
  if (!state.maps.main && $("#main-map")) {
    state.maps.main = L.map("main-map", { zoomControl: true, attributionControl: true }).setView([22.99, 72.55], 10);
    addMapTiles(state.maps.main);
  }
  renderMaps();
}

function renderMaps() {
  if (!window.L) return;
  [["overview", state.maps.overview], ["main", state.maps.main]].forEach(([key, map]) => {
    if (!map) return;
    state.markerLayers[key].forEach((layer) => map.removeLayer(layer));
    state.markerLayers[key] = [];
    const filter = key === "main" ? $("[data-map-filter].active")?.dataset.mapFilter : "all";
    state.cameras.filter((camera) => filter === "all" || camera.status === filter).forEach((camera) => {
      const alertSeverity = cameraAlertState(camera);
      const marker = L.marker([camera.latitude, camera.longitude], { icon: markerIcon(camera.status, alertSeverity), title: camera.name }).addTo(map);
      const alertText = alertSeverity ? `<br><strong>${titleCase(alertSeverity)} alert</strong> · ${camera.active_alert_count || "active"}` : "";
      marker.bindPopup(`<strong>${escapeHtml(camera.name)}</strong><br>${escapeHtml(camera.camera_id)} · ${escapeHtml(camera.department)}<br>${titleCase(camera.status)} · ${escapeHtml(camera.source_protocol)}${alertText}`);
      state.markerLayers[key].push(marker);
    });
  });
}

async function traceEntity(identifier = $("#entity-search-input")?.value.trim()) {
  if (!identifier) return;
  switchView("map");
  $("#trace-title").textContent = identifier.toUpperCase();
  $("#trace-count").textContent = "loading";
  try {
    const history = await api(`/api/v1/events/entities/${encodeURIComponent(identifier)}/history`);
    $("#trace-count").textContent = `${history.total} points`;
    $("#route-summary").innerHTML = `<div><span>Observations</span><strong>${history.total}</strong></div><div><span>Entity type</span><strong>${escapeHtml(history.entity_type || "entity")}</strong></div><div><span>First seen</span><strong>${history.points.length ? formatDate(history.points[0].occurred_at) : "—"}</strong></div><div><span>Last seen</span><strong>${history.points.length ? formatDate(history.points[history.points.length - 1].occurred_at) : "—"}</strong></div>`;
    $("#route-timeline").innerHTML = history.points.length ? history.points.map((point) => `<div class="route-point"><i class="route-dot"></i><div class="route-copy"><strong>${escapeHtml(point.camera_name)}</strong><small>${escapeHtml(point.zone)} · ${escapeHtml(point.department)}</small><small class="route-time">${formatDate(point.occurred_at, true)} · ${point.alert_id ? "watchlist match" : "clear"}</small></div></div>`).join("") : '<div class="empty-table">No movement observations found.</div>';
    initializeMaps();
    if (state.maps.main) {
      state.routeLayer?.remove();
      state.routeLayer = L.polyline(history.route, { color: "#a18bff", weight: 4, opacity: .85, dashArray: "8 8" }).addTo(state.maps.main);
      if (history.route.length) state.maps.main.fitBounds(history.route, { padding: [45, 45], maxZoom: 13 });
    }
  } catch (error) { showToast(error.message, "error"); $("#trace-count").textContent = "error"; }
}

function openModal(id) { $(`#${id}`).classList.remove("hidden"); }
function closeModal(id) { $(`#${id}`).classList.add("hidden"); }

function openCameraModal(camera = null) {
  $("#camera-form").reset();
  $("#camera-edit-id").value = camera?.camera_id || "";
  $("#camera-modal-title").textContent = camera ? `Edit ${camera.camera_id}` : "Add camera source";
  if (camera) {
    $("#camera-id-input").value = camera.camera_id;
    $("#camera-id-input").disabled = true;
    $("#camera-name-input").value = camera.name;
    $("#camera-department-input").value = camera.department;
    $("#camera-zone-input").value = camera.zone;
    $("#camera-latitude-input").value = camera.latitude;
    $("#camera-longitude-input").value = camera.longitude;
    $("#camera-type-input").value = camera.camera_type;
    $("#camera-protocol-input").value = camera.source_protocol;
    $("#camera-stream-input").value = camera.stream_endpoint;
    $("#camera-storage-input").value = camera.storage_provider || "";
    $("#camera-retention-input").value = camera.storage_retention_days || "";
  } else {
    $("#camera-id-input").disabled = false;
  }
  openModal("camera-modal");
}

async function submitCamera(event) {
  event.preventDefault();
  const editId = $("#camera-edit-id").value;
  const payload = {
    camera_id: $("#camera-id-input").value.trim(),
    name: $("#camera-name-input").value.trim(),
    department: $("#camera-department-input").value.trim(),
    latitude: Number($("#camera-latitude-input").value),
    longitude: Number($("#camera-longitude-input").value),
    camera_type: $("#camera-type-input").value.trim(),
    source_protocol: $("#camera-protocol-input").value,
    stream_endpoint: $("#camera-stream-input").value.trim(),
    zone: $("#camera-zone-input").value.trim(),
    storage_provider: $("#camera-storage-input").value.trim() || null,
    storage_retention_days: Number($("#camera-retention-input").value) || null,
  };
  try {
    if (editId) await api(`/api/v1/cameras/${encodeURIComponent(editId)}`, { method: "PATCH", body: JSON.stringify(payload) });
    else await api("/api/v1/cameras", { method: "POST", body: JSON.stringify({ ...payload, status: "ONLINE", enabled: true, extra_data: {} }) });
    closeModal("camera-modal");
    showToast(editId ? "Camera metadata updated" : "Camera source onboarded", "success");
    await Promise.all([loadStats(), loadCameras(), loadGap()]);
    renderAll();
  } catch (error) { showToast(error.message, "error"); }
}

function openWatchlistModal() {
  $("#watchlist-form").reset();
  openModal("watchlist-modal");
}

async function submitWatchlist(event) {
  event.preventDefault();
  const payload = {
    entity_type: $("#watchlist-type-input").value,
    identifier: $("#watchlist-identifier-input").value.trim(),
    display_name: $("#watchlist-name-input").value.trim(),
    reason: $("#watchlist-reason-input").value.trim(),
    severity: $("#watchlist-severity-input").value,
    department: $("#watchlist-department-input").value.trim() || null,
    active: true,
    extra_data: { source: "console" },
  };
  try {
    await api("/api/v1/watchlist", { method: "POST", body: JSON.stringify(payload) });
    closeModal("watchlist-modal");
    showToast("Watchlist record added", "success");
    await Promise.all([loadWatchlist(), loadStats()]);
    renderAll();
  } catch (error) { showToast(error.message, "error"); }
}

async function disableCamera(cameraId) {
  if (!window.confirm(`Disable ${cameraId}? The source will remain auditable but will stop receiving heartbeats.`)) return;
  try { await api(`/api/v1/cameras/${encodeURIComponent(cameraId)}`, { method: "DELETE" }); showToast(`${cameraId} disabled`, "success"); await Promise.all([loadCameras(), loadStats()]); renderAll(); } catch (error) { showToast(error.message, "error"); }
}

async function updateAlert(alertId, action) {
  try { await api(`/api/v1/alerts/${encodeURIComponent(alertId)}/${action}`, { method: "POST" }); showToast(`Alert ${action}d`, "success"); await Promise.all([loadAlerts(), loadStats()]); renderAll(); } catch (error) { showToast(error.message, "error"); }
}

async function simulateDetection(cameraId) {
  try {
    const payload = cameraId ? { camera_id: cameraId, entity_identifier: "GJ01AB1234", confidence: 0.98 } : {};
    const result = await api("/api/v1/events/simulator/emit", { method: "POST", body: JSON.stringify(payload) });
    showToast(result.alert ? `Watchlist match: ${result.alert.matched_identifier}` : `Detection received: ${result.event.entity_identifier}`, result.alert ? "success" : "info");
    await Promise.all([loadStats(), loadEvents(), loadAlerts(), loadCameras(), loadActivity()]);
    renderAll();
  } catch (error) { showToast(error.message, "error"); }
}

function connectRealtime() {
  if (state.socket && state.socket.readyState <= WebSocket.OPEN) return;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const socket = new WebSocket(`${protocol}//${window.location.host}/ws`);
  state.socket = socket;
  socket.addEventListener("open", () => { $("#connection-label").textContent = "Realtime connected"; $(".connection-status .pulse-dot")?.classList.remove("offline"); });
  socket.addEventListener("message", async (message) => {
    try {
      const payload = JSON.parse(message.data);
      if (payload.type === "detection") {
        const matched = Boolean(payload.alert);
        showToast(matched ? `ALERT · ${payload.alert.matched_identifier} matched at ${payload.alert.camera_id}` : `Detection · ${payload.event.entity_identifier || "entity"} received`, matched ? "success" : "info");
        $("#notification-dot").classList.remove("hidden");
        await Promise.all([loadStats(), loadEvents(), loadAlerts(), loadCameras(), loadActivity()]);
        renderAll();
      } else if (payload.type === "alert.updated") {
        await Promise.all([loadAlerts(), loadStats()]);
        renderAll();
      } else if (payload.type === "camera.health") {
        await Promise.all([loadCameras(), loadStats()]);
        renderAll();
      }
    } catch (error) { console.warn("Realtime message ignored", error); }
  });
  socket.addEventListener("close", () => {
    $("#connection-label").textContent = "Reconnecting";
    $(".connection-status .pulse-dot")?.classList.add("offline");
    if (state.user) state.reconnectTimer = window.setTimeout(connectRealtime, 3000);
  });
  socket.addEventListener("error", () => { $("#connection-label").textContent = "Connection issue"; });
}

function updateLiveFeeds() {
  if (!state.user || state.activeView !== "overview") return;
  renderLiveGrid();
}

function bindEvents() {
  $("#login-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const errorBox = $("#login-error");
    errorBox.textContent = "";
    try {
      const payload = await api("/api/v1/auth/login", { method: "POST", body: JSON.stringify({ username: $("#login-username").value.trim(), password: $("#login-password").value }) });
      state.user = payload.user;
      await showApp();
    } catch (error) { errorBox.textContent = error.message; }
  });
  $$("[data-demo-user]").forEach((button) => button.addEventListener("click", () => {
    const admin = button.dataset.demoUser === "admin";
    $("#login-username").value = button.dataset.demoUser;
    $("#login-password").value = admin ? "ChangeMe123!" : "Operator123!";
  }));
  $("#logout-button").addEventListener("click", async () => {
    try { await fetch("/api/v1/auth/logout", { method: "POST", credentials: "include" }); } catch { }
    state.user = null;
    state.socket?.close();
    showLogin();
  });
  $$("[data-view]").forEach((button) => button.addEventListener("click", () => switchView(button.dataset.view)));
  $$("[data-view-target]").forEach((button) => button.addEventListener("click", () => setViewFromTarget(button.dataset.viewTarget)));
  $("#add-camera-button").addEventListener("click", () => openCameraModal());
  $("#overview-simulate").addEventListener("click", () => simulateDetection());
  $("#event-simulate-button").addEventListener("click", () => simulateDetection());
  $("#alert-simulate-button").addEventListener("click", () => simulateDetection("C001"));
  $("#add-watchlist-button").addEventListener("click", openWatchlistModal);
  $("#camera-form").addEventListener("submit", submitCamera);
  $("#watchlist-form").addEventListener("submit", submitWatchlist);
  $$("[data-close-modal]").forEach((button) => button.addEventListener("click", () => closeModal(button.dataset.closeModal)));
  $$(".modal-backdrop").forEach((backdrop) => backdrop.addEventListener("click", (event) => { if (event.target === backdrop) closeModal(backdrop.id); }));
  $("#camera-search").addEventListener("input", () => window.clearTimeout(window.cameraSearchTimer) || (window.cameraSearchTimer = window.setTimeout(async () => { await loadCameras(); renderAll(); }, 250)));
  $("#camera-status-filter").addEventListener("change", async () => { await loadCameras(); renderAll(); });
  $("#camera-protocol-filter").addEventListener("change", async () => { await loadCameras(); renderAll(); });
  $("#camera-filter-reset").addEventListener("click", () => { $("#camera-search").value = ""; $("#camera-status-filter").value = ""; $("#camera-protocol-filter").value = ""; loadCameras().then(renderAll); });
  $("#event-search").addEventListener("input", () => window.clearTimeout(window.eventSearchTimer) || (window.eventSearchTimer = window.setTimeout(async () => { await loadEvents(); renderAll(); }, 250)));
  $("#event-type-filter").addEventListener("change", async () => { await loadEvents(); renderAll(); });
  $("#event-refresh").addEventListener("click", async () => { await Promise.all([loadEvents(), loadStats()]); renderAll(); showToast("Event stream refreshed", "success"); });
  $("#alert-status-filter").addEventListener("change", async () => { await loadAlerts(); renderAll(); });
  $("#watchlist-search").addEventListener("input", () => window.clearTimeout(window.watchlistTimer) || (window.watchlistTimer = window.setTimeout(async () => { await loadWatchlist(); renderAll(); }, 250)));
  $("#watchlist-type-filter").addEventListener("change", async () => { await loadWatchlist(); renderAll(); });
  $("#trace-entity-button").addEventListener("click", () => traceEntity());
  $("#entity-search-input").addEventListener("keydown", (event) => { if (event.key === "Enter") traceEntity(); });
  $("#global-search").addEventListener("keydown", (event) => { if (event.key === "Enter") { const value = event.target.value.trim(); if (!value) return; if (/^[A-Z0-9-]{4,}$/i.test(value)) { $("#entity-search-input").value = value; traceEntity(value); } else { switchView("cameras"); $("#camera-search").value = value; loadCameras().then(renderAll); } } });
  $("#refresh-activity").addEventListener("click", async () => { await loadActivity(); renderActivity(); showToast("Activity refreshed", "success"); });
  $("#notification-button").addEventListener("click", () => { switchView("alerts"); $("#notification-dot").classList.add("hidden"); });
  $("#event-api-button").addEventListener("click", () => window.open("/docs", "_blank"));
  $("#camera-table").addEventListener("click", async (event) => {
    const editId = event.target.closest("[data-edit-camera]")?.dataset.editCamera;
    const disableId = event.target.closest("[data-disable-camera]")?.dataset.disableCamera;
    if (editId) { const camera = state.cameras.find((item) => item.camera_id === editId); if (camera) openCameraModal(camera); }
    if (disableId) disableCamera(disableId);
  });
  $("#alert-table").addEventListener("click", (event) => {
    const ack = event.target.closest("[data-ack-alert]")?.dataset.ackAlert;
    const resolve = event.target.closest("[data-resolve-alert]")?.dataset.resolveAlert;
    if (ack) updateAlert(ack, "acknowledge");
    if (resolve) updateAlert(resolve, "resolve");
  });
  $$("[data-map-filter]").forEach((button) => button.addEventListener("click", () => { $$("[data-map-filter]").forEach((item) => item.classList.remove("active")); button.classList.add("active"); renderMaps(); }));
  document.addEventListener("keydown", (event) => { if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); $("#global-search").focus(); } });
  window.setInterval(updateLiveFeeds, 15000);
}

function bindShortcuts() {
  document.addEventListener("keydown", (event) => {
    if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      $("#global-search")?.focus();
    }
  });
}

async function bootstrap() {
  bindEvents();
  bindShortcuts();
  try {
    const user = await api("/api/v1/auth/me");
    state.user = user;
    await showApp();
  } catch {
    showLogin();
  }
}

document.addEventListener("DOMContentLoaded", bootstrap);
