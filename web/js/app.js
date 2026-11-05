const state = {
  users: [],
  projects: [],
  currentProjectId: null,
  taskLists: [],
  tasks: [],
  currentTab: "board",
  filesPath: "",
  filesTree: null,
  collapsedFolders: new Set(),
  selectedEntry: null,
  calendarMonth: startOfMonth(new Date()),
  gcalConnected: false,
  currentUserId: localStorage.getItem("vpm_current_user_id") || "",
  searchResults: [],
  filesPath: "",
  filesTree: null,
  collapsedFolders: new Set(),
  selectedEntry: null,
  calendarMonth: startOfMonth(new Date()),
  gcalConnected: false,
  currentUserId: localStorage.getItem("vpm_current_user_id") || "",
};

const FOLDER_COLOR_PRESETS = ["#eb5757", "#f2994a", "#f2c94c", "#2ecc71", "#4dabf7", "#6c5ce7", "#a29bfe", "#e17055"];

const PROJECT_TYPE_ICON = { "Vídeo": "🎥", "Animación": "🎞️", "Edición": "✂️", "3D": "🧊", "Rodaje": "🎬", "Otro": "📁" };

// Mirrors vpm/project_templates.py, just for the "this is what will be created" preview in the UI.
const FOLDER_TEMPLATES_PREVIEW = {
  "Vídeo": ["00_Admin", "01_Preproduccion", "02_Rodaje", "03_Material_Bruto", "04_Edicion", "05_Sonido", "06_Color", "07_Entregas"],
  "Animación": ["00_Admin", "01_Preproduccion", "02_Guion_Storyboard", "03_Diseno_Personajes", "04_Animatica", "05_Animacion", "06_Render", "07_Composicion", "08_Sonido", "09_Entregas"],
  "Edición": ["00_Admin", "01_Material_Bruto", "02_Proyecto_Edicion", "03_Musica_Sonido", "04_Grafismos", "05_Color", "06_Entregas"],
  "3D": ["00_Admin", "01_Referencias", "02_Modelado", "03_Texturizado", "04_Rigging", "05_Animacion", "06_Render", "07_Composicion", "08_Entregas"],
  "Rodaje": ["00_Preproduccion", "01_Guion_Shotlist", "02_Localizaciones", "03_Casting", "04_Material_Rodaje", "05_Sonido_Directo", "06_Entregas"],
  "Otro": ["00_Admin", "01_Material", "02_Entregas"],
};

function $(sel) { return document.querySelector(sel); }
function $$(sel) { return Array.from(document.querySelectorAll(sel)); }
function startOfMonth(d) { return new Date(d.getFullYear(), d.getMonth(), 1); }

// Parses a Date, a bare "YYYY-MM-DD", or a full "YYYY-MM-DDTHH:MM:SS" string into a Date
// representing that calendar day at LOCAL midnight. Deliberately ignores any timezone/offset
// info in the string: this app only ever cares about whole calendar days, and letting the
// native Date UTC-parsing rules touch these strings causes an off-by-one-day bug for anyone
// east of UTC (dates would silently shift back a day when dragged on the calendar/timeline).
function parseAnyDate(d) {
  if (!d) return null;
  if (d instanceof Date) return new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), d.getMinutes(), d.getSeconds());
  const datePart = String(d).split("T")[0];
  const [y, m, day] = datePart.split("-").map(Number);
  return new Date(y, m - 1, day);
}
function fmtDate(d) {
  if (!d) return "";
  const dt = parseAnyDate(d);
  return dt.getFullYear() + "-" + String(dt.getMonth() + 1).padStart(2, "0") + "-" + String(dt.getDate()).padStart(2, "0");
}
function fmtDateHuman(d) { if (!d) return ""; const dt = parseAnyDate(d); return dt.toLocaleDateString("es-ES", { day: "2-digit", month: "short" }); }
function initials(name) { return (name || "?").trim().split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase(); }
function userById(id) { return state.users.find(u => u.id === id); }
function projectById(id) { return state.projects.find(p => p.id === id); }
function toast(msg, isError) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  $("#toast-container").appendChild(el);
  setTimeout(() => el.remove(), 4000);
}

function openModal(id) { $("#modal-backdrop").classList.remove("hidden"); $(id).classList.remove("hidden"); }
function closeModals() {
  $("#modal-backdrop").classList.add("hidden");
  $$(".modal").forEach(m => m.classList.add("hidden"));
}
$("#modal-backdrop").addEventListener("click", closeModals);
$$("[data-close]").forEach(b => b.addEventListener("click", closeModals));

// ---------- INIT ----------
async function init() {
  await Promise.all([loadUsers(), loadProjects(), refreshGcalStatus()]);
  if (state.projects.length) await selectProject(state.projects[0].id);
  bindGlobalEvents();
  renderWhoAmI();
  refreshInboxBadge();
}

async function loadUsers() {
  state.users = await api.users.list();
}

async function loadProjects() {
  state.projects = await api.projects.list();
  renderProjectList();
}

function renderProjectList() {
  const el = $("#project-list");
  el.innerHTML = "";
  state.projects.forEach(p => {
    const div = document.createElement("div");
    div.className = "project-item" + (p.id === state.currentProjectId ? " active" : "");
    div.innerHTML = `<span class="dot" style="background:${p.color}"></span>
      <span class="name">${PROJECT_TYPE_ICON[p.project_type] || "📁"} ${escapeHtml(p.name)}</span>`;
    div.addEventListener("click", () => selectProject(p.id));
    el.appendChild(div);
  });
}

function escapeHtml(s) {
  return (s ?? "").toString().replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------- PROJECT SELECTION ----------
async function selectProject(id) {
  state.currentProjectId = id;
  state.filesPath = "";
  state.filesTree = null;
  state.collapsedFolders = new Set();
  state.selectedEntry = null;
  renderProjectList();
  const project = projectById(id);
  if (!project) return;

  $("#empty-state").classList.add("hidden");
  $("#project-view").classList.remove("hidden");
  $("#pv-name").textContent = project.name;
  $("#pv-type").textContent = `${PROJECT_TYPE_ICON[project.project_type] || ""} ${project.project_type}`;
  $("#pv-color").style.background = project.color;

  await loadProjectData();
  switchTab(state.currentTab);
}

async function loadProjectData() {
  const id = state.currentProjectId;
  [state.taskLists, state.tasks] = await Promise.all([
    api.taskLists.list(id),
    api.tasks.listByProject(id),
  ]);
}

async function switchTab(tab, selectRelPath) {
  state.currentTab = tab;
  $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === tab));
  $$(".tab-panel").forEach(p => p.classList.add("hidden"));
  $(`#panel-${tab}`).classList.remove("hidden");
  if (tab === "board") renderBoard();
  if (tab === "timeline") renderTimeline();
  if (tab === "calendar") renderCalendar();
  if (tab === "files") await renderFiles(selectRelPath);
}

// ---------- BOARD ----------
function renderBoard() {
  const project = projectById(state.currentProjectId);
  const panel = $("#panel-board");
  panel.innerHTML = "";
  const board = document.createElement("div");
  board.className = "board";

  project.statuses.forEach(status => {
    const col = document.createElement("div");
    col.className = "board-column";
    const tasksInCol = state.tasks.filter(t => t.status === status).sort((a, b) => a.position - b.position);
    col.innerHTML = `<div class="board-column-header"><span>${escapeHtml(status)}</span><span>${tasksInCol.length}</span></div>
      <div class="board-column-body" data-status="${escapeHtml(status)}"></div>`;
    const body = col.querySelector(".board-column-body");
    tasksInCol.forEach(t => body.appendChild(renderTaskCard(t)));

    body.addEventListener("dragover", e => { e.preventDefault(); body.classList.add("drag-over"); });
    body.addEventListener("dragleave", () => body.classList.remove("drag-over"));
    body.addEventListener("drop", async e => {
      e.preventDefault();
      body.classList.remove("drag-over");
      const taskId = e.dataTransfer.getData("text/task-id");
      const task = state.tasks.find(t => t.id === taskId);
      if (!task) return;
      task.status = status;
      await api.tasks.patch(taskId, { status });
      await loadProjectData();
      renderBoard();
    });
    board.appendChild(col);
  });
  panel.appendChild(board);
}

function renderTaskCard(task) {
  const card = document.createElement("div");
  card.className = "task-card";
  card.draggable = true;
  card.addEventListener("dragstart", e => e.dataTransfer.setData("text/task-id", task.id));
  card.addEventListener("click", () => openTaskModal(task.id));

  const assignee = userById(task.assignee_id);
  const overdue = task.due_date && new Date(task.due_date) < new Date() && task.status !== (projectById(state.currentProjectId).statuses.slice(-1)[0]);

  card.innerHTML = `
    <div class="title">${escapeHtml(task.title)}</div>
    <div class="tags">${(task.tags || []).map(t => `<span class="tag-chip">${escapeHtml(t)}</span>`).join("")}</div>
    <div class="meta-row">
      <div style="display:flex;gap:6px;align-items:center;">
        <span class="priority-chip priority-${task.priority}">${task.priority}</span>
        ${task.due_date ? `<span class="due-chip ${overdue ? "overdue" : ""}">📅 ${fmtDateHuman(task.due_date)}</span>` : ""}
        ${task.gcal_event_id ? `<span title="Sincronizado con Google Calendar">🔗</span>` : ""}
      </div>
      ${assignee ? `<span class="avatar" style="background:${assignee.color}" title="${escapeHtml(assignee.name)}">${initials(assignee.name)}</span>` : ""}
    </div>`;
  return card;
}

