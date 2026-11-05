const api = {
  async _req(method, url, body) {
    const opts = { method, headers: {} };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    if (!res.ok) {
      let msg = res.statusText;
      try { const j = await res.json(); msg = j.detail || msg; } catch (e) {}
      throw new Error(msg);
    }
    if (res.status === 204) return null;
    const text = await res.text();
    return text ? JSON.parse(text) : null;
  },
  get(url) { return this._req("GET", url); },
  post(url, body) { return this._req("POST", url, body); },
  patch(url, body) { return this._req("PATCH", url, body); },
  del(url) { return this._req("DELETE", url); },

  users: {
    list: () => api.get("/api/users"),
    create: (data) => api.post("/api/users", data),
    update: (id, data) => api.patch(`/api/users/${id}`, data),
    remove: (id) => api.del(`/api/users/${id}`),
  },
  projects: {
    list: () => api.get("/api/projects"),
    create: (data) => api.post("/api/projects", data),
    get: (id) => api.get(`/api/projects/${id}`),
    patch: (id, data) => api.patch(`/api/projects/${id}`, data),
    remove: (id) => api.del(`/api/projects/${id}`),
  },
  taskLists: {
    list: (projectId) => api.get(`/api/task-lists?project_id=${projectId}`),
    create: (data) => api.post("/api/task-lists", data),
    remove: (id) => api.del(`/api/task-lists/${id}`),
  },
  tasks: {
    listByProject: (projectId) => api.get(`/api/tasks?project_id=${projectId}`),
    create: (data) => api.post("/api/tasks", data),
    get: (id) => api.get(`/api/tasks/${id}`),
    patch: (id, data) => api.patch(`/api/tasks/${id}`, data),
    remove: (id) => api.del(`/api/tasks/${id}`),
  },
  comments: {
    listForTask: (taskId) => api.get(`/api/comments?task_id=${taskId}`),
    listForAsset: (projectId, relPath) => api.get(`/api/comments?project_id=${projectId}&asset_rel_path=${encodeURIComponent(relPath)}`),
    create: (data) => api.post("/api/comments", data),
    remove: (id) => api.del(`/api/comments/${id}`),
  },
  files: {
    browse: (projectId, relPath) => api.get(`/api/files/browse?project_id=${projectId}&rel_path=${encodeURIComponent(relPath || "")}`),
    tree: (projectId) => api.get(`/api/files/tree?project_id=${projectId}`),
    mkdir: (projectId, relPath, name) => api.post("/api/files/mkdir", { project_id: projectId, rel_path: relPath, name }),
    rename: (projectId, relPath, newName) => api.post("/api/files/rename", { project_id: projectId, rel_path: relPath, new_name: newName }),
    thumbnailUrl: (projectId, relPath) => `/api/files/thumbnail?project_id=${projectId}&rel_path=${encodeURIComponent(relPath)}`,
    openFile: (projectId, relPath, reveal) => api.post("/api/files/open", { project_id: projectId, rel_path: relPath, reveal: !!reveal }),
    getMeta: (projectId, relPath) => api.get(`/api/files/meta?project_id=${projectId}&rel_path=${encodeURIComponent(relPath)}`),
    patchMeta: (projectId, relPath, data) => api.patch(`/api/files/meta?project_id=${projectId}&rel_path=${encodeURIComponent(relPath)}`, data),
  },
  locks: {
    lock: (projectId, relPath, note) => api.post("/api/locks", { project_id: projectId, rel_path: relPath, note, user_id: localStorage.getItem("vpm_current_user_id") || null }),
    unlock: (projectId, relPath) => api.del(`/api/locks?project_id=${projectId}&rel_path=${encodeURIComponent(relPath)}&user_id=${localStorage.getItem("vpm_current_user_id") || ""}`),
  },
  calendar: {
    status: () => api.get("/api/calendar/status"),
    connect: () => api.post("/api/calendar/connect"),
    disconnect: () => api.post("/api/calendar/disconnect"),
  },
  settings: {
    get: () => api.get("/api/settings"),
    set: (data) => api.post("/api/settings", data),
  },
  search: {
    query: (q) => api.get(`/api/search?q=${encodeURIComponent(q)}`),
  },
  notifications: {
    listForUser: (userId) => api.get(`/api/notifications?to_user_id=${userId}`),
    unreadCount: (userId) => api.get(`/api/notifications/unread-count?to_user_id=${userId}`),
    create: (data) => api.post("/api/notifications", data),
    markRead: (id) => api.patch(`/api/notifications/${id}/read`),
    remove: (id) => api.del(`/api/notifications/${id}`),
  },
};
