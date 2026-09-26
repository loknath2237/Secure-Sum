/* ==========================================================================
   SecureSum — Frontend application logic
   Vanilla JS. Talks to the Flask API. Renders Chart.js graphs.
   ========================================================================== */

const NODE_COLORS = ['#FF7A33', '#27B369', '#F5A524', '#7C6CE8', '#3B82F6', '#EC4899', '#14B8A6', '#EF4444'];

let functionChart = null;
let errorChart = null;
let timeChart = null;
let resultChart = null;

// ------------------------------------------------------------------
// Navigation
// ------------------------------------------------------------------

const PAGE_TITLES = {
  'dashboard': 'Dashboard',
  'new-simulation': 'New Simulation',
  'simulations': 'Simulations',
  'nodes': 'Nodes',
  'blockchain': 'Blockchain',
  'results': 'Results & Analysis',
  'privacy': 'Privacy & Security',
  'about': 'About',
};

function gotoPage(pageKey) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  const target = document.getElementById('page-' + pageKey);
  if (target) target.classList.add('active');

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const navBtn = document.querySelector(`.nav-item[data-page="${pageKey}"]`);
  if (navBtn) navBtn.classList.add('active');

  document.getElementById('topbarTitle').textContent = PAGE_TITLES[pageKey] || 'SecureSum';

  closeSidebar();

  // Lazy-load page-specific data
  if (pageKey === 'simulations') loadSimulationsTable();
  if (pageKey === 'nodes') loadNodesPage();
  if (pageKey === 'blockchain') loadBlockchainPage();

  window.scrollTo({ top: 0, behavior: 'instant' in window ? 'instant' : 'auto' });
}

document.querySelectorAll('.nav-item[data-page]').forEach(btn => {
  btn.addEventListener('click', () => gotoPage(btn.dataset.page));
});
document.querySelectorAll('[data-goto]').forEach(btn => {
  btn.addEventListener('click', () => gotoPage(btn.dataset.goto));
});

function openSidebar() {
  document.getElementById('sidebar').classList.add('open');
  document.getElementById('sidebarScrim').classList.add('show');
}
function closeSidebar() {
  document.getElementById('sidebar').classList.remove('open');
  document.getElementById('sidebarScrim').classList.remove('show');
}
document.getElementById('menuToggle').addEventListener('click', openSidebar);
document.getElementById('sidebarScrim').addEventListener('click', closeSidebar);

// ------------------------------------------------------------------
// Toasts
// ------------------------------------------------------------------

function showToast(message, type = 'default') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.classList.add('hide');
    setTimeout(() => toast.remove(), 220);
  }, 3200);
}

// ------------------------------------------------------------------
// API helpers
// ------------------------------------------------------------------

async function apiGet(url) {
  const res = await fetch(url);
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed.');
  return data;
}

async function apiPost(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || 'Request failed.');
  return data;
}

function formatFnDisplay(fn) {
  return fn.replace(/\^/g, '^').replace(/\*\*/g, '^');
}

function fmt(num, digits = 6) {
  if (num === null || num === undefined || Number.isNaN(num)) return '—';
  return Number(num).toFixed(digits);
}

function fmtShort(num, digits = 4) {
  if (num === null || num === undefined || Number.isNaN(num)) return '—';
  return Number(num).toFixed(digits);
}

function timeAgo(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleString();
}

// ------------------------------------------------------------------
// Dashboard summary
// ------------------------------------------------------------------

async function loadDashboardStats() {
  try {
    const d = await apiGet('/api/dashboard');
    document.getElementById('statTotalSims').textContent = d.total_simulations;
    document.getElementById('statCompleted').textContent = `Completed: ${d.completed_simulations}`;
    document.getElementById('statActiveNodes').textContent = d.active_nodes;
    document.getElementById('statBlocks').textContent = d.total_blocks;
    document.getElementById('statValidBlocks').textContent = `${d.valid_blocks} Valid Blocks ✓`;
    document.getElementById('statLastResult').textContent = d.last_result !== null ? fmtShort(d.last_result) : '—';
    document.getElementById('statLastMethod').textContent = d.last_method || '—';
  } catch (e) {
    console.error(e);
  }
}