// ---------- TIMELINE ----------
const TL_DAY_WIDTH = 32;

function tlDayIndexFromOffset(offsetPx) {
  return Math.floor(offsetPx / TL_DAY_WIDTH);
}
function tlAddDays(date, days) {
  const d = parseAnyDate(date); d.setDate(d.getDate() + days); return d;
}

function renderTimeline() {
  const panel = $("#panel-timeline");
  panel.innerHTML = "";
  const dated = state.tasks.filter(t => t.start_date || t.due_date);
  const undated = state.tasks.filter(t => !t.start_date && !t.due_date);

  let minDate, maxDate;
  const today = new Date(); today.setHours(0, 0, 0, 0);
  if (dated.length) {
    const dates = dated.flatMap(t => [t.start_date, t.due_date].filter(Boolean).map(d => parseAnyDate(d)));
    minDate = new Date(Math.min(...dates, today));
    maxDate = new Date(Math.max(...dates, today));
  } else {
    minDate = new Date(today);
    maxDate = new Date(today);
  }
  minDate.setDate(minDate.getDate() - 3);
  maxDate.setDate(maxDate.getDate() + 14);
  let totalDays = Math.round((maxDate - minDate) / 86400000) + 1;
  if (totalDays > 220) totalDays = 220;
  const dayWidth = TL_DAY_WIDTH;
  const trackWidth = totalDays * dayWidth;

  const wrap = document.createElement("div");
  wrap.className = "timeline-wrap";

  const header = document.createElement("div");
  header.className = "timeline-header";
  header.innerHTML = `<div class="timeline-row-label"></div>`;
  const headerTrack = document.createElement("div");
  headerTrack.style.display = "flex";
  for (let i = 0; i < totalDays; i++) {
    const d = tlAddDays(minDate, i);
    const cell = document.createElement("div");
    cell.className = "timeline-day" + (d.toDateString() === today.toDateString() ? " today" : "");
    cell.style.minWidth = dayWidth + "px";
    cell.textContent = d.getDate() + "/" + (d.getMonth() + 1);
    headerTrack.appendChild(cell);
  }
  header.appendChild(headerTrack);
  wrap.appendChild(header);

  const hint = document.createElement("p");
  hint.className = "hint";
  hint.style.cssText = "padding:8px 0;";
  hint.textContent = "Arrastra sobre una fila para crear o fijar fechas · arrastra una barra para moverla · arrastra sus bordes para ajustar el rango · doble clic para editar.";
  wrap.appendChild(hint);

  state.taskLists.forEach(list => {
    const tasksInList = state.tasks.filter(t => t.task_list_id === list.id);
    if (!tasksInList.length) return;
    const listHeader = document.createElement("div");
    listHeader.style.cssText = "font-size:12px;font-weight:600;color:var(--text-1);margin:10px 0 4px 0;";
    listHeader.textContent = list.name;
    wrap.appendChild(listHeader);

    tasksInList.forEach(t => {
      const row = document.createElement("div");
      row.className = "timeline-row";
      row.innerHTML = `<div class="timeline-row-label">${escapeHtml(t.title)}</div>
        <div class="timeline-track" style="width:${trackWidth}px;"></div>`;
      const track = row.querySelector(".timeline-track");

      if (t.start_date || t.due_date) {
        track.appendChild(buildTimelineBar(t, minDate, dayWidth));
      } else {
        // No dates yet: dragging on this row's track sets its start/due directly.
        attachTrackCreateDrag(track, minDate, dayWidth, async (startDate, dueDate) => {
          await api.tasks.patch(t.id, { start_date: fmtDate(startDate), due_date: fmtDate(dueDate) });
          await loadProjectData();
          renderTimeline();
        });
      }
      wrap.appendChild(row);
    });

    // Extra blank row to create brand-new tasks in this list by dragging.
    const newRow = document.createElement("div");
    newRow.className = "timeline-row timeline-row-new";
    newRow.innerHTML = `<div class="timeline-row-label">+ Nueva tarea</div>
      <div class="timeline-track" style="width:${trackWidth}px;"></div>`;
    attachTrackCreateDrag(newRow.querySelector(".timeline-track"), minDate, dayWidth, (startDate, dueDate) => {
      openNewTaskModal({ start_date: fmtDate(startDate), due_date: fmtDate(dueDate), task_list_id: list.id });
    });
    wrap.appendChild(newRow);
  });

  if (!state.taskLists.some(l => state.tasks.some(t => t.task_list_id === l.id))) {
    const empty = document.createElement("p");
    empty.className = "hint";
    empty.textContent = "Todavía no hay tareas. Crea una desde el tablero o arrastra en la fila \"+ Nueva tarea\" de una lista.";
    wrap.appendChild(empty);
  }

  panel.appendChild(wrap);
}

function buildTimelineBar(t, minDate, dayWidth) {
  const start = parseAnyDate(t.start_date || t.due_date);
  const end = parseAnyDate(t.due_date || t.start_date);
  const left = Math.round((start - minDate) / 86400000) * dayWidth;
  const width = Math.max(1, Math.round((end - start) / 86400000) + 1) * dayWidth - 4;
  const assignee = userById(t.assignee_id);

  const bar = document.createElement("div");
  bar.className = "timeline-bar";
  bar.style.left = left + "px";
  bar.style.width = width + "px";
  bar.style.background = assignee ? assignee.color : "#6c5ce7";
  bar.title = "Arrastra para mover · bordes para ajustar · doble clic para editar";
  bar.innerHTML = `<div class="tl-handle tl-handle-left"></div><span class="tl-bar-label">${escapeHtml(t.title)}</span><div class="tl-handle tl-handle-right"></div>`;

  bar.addEventListener("dblclick", e => { e.stopPropagation(); openTaskModal(t.id); });

  attachTimelineBarDrag(bar, t, minDate, dayWidth);
  return bar;
}

// Generic pointer-drag: move whole bar, or resize from either edge, snapped to whole days.
function attachTimelineBarDrag(bar, task, minDate, dayWidth) {
  function startDrag(mode) {
    return e => {
      e.preventDefault();
      e.stopPropagation();
      const startX = e.clientX;
      const origLeft = parseFloat(bar.style.left);
      const origWidth = parseFloat(bar.style.width);
      document.body.classList.add("tl-dragging");
      let deltaDays = 0;

      function onMove(ev) {
        const deltaPx = ev.clientX - startX;
        deltaDays = Math.round(deltaPx / dayWidth);
        if (mode === "move") {
          bar.style.left = (origLeft + deltaDays * dayWidth) + "px";
        } else if (mode === "left") {
          const maxDelta = Math.round((origWidth - dayWidth) / dayWidth);
          const d = Math.min(Math.max(deltaDays, -9999), maxDelta);
          bar.style.left = (origLeft + d * dayWidth) + "px";
          bar.style.width = (origWidth - d * dayWidth) + "px";
          deltaDays = d;
        } else if (mode === "right") {
          const minDelta = -Math.round((origWidth - dayWidth) / dayWidth);
          const d = Math.max(deltaDays, minDelta);
          bar.style.width = (origWidth + d * dayWidth) + "px";
          deltaDays = d;
        }
      }
      async function onUp() {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.body.classList.remove("tl-dragging");
        if (deltaDays === 0) return;
        const patch = {};
        if (mode === "move") {
          if (task.start_date) patch.start_date = fmtDate(tlAddDays(task.start_date, deltaDays));
          if (task.due_date) patch.due_date = fmtDate(tlAddDays(task.due_date, deltaDays));
        } else if (mode === "left") {
          patch.start_date = fmtDate(tlAddDays(task.start_date || task.due_date, deltaDays));
        } else if (mode === "right") {
          patch.due_date = fmtDate(tlAddDays(task.due_date || task.start_date, deltaDays));
        }
        await api.tasks.patch(task.id, patch);
        await loadProjectData();
        renderTimeline();
      }
      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
    };
  }

  bar.querySelector(".tl-handle-left").addEventListener("mousedown", startDrag("left"));
  bar.querySelector(".tl-handle-right").addEventListener("mousedown", startDrag("right"));
  bar.addEventListener("mousedown", e => {
    if (e.target.classList.contains("tl-handle")) return;
    startDrag("move")(e);
  });
}

// Drag-to-select a date range on an empty track; calls onCreate(startDate, dueDate) on release.
function attachTrackCreateDrag(track, minDate, dayWidth, onCreate) {
  track.addEventListener("mousedown", e => {
    if (e.target !== track) return;
    e.preventDefault();
    const rect = track.getBoundingClientRect();
    const startDay = tlDayIndexFromOffset(e.clientX - rect.left);
    let currentDay = startDay;
    document.body.classList.add("tl-dragging");

    const ghost = document.createElement("div");
    ghost.className = "timeline-bar timeline-ghost";
    ghost.style.left = (startDay * dayWidth) + "px";
    ghost.style.width = (dayWidth - 4) + "px";
    track.appendChild(ghost);

    function onMove(ev) {
      currentDay = tlDayIndexFromOffset(ev.clientX - rect.left);
      const lo = Math.min(startDay, currentDay), hi = Math.max(startDay, currentDay);
      ghost.style.left = (lo * dayWidth) + "px";
      ghost.style.width = ((hi - lo + 1) * dayWidth - 4) + "px";
    }
    function onUp() {
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
      document.body.classList.remove("tl-dragging");
      ghost.remove();
      const lo = Math.min(startDay, currentDay), hi = Math.max(startDay, currentDay);
      onCreate(tlAddDays(minDate, lo), tlAddDays(minDate, hi));
    }
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  });
}

