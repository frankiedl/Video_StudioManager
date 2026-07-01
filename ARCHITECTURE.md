# Architecture reference

Technical map of the codebase for whoever (human or Claude) picks this up next. Read
this before exploring the code — it should answer "where does X live" without needing to
grep the whole project first. User-facing feature docs are in [README.md](README.md).

## Stack

- **Backend**: FastAPI + SQLAlchemy + SQLite (`studio.db`), single process, no auth.
  The DB file is resolved by `vpm/database.py` and can live in the project-local `data/`
  folder, in a Dropbox-backed path (for example `~/Dropbox/<project-name>/data/`), or in
  a custom location defined via `VPM_DATA_DIR`.
- **Frontend**: vanilla HTML/CSS/JS, no build step, no framework. One `web/index.html`
  shell with all modals pre-declared (hidden by default), one `web/js/app.js` with all
  view logic, `web/js/api.js` as the thin fetch wrapper.
- **Launch**: `app.py` runs uvicorn and opens the browser; `start.bat` (Windows) and
  `start.sh` (macOS/Linux) set up the venv and launch the app.

## Backend layout

```
app.py                    Entry point: creates tables, runs lightweight column migrations, mounts routers + static web/
vpm/database.py           SQLAlchemy engine/session, DATA_DIR/THUMB_DIR paths, DB path resolution (Dropbox-aware + VPM_DATA_DIR override)
vpm/models.py              All ORM models (see Data model below)
vpm/schemas.py             Pydantic request/response models
vpm/project_templates.py   Per-project-type folder name lists (used on project creation)
vpm/google_calendar.py     OAuth + Google Calendar event upsert/delete
vpm/thumbnails.py          Image (Pillow) / video (ffmpeg if present) thumbnail generation, cached in data/thumbnails/
vpm/routers/               One file per resource, see API endpoints below
```

**Adding a DB column to an existing table**: `Base.metadata.create_all()` only creates
missing *tables*, not new columns on existing ones. If you add a column, also add an
`ALTER TABLE` line in `app.py`'s `_migrate()` (see the `asset_meta.color` example) so
existing installs (with real user data in the resolved DB path, whether that is a local
`data/` folder or a Dropbox-backed path) don't break on startup.

## Data model (`vpm/models.py`)

