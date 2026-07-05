'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let tasks = [];
let expandedSlugs = new Set();
let modalSlug = null;
let refreshInterval = null;
let showArchived = false;
const REFRESH_MS = 3000;

// Preserve token from URL for API calls
const urlToken = new URLSearchParams(window.location.search).get('token') || '';
function apiUrl(path, extra = {}) {
  const params = new URLSearchParams(extra);
  if (urlToken) params.set('token', urlToken);
  const qs = params.toString();
  return qs ? `${path}?${qs}` : path;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function fetchTasks() {
  const url = apiUrl('/api/tasks', showArchived ? {all: '1'} : {});
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function fetchTask(slug) {
  const r = await fetch(apiUrl(`/api/tasks/${slug}`));
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function sendInput(slug, text, enter) {
  const r = await fetch(apiUrl(`/api/tasks/${slug}/send`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text, enter }),
  });
  return r.json();
}

async function killSession(slug) {
  const r = await fetch(apiUrl(`/api/tasks/${slug}`), { method: 'DELETE' });
  return r.json();
}

// ---------------------------------------------------------------------------
// Render
// ---------------------------------------------------------------------------

function statusDotClass(status) {
  return ['working', 'waiting', 'idle', 'starting', 'done', 'dead', 'error'].includes(status)
    ? status : 'idle';
}

function renderTask(task) {
  const expanded  = expandedSlugs.has(task.slug);
  const dead      = !task.alive && !task.archived;
  const archived  = task.archived;
  const statusCls = statusDotClass(task.status);

  const card = document.createElement('div');
  card.className = [
    'task-card',
    expanded  ? 'expanded'  : '',
    dead      ? 'dead'      : '',
    archived  ? 'archived'  : '',
  ].filter(Boolean).join(' ');
  card.dataset.slug = task.slug;

  // Actions always visible in header
  let headerActions = '';
  if (task.alive) {
    headerActions = `
      <button class="btn btn-sm btn-secondary" data-action="send" data-slug="${esc(task.slug)}" title="Send input">✏</button>
      <button class="btn btn-sm btn-danger"    data-action="kill" data-slug="${esc(task.slug)}" title="Kill session">✕</button>`;
  } else if (!archived) {
    headerActions = `<button class="btn btn-sm btn-ghost" data-action="resume" data-slug="${esc(task.slug)}" title="Resume Claude">▶ Resume</button>`;
  }

  const modelTag = task.model
    ? `<span class="task-model" title="Model">${esc(task.model.replace('claude-',''))}</span>`
    : '';

  // Inline preview — always visible for alive sessions, no click needed.
  // Updated from task.preview on every poll (included in /api/tasks response).
  let inlinePreview = '';
  if (task.alive && task.preview) {
    inlinePreview = `<pre class="pane-preview-inline" id="preview-${esc(task.slug)}">${esc(task.preview)}</pre>`;
  } else if (task.alive) {
    inlinePreview = `<pre class="pane-preview-inline pane-preview-empty" id="preview-${esc(task.slug)}">Loading…</pre>`;
  }

  // Expand section: goal + cwd (extra context, not the preview)
  const expandSection = `
    <div class="task-detail">
      <div class="task-detail-inner">
        <div class="task-cwd">📁 ${esc(task.cwd)}</div>
        ${task.goal ? `<div class="task-goal">${esc(task.goal)}</div>` : ''}
      </div>
    </div>`;

  card.innerHTML = `
    <div class="task-header">
      <span class="status-dot ${statusCls}"></span>
      <span class="task-slug">${esc(task.slug)}</span>
      <div class="task-meta">
        <span class="status-badge ${statusCls}">${esc(task.status)}</span>
        ${task.project ? `<span class="task-project">${esc(task.project)}</span>` : ''}
        ${modelTag}
        <span class="task-age">${esc(task.age)}</span>
        <div class="header-actions" onclick="event.stopPropagation()">
          ${headerActions}
        </div>
        ${task.alive ? `<span class="task-expand" title="Toggle goal/path">▶</span>` : ''}
      </div>
    </div>
    ${inlinePreview}
    ${expandSection}
  `;

  // Header click → expand/collapse (shows goal + cwd)
  card.querySelector('.task-header').addEventListener('click', () => toggleExpand(task.slug));

  // Action buttons
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      handleAction(btn.dataset.action, btn.dataset.slug);
    });
  });

  // Scroll inline preview to bottom after DOM insertion
  if (task.alive && task.preview) {
    requestAnimationFrame(() => {
      const preEl = card.querySelector(`#preview-${task.slug}`);
      if (preEl) preEl.scrollTop = preEl.scrollHeight;
    });
  }

  return card;
}