// ------------------------------------------------------------------
// Function graph (live preview as user types, using Chart.js)
// ------------------------------------------------------------------

function renderFunctionChart(xs, ys, exactVal, fnDisplay, a, b) {
  const ctx = document.getElementById('functionChart').getContext('2d');
  if (functionChart) functionChart.destroy();

  functionChart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: xs.map(x => x.toFixed(2)),
      datasets: [{
        label: 'f(x)',
        data: ys,
        borderColor: '#FF7A33',
        backgroundColor: 'rgba(255,122,51,0.12)',
        fill: true,
        pointRadius: 0,
        borderWidth: 2.5,
        tension: 0.15,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          ticks: { maxTicksLimit: 8, color: '#8A8D9B', font: { family: 'JetBrains Mono', size: 10 } },
          grid: { color: '#F1EDE7' },
        },
        y: {
          ticks: { color: '#8A8D9B', font: { family: 'JetBrains Mono', size: 10 } },
          grid: { color: '#F1EDE7' },
        }
      }
    }
  });

  document.getElementById('graphFnLabel').textContent = `f(x) = ${fnDisplay}`;
}

let previewDebounce = null;
async function updateFunctionPreview() {
  const fn = document.getElementById('fnFunction').value;
  const a = document.getElementById('fnLower').value;
  const b = document.getElementById('fnUpper').value;

  try {
    const data = await apiPost('/api/function/preview', { function: fn, lower_limit: a, upper_limit: b });
    renderFunctionChart(data.x, data.y, data.exact_result, data.expression, a, b);
    const exactStr = data.exact_available ? fmtShort(data.exact_result) : 'unavailable';
    document.getElementById('integralFormula').textContent =
      `∫${subscriptNum(a)}${superscriptNum(b)} ${data.expression} dx = ${exactStr}`;
    document.getElementById('formError').textContent = '';
  } catch (e) {
    document.getElementById('formError').textContent = e.message;
  }
}

function subscriptNum(n) {
  const map = { '0':'₀','1':'₁','2':'₂','3':'₃','4':'₄','5':'₅','6':'₆','7':'₇','8':'₈','9':'₉','-':'₋','.':'.' };
  return String(n).split('').map(c => map[c] || c).join('');
}
function superscriptNum(n) {
  const map = { '0':'⁰','1':'¹','2':'²','3':'³','4':'⁴','5':'⁵','6':'⁶','7':'⁷','8':'⁸','9':'⁹','-':'⁻','.':'.' };
  return String(n).split('').map(c => map[c] || c).join('');
}

['fnFunction', 'fnLower', 'fnUpper'].forEach(id => {
  document.getElementById(id).addEventListener('input', () => {
    clearTimeout(previewDebounce);
    previewDebounce = setTimeout(updateFunctionPreview, 400);
  });
});

// ------------------------------------------------------------------
// Node status rendering (dashboard mini list + nodes page)
// ------------------------------------------------------------------

function renderNodeStatusList(nodes, animating = false) {
  const container = document.getElementById('nodeStatusList');
  if (!nodes || nodes.length === 0) {
    container.innerHTML = '<div class="empty-hint">Run a simulation to see node status.</div>';
    return;
  }
  container.innerHTML = nodes.map((n, i) => `
    <div class="node-status-row ${n.status === 'Processing' ? 'processing' : ''}">
      <div class="ns-top">
        <span class="node-color-dot" style="background:${NODE_COLORS[i % NODE_COLORS.length]}"></span>
        <span class="n-id">${n.node_id}</span>
        <span class="n-badge ${n.status === 'Completed' ? 'completed' : ''}">${n.status}</span>
      </div>
      <div class="ns-bottom">
        <span class="n-interval">[${fmtShort(n.interval[0], 2)}, ${fmtShort(n.interval[1], 2)}]</span>
        ${n.status === 'Completed' ? `<span class="n-result">${fmtShort(n.local_result, 6)}</span>` : ''}
      </div>
    </div>
  `).join('');
}

// ------------------------------------------------------------------
// Block preview rendering (dashboard mini list)
// ------------------------------------------------------------------

