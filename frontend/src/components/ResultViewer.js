/**
 * ResultViewer.js — Live Agent Execution & Result Display
 * =========================================================
 * Centre panel of the dashboard.
 *
 * Responsibilities:
 *   1. When a PENDING task is selected, connect to the SSE stream.
 *   2. Display each incoming log event in a live timeline.
 *   3. Show a progress bar while the agent is running.
 *   4. On COMPLETE, fetch the full task detail and display the result.
 *   5. On ERROR, show the error message clearly.
 *   6. If a COMPLETED task is selected, fetch and display its result immediately.
 *
 * SSE (Server-Sent Events) explained:
 *   EventSource is a browser API that opens a persistent HTTP connection.
 *   The server pushes events as:   data: {...JSON...}\n\n
 *   EventSource fires the onmessage callback for each event.
 *   We close the connection when the task reaches a terminal state.
 */

import axios from 'axios';
import { useCallback, useEffect, useRef, useState } from 'react';

// ---- Inline styles --------------------------------------------------

const S = {
  empty: {
    display: 'flex', flexDirection: 'column', alignItems: 'center',
    justifyContent: 'center', height: '100%', gap: '12px',
    color: 'var(--text-muted)', textAlign: 'center', padding: '40px',
  },
  emptyIcon: { fontSize: '48px' },
  emptyTitle: { fontSize: '18px', fontWeight: '600', color: 'var(--text-primary)' },
  emptyText: { fontSize: '14px', maxWidth: '300px', lineHeight: '1.6' },
  container: { display: 'flex', flexDirection: 'column', gap: '20px', height: '100%' },
  header: { display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' },
  title: { fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)' },
  goal: { fontSize: '13px', color: 'var(--text-muted)', marginTop: '4px', lineHeight: '1.5' },
  statusRow: { display: 'flex', alignItems: 'center', gap: '8px', marginTop: '8px' },
  dot: (status) => ({
    width: '8px', height: '8px', borderRadius: '50%',
    background: status === 'completed' ? 'var(--success)'
               : status === 'running'  ? 'var(--warning)'
               : status === 'failed'   ? 'var(--error)'
               : 'var(--text-muted)',
    // Pulse animation for running state
    animation: status === 'running' ? 'pulse 1.5s infinite' : 'none',
  }),
  statusText: (status) => ({
    fontSize: '12px', fontWeight: '600', textTransform: 'uppercase',
    letterSpacing: '0.8px',
    color: status === 'completed' ? 'var(--success)'
          : status === 'running'  ? 'var(--warning)'
          : status === 'failed'   ? 'var(--error)'
          : 'var(--text-muted)',
  }),
  progressBar: {
    width: '100%', height: '4px', background: 'var(--border)',
    borderRadius: '2px', overflow: 'hidden',
  },
  progressFill: (pct) => ({
    height: '100%', width: `${pct}%`,
    background: 'var(--accent)', borderRadius: '2px',
    transition: 'width 0.5s ease',
  }),
  divider: { border: 'none', borderTop: '1px solid var(--border)', margin: '4px 0' },
  sectionLabel: {
    fontSize: '11px', fontWeight: '700', color: 'var(--text-muted)',
    textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '10px',
  },
  logList: {
    flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column',
    gap: '6px', minHeight: '200px', maxHeight: '320px',
    padding: '12px', background: '#0a1628',
    borderRadius: '8px', border: '1px solid var(--border)',
  },
  logEntry: (type) => ({
    display: 'flex', gap: '10px', alignItems: 'flex-start',
    fontSize: '13px', lineHeight: '1.5',
    color: type === 'ERROR'    ? 'var(--error)'
          : type === 'COMPLETE' ? 'var(--success)'
          : type === 'STARTED'  ? 'var(--accent)'
          : 'var(--text-primary)',
  }),
  logTime: {
    color: 'var(--text-muted)', fontSize: '11px', fontFamily: 'var(--font-mono)',
    whiteSpace: 'nowrap', marginTop: '2px', minWidth: '60px',
  },
  logMsg: { flex: 1 },
  // Result card
  resultCard: {
    background: 'var(--bg-card)', borderRadius: '10px',
    border: '1px solid var(--border)', overflow: 'hidden',
  },
  resultHeader: {
    padding: '14px 16px', borderBottom: '1px solid var(--border)',
    display: 'flex', justifyContent: 'space-between', alignItems: 'center',
  },
  resultTitle: { fontSize: '14px', fontWeight: '600', color: 'var(--success)' },
  resultDuration: { fontSize: '12px', color: 'var(--text-muted)' },
  resultBody: { padding: '16px' },
  rawText: {
    fontSize: '14px', lineHeight: '1.7', color: 'var(--text-primary)',
    whiteSpace: 'pre-wrap', wordBreak: 'break-word',
  },
  jsonBlock: {
    background: '#0a1628', borderRadius: '8px', padding: '14px',
    fontFamily: 'var(--font-mono)', fontSize: '13px', lineHeight: '1.6',
    color: '#86efac', overflowX: 'auto',
    border: '1px solid var(--border)', marginTop: '12px',
  },
  screenshotLink: {
    display: 'inline-flex', alignItems: 'center', gap: '6px',
    color: 'var(--accent)', fontSize: '13px', marginTop: '10px',
  },
  errorCard: {
    background: '#1a0f0f', border: '1px solid var(--error)',
    borderRadius: '10px', padding: '16px',
    color: 'var(--error)', fontSize: '14px', lineHeight: '1.6',
  },
};

// Add CSS animation for the pulsing dot via a style tag
const pulseStyle = `
  @keyframes pulse {
    0%   { opacity: 1; transform: scale(1); }
    50%  { opacity: 0.5; transform: scale(1.3); }
    100% { opacity: 1; transform: scale(1); }
  }
`;

// ---- Utility --------------------------------------------------------

function formatTime(dateString) {
  /** Format a timestamp as HH:MM:SS for the log timeline. */
  const d = dateString ? new Date(dateString) : new Date();
  return d.toTimeString().slice(0, 8);
}

function eventIcon(eventType) {
  const icons = {
    STARTED:  '▶',
    PROGRESS: '·',
    COMPLETE: '✓',
    ERROR:    '✗',
  };
  return icons[eventType] || '·';
}

// =====================================================================
// Component
// =====================================================================

export default function ResultViewer({ apiBase, task, onStatusUpdate }) {
  const [logs,         setLogs]         = useState([]);   // live SSE log entries
  const [result,       setResult]       = useState(null); // final TaskResult object
  const [progress,     setProgress]     = useState(0);    // 0–100 progress estimate
  const [streamError,  setStreamError]  = useState(null); // SSE connection error
  const logListRef  = useRef(null);  // ref to the log list div for auto-scroll
  const eventSrcRef = useRef(null);  // reference to the active EventSource

  // ---- Cleanup SSE on task change ----------------------------------
  useEffect(() => {
    // Close any existing SSE connection when the task changes
    if (eventSrcRef.current) {
      eventSrcRef.current.close();
      eventSrcRef.current = null;
    }
    // Reset viewer state
    setLogs([]);
    setResult(null);
    setProgress(0);
    setStreamError(null);

    if (!task) return;

    // ---- If task already completed, just fetch the detail ----------
    if (task.status === 'completed' || task.status === 'failed') {
      fetchTaskDetail(task.id);
      return;
    }

    // ---- If task is pending or running, open SSE stream ------------
    if (task.status === 'pending' || task.status === 'running') {
      openStream(task.id);
    }

    // Cleanup function — closes SSE when component unmounts
    return () => {
      if (eventSrcRef.current) {
        eventSrcRef.current.close();
      }
    };
  }, [task?.id]); // re-run when the selected task ID changes

  // ---- Auto-scroll log list to bottom on new entries ---------------
  useEffect(() => {
    if (logListRef.current) {
      logListRef.current.scrollTop = logListRef.current.scrollHeight;
    }
  }, [logs]);

  // ---- Fetch completed task detail (logs + result) -----------------
  const fetchTaskDetail = useCallback(async (taskId) => {
    try {
      const response = await axios.get(`${apiBase}/api/tasks/${taskId}`);
      const detail = response.data;
      setLogs(detail.logs || []);
      setResult(detail.result || null);
      setProgress(detail.status === 'completed' ? 100 : 0);
    } catch (err) {
      console.error('[ResultViewer] fetchTaskDetail error:', err);
    }
  }, [apiBase]);

  // ---- Open SSE stream for live task execution ---------------------
  const openStream = useCallback((taskId) => {
    const url = `${apiBase}/api/tasks/${taskId}/stream`;
    // EventSource is the native browser API for SSE — no library needed
    const es = new EventSource(url);
    eventSrcRef.current = es;

    let progressCounter = 0;  // we increment this for each PROGRESS event

    es.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        const { event, message, data } = payload;

        // Add log entry to the timeline
        setLogs(prev => [...prev, {
          id: Date.now(),
          event_type: event,
          message,
          timestamp: new Date().toISOString(),
          metadata_json: data,
        }]);

        // Update progress estimate
        if (event === 'STARTED')  { setProgress(5); }
        if (event === 'PROGRESS') {
          progressCounter += Math.random() * 8 + 3; // random increment 3–11%
          setProgress(Math.min(progressCounter + 10, 90)); // cap at 90% until COMPLETE
        }
        if (event === 'COMPLETE') {
          setProgress(100);
          onStatusUpdate?.(taskId, 'completed', {
            completed_at: new Date().toISOString(),
          });
          // Fetch full detail to get the structured result object
          fetchTaskDetail(taskId);
          es.close();
          eventSrcRef.current = null;
        }
        if (event === 'ERROR') {
          setStreamError(message);
          onStatusUpdate?.(taskId, 'failed', { error_message: message });
          es.close();
          eventSrcRef.current = null;
        }

        // Update running status in parent App
        if (event === 'STARTED') {
          onStatusUpdate?.(taskId, 'running');
        }
      } catch (parseError) {
        console.warn('[ResultViewer] Failed to parse SSE event:', e.data);
      }
    };

    es.onerror = (err) => {
      // EventSource reconnects automatically on network errors,
      // but if the server closes the stream intentionally, readyState will be CLOSED.
      if (es.readyState === EventSource.CLOSED) {
        console.log('[ResultViewer] SSE stream closed');
        eventSrcRef.current = null;
      } else {
        console.warn('[ResultViewer] SSE error — will retry:', err);
      }
    };
  }, [apiBase, fetchTaskDetail, onStatusUpdate]);

  // ---- Render: no task selected ------------------------------------
  if (!task) {
    return (
      <>
        <style>{pulseStyle}</style>
        <div style={S.empty}>
          <div style={S.emptyIcon}>🤖</div>
          <h3 style={S.emptyTitle}>No Task Selected</h3>
          <p style={S.emptyText}>
            Submit a new task using the form on the left, or click an existing
            task in the history panel to view its result.
          </p>
          <p style={{ ...S.emptyText, marginTop: '8px', color: 'var(--accent)' }}>
            Try: "Find the price of AirPods Pro on Amazon"
          </p>
        </div>
      </>
    );
  }

  // ---- Render: task selected ----------------------------------------
  return (
    <>
      <style>{pulseStyle}</style>
      <div style={S.container}>

        {/* ---- Task header ---- */}
        <div style={S.header}>
          <div>
            <div style={S.title}>{task.title}</div>
            <div style={S.goal}>
              <strong>URL:</strong> {task.target_url}<br />
              <strong>Goal:</strong> {task.goal}
            </div>
            <div style={S.statusRow}>
              <div style={S.dot(task.status)} />
              <span style={S.statusText(task.status)}>{task.status}</span>
              {task.duration_seconds && (
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  · {task.duration_seconds}s
                </span>
              )}
            </div>
          </div>
        </div>

        {/* ---- Progress bar ---- */}
        {(task.status === 'running' || task.status === 'pending') && (
          <div style={S.progressBar}>
            <div style={S.progressFill(progress)} />
          </div>
        )}

        <hr style={S.divider} />

        {/* ---- Live Event Log ---- */}
        <div>
          <div style={S.sectionLabel}>
            Agent Activity Log
            {task.status === 'running' && (
              <span style={{ color: 'var(--warning)', marginLeft: '8px' }}>● LIVE</span>
            )}
          </div>
          <div ref={logListRef} style={S.logList}>
            {logs.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', fontSize: '13px', textAlign: 'center', paddingTop: '20px' }}>
                {task.status === 'pending'
                  ? 'Waiting for agent to start…'
                  : 'No activity logged yet.'}
              </div>
            ) : (
              logs.map((log, idx) => (
                <div key={log.id || idx} style={S.logEntry(log.event_type)}>
                  <span style={S.logTime}>{formatTime(log.timestamp)}</span>
                  <span style={{ marginTop: '1px', minWidth: '14px' }}>
                    {eventIcon(log.event_type)}
                  </span>
                  <span style={S.logMsg}>{log.message}</span>
                </div>
              ))
            )}
          </div>
        </div>

        {/* ---- Error message ---- */}
        {(streamError || task.error_message) && (
          <div style={S.errorCard}>
            <strong>⚠ Task Failed</strong><br />
            {streamError || task.error_message}
          </div>
        )}

        {/* ---- Final Result ---- */}
        {result && (
          <div>
            <div style={S.sectionLabel}>Extracted Result</div>
            <div style={S.resultCard}>
              <div style={S.resultHeader}>
                <span style={S.resultTitle}>✓ Task Completed Successfully</span>
                {task.duration_seconds && (
                  <span style={S.resultDuration}>
                    Completed in {task.duration_seconds}s
                  </span>
                )}
              </div>
              <div style={S.resultBody}>
                {/* Raw text summary */}
                {result.raw_text && (
                  <p style={S.rawText}>{result.raw_text}</p>
                )}

                {/* Structured JSON data */}
                {result.data && (
                  <>
                    <div style={{ ...S.sectionLabel, marginTop: '12px' }}>
                      Structured Data
                    </div>
                    <pre style={S.jsonBlock}>
                      {JSON.stringify(result.data, null, 2)}
                    </pre>
                  </>
                )}

                {/* Screenshot link */}
                {result.screenshot_url && (
                  <a
                    href={result.screenshot_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={S.screenshotLink}
                  >
                    📸 View Screenshot
                  </a>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </>
  );
}
