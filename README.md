# Studio Manager

Local project manager for video, animation, editing, 3D, and shooting: features a kanban board, timeline, Google Calendar-style calendar, and a file explorer with thumbnails and comments. Everything is backed by your Dropbox folder and synced with Google Calendar.

It focuses on project management + assets + calendar.

For technical details (data model, endpoints, code structure), see [ARCHITECTURE.md](ARCHITECTURE.md) — read it before touching the code so you don't have to reread the entire project from scratch.

## How to Run

On Windows, double-click `start.bat`. On macOS, you can run `bash start.sh` from the terminal. The first time, it will create a Python virtual environment and install dependencies (takes about a minute); subsequent times, it will start instantly. Your browser will open at `http://127.0.0.1:8420`.

The SQLite database is saved in `data/studio.db` within the project folder. However, if it detects an available Dropbox folder, it moves it to a path like `~/Dropbox/<project-name>/data/studio.db` or to the path specified by `VPM_DATA_DIR`. This way, each installation of the project shares the same database locally and synchronously. The actual files (videos, PSDs, 3D scenes…) are not copied anywhere: the app simply reads and organizes them directly inside your already synced Dropbox folder.

## Dropbox

It does not use the Dropbox API or request passwords: when you create a project, you point its "project folder" to a path inside your local Dropbox (the app automatically detects where you have Dropbox installed and suggests it). Dropbox continues syncing those files as usual; the app only organizes them, adds tags/status/comments, and generates thumbnails.

## Automatic Folder Structure

When creating a project, depending on the chosen **type** (Video / Animation / Editing / 3D / Shooting / Other), a numbered folder structure is automatically created in the typical style of an animation/post-production studio (e.g., `00_Admin`, `01_Preproduction`, `02_Shooting`... for Video). You can uncheck the corresponding box in the "New Project" modal if you prefer not to create it. It is non-destructive: it only adds missing folders and never touches or deletes anything existing. The complete list of folders by type can be found in [vpm/project_templates.py](https://www.google.com/search?q=vpm/project_templates.py).

## Google Calendar (Deadlines per User)

When a task has a due date and an assigned person, an event is created in Google Calendar, inviting that person via email. The deadline appears directly on THEIR calendar, even if only one Google login is connected (the studio's account).

To activate it:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/) → create a project → enable the "Google Calendar API".
2. Create OAuth credentials of the **Desktop Application** type.
3. Download the JSON and save it as `data/google_credentials.json`.
4. In the app, open **⚙️ Settings → Connect Google Calendar** and authorize your account in the browser.

Without this step, the app works exactly the same but without syncing deadlines to the calendar.

## Team

In **👥 Team**, you add each person (name + email). This email is the one that will receive the calendar invitation when they are assigned a task with a due date, and it is also who you can send file links to (see "Inbox" below).

## Timeline and Calendar (Visual Editing like iCal / Google Calendar)

* **Calendar**: Each task with a start and/or due date is drawn as a bar spanning from the day it starts to the day it ends (just like in Google Calendar), and can cross multiple weeks. Drag a bar to another day to move it entirely; double-clicking an empty space on a day creates a new task with that date; double-clicking a bar opens it for editing. The colors match those of the assigned person.
* **Timeline**: Drag across the "+ New task" row of a list to create a task within that date range; drag an existing bar to move it; drag its left/right edges to adjust the start or due date; double-clicking opens it for editing. If a task does not have dates yet, you can drag directly across its own row to set them.

## File Explorer

The **Files** tab has three panels: a folder tree always expanded on the left (with a colored dot per folder, click to assign a color), a central table with inline-editable Status/Assigned/Tags, and a preview panel on the right with a thumbnail, notes, and shortcuts. Use **+ Folder** to create subfolders without leaving the app. Double-clicking a file opens its full details page with comments/review options.

**Rename**: Hover over a row (or look at the preview panel) and click the ✏️ icon next to the name; type the new name and press Enter. This renames the actual file or folder on the disk (inside Dropbox) and automatically updates any saved tags/status/comments, including those of files inside a renamed folder.

## Inbox (Send a Link to a File)

This app does not have a real login system, so "sending something to someone's inbox" functions as an internal inbox within the app itself: in the sidebar, each person chooses who they are in the **"I am: ..."** selector. From the preview panel of any file, the **📤 Send link to…** button allows you to choose whom to send it to (from your Team) along with an optional message. When that person selects their name in "I am:", they will see a counter in the **📥 Inbox** and can open it to click "Go to file", which opens the app directly in the correct project and folder with that file selected.

## Notes

* Video thumbnails require `ffmpeg` installed and added to the PATH; if unavailable, a generic icon based on the file type will be displayed.
* Deleting a project in the app only removes its organization (tasks, comments, tags); it never deletes files from your Dropbox.

## Multiusuario y login

La primera vez que abres la app te pide crear la cuenta de **administrador**. Después el admin crea usuarios (con contraseña) en **Equipo**; cada uno inicia sesión con su email. Las contraseñas se guardan con scrypt y las sesiones son cookies HttpOnly.

Variables de entorno: `VPM_AUTH=off` (modo local de un solo usuario sin login), `VPM_DATABASE_URL` (p. ej. `postgresql+psycopg://user:pw@host/db` para un servidor compartido; instala `psycopg[binary]`), `VPM_COOKIE_SECURE=1` (si sirves por HTTPS), `VPM_HOST=0.0.0.0` (para exponerlo en red; ponlo detrás de HTTPS).

## Ejecutable (sin instalar Python)

`pyinstaller studiomanager.spec` genera `dist/StudioManager` (.exe en Windows). Los datos se guardan en `%APPDATA%\StudioManager` (Windows), `~/Library/Application Support/StudioManager` (macOS) o `~/.local/share/StudioManager` (Linux), o en `VPM_DATA_DIR`. Para miniaturas de vídeo sigue haciendo falta `ffmpeg` en el PATH. GitHub Actions (`.github/workflows/build.yml`) compila para Windows, macOS y Linux; al crear una etiqueta `vX.Y.Z` publica los binarios en Releases.

## Permisos por proyecto

Cada proyecto tiene miembros con rol **Lector** (ve, comenta), **Editor** (además crea/edita tareas y archivos, bloquea) o **Propietario** (además gestiona miembros y ajustes, borra). Quien crea un proyecto es su propietario. Los administradores de la app lo ven todo. Un proyecto sin miembros solo lo ven los administradores: tras actualizar una instalación existente, el admin debe añadir miembros desde ⚙️ Proyecto → Miembros y permisos. Con `VPM_AUTH=off` no hay restricciones.

## Versiones de archivos (snapshots)

En la ficha de un archivo, **📜 Versiones** permite guardar una versión (con nota), descargarla o restaurarla. Restaurar guarda antes el estado actual, así que nunca se pierde trabajo. Las copias se guardan sin duplicados (por hash) en `.studio_versions/` dentro de la carpeta del proyecto, oculta en el explorador. Respeta los bloqueos y el historial sigue al archivo si se renombra. Solo archivos, no carpetas; borrar una versión requiere ser propietario. Ojo: archivos muy grandes ocupan espacio por cada versión distinta.
