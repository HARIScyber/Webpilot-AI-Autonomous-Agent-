/**
 * TaskHistory.js — Past Tasks Sidebar Panel
 * ===========================================
 * Right panel of the dashboard.
 *
 * Shows all tasks ordered by most recently created.
 * Each item shows:
 *   - Status badge (colour-coded)
 *   - Task title
 *   - Target URL (truncated)
 *   - Time since creation
 *   - Category tag
 *   - Delete button
 *
 * Clicking a task calls onSelectTask(id) in App.js which sets
 * the activeTaskId so ResultViewer loads that task.
 */

import { useState } from 'react';

// ---- Status badge config ------------------------------------------

const STATUS_CONFIG = {
  pending:   { label: 'Pending',   bg: '#1e2030', color: '#94a3b8', icon: '○' },
  running:   { label: 'Running',   bg: '#1e1a05', color: '#f59e0b', icon: '◉' },
  completed: { label: 'Done',      bg: '#0a1f0a', color: '#22c55e', icon: '✓' },
  failed:    { label: 'Failed',    bg: '#1a0a0a', color: '#ef4444', icon: '✗' },
};

// ---- Inline styles ------------------------------------------------

const S = {
  container: { display: 'flex', flexDirection: 'column', gap: '12px' },
  headerRow: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  heading: { fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)' },
  count: {
    background: 'var(--bg-input)', color: 'var(--text-muted)',
    fontSize: '12px', padding: '2px 8px', borderRadius: '10px',
    border: '1px solid var(--border)',
  },
  loadingMsg: { color: 'var(--text-muted)', fontSize: '14px', textAlign: 'center', padding: '24px 0' },
  emptyMsg: {
    color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center',
    padding: '32px 0', lineHeight: '1.6',
  },
  taskCard: (isActive) => ({
    background: isActive ? '#162032' : 'var(--bg-card)',
    border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
    borderRadius: '10px', padding: '12px', cursor: 'pointer',
    transition: 'border-color 0.2s, background 0.2s',
    position: 'relative',
  }),
  statusBadge: (status) => {
    const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.pending;
    return {
      display: 'inline-flex', alignItems: 'center', gap: '4px',
      background: cfg.bg, color: cfg.color,
      fontSize: '11px', fontWeight: '600', padding: '2px 8px',
      borderRadius: '10px', letterSpacing: '0.5px',
    };
  },
  taskTitle: {
    fontSize: '13px', fontWeight: '600', color: 'var(--text-primary)',
    marginTop: '6px', lineHeight: '1.4',
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  },
  taskUrl: {
    fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px',
    whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
  },
  tagsRow: {
    display: 'flex', gap: '6px', marginTop: '8px', alignItems: 'center',
    justifyContent: 'space-between',
  },
  categoryTag: {
    background: '#0f1e33', color: 'var(--accent)',
    fontSize: '10px', fontWeight: '600', padding: '2px 7px',
    borderRadius: '8px', letterSpacing: '0.3px',
  },
  timeAgo: { fontSize: '11px', color: 'var(--text-muted)' },
  deleteBtn: {
    position: 'absolute', top: '10px', right: '10px',
    background: 'transparent', border: 'none', color: 'var(--text-muted)',
    cursor: 'pointer', fontSize: '14px', padding: '2px 4px', borderRadius: '4px',
    lineHeight: 1,
    transition: 'color 0.2s',
  },
  filterRow: { display: 'flex', gap: '6px', flexWrap: 'wrap' },
  filterBtn: (active) => ({
    padding: '4px 10px', borderRadius: '14px', fontSize: '11px',
    fontWeight: '600', cursor: 'pointer', border: '1px solid var(--border)',
    background: active ? 'var(--accent)' : 'transparent',
    color:      active ? '#fff'          : 'var(--text-muted)',
    transition: 'background 0.2s, color 0.2s',
  }),
};

// ---- Utility -------------------------------------------------------

function timeAgo(dateStr) {
  /** Returns a human-friendly string: "2m ago", "just now", "3h ago" */
  if (!dateStr) return '';
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
  if (diff < 10)    return 'just now';
  if (diff < 60)    return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// =====================================================================
// Component
// =====================================================================

export default function TaskHistory({
  tasks,
  loading,
  activeTaskId,
  onSelectTask,
  onDeleteTask,
}) {
  const [statusFilter, setStatusFilter] = useState('all');  // filter by status
  const [hoveredId,    setHoveredId]    = useState(null);   // for delete button visibility

  // Apply status filter
  const visibleTasks = statusFilter === 'all'
    ? tasks
    : tasks.filter(t => t.status === statusFilter);

  // Filter options shown above the list
  const FILTERS = ['all', 'running', 'completed', 'failed', 'pending'];

  return (
    <div style={S.container}>
      {/* ---- Header ---- */}
      <div style={S.headerRow}>
        <h2 style={S.heading}>Task History</h2>
        <span style={S.count}>{tasks.length}</span>
      </div>

      {/* ---- Status filter buttons ---- */}
      <div style={S.filterRow}>
        {FILTERS.map(f => (
          <button
            key={f}
            style={S.filterBtn(statusFilter === f)}
            onClick={() => setStatusFilter(f)}
          >
            {f === 'all' ? 'All' : f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>

      {/* ---- Loading / empty states ---- */}
      {loading && (
        <p style={S.loadingMsg}>Loading tasks…</p>
      )}
      {!loading && visibleTasks.length === 0 && (
        <p style={S.emptyMsg}>
          {statusFilter === 'all'
            ? 'No tasks yet.\nSubmit one using the form on the left.'
            : `No ${statusFilter} tasks.`}
        </p>
      )}

      {/* ---- Task cards ---- */}
      {visibleTasks.map(task => {
        const cfg = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
        const isActive = task.id === activeTaskId;
        const isHovered = task.id === hoveredId;

        return (
          <div
            key={task.id}
            style={S.taskCard(isActive)}
            onClick={() => onSelectTask(task.id)}
            onMouseEnter={() => setHoveredId(task.id)}
            onMouseLeave={() => setHoveredId(null)}
            role="button"
            tabIndex={0}
            onKeyDown={e => e.key === 'Enter' && onSelectTask(task.id)}
            aria-label={`Select task: ${task.title}`}
          >
            {/* Delete button — only visible on hover */}
            {isHovered && (
              <button
                style={S.deleteBtn}
                title="Delete task"
                onClick={e => {
                  e.stopPropagation();  // don't trigger card click
                  onDeleteTask(task.id);
                }}
                aria-label="Delete task"
              >
                ✕
              </button>
            )}

            {/* Status badge */}
            <div style={S.statusBadge(task.status)}>
              <span>{cfg.icon}</span>
              <span>{cfg.label}</span>
            </div>

            {/* Title */}
            <div style={S.taskTitle} title={task.title}>
              {task.title}
            </div>

            {/* URL */}
            <div style={S.taskUrl} title={task.target_url}>
              {task.target_url.replace(/^https?:\/\//, '')}
            </div>

            {/* Category tag + timestamp */}
            <div style={S.tagsRow}>
              {task.category ? (
                <span style={S.categoryTag}>
                  {task.category.replace('_', ' ')}
                </span>
              ) : (
                <span />  /* empty spacer */
              )}
              <span style={S.timeAgo}>{timeAgo(task.created_at)}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