function renderBlockPreview(blocks) {
  const container = document.getElementById('blockPreviewList');
  if (!blocks || blocks.length === 0) {
    container.innerHTML = '<div class="empty-hint">No blocks yet.</div>';
    return;
  }
  const recent = [...blocks].reverse().slice(0, 4);
  container.innerHTML = recent.map(b => `
    <div class="block-preview-item">
      <div class="bp-top">
        <span>Block #${b.block_id}</span>
        <span class="bp-valid">Valid</span>
      </div>
      <div class="bp-meta">${b.node_id} · Hash: ${b.current_hash.slice(0, 10)}...${b.current_hash.slice(-6)}</div>
    </div>
  `).join('');
}

// ------------------------------------------------------------------
// Simulation results rendering (dashboard result cards)
// ------------------------------------------------------------------

function renderResultSummary(sim) {
  document.getElementById('rmFinal').textContent = fmt(sim.numerical_result);
  document.getElementById('rmExact').textContent = sim.exact_available ? fmt(sim.exact_result) : 'N/A';
  document.getElementById('rmError').textContent = sim.exact_available ? fmt(sim.absolute_error) : '—';
  document.getElementById('rmTime').textContent = `${fmt(sim.execution_time, 3)} s`;

  const acc = sim.accuracy !== null && sim.accuracy !== undefined ? Math.max(0, Math.min(100, sim.accuracy)) : null;
  document.getElementById('accuracyFill').style.width = acc !== null ? `${acc}%` : '0%';
  document.getElementById('accuracyPct').textContent = acc !== null ? `${acc.toFixed(2)}%` : '—';
  document.getElementById('accuracyBadge').textContent = acc !== null
    ? (acc > 99.9 ? 'Very Accurate' : acc > 95 ? 'Accurate' : 'Approximate')
    : '—';
}

// ------------------------------------------------------------------
// Run simulation (with staged animation)
// ------------------------------------------------------------------

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

document.getElementById('simForm').addEventListener('submit', async (e) => {
  e.preventDefault();

  const fn = document.getElementById('fnFunction').value;
  const a = document.getElementById('fnLower').value;
  const b = document.getElementById('fnUpper').value;
  const methodKey = document.getElementById('fnMethod').value;
  const numNodes = parseInt(document.getElementById('fnNodes').value, 10);
  const subintervals = document.getElementById('fnSubintervals').value;

  const errEl = document.getElementById('formError');
  errEl.textContent = '';

  const startBtn = document.getElementById('startSimBtn');
  startBtn.disabled = true;
  const originalBtnHTML = startBtn.innerHTML;

  try {
    // ---- Staged visual animation (frontend-driven) ----
    // Build placeholder "processing" node rows immediately for feedback.
    const width = (parseFloat(b) - parseFloat(a)) / numNodes;
    const placeholderNodes = Array.from({ length: numNodes }, (_, i) => ({
      node_id: `NODE_${String(i + 1).padStart(2, '0')}`,
      interval: [parseFloat(a) + i * width, i === numNodes - 1 ? parseFloat(b) : parseFloat(a) + (i + 1) * width],
      status: 'Processing',
      local_result: null,
    }));
    renderNodeStatusList(placeholderNodes, true);
    startBtn.innerHTML = '<span class="spin">⏳</span> Processing nodes...';

    await sleep(550);

    // ---- Actual backend call ----
    const sim = await apiPost('/api/simulations', {
      function: fn,
      lower_limit: a,
      upper_limit: b,
      method: methodKey,
      num_nodes: numNodes,
      subintervals: subintervals,
    });

    // Show nodes as completed
    renderNodeStatusList(sim.nodes.map(n => ({ ...n, status: 'Completed' })));
    startBtn.innerHTML = 'Aggregating results...';
    await sleep(400);

    startBtn.innerHTML = 'Creating blockchain blocks...';
    await sleep(400);

    startBtn.innerHTML = 'Blockchain verified ✓';
    await sleep(350);

    // ---- Final render ----
    renderResultSummary(sim);
    renderBlockPreview(sim.blocks);
    updateFunctionPreview(); // refresh graph/exact result label

    showToast('Simulation completed', 'success');
    loadDashboardStats();

  } catch (err) {
    errEl.textContent = err.message;
    showToast(err.message, 'error');
  } finally {
    startBtn.disabled = false;
    startBtn.innerHTML = originalBtnHTML;
  }
});