// ---------- CALENDAR (Google Calendar / iCal-style month view: bars span start->due) ----------
function renderCalendar() {
  const panel = $("#panel-calendar");
  panel.innerHTML = "";

  const toolbar = document.createElement("div");
  toolbar.className = "calendar-toolbar";
  const monthLabel = state.calendarMonth.toLocaleDateString("es-ES", { month: "long", year: "numeric" });
  toolbar.innerHTML = `
    <button class="btn btn-ghost" id="cal-prev">‹</button>
    <strong style="text-transform:capitalize;">${monthLabel}</strong>
    <button class="btn btn-ghost" id="cal-next">›</button>
    <button class="btn btn-ghost" id="cal-today">Hoy</button>`;
  panel.appendChild(toolbar);
  toolbar.querySelector("#cal-prev").addEventListener("click", () => { state.calendarMonth.setMonth(state.calendarMonth.getMonth() - 1); renderCalendar(); });
  toolbar.querySelector("#cal-next").addEventListener("click", () => { state.calendarMonth.setMonth(state.calendarMonth.getMonth() + 1); renderCalendar(); });
  toolbar.querySelector("#cal-today").addEventListener("click", () => { state.calendarMonth = startOfMonth(new Date()); renderCalendar(); });

  const wrap = document.createElement("div");
  wrap.className = "calendar-grid-wrap";

  const dow = document.createElement("div");
  dow.className = "calendar-dow-row";
  ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"].forEach(d => {
    const el = document.createElement("div"); el.className = "calendar-dow"; el.textContent = d; dow.appendChild(el);
  });
  wrap.appendChild(dow);

  const first = startOfMonth(state.calendarMonth);
  const firstWeekday = (first.getDay() + 6) % 7; // Monday = 0
  const gridStart = tlAddDays(first, -firstWeekday);
  const today = new Date(); today.setHours(0, 0, 0, 0);

  const dated = state.tasks
    .filter(t => t.start_date || t.due_date)
    .map(t => ({
      task: t,
      start: parseAnyDate(t.start_date || t.due_date),
      end: parseAnyDate(t.due_date || t.start_date),
    }));

  for (let w = 0; w < 6; w++) {
    const weekStart = tlAddDays(gridStart, w * 7);
    const dayDates = Array.from({ length: 7 }, (_, i) => tlAddDays(weekStart, i));
    const weekEnd = dayDates[6];

    const weekEl = document.createElement("div");
    weekEl.className = "calendar-week";

    const daysRow = document.createElement("div");
    daysRow.className = "calendar-days-row";
    dayDates.forEach(d => {
      const cell = document.createElement("div");
      cell.className = "calendar-cell";
      if (d.getMonth() !== state.calendarMonth.getMonth()) cell.classList.add("other-month");
      if (d.toDateString() === today.toDateString()) cell.classList.add("today");
      cell.innerHTML = `<div class="day-num">${d.getDate()}</div>`;
      daysRow.appendChild(cell);
    });
    weekEl.appendChild(daysRow);

    const barsLayer = document.createElement("div");
    barsLayer.className = "calendar-bars-layer";
    weekEl.appendChild(barsLayer);

    const items = dated
      .filter(x => x.end >= weekStart && x.start <= weekEnd)
      .map(x => {
        const clampedStart = x.start < weekStart ? weekStart : x.start;
        const clampedEnd = x.end > weekEnd ? weekEnd : x.end;
        return {
          ...x,
          colStart: Math.round((clampedStart - weekStart) / 86400000),
          colEnd: Math.round((clampedEnd - weekStart) / 86400000),
          continuesBefore: x.start < weekStart,
          continuesAfter: x.end > weekEnd,
        };
      })
      .sort((a, b) => a.colStart - b.colStart || (b.colEnd - b.colStart) - (a.colEnd - a.colStart));

    const laneEnds = [];
    items.forEach(item => {
      let lane = laneEnds.findIndex(end => end < item.colStart);
      if (lane === -1) { lane = laneEnds.length; laneEnds.push(item.colEnd); }
      else laneEnds[lane] = item.colEnd;
      item.lane = lane;
    });
    const laneCount = Math.max(1, laneEnds.length);
    weekEl.style.minHeight = (26 + laneCount * 20 + 6) + "px";

    items.forEach(item => barsLayer.appendChild(buildCalendarBar(item)));

    attachWeekInteractions(weekEl, dayDates);
    wrap.appendChild(weekEl);
  }

  panel.appendChild(wrap);
}

function buildCalendarBar(item) {
  const { task, lane, colStart, colEnd, continuesBefore, continuesAfter } = item;
  const assignee = userById(task.assignee_id);
  const bar = document.createElement("div");
  bar.className = "calendar-bar";
  if (continuesBefore) bar.classList.add("continues-before");
  if (continuesAfter) bar.classList.add("continues-after");
  bar.style.left = (colStart / 7 * 100) + "%";
  bar.style.width = ((colEnd - colStart + 1) / 7 * 100) + "%";
  bar.style.top = (lane * 20) + "px";
  bar.style.background = assignee ? assignee.color : "#6c5ce7";
  bar.draggable = true;
  bar.title = "Arrastra para mover · doble clic para editar";
  bar.textContent = (continuesBefore ? "◂ " : "") + (task.gcal_event_id ? "🔗 " : "") + task.title + (continuesAfter ? " ▸" : "");

  bar.addEventListener("dragstart", e => {
    e.dataTransfer.setData("text/task-id", task.id);
    e.stopPropagation();
    setTimeout(() => bar.classList.add("dragging"), 0);
  });
  bar.addEventListener("dragend", () => bar.classList.remove("dragging"));
  bar.addEventListener("dblclick", e => { e.stopPropagation(); openTaskModal(task.id); });
  return bar;
}

// Drag-over/drop/dblclick are handled once per week row (not per day cell): the target
// day is derived from the pointer's X position, which works no matter whether the
// pointer is over the day-number grid or the bars overlay sitting on top of it.
function attachWeekInteractions(weekEl, dayDates) {
  function colFromEvent(e) {
    const rect = weekEl.getBoundingClientRect();
    const relX = e.clientX - rect.left;
    return Math.min(6, Math.max(0, Math.floor(relX / (rect.width / 7))));
  }

  weekEl.addEventListener("dblclick", e => {
    if (e.target.closest(".calendar-bar")) return;
    const dayKey = fmtDate(dayDates[colFromEvent(e)]);
    openNewTaskModal({ due_date: dayKey });
  });

  weekEl.addEventListener("dragover", e => { e.preventDefault(); weekEl.classList.add("drag-over"); });
  weekEl.addEventListener("dragleave", () => weekEl.classList.remove("drag-over"));
  weekEl.addEventListener("drop", async e => {
    e.preventDefault();
    weekEl.classList.remove("drag-over");
    const taskId = e.dataTransfer.getData("text/task-id");
    const task = state.tasks.find(t => t.id === taskId);
    if (!task || (!task.due_date && !task.start_date)) return;
    const dayKey = fmtDate(dayDates[colFromEvent(e)]);
    const anchor = parseAnyDate(task.due_date || task.start_date);
    const deltaDays = Math.round((parseAnyDate(dayKey) - anchor) / 86400000);
    if (deltaDays === 0) return;
    const payload = {};
    if (task.due_date) payload.due_date = fmtDate(tlAddDays(task.due_date, deltaDays));
    if (task.start_date) payload.start_date = fmtDate(tlAddDays(task.start_date, deltaDays));
    await api.tasks.patch(taskId, payload);
    await loadProjectData();
    renderCalendar();
    toast("Tarea movida al " + fmtDateHuman(dayKey));
  });
}

// ---------- FILES ----------
const IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"];
const VIDEO_EXTS = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".mxf"];
const STATUS_COLORS = { "Por hacer": "#636e72", "En progreso": "#0984e3", "Revisión": "#f2994a", "Hecho": "#2ecc71" };

function statusColor(status) { return STATUS_COLORS[status] || "#636e72"; }

async function renderFiles(selectRelPath) {
  const panel = $("#panel-files");
  panel.className = "tab-panel files-mode";
  panel.innerHTML = `
    <div class="files-tree" id="files-tree">Cargando árbol…</div>
    <div class="files-main">
      <div class="file-toolbar">
        <div class="breadcrumb" id="file-breadcrumb"></div>
        <button class="btn btn-secondary" id="btn-new-folder">+ Carpeta</button>
      </div>
      <div id="file-table-wrap">Cargando…</div>
    </div>
    <div class="files-preview" id="files-preview"><p class="hint">Selecciona un archivo o carpeta para ver los detalles.</p></div>`;

  $("#btn-new-folder").addEventListener("click", openNewFolderModal);

  if (!state.filesTree) {
    try { state.filesTree = await api.files.tree(state.currentProjectId); }
    catch (e) { state.filesTree = { children: [], truncated: false }; }
  }
  renderFileTree();
  await renderFileTable(selectRelPath);
}

