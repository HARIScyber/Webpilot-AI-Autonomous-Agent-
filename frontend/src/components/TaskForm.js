/**
 * TaskForm.js — New Task Submission Panel
 * ========================================
 * Left panel of the dashboard.  Lets the user:
 *   1. Enter a target URL (e.g. https://amazon.com)
 *   2. Type a natural language goal (e.g. "Find the price of AirPods Pro")
 *   3. Give the task a short title and optional category
 *   4. Submit — triggers POST /api/tasks
 *
 * After submission the component calls onTaskCreated(task) so App.js
 * can set the new task as active and start streaming.
 *
 * Quick-fill examples let students try the system instantly
 * without having to type a full task.
 */

import axios from 'axios';
import { useState } from 'react';
import { toast } from 'react-hot-toast';

// ---- Predefined example tasks so students can test quickly ----------

const EXAMPLE_TASKS = [
  {
    label: '🛒 Price Check',
    title: 'Find AirPods Pro price on Amazon',
    target_url: 'https://www.amazon.com',
    goal: 'Search for "AirPods Pro 2nd generation" and return the lowest price and product title.',
    category: 'price_check',
  },
  {
    label: '💼 Job Search',
    title: 'Software Engineer jobs on LinkedIn',
    target_url: 'https://www.linkedin.com/jobs',
    goal: 'Search for "Software Engineer" jobs in San Francisco and return the first 5 job titles, companies, and links.',
    category: 'job_search',
  },
  {
    label: '📦 Availability Check',
    title: 'Check PS5 stock on Best Buy',
    target_url: 'https://www.bestbuy.com',
    goal: 'Search for "PlayStation 5" and tell me if it is currently in stock and at what price.',
    category: 'availability_check',
  },
  {
    label: '📰 News Headlines',
    title: 'Latest AI news from Hacker News',
    target_url: 'https://news.ycombinator.com',
    goal: 'Return the top 5 story titles and their URLs from the Hacker News front page.',
    category: 'research',
  },
];

// ---- Inline styles --------------------------------------------------

const S = {
  container: { display: 'flex', flexDirection: 'column', gap: '20px' },
  heading: { fontSize: '16px', fontWeight: '600', color: 'var(--text-primary)', marginBottom: '-8px' },
  subheading: { fontSize: '13px', color: 'var(--text-muted)' },
  label: {
    display: 'block', fontSize: '12px', fontWeight: '600',
    color: 'var(--text-muted)', textTransform: 'uppercase',
    letterSpacing: '0.8px', marginBottom: '6px',
  },
  input: {
    width: '100%', padding: '10px 12px',
    background: 'var(--bg-input)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: '8px',
    fontSize: '14px', outline: 'none', transition: 'border-color 0.2s',
  },
  textarea: {
    width: '100%', padding: '10px 12px', minHeight: '100px', resize: 'vertical',
    background: 'var(--bg-input)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: '8px',
    fontSize: '14px', outline: 'none', fontFamily: 'inherit', lineHeight: '1.5',
  },
  select: {
    width: '100%', padding: '10px 12px',
    background: 'var(--bg-input)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: '8px', fontSize: '14px',
  },
  submitBtn: {
    width: '100%', padding: '12px',
    background: 'var(--accent)', color: '#fff',
    border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: '600',
    cursor: 'pointer', transition: 'background 0.2s', letterSpacing: '0.3px',
  },
  submitBtnDisabled: {
    width: '100%', padding: '12px',
    background: 'var(--border)', color: 'var(--text-muted)',
    border: 'none', borderRadius: '8px', fontSize: '14px', fontWeight: '600',
    cursor: 'not-allowed',
  },
  divider: { border: 'none', borderTop: '1px solid var(--border)' },
  examplesGrid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' },
  exampleBtn: {
    padding: '8px 10px', background: 'var(--bg-card)', color: 'var(--text-primary)',
    border: '1px solid var(--border)', borderRadius: '8px', fontSize: '12px',
    cursor: 'pointer', textAlign: 'left', transition: 'border-color 0.2s',
  },
  fieldGroup: { display: 'flex', flexDirection: 'column' },
  errorMsg: { color: 'var(--error)', fontSize: '12px', marginTop: '4px' },
};

// =====================================================================
// Component
// =====================================================================

