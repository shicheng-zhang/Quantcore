// ——— QuantCore Operator Console ———
// The functional layer: real commands against the engine, live fill tape,
// and audit-chain telemetry. Nothing here is decoration — every pixel is
// either a reading from the backend or a control that changes state.
//
// Exposed on window.QC so pages can call QC.exec(...) directly.
window.QC = window.QC || {};

// ——— Command registry ———
// name        unique id
// pattern     human-readable invocation, e.g. "paper SPY BUY 10 MARKET"
// usage       arg grammar shown in the palette / help
// run         async fn(...args) -> result. Return value is rendered by the caller.
// group       palette grouping
// dangerous   true routes through a confirm step before running
const QC_COMMANDS = [
  {
    name: 'verify ledger',
    pattern: 'verify',
    usage: 'verify',
    group: 'Audit',
    run: () => QC.api('/api/sim/ledger_verify'),
  },
  {
    name: 'paper order',
    pattern: 'paper SYMBOL SIDE QTY [ALGO]',
    usage: 'paper SPY BUY 10 MARKET',
    group: 'Execution',
    run: (...a) => QC.api('/api/paper/order', {
      method: 'POST',
      body: { symbol: String(a[0] || '').toUpperCase(), side: String(a[1] || '').toUpperCase(),
              qty: Number(a[2] || 0), algo: String(a[3] || 'MARKET').toUpperCase() },
    }),
  },
  {
    name: 'ledger head',
    pattern: 'head',
    usage: 'head',
    group: 'Audit',
    run: () => QC.api('/api/sim/ledger_verify').then(r => ({ head: r.head, entries: r.entries, valid: r.valid })),
  },
  {
    name: 'force data seed',
    pattern: 'seed',
    usage: 'seed',
    group: 'Data',
    dangerous: true,
    run: () => QC.api('/api/seed/force', { method: 'POST' }),
  },
  {
    name: 'seed status',
    pattern: 'seed-status',
    usage: 'seed-status',
    group: 'Data',
    run: () => QC.api('/api/seed/status'),
  },
  {
    name: 'broker status',
    pattern: 'broker',
    usage: 'broker',
    group: 'Execution',
    run: () => QC.api('/api/paper/state'),
  },
  {
    name: 'reset paper account',
    pattern: 'reset',
    usage: 'reset',
    group: 'Execution',
    dangerous: true,
    run: () => QC.api('/api/paper/reset', { method: 'POST' }),
  },
  {
    name: 'disengage autopilot',
    pattern: 'autopilot-off',
    usage: 'autopilot-off',
    group: 'Execution',
    dangerous: true,
    run: () => QC.api('/api/paper/autopilot/disengage', { method: 'POST' }),
  },
  {
    name: 'engage autopilot',
    pattern: 'autopilot-on',
    usage: 'autopilot-on',
    group: 'Execution',
    dangerous: true,
    run: () => QC.api('/api/paper/autopilot/engage', { method: 'POST' }),
  },
  {
    name: 'system status',
    pattern: 'status',
    usage: 'status',
    group: 'Audit',
    run: () => QC.api('/api/overview'),
  },
];