// ---- Tree (always expanded by default, like a professional asset browser) ----
function renderFileTree() {
  const el = $("#files-tree");
  el.innerHTML = "";
  const project = projectById(state.currentProjectId);

  const rootRow = buildTreeRow(`🗂️ ${project.name}`, "", 0, null);
  el.appendChild(rootRow);

  const childWrap = document.createElement("div");
  (state.filesTree.children || []).forEach(child => childWrap.appendChild(buildTreeNode(child, 1)));
  el.appendChild(childWrap);

  if (state.filesTree.truncated) {
    const note = document.createElement("p");
    note.className = "hint";
    note.style.padding = "6px 10px";
    note.textContent = "Árbol muy grande: se truncó la vista.";
    el.appendChild(note);
  }
}

function buildTreeNode(node, depth) {
  const wrap = document.createElement("div");
  const hasChildren = node.children && node.children.length > 0;
  const collapsed = state.collapsedFolders.has(node.rel_path);

  const row = buildTreeRow(node.name, node.rel_path, depth, node.color, hasChildren, collapsed);
  wrap.appendChild(row);

  if (hasChildren) {
    const childWrap = document.createElement("div");
    childWrap.className = "tree-children" + (collapsed ? " hidden" : "");
    node.children.forEach(c => childWrap.appendChild(buildTreeNode(c, depth + 1)));
    wrap.appendChild(childWrap);

    row.querySelector(".tree-toggle").addEventListener("click", e => {
      e.stopPropagation();
      if (state.collapsedFolders.has(node.rel_path)) state.collapsedFolders.delete(node.rel_path);
      else state.collapsedFolders.add(node.rel_path);
      childWrap.classList.toggle("hidden");
      row.querySelector(".tree-toggle").textContent = state.collapsedFolders.has(node.rel_path) ? "▸" : "▾";
    });
  }
  return wrap;
}

function buildTreeRow(name, relPath, depth, color, hasChildren, collapsed) {
  const row = document.createElement("div");
  row.className = "tree-row" + (relPath === state.filesPath ? " active" : "");
  row.style.paddingLeft = (10 + depth * 14) + "px";
  row.innerHTML = `
    <span class="tree-toggle">${hasChildren ? (collapsed ? "▸" : "▾") : ""}</span>
    <span class="tree-dot" style="background:${color || "transparent"};border-color:${color || "var(--text-2)"}"></span>
    <span class="tree-name">${escapeHtml(name)}</span>`;
  row.addEventListener("click", () => { state.filesPath = relPath; renderFileTree(); renderFileTable(); });
  return row;
}

// ---- Breadcrumb ----
function renderBreadcrumb(relPath) {
  const el = $("#file-breadcrumb");
  el.innerHTML = "";
  const project = projectById(state.currentProjectId);
  const root = document.createElement("span");
  root.textContent = `📁 ${project.name}`;
  root.addEventListener("click", () => { state.filesPath = ""; renderFileTree(); renderFileTable(); });
  el.appendChild(root);
  if (!relPath) return;
  const parts = relPath.split("/");
  let accum = "";
  parts.forEach(part => {
    accum = accum ? `${accum}/${part}` : part;
    const sep = document.createElement("span"); sep.textContent = " / "; sep.style.cursor = "default"; el.appendChild(sep);
    const span = document.createElement("span");
    span.textContent = part;
    const target = accum;
    span.addEventListener("click", () => { state.filesPath = target; renderFileTree(); renderFileTable(); });
    el.appendChild(span);
  });
}

