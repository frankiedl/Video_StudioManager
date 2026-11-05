# Roadmap (opción B: gestor de proyectos + assets sobre carpetas sincronizadas)

Meta: reemplazo de Anchorpoint sin suscripción, multiplataforma, multiusuario.

## Brecha vs Anchorpoint
| Área | Anchorpoint | Aquí hoy | Prioridad |
|---|---|---|---|
| Multiusuario con login/roles | Sí (cloud) | No (selector "Soy:") | P0 |
| Datos compartidos seguros | Servidor | SQLite en Dropbox (riesgo de corrupción) | P0 |
| Tareas/Kanban/Timeline | Sí | Sí | hecho |
| Etiquetas/estado/comentarios por archivo | Sí | Sí | hecho |
| Miniaturas y previews | Sí (muchos formatos) | Img + video (ffmpeg) | P2 |
| Bloqueo de archivos (avisar que alguien edita) | Sí | No | P1 |
| Historial/versiones de archivo | Git/Perforce | No | P2 (snapshots ligeros) |
| Integración DCC (Blender, C4D, AE, Resolve) | Sí | No | P2 |
| App de escritorio sin instalar Python | Sí | No | P1 |

## Fases
1. **Base multiusuario (P0):** PostgreSQL (o SQLite solo-servidor) + Alembic; auth (usuarios, contraseña hash, sesiones/JWT); roles admin/miembro; modo servidor (`VPM_HOST`) con la DB fuera de Dropbox.
2. **Empaquetado (P1):** PyInstaller o Tauri para Windows/macOS/Linux; ffmpeg incluido.
3. **Bloqueo de archivos (P1):** tabla `file_lock` + aviso en UI; heartbeat.
4. **Snapshots de versión (P2):** hash + copia de versiones anteriores en carpeta oculta, restaurar desde UI.
5. **Integraciones DCC (P2):** scripts para abrir/guardar/bloquear desde Blender, C4D, Resolve.
6. **Calidad:** partir `app.js` en módulos, ampliar tests, CI en GitHub Actions.