// ——— Transport ———
// Single choke point so latency, error shape and toasts are uniform.
QC.api = async function (url, opts = {}) {
  const t0 = performance.now();
  try {
    const res = await fetch(url, {
      method: opts.method || 'GET',
      headers: opts.body ? { 'Content-Type': 'application/json' } : undefined,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    const data = await res.json().catch(() => ({ msg: `non-JSON response (${res.status})` }));
    QC.latency = Math.round(performance.now() - t0);
    if (!res.ok && data.msg === undefined) data.msg = `HTTP ${res.status}`;
    return data;
  } catch (e) {
    QC.latency = Math.round(performance.now() - t0);
    return { __error: String(e) };
  }
};

// ——— Command dispatch ———
// Resolve a command name, parse its args, confirm if flagged dangerous, run it,
// and surface the result. Returns a promise so callers can chain.
QC.exec = async function (query, opts = {}) {
  const parts = String(query).trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return { __error: 'empty command' };
  // Exact name/pattern wins, then prefix. Prevents `/s` silently resolving to
  // whichever command happens to sit first in the array.
  const head = parts[0].toLowerCase();
  let cmd = QC_COMMANDS.find(c => c.name === head || c.pattern === head)
        || QC_COMMANDS.find(c => c.pattern.startsWith(head) && !c.pattern.includes(' '))
        || QC_COMMANDS.find(c => c.name.startsWith(head));
  if (!cmd) return { __error: `unknown command: ${head}` };

  const args = parts.slice(1);

  if (cmd.dangerous && !opts.skipConfirm) {
    const ok = QC.confirm(`Run "${cmd.name}"?`, `${cmd.pattern}\n\nThis changes engine state.`);
    if (!ok) return { __cancelled: true };
  }

  QC.tape.push({ kind: 'cmd', text: cmd.pattern, tone: 'info' });

  let result;
  try {
    result = await cmd.run(...args);
  } catch (e) {
    result = { __error: String(e) };
  }

  QC.lastResult = result;
  if (!opts.silent) QC.renderCommandResult(cmd, args, result);
  return result;
};

// ——— Result rendering ———
// Kept deliberately plain: monospace, tabular, no chrome. The point is the data.
QC.renderCommandResult = function (cmd, args, result) {
  if (result.__cancelled) { window.toast?.(`${cmd.name} cancelled`, 'info'); return; }

  if (result.__error) {
    window.toast?.(`${cmd.name} failed: ${result.__error}`, 'error');
    QC.tape.push({ kind: 'err', text: `${cmd.name}: ${result.__error}`, tone: 'error' });
    return;
  }

  // Status maps to the one piece of colour the console uses.
  const ok = result.status === 'FILLED' || result.valid === true || result.status === 'RESET'
    || result.engaged !== undefined || result.ok !== false;
  const bad = result.status === 'REJECTED' || result.valid === false;

  const detail = QC.summarise(cmd, result);
  window.toast?.(detail, bad ? 'error' : (ok ? 'success' : 'info'));

  if (QC.consoleEl) {
    QC.consoleEl.innerHTML = `<div class="qc-out ${bad ? 'bad' : 'ok'}">
      <div class="qc-out-head">${cmd.pattern}${args.length ? ' ' + args.join(' ') : ''}</div>
      <pre>${QC.escapeHtml(JSON.stringify(result, null, 2))}</pre>
    </div>` + QC.consoleEl.innerHTML;
  }
  QC.tape.push({ kind: 'cmd', text: detail, tone: bad ? 'error' : 'ok' });
};

// Short one-line human summary per command — what a trader actually wants first.
QC.summarise = function (cmd, r) {
  switch (cmd.pattern) {
    case 'verify':
      return r.valid
        ? `ledger verified · ${r.entries.toLocaleString()} entries · head ${r.head}`
        : `ledger BROKEN · ${r.entries.toLocaleString()} entries · ${r.anomaly_count} anomalies · ${r.chain_breaks} breaks`;
    case 'head':
      return `head ${r.head} · ${Number(r.entries).toLocaleString()} entries`;
    case 'paper SYMBOL SIDE QTY [ALGO]':
      return r.status === 'FILLED'
        ? `FILLED ${r.side} ${r.qty} ${r.symbol} @ ${r.fill_price} (slip ${r.slippage_bps}bps)`
        : `REJECTED ${r.symbol}: ${r.reason}`;
    case 'reset':
      return `paper account reset · ${r.status}`;
    case 'seed':
    case 'seed-status':
      return r.msg || r.status || JSON.stringify(r);
    case 'broker':
      return `equity $${Number(r.total_equity || 0).toLocaleString()} · cash $${Number(r.cash || 0).toLocaleString()} · ${(r.positions || []).length} positions`;
    default:
      return cmd.name + ' complete';
  }
};

QC.escapeHtml = function (s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
};

// ——— Non-blocking confirm ———
// window.confirm() freezes the page and looks like 1998. Commands flagged
// dangerous route through here instead. Overridden with a DOM version at init.
QC.__confirmImpl = null;
QC.confirm = function (title, body) {
  if (QC.__confirmImpl) return QC.__confirmImpl(title, body);
  return Promise.resolve(false);
};

// ——— Live tape ———
// Streams fills from /ws/tape. Reconnects with backoff, exposes msg/latency
// counters, and renders a dense monospace ticker.
QC.tape = (function () {
  const queue = [];
  const listeners = [];
  let ws = null, retry = 0, connected = false, msgs = 0, dropped = 0;

  function push(item) {
    queue.unshift(Object.assign({ at: Date.now() }, item));
    if (queue.length > 200) { queue.pop(); dropped++; }
    listeners.forEach(fn => { try { fn(item, queue); } catch {} });
  }

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    try { ws = new WebSocket(`${proto}//${location.host}/ws/tape`); } catch (e) { schedule(); return; }

    ws.onopen = () => { connected = true; retry = 0; push({ kind: 'sys', text: 'tape connected', tone: 'ok' }); };
    ws.onmessage = (ev) => {
      msgs++;
      let m; try { m = JSON.parse(ev.data); } catch { return; }
      const tone = m.side === 'BUY' ? 'buy' : 'sell';
      push({
        kind: 'fill',
        symbol: m.symbol, side: m.side, qty: m.qty, price: m.fill_price,
        slip: m.slippage_bps, algo: m.algo || '', text: '', tone,
      });
    };
    ws.onclose = () => { connected = false; push({ kind: 'sys', text: 'tape disconnected', tone: 'warn' }); schedule(); };
    ws.onerror = () => { try { ws.close(); } catch {} };
  }

  function schedule() {
    retry = Math.min(retry + 1, 6);
    setTimeout(connect, Math.min(1000 * 2 ** retry, 30000));
  }

  return {
    push, connect,
    get connected() { return connected; },
    get msgs() { return msgs; },
    get queue() { return queue.slice(); },
    onChange(fn) { listeners.push(fn); },
  };
})();

// ——— Formatting helpers (dense, monospace, trader-native) ———
QC.fmt = {
  money: (n) => '$' + Number(n || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  int: (n) => Number(n || 0).toLocaleString(),
  pct: (n) => Number(n || 0).toFixed(2) + '%',
  bps: (n) => Number(n || 0).toFixed(1) + 'bps',
  hash: (h) => h ? String(h).slice(0, 8) + '…' + String(h).slice(-6) : '—',
};

// ——— Telemetry health ———
// Attaches a LIVE / STALE / OFFLINE badge and a warning strip to a page, and
// dims the instrumented values when they are not live. The readings stay
// visible — a stale number is information about the engine, not noise.
//
//   QC.telemetryMount({
//     selector: '.qc-tel-scope',   // element carrying the state attribute
//     badge:    '#tel-badge',      // element receiving the badge text
//     warn:     '#tel-warn',       // element receiving the warning strip
//     fetch:    '/api/nexus/telemetry',
//     onData:   (d) => {...},     // page-specific rendering
//     interval: 2000,
//   });
QC.telemetryMount = function (opts) {
  const scope = typeof opts.selector === 'string' ? document.querySelector(opts.selector) : opts.selector;
  const badge = opts.badge && document.querySelector(opts.badge);
  const warn = opts.warn && document.querySelector(opts.warn);
  if (!scope) return () => {};

  const setState = (state, label) => {
    scope.dataset.state = state;
    if (badge) {
      badge.dataset.state = state;
      badge.innerHTML = `<span class="qc-dot"></span>${label || state}`;
    }
    if (warn) warn.innerHTML = '';
  };

  let stopped = false;
  const tick = async () => {
    if (stopped) return;
    const d = await QC.api(opts.fetch);
    if (stopped) return;

    if (d.__error) { setState('UNKNOWN', '?'); return; }

    const state = d.telemetry_state || 'UNKNOWN';
    const label = state === 'LIVE' ? 'LIVE'
      : state === 'STALE' ? `STALE ${d.telemetry_age_human || ''}`
      : `OFFLINE ${d.telemetry_age_human || ''}`;
    setState(state, label);

    if (warn) {
      const list = Array.isArray(d.warnings) ? d.warnings : [];
      if (list.length) {
        warn.innerHTML = `<span class="qc-tel-warn-icon">!</span><span>${QC.escapeHtml(list.join(' · '))}</span>`;
      } else {
        warn.innerHTML = '';
      }
    }

    if (opts.onData) opts.onData(d);
  };

  tick();
  const timer = setInterval(tick, opts.interval || 2000);
  return () => { stopped = true; clearInterval(timer); };
};