- **User** — id, name, email, color. Global list, not scoped per-project (any user can be
  assigned to any project's tasks/assets).
- **Project** — id, name, project_type, root_path (absolute path inside the user's local
  Dropbox folder), color, statuses (JSON list, the kanban columns), archived.
- **TaskList** — belongs to a Project; a named grouping of tasks (shown as board columns'
  source and as timeline row groups). `folder_path` field exists but is largely inert
  metadata (kept in sync on file renames, not otherwise used by the UI).
- **Task** — belongs to a TaskList. title, description, status (must be one of the
  project's `statuses`), priority, assignee_id, start_date, due_date, tags (JSON list),
  position, gcal_event_id (set once synced to Google Calendar).
- **Comment** — attached to either a Task (`task_id`) or a file/folder
  (`project_id` + `asset_rel_path`), never both.
- **AssetMeta** — the metadata layer over real files/folders on disk. Keyed by
  `(project_id, rel_path)`, created lazily on first edit (no row = defaults). Holds
  status, assignee_id, tags, starred, notes, color (folder color swatch).
- **Notification** — an in-app "inbox" entry (see Notifications below).
- **AppSetting** — single key/value store, currently only `default_dropbox_root`.

**Path-referencing rows**: `AssetMeta.rel_path`, `Comment.asset_rel_path`,
`Notification.rel_path`, and `TaskList.folder_path` all store a path *relative to the
project root*, forward-slash-separated. Renaming a file/folder
(`POST /api/files/rename`) rewrites all four via `_rewrite_path_prefix()` in
`vpm/routers/files.py` — if you add another table that stores a rel_path, add it there
too.

## API endpoints

All under `/api`. Grouped by router file (`vpm/routers/*.py`):

| Router | Endpoints |
|---|---|
| `users.py` | `GET/POST /users`, `PATCH/DELETE /users/{id}` |
| `projects.py` | `GET/POST /projects`, `GET/PATCH/DELETE /projects/{id}` — POST also scaffolds the folder template unless `create_structure: false` |
| `tasklists.py` | `GET/POST /task-lists`, `DELETE /task-lists/{id}` |
| `tasks.py` | `GET/POST /tasks`, `GET/PATCH/DELETE /tasks/{id}` — PATCH/POST also push to Google Calendar if connected (best-effort, never blocks on failure) |
| `comments.py` | `GET/POST /comments`, `DELETE /comments/{id}` — GET filters by `task_id` or by `project_id`+`asset_rel_path` |
| `files.py` | `GET /files/browse` (list a folder + merged AssetMeta), `GET /files/tree` (full recursive dir tree, capped at 3000 nodes / depth 10), `POST /files/mkdir`, `POST /files/rename`, `GET /files/thumbnail`, `GET /files/download`, `POST /files/open` (opens/reveals in OS file explorer), `GET/PATCH /files/meta` |
| `calendar_router.py` | `GET /calendar/status`, `POST /calendar/connect` (blocking OAuth flow, opens browser), `POST /calendar/disconnect` |
| `settings_router.py` | `GET/POST /settings` — GET also returns auto-detected local Dropbox folder path(s) |
| `notifications.py` | `GET /notifications?to_user_id=`, `GET /notifications/unread-count?to_user_id=`, `POST /notifications`, `PATCH /notifications/{id}/read`, `DELETE /notifications/{id}` |

All file endpoints take `project_id` + `rel_path` and resolve/validate the path stays
inside `project.root_path` (see `_resolve()` in `files.py`) — never trust a `rel_path`
without going through it.

## Frontend layout (`web/js/app.js`)

Single global `state` object (projects, tasks, current selections, UI flags) and a flat
set of `render*()` functions per view, each rebuilding its DOM subtree from `state` on
every call (no virtual-DOM/diffing — always safe to just re-call the render function).
Sections are marked with `// ---------- SECTION ----------` banner comments; the main
ones, in file order:

1. **State + generic helpers** — `$`/`$$` (querySelector), `escapeHtml`, `toast`,
   `openModal`/`closeModals`, date helpers (see below).
2. **Project selection** — `selectProject()`, `switchTab()` (now `async`, since the Files
   tab's render is async; pass a second arg to jump straight to a file, see
   `navigateToFile()`).
3. **Board** — kanban columns from `project.statuses`, native HTML5 drag&drop to change
   `status`.
4. **Timeline** — Gantt-style. Pointer-based (mousedown/mousemove/mouseup) drag to move a
   bar, resize its edges, or drag-select an empty range to create a task. See
   `attachTimelineBarDrag()` / `attachTrackCreateDrag()`.
5. **Calendar** — Google Calendar/iCal-style month grid. Tasks render as bars spanning
   `start_date`→`due_date` (clamped per week, stacked into lanes to avoid overlap — see
   `renderCalendar()`'s lane-assignment loop). Drag/drop and double-click-to-create are
   handled **once per week row** (`attachWeekInteractions()`), not per day cell: the
   target day is derived from the pointer's X position within the row, because the bars
   overlay sits on top of the day cells and per-cell listeners would miss drops that land
   on a bar.
6. **Files** — three-pane explorer: `renderFileTree()` (always-expanded recursive tree,
   collapse state kept in `state.collapsedFolders`), `renderFileTable()` (inline-editable
   status/assignee/tags, rename via `startInlineRename()`), `renderFilePreview()` (right
   panel: big preview, quick actions, "Enviar enlace a…").
7. **Task / Asset modals** — `openTaskModal()`/`openAssetModal()` and their save/comment
   handlers.
8. **Who am I / Inbox** — `state.currentUserId` (persisted in `localStorage`, no real
   auth) drives the "Soy: …" sidebar selector and the inbox unread badge. Sending a link
   creates a `Notification` row; "Ir al archivo" in the inbox calls `navigateToFile()`
   which switches project (if needed), sets `state.filesPath` to the file's parent
   folder, and selects it in the table.
9. **New project / project settings / team / general settings modals**.

### Date handling — read this before touching any date code

All task/calendar/timeline dates are **calendar days**, never timestamps with meaningful
time-of-day. Two helpers in `app.js` exist specifically to avoid a JS footgun where
`new Date("2026-07-12")` (bare date, no time) parses as **UTC midnight**, which shifts to
the *previous* local day when printed back out in any timezone ahead of UTC (all of
Europe, for example) — this caused a real one-day-off bug when calendar drag-and-drop was
first built.

- `parseAnyDate(d)` — accepts a `Date`, a bare `"YYYY-MM-DD"`, or a full
  `"YYYY-MM-DDTHH:MM:SS"` string, and always returns a `Date` at **local midnight** for
  that calendar day, ignoring any timezone info in the string entirely.
- `fmtDate(d)` — the inverse: formats a `Date`/string back to `"YYYY-MM-DD"` using the
  Date's *local* getters (`getFullYear`/`getMonth`/`getDate`), never `toISOString()`.
- `tlAddDays(date, n)` — `parseAnyDate` + add `n` days, used everywhere a date needs
  shifting (drag deltas, timeline range).

Rule of thumb: **never** call `new Date(someDateString)` directly on a task/calendar date
in this codebase — always go through `parseAnyDate`/`fmtDate`/`tlAddDays`. The only
exceptions are true instants like `created_at`/`mtime` (used only for display timestamps,
via `toLocaleString`), which don't need calendar-day semantics.

### Drag & drop patterns

- **Board / Calendar**: native HTML5 DnD (`draggable=true`, `dragstart`/`dragover`/
  `drop`), since it's single-element-to-single-target.
- **Timeline**: manual pointer dragging (`mousedown`+`document`-level `mousemove`/
  `mouseup`), because it needs continuous pixel-level feedback (resize handles, live
  ghost preview) that HTML5 DnD doesn't give you.

## Known simplifications (by design, not oversights)

- No real authentication/login — "Soy: …" is a local trust-based selector.
- Google Calendar sync uses **one** OAuth-connected account (the studio's); per-task
  assignees are added as event *attendees* rather than each having their own connected
  calendar.
- Dropbox integration is filesystem-only (point at the already-synced local folder) — no
  Dropbox API/OAuth, matching how Anchorpoint itself treats cloud-synced folders.
- `TaskList.folder_path` is mostly vestigial; don't assume it drives any filtering.