// ---- Main table ----
async function renderFileTable(selectRelPath) {
  renderBreadcrumb(state.filesPath);
  const wrap = $("#file-table-wrap");
  wrap.innerHTML = "Cargando…";
  let data;
  try {
    data = await api.files.browse(state.currentProjectId, state.filesPath);
  } catch (e) {
    wrap.innerHTML = `<p class="hint">${escapeHtml(e.message)}</p>`;
    return;
  }
  if (!data.entries.length) {
    wrap.innerHTML = `<p class="hint">Carpeta vacía. Usa "+ Carpeta" para crear una subcarpeta aquí.</p>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "file-table";
  table.innerHTML = `<thead><tr>
      <th>Nombre</th><th>Estado</th><th>Asignado</th><th>Etiquetas</th><th>Modificado</th><th>Tamaño</th>
    </tr></thead>`;
  const tbody = document.createElement("tbody");
  data.entries.forEach(entry => tbody.appendChild(buildFileRow(entry)));
  table.appendChild(tbody);
  wrap.innerHTML = "";
  wrap.appendChild(table);

  if (selectRelPath) {
    const target = data.entries.find(e => e.rel_path === selectRelPath);
    if (target) {
      state.selectedEntry = target;
      renderFilePreview(target);
      $$(".file-table tbody tr").forEach(r => r.classList.remove("selected"));
      const idx = data.entries.indexOf(target);
      tbody.children[idx]?.classList.add("selected");
    }
  }
}

function buildFileRow(entry) {
  const project = projectById(state.currentProjectId);
  const tr = document.createElement("tr");
  tr.className = entry.is_dir ? "row-folder" : "row-file";
  if (state.selectedEntry && state.selectedEntry.rel_path === entry.rel_path) tr.classList.add("selected");

  // Name cell (with folder color swatch + icon + rename)
  const nameTd = document.createElement("td");
  nameTd.className = "cell-name";
  if (entry.is_dir) {
    const colorLabel = document.createElement("label");
    colorLabel.className = "folder-color-dot";
    colorLabel.style.background = entry.meta.color || "transparent";
    colorLabel.title = "Color de carpeta";
    const colorInput = document.createElement("input");
    colorInput.type = "color";
    colorInput.value = entry.meta.color || "#3B82F6";
    colorInput.addEventListener("click", e => e.stopPropagation());
    colorInput.addEventListener("input", async e => {
      await api.files.patchMeta(state.currentProjectId, entry.rel_path, { color: e.target.value });
      colorLabel.style.background = e.target.value;
      invalidateFileTree();
    });
    colorLabel.appendChild(colorInput);
    nameTd.appendChild(colorLabel);
    nameTd.insertAdjacentHTML("beforeend", " 📁 ");
  } else {
    nameTd.insertAdjacentHTML("beforeend", fileIcon(entry.ext) + " ");
  }
  const nameSpan = document.createElement("span");
  nameSpan.className = "name-text";
  nameSpan.textContent = (entry.lock ? "🔒 " : "") + (entry.meta.starred ? "⭐ " : "") + entry.name;
  if (entry.lock) nameSpan.title = "Bloqueado por " + ((userById(entry.lock.user_id) || {}).name || "otro usuario");
  nameTd.appendChild(nameSpan);

  const renameBtn = document.createElement("span");
  renameBtn.className = "rename-btn";
  renameBtn.textContent = "✏️";
  renameBtn.title = "Renombrar";
  renameBtn.addEventListener("click", e => { e.stopPropagation(); startInlineRename(nameTd, nameSpan, entry); });
  nameTd.appendChild(renameBtn);
  tr.appendChild(nameTd);

  // Status
  const statusTd = document.createElement("td");
  const statusSel = document.createElement("select");
  statusSel.innerHTML = `<option value="">Sin estado</option>` + project.statuses.map(s => `<option value="${escapeHtml(s)}" ${entry.meta.status === s ? "selected" : ""}>${escapeHtml(s)}</option>`).join("");
  statusSel.style.color = statusColor(entry.meta.status);
  statusSel.addEventListener("click", e => e.stopPropagation());
  statusSel.addEventListener("change", async () => {
    await api.files.patchMeta(state.currentProjectId, entry.rel_path, { status: statusSel.value || null });
    entry.meta.status = statusSel.value || null;
    statusSel.style.color = statusColor(entry.meta.status);
    if (state.selectedEntry && state.selectedEntry.rel_path === entry.rel_path) renderFilePreview(entry);
  });
  statusTd.appendChild(statusSel);
  tr.appendChild(statusTd);

  // Assignee
  const assigneeTd = document.createElement("td");
  const assigneeSel = document.createElement("select");
  assigneeSel.innerHTML = `<option value="">Sin asignar</option>` + state.users.map(u => `<option value="${u.id}" ${entry.meta.assignee_id === u.id ? "selected" : ""}>${escapeHtml(u.name)}</option>`).join("");
  assigneeSel.addEventListener("click", e => e.stopPropagation());
  assigneeSel.addEventListener("change", async () => {
    await api.files.patchMeta(state.currentProjectId, entry.rel_path, { assignee_id: assigneeSel.value || null });
    entry.meta.assignee_id = assigneeSel.value || null;
    if (state.selectedEntry && state.selectedEntry.rel_path === entry.rel_path) renderFilePreview(entry);
  });
  assigneeTd.appendChild(assigneeSel);
  tr.appendChild(assigneeTd);

  // Tags (click to edit inline)
  const tagsTd = document.createElement("td");
  tagsTd.className = "cell-tags";
  renderTagsCell(tagsTd, entry);
  tr.appendChild(tagsTd);

  // Modified / size
  const modTd = document.createElement("td");
  modTd.className = "hint";
  modTd.textContent = entry.mtime ? new Date(entry.mtime * 1000).toLocaleDateString("es-ES") : "—";
  tr.appendChild(modTd);

  const sizeTd = document.createElement("td");
  sizeTd.className = "hint";
  sizeTd.textContent = entry.is_dir ? "—" : fmtSize(entry.size);
  tr.appendChild(sizeTd);

  tr.addEventListener("click", () => {
    state.selectedEntry = entry;
    renderFilePreview(entry);
    $$(".file-table tbody tr").forEach(r => r.classList.remove("selected"));
    tr.classList.add("selected");
  });
  tr.addEventListener("dblclick", () => {
    if (entry.is_dir) { state.filesPath = entry.rel_path; renderFileTree(); renderFileTable(); }
    else openAssetModal(entry.rel_path, entry.name);
  });
  return tr;
}

function renderTagsCell(td, entry) {
  td.innerHTML = "";
  (entry.meta.tags || []).forEach(t => {
    const chip = document.createElement("span");
    chip.className = "tag-chip";
    chip.textContent = t;
    td.appendChild(chip);
  });
  const addBtn = document.createElement("span");
  addBtn.className = "tag-add-btn";
  addBtn.textContent = "+";
  addBtn.title = "Editar etiquetas";
  addBtn.addEventListener("click", e => {
    e.stopPropagation();
    const input = document.createElement("input");
    input.type = "text";
    input.className = "tag-inline-input";
    input.value = (entry.meta.tags || []).join(", ");
    input.placeholder = "etiqueta1, etiqueta2";
    td.innerHTML = "";
    td.appendChild(input);
    input.focus();
    async function commit() {
      const tags = input.value.split(",").map(s => s.trim()).filter(Boolean);
      await api.files.patchMeta(state.currentProjectId, entry.rel_path, { tags });
      entry.meta.tags = tags;
      renderTagsCell(td, entry);
      if (state.selectedEntry && state.selectedEntry.rel_path === entry.rel_path) renderFilePreview(entry);
    }
    input.addEventListener("keydown", e2 => { if (e2.key === "Enter") input.blur(); });
    input.addEventListener("blur", commit);
  });
  td.appendChild(addBtn);
}

// Turns a name span into an inline text input; commits the rename on Enter/blur.
function startInlineRename(container, nameSpan, entry) {
  const input = document.createElement("input");
  input.type = "text";
  input.className = "rename-inline-input";
  input.value = entry.name;
  nameSpan.replaceWith(input);
  input.focus();
  input.select();

  let done = false;
  async function commit() {
    if (done) return;
    done = true;
    const newName = input.value.trim();
    if (!newName || newName === entry.name) {
      input.replaceWith(nameSpan);
      return;
    }
    try {
      const res = await api.files.rename(state.currentProjectId, entry.rel_path, newName);
      entry.name = newName;
      entry.rel_path = res.rel_path;
      invalidateFileTree();
      await renderFileTable();
      if (state.selectedEntry && state.selectedEntry.rel_path === entry.rel_path) renderFilePreview(entry);
      toast("Renombrado a \"" + newName + "\"");
    } catch (e) {
      toast(e.message, true);
      input.replaceWith(nameSpan);
    }
  }
  input.addEventListener("keydown", e => {
    if (e.key === "Enter") input.blur();
    if (e.key === "Escape") { done = true; input.replaceWith(nameSpan); }
  });
  input.addEventListener("blur", commit);
  input.addEventListener("click", e => e.stopPropagation());
}

function fileIcon(ext) {
  if (IMAGE_EXTS.includes(ext)) return "🖼️";
  if (VIDEO_EXTS.includes(ext)) return "🎞️";
  if ([".c4d", ".blend", ".fbx", ".obj", ".glb", ".gltf", ".usd", ".ma", ".mb"].includes(ext)) return "🧊";
  if ([".psd", ".ai", ".xd"].includes(ext)) return "🎨";
  if ([".aep", ".prproj", ".drp"].includes(ext)) return "🎬";
  if ([".pdf"].includes(ext)) return "📕";
  if ([".wav", ".mp3"].includes(ext)) return "🎵";
  return "📄";
}

function fmtSize(bytes) {
  if (bytes == null) return "—";
  if (bytes < 1024) return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  if (bytes < 1024 * 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return (bytes / 1024 / 1024 / 1024).toFixed(2) + " GB";
}

function invalidateFileTree() {
  state.filesTree = null;
  api.files.tree(state.currentProjectId).then(tree => { state.filesTree = tree; renderFileTree(); });
}

function dirnameOf(relPath) {
  const idx = relPath.lastIndexOf("/");
  return idx === -1 ? "" : relPath.slice(0, idx);
}

// Opens the given project (switching if needed), navigates the Files tab to the
// containing folder, and selects the target file/folder - used by "Ir al archivo"
// links from the inbox and by the send-link flow's own confirmation.
async function navigateToFile(projectId, relPath) {
  if (state.currentProjectId !== projectId) await selectProject(projectId);
  state.filesPath = dirnameOf(relPath);
  await switchTab("files", relPath);
}

// ---- Preview panel ----
function renderFilePreview(entry) {
  const el = $("#files-preview");
  const project = projectById(state.currentProjectId);
  el.innerHTML = "";

  const previewArea = document.createElement("div");
  if (!entry.is_dir && (IMAGE_EXTS.includes(entry.ext) || VIDEO_EXTS.includes(entry.ext))) {
    previewArea.innerHTML = `<img class="asset-preview" src="${api.files.thumbnailUrl(state.currentProjectId, entry.rel_path)}">`;
  } else {
    previewArea.innerHTML = `<div class="preview-big-icon">${entry.is_dir ? "📁" : fileIcon(entry.ext)}</div>`;
  }
  el.appendChild(previewArea);

  const titleRow = document.createElement("div");
  titleRow.style.cssText = "display:flex;align-items:center;gap:6px;margin-top:8px;";
  const title = document.createElement("h3");
  title.style.cssText = "margin:0;font-size:14px;word-break:break-all;flex:1;";
  title.textContent = entry.name;
  const renameBtn = document.createElement("span");
  renameBtn.className = "rename-btn";
  renameBtn.textContent = "✏️";
  renameBtn.title = "Renombrar";
  renameBtn.addEventListener("click", () => startInlineRename(titleRow, title, entry));
  titleRow.appendChild(title);
  titleRow.appendChild(renameBtn);
  el.appendChild(titleRow);

  const meta = document.createElement("p");
  meta.className = "hint";
  meta.textContent = entry.is_dir ? "Carpeta" : `${fmtSize(entry.size)} · ${entry.mtime ? new Date(entry.mtime * 1000).toLocaleString("es-ES") : ""}`;
  el.appendChild(meta);

  {
    const me = state.currentUserId;
    const lockRow = document.createElement("div");
    lockRow.style.cssText = "display:flex;align-items:center;gap:8px;margin:6px 0;";
    const owner = entry.lock && userById(entry.lock.user_id);
    const mine = entry.lock && entry.lock.user_id === me;
    const lbl = document.createElement("span");
    lbl.className = "hint";
    lbl.textContent = entry.lock ? (mine ? "🔒 Bloqueado por ti" : `🔒 Bloqueado por ${owner ? owner.name : "otro usuario"}`) : "Libre";
    const btn = document.createElement("button");
    btn.className = "btn btn-secondary";
    btn.textContent = entry.lock ? (mine ? "Desbloquear" : "Forzar desbloqueo") : "Bloquear";
    btn.addEventListener("click", async () => {
      try {
        if (entry.lock) await api.locks.unlock(state.currentProjectId, entry.rel_path);
        else await api.locks.lock(state.currentProjectId, entry.rel_path);
        await renderFileTable(entry.rel_path);
      } catch (e) { toast(e.message, true); }
    });
    lockRow.appendChild(lbl);
    lockRow.appendChild(btn);
    el.appendChild(lockRow);
    if (!entry.is_dir) {
      const vb = document.createElement("button");
      vb.className = "btn btn-secondary btn-block";
      vb.textContent = "📜 Versiones";
      vb.addEventListener("click", () => openVersions(entry));
      el.appendChild(vb);
    }
  }

  if (entry.meta.tags && entry.meta.tags.length) {
    const tagsRow = document.createElement("div");
    tagsRow.className = "tags";
    tagsRow.style.margin = "6px 0";
    entry.meta.tags.forEach(t => tagsRow.insertAdjacentHTML("beforeend", `<span class="tag-chip">${escapeHtml(t)}</span>`));
    el.appendChild(tagsRow);
  }

  const actions = document.createElement("div");
  actions.style.cssText = "display:flex;flex-direction:column;gap:6px;margin-top:10px;";
  if (entry.is_dir) {
    const openFolderBtn = document.createElement("button");
    openFolderBtn.className = "btn btn-primary btn-block";
    openFolderBtn.textContent = "Abrir carpeta";
    openFolderBtn.addEventListener("click", () => { state.filesPath = entry.rel_path; renderFileTree(); renderFileTable(); });
    actions.appendChild(openFolderBtn);
  } else {
    const openBtn = document.createElement("button");
    openBtn.className = "btn btn-primary btn-block";
    openBtn.textContent = "Abrir archivo";
    openBtn.addEventListener("click", async () => { try { await api.files.openFile(state.currentProjectId, entry.rel_path, false); } catch (e) { toast(e.message, true); } });
    actions.appendChild(openBtn);
  }
  const detailsBtn = document.createElement("button");
  detailsBtn.className = "btn btn-secondary btn-block";
  detailsBtn.textContent = "💬 Detalles y comentarios";
  detailsBtn.addEventListener("click", () => openAssetModal(entry.rel_path, entry.name));
  actions.appendChild(detailsBtn);
  const sendBtn = document.createElement("button");
  sendBtn.className = "btn btn-secondary btn-block";
  sendBtn.textContent = "📤 Enviar enlace a…";
  sendBtn.addEventListener("click", () => openSendLinkModal(entry));
  actions.appendChild(sendBtn);
  const revealBtn = document.createElement("button");
  revealBtn.className = "btn btn-ghost btn-block";
  revealBtn.textContent = "Mostrar en el explorador de Windows";
  revealBtn.addEventListener("click", async () => { try { await api.files.openFile(state.currentProjectId, entry.rel_path, true); } catch (e) { toast(e.message, true); } });
  actions.appendChild(revealBtn);
  el.appendChild(actions);
}

// ---- New folder modal ----
function openNewFolderModal() {
  $("#nf-name").value = "";
  openModal("#modal-new-folder");
  $("#nf-name").focus();
}

// ---------- TASK MODAL ----------
let editingTaskId = null;

function openNewTaskModal(prefill) {
  prefill = prefill || {};
  editingTaskId = null;
  $("#tk-heading").textContent = "Nueva tarea";
  $("#tk-title").value = "";
  $("#tk-description").value = "";
  $("#tk-priority").value = "Media";
  $("#tk-start").value = prefill.start_date || "";
  $("#tk-due").value = prefill.due_date || "";
  $("#tk-tags").value = "";
  fillTaskStatusOptions();
  fillTaskAssigneeOptions();
  fillTaskListOptions();
  if (prefill.task_list_id) $("#tk-tasklist").value = prefill.task_list_id;
  $("#tk-comments").innerHTML = "";
  $("#tk-gcal-note").textContent = "";
  $("#tk-delete").classList.add("hidden");
  fillCommentAuthorOptions("#tk-comment-author");
  openModal("#modal-task");
  $("#tk-title").focus();
}

async function openTaskModal(taskId) {
  editingTaskId = taskId;
  const task = state.tasks.find(t => t.id === taskId);
  $("#tk-heading").textContent = "Editar tarea";
  $("#tk-title").value = task.title;
  $("#tk-description").value = task.description || "";
  fillTaskStatusOptions(); $("#tk-status").value = task.status;
  $("#tk-priority").value = task.priority;
  fillTaskAssigneeOptions(); $("#tk-assignee").value = task.assignee_id || "";
  fillTaskListOptions(); $("#tk-tasklist").value = task.task_list_id;
  $("#tk-start").value = fmtDate(task.start_date);
  $("#tk-due").value = fmtDate(task.due_date);
  $("#tk-tags").value = (task.tags || []).join(", ");
  $("#tk-delete").classList.remove("hidden");
  $("#tk-gcal-note").textContent = task.gcal_event_id
    ? "🔗 Sincronizada con Google Calendar."
    : (state.gcalConnected ? "Se sincronizará al guardar si tiene fecha de entrega." : "");
  fillCommentAuthorOptions("#tk-comment-author");
  await renderTaskComments(taskId);
  openModal("#modal-task");
}

function fillTaskStatusOptions() {
  const project = projectById(state.currentProjectId);
  const sel = $("#tk-status");
  sel.innerHTML = project.statuses.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
}
function fillTaskAssigneeOptions() {
  const sel = $("#tk-assignee");
  sel.innerHTML = `<option value="">Sin asignar</option>` + state.users.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
}
function fillTaskListOptions() {
  const sel = $("#tk-tasklist");
  sel.innerHTML = state.taskLists.map(l => `<option value="${l.id}">${escapeHtml(l.name)}</option>`).join("");
}
function fillCommentAuthorOptions(sel) {
  $(sel).innerHTML = state.users.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
}

async function renderTaskComments(taskId) {
  const comments = await api.comments.listForTask(taskId);
  const el = $("#tk-comments");
  el.innerHTML = comments.length ? "" : `<p class="hint">Sin comentarios.</p>`;
  comments.forEach(c => {
    const author = userById(c.author_id);
    const div = document.createElement("div");
    div.className = "comment-item";
    div.innerHTML = `<div class="comment-meta">${author ? escapeHtml(author.name) : "?"} · ${new Date(c.created_at).toLocaleString("es-ES")}</div>${escapeHtml(c.body)}`;
    el.appendChild(div);
  });
}

$("#tk-save").addEventListener("click", async () => {
  const payload = {
    title: $("#tk-title").value.trim(),
    description: $("#tk-description").value,
    status: $("#tk-status").value,
    priority: $("#tk-priority").value,
    assignee_id: $("#tk-assignee").value || null,
    tags: $("#tk-tags").value.split(",").map(s => s.trim()).filter(Boolean),
  };
  if (!payload.title) { toast("El título es obligatorio", true); return; }
  const start = $("#tk-start").value;
  const due = $("#tk-due").value;

  try {
    if (editingTaskId) {
      payload.task_list_id = $("#tk-tasklist").value;
      if (start) payload.start_date = start; else payload.clear_start_date = true;
      if (due) payload.due_date = due; else payload.clear_due_date = true;
      if (!payload.assignee_id) payload.clear_assignee = true;
      await api.tasks.patch(editingTaskId, payload);
    } else {
      payload.task_list_id = $("#tk-tasklist").value;
      if (start) payload.start_date = start;
      if (due) payload.due_date = due;
      await api.tasks.create(payload);
    }
    await loadProjectData();
    closeModals();
    switchTab(state.currentTab);
    toast("Tarea guardada");
  } catch (e) { toast(e.message, true); }
});

$("#tk-delete").addEventListener("click", async () => {
  if (!editingTaskId) return;
  if (!confirm("¿Eliminar esta tarea?")) return;
  await api.tasks.remove(editingTaskId);
  await loadProjectData();
  closeModals();
  switchTab(state.currentTab);
  toast("Tarea eliminada");
});

$("#tk-comment-send").addEventListener("click", async () => {
  const body = $("#tk-comment-body").value.trim();
  if (!body || !editingTaskId) return;
  await api.comments.create({ task_id: editingTaskId, author_id: $("#tk-comment-author").value || null, body });
  $("#tk-comment-body").value = "";
  await renderTaskComments(editingTaskId);
});

// ---------- ASSET MODAL ----------
let editingAssetPath = null;

async function openAssetModal(relPath, name) {
  editingAssetPath = relPath;
  $("#asset-heading").textContent = name;
  const ext = "." + name.split(".").pop().toLowerCase();
  $("#asset-preview").src = (IMAGE_EXTS.includes(ext) || VIDEO_EXTS.includes(ext))
    ? api.files.thumbnailUrl(state.currentProjectId, relPath) : "";
  $("#asset-preview").style.display = (IMAGE_EXTS.includes(ext) || VIDEO_EXTS.includes(ext)) ? "block" : "none";

  const sel = $("#asset-assignee");
  sel.innerHTML = `<option value="">Sin asignar</option>` + state.users.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");

  const project = projectById(state.currentProjectId);
  $("#asset-status").innerHTML = `<option value="">Sin estado</option>` + project.statuses.map(s => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");

  const meta = await api.files.getMeta(state.currentProjectId, relPath);
  $("#asset-status").value = meta.status || "";
  $("#asset-assignee").value = meta.assignee_id || "";
  $("#asset-tags").value = (meta.tags || []).join(", ");
  $("#asset-starred").checked = !!meta.starred;
  $("#asset-notes").value = meta.notes || "";

  fillCommentAuthorOptions("#asset-comment-author");
  await renderAssetComments();
  openModal("#modal-asset");
}

async function renderAssetComments() {
  const comments = await api.comments.listForAsset(state.currentProjectId, editingAssetPath);
  const el = $("#asset-comments");
  el.innerHTML = comments.length ? "" : `<p class="hint">Sin comentarios.</p>`;
  comments.forEach(c => {
    const author = userById(c.author_id);
    const div = document.createElement("div");
    div.className = "comment-item";
    div.innerHTML = `<div class="comment-meta">${author ? escapeHtml(author.name) : "?"} · ${new Date(c.created_at).toLocaleString("es-ES")}</div>${escapeHtml(c.body)}`;
    el.appendChild(div);
  });
}

async function saveAssetMeta() {
  await api.files.patchMeta(state.currentProjectId, editingAssetPath, {
    status: $("#asset-status").value || null,
    assignee_id: $("#asset-assignee").value || null,
    tags: $("#asset-tags").value.split(",").map(s => s.trim()).filter(Boolean),
    starred: $("#asset-starred").checked,
    notes: $("#asset-notes").value,
  });
}
["#asset-status", "#asset-assignee", "#asset-tags", "#asset-starred", "#asset-notes"].forEach(sel => {
  $(sel).addEventListener("change", async () => {
    await saveAssetMeta();
    await renderFileTable();
    if (state.selectedEntry && state.selectedEntry.rel_path === editingAssetPath) {
      state.selectedEntry.meta = await api.files.getMeta(state.currentProjectId, editingAssetPath);
      renderFilePreview(state.selectedEntry);
    }
  });
});

$("#asset-open").addEventListener("click", async () => {
  try { await api.files.openFile(state.currentProjectId, editingAssetPath, false); }
  catch (e) { toast(e.message, true); }
});
$("#asset-reveal").addEventListener("click", async () => {
  try { await api.files.openFile(state.currentProjectId, editingAssetPath, true); }
  catch (e) { toast(e.message, true); }
});
$("#asset-comment-send").addEventListener("click", async () => {
  const body = $("#asset-comment-body").value.trim();
  if (!body) return;
  await api.comments.create({ project_id: state.currentProjectId, asset_rel_path: editingAssetPath, author_id: $("#asset-comment-author").value || null, body });
  $("#asset-comment-body").value = "";
  await renderAssetComments();
});

// ---------- NEW PROJECT ----------
function renderStructurePreview() {
  const folders = FOLDER_TEMPLATES_PREVIEW[$("#np-type").value] || FOLDER_TEMPLATES_PREVIEW["Otro"];
  const el = $("#np-structure-preview");
  if ($("#np-structure").checked) {
    el.textContent = "Se crearán: " + folders.join(", ");
  } else {
    el.textContent = "";
  }
}

async function openNewProjectModal() {
  $("#np-name").value = "";
  $("#np-path").value = "";
  $("#np-color").value = "#3B82F6";
  $("#np-structure").checked = true;
  const settings = await api.settings.get();
  const hint = $("#np-dropbox-hint");
  if (settings.detected_dropbox_paths.length) {
    hint.innerHTML = "Carpeta de Dropbox detectada: " + settings.detected_dropbox_paths
      .map(p => `<span class="suggestion" data-path="${escapeHtml(p)}">${escapeHtml(p)}</span>`).join(", ");
    hint.querySelectorAll(".suggestion").forEach(s => s.addEventListener("click", () => { $("#np-path").value = s.dataset.path + "\\"; }));
  } else {
    hint.textContent = "No se detectó Dropbox automáticamente; escribe la ruta completa de la carpeta del proyecto.";
  }
  renderStructurePreview();
  openModal("#modal-new-project");
}

$("#btn-new-project").addEventListener("click", openNewProjectModal);
$("#np-type").addEventListener("change", renderStructurePreview);
$("#np-structure").addEventListener("change", renderStructurePreview);
$("#np-create").addEventListener("click", async () => {
  const name = $("#np-name").value.trim();
  const root_path = $("#np-path").value.trim();
  if (!name || !root_path) { toast("Nombre y carpeta son obligatorios", true); return; }
  try {
    const project = await api.projects.create({
      name, project_type: $("#np-type").value, root_path, color: $("#np-color").value,
      create_structure: $("#np-structure").checked,
    });
    await loadProjects();
    closeModals();
    await selectProject(project.id);
    toast($("#np-structure").checked ? "Proyecto creado con su estructura de carpetas" : "Proyecto creado");
  } catch (e) { toast(e.message, true); }
});

// ---------- VERSIONS ----------
let verEntry = null;
async function openVersions(entry) {
  verEntry = entry;
  $("#ver-file").textContent = entry.rel_path;
  $("#ver-note").value = "";
  openModal("#modal-versions");
  await renderVersions();
}
async function renderVersions() {
  const box = $("#ver-list");
  const pid = state.currentProjectId;
  let list = [];
  try { list = await api.versions.list(pid, verEntry.rel_path); } catch (e) { box.textContent = e.message; return; }
  box.innerHTML = list.length ? "" : '<p class="hint">Aún no hay versiones.</p>';
  list.forEach((v, i) => {
    const u = userById(v.user_id);
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid #2a2d35";
    row.innerHTML = `<div style="flex:1"><b>v${list.length - i}</b> · ${new Date(v.created_at + "Z").toLocaleString("es-ES")} · ${fmtSize(v.size)}<br><span class="hint">${escapeHtml(u ? u.name : "")}${v.note ? " — " + escapeHtml(v.note) : ""}</span></div>`;
    const dl = document.createElement("a");
    dl.className = "btn btn-ghost"; dl.textContent = "⬇"; dl.href = api.versions.downloadUrl(v.id); dl.title = "Descargar";
    const rs = document.createElement("button");
    rs.className = "btn btn-secondary"; rs.type = "button"; rs.textContent = "Restaurar";
    rs.addEventListener("click", async () => {
      if (!confirm("¿Restaurar esta versión? La actual se guarda antes como versión nueva.")) return;
      try { await api.versions.restore(v.id); toast("Versión restaurada"); await renderVersions(); await renderFileTable(verEntry.rel_path); }
      catch (e) { toast(e.message, true); }
    });
    row.appendChild(dl); row.appendChild(rs); box.appendChild(row);
  });
}
$("#ver-save").addEventListener("click", async () => {
  try { await api.versions.create(state.currentProjectId, verEntry.rel_path, $("#ver-note").value || null); $("#ver-note").value = ""; }
  catch (e) { toast(e.message, true); }
  renderVersions();
});

// ---------- PROJECT SETTINGS ----------
$("#btn-project-settings").addEventListener("click", () => {
  const p = projectById(state.currentProjectId);
  $("#ps-name").value = p.name;
  $("#ps-type").value = p.project_type;
  $("#ps-path").value = p.root_path;
  $("#ps-color").value = p.color;
  $("#ps-statuses").value = p.statuses.join(", ");
  initAccessUI(p);
  openModal("#modal-project-settings");
});

let showRoles = true;
let appMode = null;
const ACCESS_HINTS = {
  open: "Lo ven y editan todas las cuentas de la app.",
  personal: "Solo tú ves este proyecto. Los miembros ya añadidos quedan inactivos (no se borran) por si lo compartes de nuevo.",
  team: "Lo ven y editan los miembros que añadas, todos con los mismos permisos.",
  studio: "Roles por proyecto (lector, editor, propietario). El administrador de la app ve todo.",
};
async function initAccessUI(p) {
  let st = { auth_enabled: false };
  try { st = await api.get("/api/auth/status"); } catch (e) {}
  appMode = st.mode;
  $("#ps-access-block").style.display = st.auth_enabled ? "" : "none";
  $("#ps-members-block").style.display = "none";
  if (!st.auth_enabled) return;   // local mode: no accounts, nothing to configure
  $("#ps-access").value = p.access || "default";
  await applyAccessUI();
}
function currentPolicy() {
  const v = $("#ps-access").value;
  return v === "default" ? (appMode === "team" ? "open" : "studio") : v;
}
async function applyAccessUI() {
  const pol = currentPolicy();
  $("#ps-access-hint").textContent = ACCESS_HINTS[pol];
  showRoles = pol === "studio";
  $("#ps-members-block").style.display = (pol === "team" || pol === "studio") ? "" : "none";
  $("#ps-member-role").style.display = showRoles ? "" : "none";
  if (pol === "team" || pol === "studio") await renderMembers();
}
$("#ps-access").addEventListener("change", async () => {
  const pid = state.currentProjectId;
  try {
    await api.projects.patch(pid, { access: $("#ps-access").value });   // applied at once; reversible
    await loadProjects();
    toast("Acceso actualizado");
  } catch (e) {
    toast(e.message, true);
    const p = projectById(pid);
    $("#ps-access").value = (p && p.access) || "default";
  }
  await applyAccessUI();
});

const ROLE_LABELS = { viewer: "Lector", editor: "Editor", owner: "Propietario" };
async function renderMembers() {
  const pid = state.currentProjectId;
  const box = $("#ps-members");
  let members = [];
  try { members = await api.projects.members(pid); } catch (e) { box.textContent = e.message; return; }
  if (!showRoles) members = members.filter(m => m.role !== "owner" || true);
  box.innerHTML = "";
  members.forEach(m => {
    const u = userById(m.user_id);
    const row = document.createElement("div");
    row.style.cssText = "display:flex;align-items:center;gap:6px;margin:3px 0";
    row.innerHTML = `<span style="flex:1">${escapeHtml(u ? u.name : m.user_id)}</span>`;
    const sel = document.createElement("select");
    sel.innerHTML = Object.entries(ROLE_LABELS).map(([k, v]) => `<option value="${k}" ${m.role === k ? "selected" : ""}>${v}</option>`).join("");
    sel.addEventListener("change", async () => {
      try { await api.projects.setMember(pid, m.user_id, sel.value); } catch (e) { toast(e.message, true); }
      renderMembers();
    });
    const del = document.createElement("button");
    del.className = "btn btn-ghost"; del.type = "button"; del.textContent = "✕";
    del.addEventListener("click", async () => {
      try { await api.projects.removeMember(pid, m.user_id); } catch (e) { toast(e.message, true); }
      renderMembers();
    });
    if (!showRoles) sel.style.display = "none";
    row.appendChild(sel); row.appendChild(del); box.appendChild(row);
  });
  const inProject = new Set(members.map(m => m.user_id));
  $("#ps-member-user").innerHTML = state.users.filter(u => !inProject.has(u.id))
    .map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
}
$("#ps-member-add").addEventListener("click", async () => {
  const uid = $("#ps-member-user").value;
  if (!uid) return;
  try { await api.projects.setMember(state.currentProjectId, uid, $("#ps-member-role").value); }
  catch (e) { toast(e.message, true); }
  renderMembers();
});
$("#ps-save").addEventListener("click", async () => {
  const p = projectById(state.currentProjectId);
  try {
    await api.projects.patch(p.id, {
      name: $("#ps-name").value.trim(),
      project_type: $("#ps-type").value,
      root_path: $("#ps-path").value.trim(),
      color: $("#ps-color").value,
      statuses: $("#ps-statuses").value.split(",").map(s => s.trim()).filter(Boolean),
    });
    await loadProjects();
    closeModals();
    await selectProject(p.id);
    toast("Proyecto actualizado");
  } catch (e) { toast(e.message, true); }
});
$("#ps-delete").addEventListener("click", async () => {
  const p = projectById(state.currentProjectId);
  if (!confirm(`¿Eliminar el proyecto "${p.name}"? Esto no borra los archivos de Dropbox, solo la organización.`)) return;
  await api.projects.remove(p.id);
  state.currentProjectId = null;
  await loadProjects();
  closeModals();
  if (state.projects.length) await selectProject(state.projects[0].id);
  else { $("#project-view").classList.add("hidden"); $("#empty-state").classList.remove("hidden"); }
});

// ---------- TEAM ----------
$("#btn-team").addEventListener("click", () => { renderTeamList(); openModal("#modal-team"); });
function renderTeamList() {
  const el = $("#team-list");
  el.innerHTML = "";
  state.users.forEach(u => {
    const row = document.createElement("div");
    row.className = "team-row";
    row.innerHTML = `<span class="avatar" style="background:${u.color}">${initials(u.name)}</span>
      <span class="name">${escapeHtml(u.name)}</span><span class="email">${escapeHtml(u.email)}</span>`;
    const del = document.createElement("button");
    del.className = "icon-btn"; del.textContent = "🗑️";
    del.addEventListener("click", async () => { await api.users.remove(u.id); await loadUsers(); renderTeamList(); renderWhoAmI(); });
    row.appendChild(del);
    el.appendChild(row);
  });
}
$("#team-add").addEventListener("click", async () => {
  const name = $("#team-name").value.trim();
  const email = $("#team-email").value.trim();
  if (!name || !email) { toast("Nombre y email son obligatorios", true); return; }
  try {
    await api.users.create({ name, email, color: $("#team-color").value });
    $("#team-name").value = ""; $("#team-email").value = "";
    await loadUsers();
    renderTeamList();
    renderWhoAmI();
  } catch (e) { toast(e.message, true); }
});

// ---------- SETTINGS / GOOGLE CALENDAR ----------
async function refreshGcalStatus() {
  try {
    const status = await api.calendar.status();
    state.gcalConnected = status.connected;
    const el = $("#gcal-status");
    if (status.connected) { el.textContent = "🔗 Google Calendar conectado"; el.classList.add("connected"); }
    else if (status.has_client_credentials) { el.textContent = "Google Calendar: no conectado"; el.classList.remove("connected"); }
    else { el.textContent = "Google Calendar: falta configurar"; el.classList.remove("connected"); }
  } catch (e) { /* ignore */ }
}

$("#btn-settings").addEventListener("click", async () => {
  const settings = await api.settings.get();
  $("#settings-dropbox-detected").textContent = settings.detected_dropbox_paths.length
    ? settings.detected_dropbox_paths.join(", ") : "No detectada (puedes indicar la ruta manualmente al crear cada proyecto).";
  const status = await api.calendar.status();
  $("#settings-gcal-status").textContent = status.connected ? "Estado: conectado ✅"
    : status.has_client_credentials ? "Estado: credenciales listas, pendiente de conectar." : "Estado: falta data/google_credentials.json";
  openModal("#modal-settings");
});
$("#settings-gcal-connect").addEventListener("click", async () => {
  try {
    toast("Se abrirá tu navegador para autorizar Google Calendar…");
    await api.calendar.connect();
    await refreshGcalStatus();
    toast("Google Calendar conectado");
    closeModals();
  } catch (e) { toast(e.message, true); }
});
$("#settings-gcal-disconnect").addEventListener("click", async () => {
  await api.calendar.disconnect();
  await refreshGcalStatus();
  toast("Google Calendar desconectado");
});

// ---------- GLOBAL EVENTS ----------
function bindGlobalEvents() {
  $$(".tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));
  $("#btn-new-task").addEventListener("click", openNewTaskModal);

  $("#nf-create").addEventListener("click", createFolderFromModal);
  $("#nf-name").addEventListener("keydown", e => { if (e.key === "Enter") createFolderFromModal(); });

  $("#whoami-select").addEventListener("change", e => {
    state.currentUserId = e.target.value;
    localStorage.setItem("vpm_current_user_id", state.currentUserId);
    refreshInboxBadge();
  });
  $("#btn-inbox").addEventListener("click", openInboxModal);
  $("#sl-send").addEventListener("click", sendLinkFromModal);
}

async function createFolderFromModal() {
  const name = $("#nf-name").value.trim();
  if (!name) { toast("Escribe un nombre para la carpeta", true); return; }
  try {
    await api.files.mkdir(state.currentProjectId, state.filesPath, name);
    closeModals();
    invalidateFileTree();
    await renderFileTable();
    toast("Carpeta creada");
  } catch (e) { toast(e.message, true); }
}

// ---------- WHO AM I / INBOX ----------
function renderWhoAmI() {
  const sel = $("#whoami-select");
  sel.innerHTML = `<option value="">(elige quién eres)</option>` +
    state.users.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
  sel.value = state.currentUserId || "";
}

async function refreshInboxBadge() {
  const badge = $("#inbox-badge");
  if (!state.currentUserId) { badge.classList.add("hidden"); return; }
  try {
    const { count } = await api.notifications.unreadCount(state.currentUserId);
    badge.textContent = count;
    badge.classList.toggle("hidden", count === 0);
  } catch (e) { badge.classList.add("hidden"); }
}

async function openInboxModal() {
  if (!state.currentUserId) { toast("Primero elige quién eres en la barra lateral", true); return; }
  const list = $("#inbox-list");
  list.innerHTML = "Cargando…";
  openModal("#modal-inbox");
  const notifs = await api.notifications.listForUser(state.currentUserId);
  list.innerHTML = notifs.length ? "" : `<p class="hint">Tu bandeja está vacía.</p>`;
  notifs.forEach(n => list.appendChild(renderInboxItem(n)));
}

function renderInboxItem(n) {
  const sender = userById(n.from_user_id);
  const project = projectById(n.project_id);
  const div = document.createElement("div");
  div.className = "inbox-item" + (n.read ? "" : " unread");
  const fileName = n.rel_path.split("/").pop();
  div.innerHTML = `
    <div class="inbox-meta">${sender ? escapeHtml(sender.name) : "Alguien"} te envió un enlace ·
      ${project ? escapeHtml(project.name) : "proyecto eliminado"} · ${new Date(n.created_at).toLocaleString("es-ES")}</div>
    <div><strong>${escapeHtml(fileName)}</strong></div>
    ${n.message ? `<div>${escapeHtml(n.message)}</div>` : ""}`;
  const actions = document.createElement("div");
  actions.className = "inbox-actions";
  const goBtn = document.createElement("button");
  goBtn.className = "btn btn-primary";
  goBtn.textContent = "Ir al archivo";
  goBtn.addEventListener("click", async () => {
    if (!project) { toast("Ese proyecto ya no existe", true); return; }
    await api.notifications.markRead(n.id);
    closeModals();
    await navigateToFile(n.project_id, n.rel_path);
    refreshInboxBadge();
  });
  actions.appendChild(goBtn);
  const delBtn = document.createElement("button");
  delBtn.className = "btn btn-ghost";
  delBtn.textContent = "Eliminar";
  delBtn.addEventListener("click", async () => {
    await api.notifications.remove(n.id);
    div.remove();
    refreshInboxBadge();
  });
  actions.appendChild(delBtn);
  div.appendChild(actions);
  return div;
}

// ---------- SEND LINK ----------
let sendLinkTarget = null;

function openSendLinkModal(entry) {
  sendLinkTarget = entry;
  $("#sl-target").textContent = "Archivo: " + entry.name;
  const options = state.users.map(u => `<option value="${u.id}">${escapeHtml(u.name)}</option>`).join("");
  $("#sl-to").innerHTML = options || `<option value="">Añade personas en Equipo primero</option>`;
  $("#sl-from").innerHTML = `<option value="">(sin especificar)</option>` + options;
  $("#sl-from").value = state.currentUserId || "";
  $("#sl-message").value = "";
  openModal("#modal-send-link");
}

async function sendLinkFromModal() {
  const toUserId = $("#sl-to").value;
  if (!toUserId) { toast("Elige a quién enviarlo", true); return; }
  try {
    await api.notifications.create({
      project_id: state.currentProjectId,
      rel_path: sendLinkTarget.rel_path,
      to_user_id: toUserId,
      from_user_id: $("#sl-from").value || null,
      message: $("#sl-message").value.trim(),
    });
    closeModals();
    toast("Enlace enviado a la bandeja de " + $("#sl-to").selectedOptions[0].textContent);
  } catch (e) { toast(e.message, true); }
}

init();