function render() {
  const list = document.getElementById('task-list');
  const empty = document.getElementById('empty-state');

  if (tasks.length === 0) {
    list.innerHTML = '';
    empty.hidden = false;
    return;
  }

  empty.hidden = true;

  // Diff: only update changed cards to avoid scroll jumping
  const existing = new Map();
  list.querySelectorAll('.task-card').forEach(el => {
    existing.set(el.dataset.slug, el);
  });

  const newSlugs = new Set(tasks.map(t => t.slug));

  // Remove cards no longer in list
  existing.forEach((el, slug) => {
    if (!newSlugs.has(slug)) el.remove();
  });

  // Add/update cards
  tasks.forEach((task, i) => {
    const newCard = renderTask(task);
    const old = existing.get(task.slug);
    if (old) {
      // Replace only if status/alive changed (avoids unnecessary reflows)
      const oldStatus = old.querySelector('.status-dot')?.className || '';
      const newStatus = `status-dot ${statusDotClass(task.status)}`;
      if (oldStatus !== newStatus || old.classList.contains('dead') !== !task.alive) {
        old.replaceWith(newCard);
      } else {
        // Update age in place
        const ageEl = old.querySelector('.task-age');
        if (ageEl) ageEl.textContent = task.age;
        // Update inline preview in place (no full re-render = no scroll jump)
        if (task.alive && task.preview) {
          const preEl = old.querySelector(`#preview-${task.slug}`);
          if (preEl) {
            preEl.textContent = task.preview;
            // Keep scrolled to bottom so newest output is always visible
            preEl.scrollTop = preEl.scrollHeight;
          }
        }
      }
    } else {
      if (i < list.children.length) {
        list.insertBefore(newCard, list.children[i]);
      } else {
        list.appendChild(newCard);
      }
    }
  });
}

// ---------------------------------------------------------------------------
// Actions
// ---------------------------------------------------------------------------

function toggleExpand(slug) {
  if (expandedSlugs.has(slug)) {
    expandedSlugs.delete(slug);
  } else {
    expandedSlugs.add(slug);
    if (tasks.find(t => t.slug === slug)?.alive) {
      loadPreview(slug);
    }
  }
  render();
}

async function loadPreview(slug) {
  const el = document.getElementById(`preview-${slug}`);
  if (!el) return;
  try {
    const detail = await fetchTask(slug);
    if (detail.preview) {
      el.textContent = detail.preview;
      el.classList.remove('pane-preview-empty');
    } else {
      el.innerHTML = '<span class="pane-preview-empty">No preview — session not active.</span>';
    }
  } catch {
    el.innerHTML = '<span class="pane-preview-empty">Failed to load preview.</span>';
  }
}

function handleAction(action, slug) {
  if (action === 'send') {
    openModal(slug);
  } else if (action === 'kill') {
    if (confirm(`Kill session for '${slug}'?`)) {
      killSession(slug).then(() => refresh());
    }
  } else if (action === 'resume') {
    const task = tasks.find(t => t.slug === slug);
    const sid = task?.session_id || '';
    if (!sid) { alert('No session_id — cannot resume.'); return; }
    sendInput(slug, `claude --resume ${sid}`, true)
      .then(() => { refresh(); })
      .catch(() => alert('Resume failed — session may not have a running shell.'));
  } else if (action === 'attach') {
    alert(`Run in your terminal:\n  loom go ${slug}`);
  }
}

// ---------------------------------------------------------------------------
// Modal
// ---------------------------------------------------------------------------

function openModal(slug) {
  modalSlug = slug;
  document.getElementById('modal-slug').textContent = slug;
  document.getElementById('modal-input').value = '';
  document.getElementById('modal-overlay').hidden = false;
  document.getElementById('modal-input').focus();
}

function closeModal() {
  document.getElementById('modal-overlay').hidden = true;
  modalSlug = null;
}

async function submitModal() {
  if (!modalSlug) return;
  const text  = document.getElementById('modal-input').value;
  const enter = document.getElementById('modal-enter').checked;
  if (!text.trim()) return;
  try {
    await sendInput(modalSlug, text, enter);
    closeModal();
    setTimeout(() => loadPreview(modalSlug), 500);
  } catch (e) {
    alert(`Failed to send: ${e.message}`);
  }
}

// ---------------------------------------------------------------------------
// Refresh loop
// ---------------------------------------------------------------------------

async function refresh() {
  const ts = new Date().toLocaleTimeString();
  try {
    tasks = await fetchTasks();
    render();
    setRefreshStatus(`↻ ${ts}`);
  } catch (e) {
    setRefreshStatus(`⚠ ${e.message}`);
  }
}

function setRefreshStatus(text) {
  document.getElementById('refresh-status').textContent = text;
}

function startAutoRefresh() {
  if (refreshInterval) clearInterval(refreshInterval);
  refreshInterval = setInterval(refresh, REFRESH_MS);
}

// ---------------------------------------------------------------------------
// Utils
// ---------------------------------------------------------------------------

function esc(s) {
  return String(s ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  // Show archived toggle
  const btnAll = document.getElementById('btn-show-all');
  btnAll.addEventListener('click', () => {
    showArchived = !showArchived;
    btnAll.textContent = showArchived ? 'Hide archived' : 'Show archived';
    btnAll.classList.toggle('active', showArchived);
    refresh();
  });

  // Refresh button
  document.getElementById('btn-refresh').addEventListener('click', () => {
    refresh();
    startAutoRefresh();
  });

  // Modal events
  document.getElementById('modal-close').addEventListener('click', closeModal);
  document.getElementById('modal-cancel').addEventListener('click', closeModal);
  document.getElementById('modal-send').addEventListener('click', submitModal);
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('modal-overlay')) closeModal();
  });
  document.getElementById('modal-input').addEventListener('keydown', e => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) submitModal();
    if (e.key === 'Escape') closeModal();
  });

  // Initial load
  refresh();
  startAutoRefresh();
});