// ------------------------------------------------------------------
// Blockchain verify (both dashboard button and blockchain page button)
// ------------------------------------------------------------------

async function runVerify(resultTargetId) {
  try {
    const result = await apiPost('/api/blockchain/verify');
    if (resultTargetId) {
      const el = document.getElementById(resultTargetId);
      el.classList.add('show');
      el.classList.toggle('valid', result.valid);
      el.classList.toggle('invalid', !result.valid);
      el.textContent = result.valid
        ? '✓ Blockchain verified — ' + result.message
        : '⚠ Blockchain integrity compromised — ' + result.message;
    }
    showToast(result.valid ? 'Blockchain verified' : 'Blockchain integrity issue detected', result.valid ? 'success' : 'error');
    loadDashboardStats();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

document.getElementById('verifyBtnDash').addEventListener('click', () => runVerify(null));
document.getElementById('verifyBtnPage').addEventListener('click', () => runVerify('verifyResult'));

// ------------------------------------------------------------------
// Simulations page
// ------------------------------------------------------------------

async function loadSimulationsTable() {
  const tbody = document.getElementById('simTableBody');
  try {
    const sims = await apiGet('/api/simulations');
    if (sims.length === 0) {
      tbody.innerHTML = '<tr><td colspan="9" class="empty-row">No simulations yet. Run one from the Dashboard.</td></tr>';
      return;
    }
    tbody.innerHTML = sims.map(s => `
      <tr>
        <td class="mono-cell">SIM-${String(s.id).padStart(3, '0')}</td>
        <td class="mono-cell">${escapeHtml(s.function_str)}</td>
        <td>${s.method}</td>
        <td>${s.num_nodes}</td>
        <td class="mono-cell">${fmtShort(s.lower_limit, 2)}–${fmtShort(s.upper_limit, 2)}</td>
        <td class="mono-cell">${s.numerical_result !== null ? fmtShort(s.numerical_result) : '—'}</td>
        <td class="mono-cell">${s.absolute_error !== null ? fmtShort(s.absolute_error) : '—'}</td>
        <td><span class="status-pill">${s.status}</span></td>
        <td>${timeAgo(s.created_at)}</td>
      </tr>
    `).join('');
  } catch (e) {
    tbody.innerHTML = `<tr><td colspan="9" class="empty-row">${e.message}</td></tr>`;
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ------------------------------------------------------------------
// Nodes page
// ------------------------------------------------------------------

async function loadNodesPage() {
  const grid = document.getElementById('nodesPageGrid');
  try {
    const nodes = await apiGet('/api/nodes');
    if (nodes.length === 0) {
      grid.innerHTML = '<div class="empty-hint">No node activity yet. Run a simulation from the Dashboard.</div>';
      return;
    }
    grid.innerHTML = nodes.map(n => `
      <div class="node-card">
        <div class="node-card-top">
          <span class="node-card-id">${n.node_id}</span>
          <span class="status-pill">${n.status}</span>
        </div>
        <div class="node-card-row"><span class="label">Interval</span><span class="value">[${fmtShort(n.interval_start,2)}, ${fmtShort(n.interval_end,2)}]</span></div>
        <div class="node-card-row"><span class="label">Method</span><span class="value">${n.method}</span></div>
        <div class="node-card-row"><span class="label">Local Result</span><span class="value">${fmtShort(n.local_result,6)}</span></div>
        <div class="node-card-row"><span class="label">Evaluations</span><span class="value">${n.evaluations}</span></div>
        <div class="node-card-row"><span class="label">Exec Time</span><span class="value">${fmt(n.execution_time,4)}s</span></div>
      </div>
    `).join('');
  } catch (e) {
    grid.innerHTML = `<div class="empty-hint">${e.message}</div>`;
  }
}

// ------------------------------------------------------------------
// Blockchain page
// ------------------------------------------------------------------

async function loadBlockchainPage() {
  const timeline = document.getElementById('blockTimeline');
  document.getElementById('verifyResult').classList.remove('show');
  try {
    const blocks = await apiGet('/api/blockchain/blocks'); // already DESC order
    if (blocks.length === 0) {
      timeline.innerHTML = '<div class="empty-hint">No blocks yet.</div>';
      return;
    }
    timeline.innerHTML = blocks.map((b, i) => `
      <div class="block-card">
        <div class="block-card-top">
          <span class="block-card-id">Block #${b.block_id}</span>
          <span class="status-pill">${b.status === 'VALID' ? '✓ Valid' : '⚠ Invalid'}</span>
        </div>
        <div class="block-card-node">${b.node_id} · [${fmtShort(b.interval[0],2)}, ${fmtShort(b.interval[1],2)}] · Result: ${fmtShort(b.local_result,6)}</div>
        <div class="block-card-hash"><span class="hlabel">Hash</span>${b.current_hash}</div>
      </div>
      ${i < blocks.length - 1 ? '<div class="block-connector">↓</div>' : ''}
    `).join('');
  } catch (e) {
    timeline.innerHTML = `<div class="empty-hint">${e.message}</div>`;
  }
}

// ------------------------------------------------------------------
// Results & Analysis page — method comparison
// ------------------------------------------------------------------

document.getElementById('cmpRunBtn').addEventListener('click', async () => {
  const fn = document.getElementById('cmpFunction').value;
  const a = document.getElementById('cmpLower').value;
  const b = document.getElementById('cmpUpper').value;
  const sub = document.getElementById('cmpSub').value;
  const errEl = document.getElementById('cmpError');
  errEl.textContent = '';

  try {
    const data = await apiPost('/api/analysis/compare', {
      function: fn, lower_limit: a, upper_limit: b, subintervals: sub,
    });

    document.getElementById('analysisResults').style.display = 'grid';

    const tbody = document.getElementById('cmpTableBody');
    tbody.innerHTML = data.comparison.map(c => `
      <tr>
        <td>${c.method}</td>
        <td class="mono-cell">${fmtShort(c.result)}</td>
        <td class="mono-cell">${c.error !== null ? fmtShort(c.error) : '—'}</td>
        <td class="mono-cell">${fmt(c.execution_time, 4)}s</td>
      </tr>
    `).join('');

    const labels = data.comparison.map(c => c.method.replace(' Rule', ''));

    renderBarChart('errorChart', errorChart, labels, data.comparison.map(c => c.error), '#EF4444', v => errorChart = v);
    renderBarChart('timeChart', timeChart, labels, data.comparison.map(c => c.execution_time * 1000), '#3B82F6', v => timeChart = v);
    renderBarChart('resultChart', resultChart, labels, data.comparison.map(c => c.result), '#27B369', v => resultChart = v);

  } catch (e) {
    errEl.textContent = e.message;
  }
});

function renderBarChart(canvasId, existing, labels, values, color, setRef) {
  if (existing) existing.destroy();
  const ctx = document.getElementById(canvasId).getContext('2d');
  const chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        data: values,
        backgroundColor: color + '33',
        borderColor: color,
        borderWidth: 2,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8A8D9B', font: { size: 10 } }, grid: { display: false } },
        y: { ticks: { color: '#8A8D9B', font: { size: 10 } }, grid: { color: '#F1EDE7' } },
      }
    }
  });
  setRef(chart);
}

// ------------------------------------------------------------------
// Init
// ------------------------------------------------------------------

(async function init() {
  await loadDashboardStats();
  await updateFunctionPreview();

  // Load the most recent simulation's results onto the dashboard, if any
  try {
    const sims = await apiGet('/api/simulations');
    if (sims.length > 0) {
      const latest = sims[0];
      const detail = await apiGet(`/api/simulations/${latest.id}`);
      renderResultSummary(detail);
      renderNodeStatusList(detail.nodes.map(n => ({
        node_id: n.node_id,
        interval: [n.interval_start, n.interval_end],
        status: 'Completed',
        local_result: n.local_result,
      })));
      renderBlockPreview(detail.blocks);
    }
  } catch (e) {
    console.error(e);
  }
})();
