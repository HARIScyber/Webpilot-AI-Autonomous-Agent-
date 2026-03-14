/**
 * index.js — React Application Entry Point
 * =========================================
 * This is the first JavaScript file executed by the browser.
 * It mounts our <App /> component into the #root div in public/index.html.
 *
 * React.StrictMode wraps the app during development to:
 *   - Double-invoke certain lifecycle methods to catch side effects
 *   - Warn about deprecated APIs
 *   - It has NO effect in the production build
 */

import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App'; // root component
import './index.css'; // global styles

// Select the #root element from index.html
const rootElement = document.getElementById('root');

// createRoot is the modern React 18 API (replaces ReactDOM.render)
const root = ReactDOM.createRoot(rootElement);

root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
