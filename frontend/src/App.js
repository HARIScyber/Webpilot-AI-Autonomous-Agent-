/**
 * App.js — Root Application Component
 * =====================================
 * This component is the single source of truth for application state.
 * It manages the list of tasks and which task is currently selected.
 *
 * Component tree:
 *
 *   App
 *   ├── header                    (inline — just the nav bar)
 *   ├── TaskForm                  (left panel — submit new tasks)
 *   ├── ResultViewer              (centre panel — live stream + result)
 *   └── TaskHistory               (right panel — list of past tasks)
 *
 * State:
 *   tasks         — array of all tasks fetched from the API
 *   activeTaskId  — the task currently being viewed / streamed
 *   loading       — spinner flag while fetching tasks on mount
 *   error         — global error message string
 *
 * Data flow:
 *   1. On mount, App fetches all existing tasks from GET /api/tasks
 *   2. User fills out TaskForm and submits → POST /api/tasks
 *   3. App adds the new task to state and sets it as activeTaskId
 *   4. ResultViewer subscribes to GET /api/tasks/{id}/stream (SSE)
 *   5. SSE events update the task's status and logs in real-time
 *   6. TaskHistory shows all tasks with their current status
 */

import axios from 'axios';
import { useCallback, useEffect, useState } from 'react';
import { Toaster, toast } from 'react-hot-toast';

import ResultViewer from './components/ResultViewer';
import TaskForm from './components/TaskForm';
import TaskHistory from './components/TaskHistory';

// ---- Axios base URL ----
// In development, package.json "proxy": "http://localhost:8000" means
// we can just use /api/... paths — no CORS issues.
// In production, set REACT_APP_API_URL in your .env.
const API_BASE = process.env.REACT_APP_API_URL || '';

// ---- Styles (inline for zero config — no CSS modules needed) ------

const styles = {
  app: {
    minHeight: '100vh',
    backgroundColor: 'var(--bg-primary)',
    display: 'flex',
    flexDirection: 'column',
  },
  header: {
    background: 'var(--bg-card)',
    borderBottom: '1px solid var(--border)',
    padding: '0 24px',
    height: '60px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    position: 'sticky',
    top: 0,
    zIndex: 100,
  },
  headerLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
  },
  logo: {
    fontSize: '22px',
    fontWeight: '700',
    color: 'var(--text-primary)',
    letterSpacing: '-0.5px',
  },
  logoAccent: {
    color: 'var(--accent)',
  },
  badge: {
    background: 'var(--accent)',
    color: '#fff',
    fontSize: '11px',
    fontWeight: '600',
    padding: '2px 8px',
    borderRadius: '12px',
    letterSpacing: '0.5px',
  },
  headerRight: {
    color: 'var(--text-muted)',
    fontSize: '13px',
  },
  main: {
    flex: 1,
    display: 'grid',
    // Three-column layout: form | viewer | history
    gridTemplateColumns: '360px 1fr 320px',
    gap: '0',
    height: 'calc(100vh - 60px)',
    overflow: 'hidden',
  },
  panel: {
    borderRight: '1px solid var(--border)',
    overflowY: 'auto',
    padding: '20px',
  },
  panelLast: {
    borderRight: 'none',
    overflowY: 'auto',
    padding: '20px',
  },
};

// ======================================================================
// App Component
// ======================================================================

export default function App() {
  // ---- State ---------------------------------------------------------
  const [tasks, setTasks]               = useState([]);        // all tasks list
  const [activeTaskId, setActiveTaskId] = useState(null);      // selected task
  const [loading, setLoading]           = useState(true);      // initial fetch
  const [globalError, setGlobalError]   = useState(null);      // fetch errors

  // ---- Fetch all tasks on mount -------------------------------------
  const fetchTasks = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/tasks?page_size=50`);
      setTasks(response.data.tasks || []);
      setGlobalError(null);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to load tasks';
      setGlobalError(msg);
      console.error('[App] fetchTasks error:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTasks();
    // Poll for task status updates every 10 seconds
    // (SSE handles live updates, but this catches any missed changes)
    const interval = setInterval(fetchTasks, 10_000);
    return () => clearInterval(interval);
  }, [fetchTasks]);

  // ---- Handle new task submission -----------------------------------
  /**
   * Called by TaskForm when the user submits a new task.
   * Adds the task to local state immediately (optimistic update)
   * and sets it as active so ResultViewer starts streaming.
   */
  const handleTaskCreated = useCallback((newTask) => {
    setTasks(prev => [newTask, ...prev]);  // prepend so it's first in history
    setActiveTaskId(newTask.id);
    toast.success(`Task started: "${newTask.title}"`);
  }, []);

  // ---- Handle task deletion -----------------------------------------
  const handleTaskDeleted = useCallback(async (taskId) => {
    try {
      await axios.delete(`${API_BASE}/api/tasks/${taskId}`);
      setTasks(prev => prev.filter(t => t.id !== taskId));
      if (activeTaskId === taskId) {
        setActiveTaskId(null);   // clear viewer if active task was deleted
      }
      toast.success('Task deleted');
    } catch (err) {
      toast.error('Failed to delete task');
    }
  }, [activeTaskId]);

  // ---- Handle SSE status updates ------------------------------------
  /**
   * ResultViewer calls this whenever a task's status changes via SSE.
   * We update the matching task in the tasks array so TaskHistory
   * shows the live status badge without a full refresh.
   */
  const handleTaskStatusUpdate = useCallback((taskId, newStatus, extra = {}) => {
    setTasks(prev =>
      prev.map(t =>
        t.id === taskId ? { ...t, status: newStatus, ...extra } : t
      )
    );
  }, []);

  // ---- Render -------------------------------------------------------
  const activeTask = tasks.find(t => t.id === activeTaskId) || null;

  return (
    <div style={styles.app}>
      {/* ---- Toast notifications (top-right corner) ---- */}
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: 'var(--bg-card)',
            color: 'var(--text-primary)',
            border: '1px solid var(--border)',
          },
        }}
      />

      {/* ---- Navigation Header ---- */}
      <header style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>
            Web<span style={styles.logoAccent}>Pilot</span> AI
          </span>
          <span style={styles.badge}>BETA</span>
        </div>
        <div style={styles.headerRight}>
          Autonomous Web Agent · TinyFish Powered
        </div>
      </header>

      {/* ---- Main Three-Column Layout ---- */}
      <main style={styles.main}>

        {/* LEFT PANEL: Task submission form */}
        <div style={styles.panel}>
          <TaskForm
            apiBase={API_BASE}
            onTaskCreated={handleTaskCreated}
          />
        </div>

        {/* CENTRE PANEL: Live stream + result viewer */}
        <div style={styles.panel}>
          {globalError && (
            <div style={{ color: 'var(--error)', marginBottom: '16px', padding: '12px',
              background: '#1f1111', borderRadius: '8px', fontSize: '14px' }}>
              ⚠ {globalError}
            </div>
          )}
          <ResultViewer
            apiBase={API_BASE}
            task={activeTask}
            onStatusUpdate={handleTaskStatusUpdate}
          />
        </div>

        {/* RIGHT PANEL: Task history list */}
        <div style={styles.panelLast}>
          <TaskHistory
            tasks={tasks}
            loading={loading}
            activeTaskId={activeTaskId}
            onSelectTask={setActiveTaskId}
            onDeleteTask={handleTaskDeleted}
          />
        </div>

      </main>
    </div>
  );
}