export default function TaskForm({ apiBase, onTaskCreated }) {
  // ---- Form field state ---------------------------------------------
  const [title,      setTitle]      = useState('');
  const [targetUrl,  setTargetUrl]  = useState('');
  const [goal,       setGoal]       = useState('');
  const [category,   setCategory]   = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [errors,     setErrors]     = useState({});  // field-level validation errors

  // ---- Field-level validation ---------------------------------------
  const validate = () => {
    const newErrors = {};
    if (!title.trim())      newErrors.title = 'Title is required';
    if (!targetUrl.trim())  newErrors.targetUrl = 'URL is required';
    else if (!targetUrl.startsWith('http://') && !targetUrl.startsWith('https://'))
      newErrors.targetUrl = 'URL must start with http:// or https://';
    if (!goal.trim())       newErrors.goal = 'Goal is required';
    else if (goal.trim().length < 10)
      newErrors.goal = 'Please write a more descriptive goal (10+ characters)';
    return newErrors;
  };

  // ---- Form submit --------------------------------------------------
  const handleSubmit = async (e) => {
    e.preventDefault();

    // Validate before sending
    const validationErrors = validate();
    if (Object.keys(validationErrors).length > 0) {
      setErrors(validationErrors);
      return;
    }
    setErrors({});
    setSubmitting(true);

    try {
      const response = await axios.post(`${apiBase}/api/tasks`, {
        title: title.trim(),
        target_url: targetUrl.trim(),
        goal: goal.trim(),
        category: category || null,
      });

      // Pass the created task back to App.js
      onTaskCreated(response.data);

      // Clear the form
      setTitle(''); setTargetUrl(''); setGoal(''); setCategory('');
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Failed to create task';
      toast.error(msg);
      console.error('[TaskForm] submit error:', err);
    } finally {
      setSubmitting(false);
    }
  };

  // ---- Fill form with an example task -------------------------------
  const fillExample = (example) => {
    setTitle(example.title);
    setTargetUrl(example.target_url);
    setGoal(example.goal);
    setCategory(example.category);
    setErrors({});
  };

  // ---- Render -------------------------------------------------------
  return (
    <div style={S.container}>
      <div>
        <h2 style={S.heading}>New Agent Task</h2>
        <p style={{ ...S.subheading, marginTop: '6px' }}>
          Describe what the agent should do. TinyFish will handle the browser.
        </p>
      </div>

      {/* ---- Quick examples ---- */}
      <div>
        <p style={S.label}>Quick Examples</p>
        <div style={S.examplesGrid}>
          {EXAMPLE_TASKS.map((ex) => (
            <button
              key={ex.label}
              style={S.exampleBtn}
              onClick={() => fillExample(ex)}
              title={ex.goal}
            >
              {ex.label}
            </button>
          ))}
        </div>
      </div>

      <hr style={S.divider} />

      {/* ---- Main form ---- */}
      <form onSubmit={handleSubmit} style={S.container} noValidate>

        {/* Task Title */}
        <div style={S.fieldGroup}>
          <label style={S.label} htmlFor="title">Task Title</label>
          <input
            id="title"
            style={S.input}
            type="text"
            placeholder="e.g. Find AirPods Pro price"
            value={title}
            onChange={e => setTitle(e.target.value)}
            maxLength={200}
          />
          {errors.title && <span style={S.errorMsg}>{errors.title}</span>}
        </div>

        {/* Target URL */}
        <div style={S.fieldGroup}>
          <label style={S.label} htmlFor="targetUrl">Starting URL</label>
          <input
            id="targetUrl"
            style={S.input}
            type="url"
            placeholder="https://amazon.com"
            value={targetUrl}
            onChange={e => setTargetUrl(e.target.value)}
          />
          {errors.targetUrl && <span style={S.errorMsg}>{errors.targetUrl}</span>}
        </div>

        {/* Goal */}
        <div style={S.fieldGroup}>
          <label style={S.label} htmlFor="goal">Agent Goal</label>
          <textarea
            id="goal"
            style={S.textarea}
            placeholder="Describe in plain English what the agent should do and return…"
            value={goal}
            onChange={e => setGoal(e.target.value)}
            maxLength={2000}
          />
          {errors.goal && <span style={S.errorMsg}>{errors.goal}</span>}
          <span style={{ ...S.subheading, marginTop: '4px', textAlign: 'right' }}>
            {goal.length}/2000
          </span>
        </div>

        {/* Category */}
        <div style={S.fieldGroup}>
          <label style={S.label} htmlFor="category">Category (optional)</label>
          <select
            id="category"
            style={S.select}
            value={category}
            onChange={e => setCategory(e.target.value)}
          >
            <option value="">— Select category —</option>
            <option value="price_check">Price Check</option>
            <option value="job_search">Job Search</option>
            <option value="availability_check">Availability Check</option>
            <option value="competitor_monitoring">Competitor Monitoring</option>
            <option value="research">Research</option>
            <option value="other">Other</option>
          </select>
        </div>

        {/* Submit */}
        <button
          type="submit"
          style={submitting ? S.submitBtnDisabled : S.submitBtn}
          disabled={submitting}
        >
          {submitting ? '⏳ Launching Agent…' : '🚀 Run Agent'}
        </button>
      </form>
    </div>
  );
}
