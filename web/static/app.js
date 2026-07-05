'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

let tasks = [];
let expandedSlugs = new Set();
let modalSlug = null;
let refreshInterval = null;
const REFRESH_MS = 3000;

// Preserve token from URL for API calls
const urlToken = new URLSearchParams(window.location.search).get('token') || '';
function apiUrl(path) {
  return urlToken ? `${path}?token=${encodeURIComponent(urlToken)}` : path;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

async function fetchTasks() {
  const r = await fetch(apiUrl('/api/tasks'));
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
  return ['working', 'waiting', 'idle', 'starting', 'done', 'error'].includes(status)
    ? status : 'idle';
}

function renderTask(task) {
  const expanded = expandedSlugs.has(task.slug);
  const dead = !task.alive;

  const card = document.createElement('div');
  card.className = `task-card${expanded ? ' expanded' : ''}${dead ? ' dead' : ''}`;
  card.dataset.slug = task.slug;

  card.innerHTML = `
    <div class="task-header">
      <span class="status-dot ${statusDotClass(task.status)}"></span>
      <span class="task-slug">${esc(task.slug)}</span>
      <div class="task-meta">
        <span class="status-badge ${statusDotClass(task.status)}">${esc(task.status)}</span>
        ${task.project ? `<span class="task-project">${esc(task.project)}</span>` : ''}
        <span class="task-age">${esc(task.age)}</span>
        <span class="task-expand">▶</span>
      </div>
    </div>
    <div class="task-detail">
      <div class="task-detail-inner">
        <div class="task-cwd">📁 ${esc(task.cwd)}</div>
        ${task.goal ? `<div class="task-goal">${esc(task.goal)}</div>` : ''}
        <div class="pane-preview" id="preview-${esc(task.slug)}">
          <span class="pane-preview-empty">Loading preview…</span>
        </div>
        <div class="task-actions">
          ${task.alive ? `<button class="btn btn-secondary" data-action="send" data-slug="${esc(task.slug)}">✏ Send input</button>` : ''}
          ${task.alive ? `<button class="btn btn-danger" data-action="kill" data-slug="${esc(task.slug)}">✕ Kill session</button>` : ''}
          <button class="btn btn-ghost" data-action="attach" data-slug="${esc(task.slug)}">⌗ Attach</button>
        </div>
      </div>
    </div>
  `;

  // Header click → expand/collapse
  card.querySelector('.task-header').addEventListener('click', () => toggleExpand(task.slug));

  // Action buttons
  card.querySelectorAll('[data-action]').forEach(btn => {
    btn.addEventListener('click', e => {
      e.stopPropagation();
      handleAction(btn.dataset.action, btn.dataset.slug);
    });
  });

  // Load preview if expanded
  if (expanded && task.alive) {
    loadPreview(task.slug);
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
  } else if (action === 'attach') {
    // Best-effort tmux deep link
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
