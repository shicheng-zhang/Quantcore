// ——— Console wiring ———
// Bridges the command registry in console.js into the existing palette, keeps
// the audit chip honest, renders the live tape, and binds the "/" command bar.
(function () {
  function boot() {
    wireConfirm();
    wirePalette();
    wireAuditChip();
    wireTape();
    wireCommandMode();
    verifyAudit(true);
  }

  // ——— Non-blocking confirm for destructive commands ———
  // Modal in the DOM; returns a promise. Default-deny if anything is missing.
  function wireConfirm() {
    let host = document.getElementById('qc-confirm');
    if (!host) {
      host = document.createElement('div');
      host.id = 'qc-confirm';
      host.className = 'fixed inset-0 z-[60] hidden';
      host.innerHTML = `
        <div class="absolute inset-0 bg-[#020618]/80 backdrop-blur-sm"></div>
        <div class="relative max-w-sm mx-auto mt-[25vh] mx-4 bg-[#0f172a] border border-[#334155] rounded-xl p-5 shadow-2xl">
          <h3 id="qc-confirm-title" class="text-sm font-bold text-white mb-2"></h3>
          <pre id="qc-confirm-body" class="text-[11px] font-mono text-slate-400 whitespace-pre-wrap mb-5"></pre>
          <div class="flex justify-end gap-2">
            <button id="qc-confirm-no" class="px-3 py-1.5 text-xs rounded-md border border-[#334155] text-slate-300 hover:bg-[#1e293b]">cancel</button>
            <button id="qc-confirm-yes" class="px-3 py-1.5 text-xs rounded-md bg-red-500/15 border border-red-500/40 text-red-300 hover:bg-red-500/25">run</button>
          </div>
        </div>`;
      document.body.appendChild(host);
    }
    const titleEl = host.querySelector('#qc-confirm-title');
    const bodyEl = host.querySelector('#qc-confirm-body');
    const yes = host.querySelector('#qc-confirm-yes');
    const no = host.querySelector('#qc-confirm-no');
    let resolveFn = null;

    const finish = (v) => { host.classList.add('hidden'); const r = resolveFn; resolveFn = null; r && r(v); };
    yes.onclick = () => finish(true);
    no.onclick = () => finish(false);
    host.addEventListener('keydown', (e) => { if (e.key === 'Escape') finish(false); });

    QC.__confirmImpl = (title, body) => {
      titleEl.textContent = title;
      bodyEl.textContent = body;
      host.classList.remove('hidden');
      yes.focus();
      return new Promise((res) => { resolveFn = res; });
    };
  }

  // ——— Palette ———
  // The existing palette keeps its navigation commands; the engine commands
  // are appended with their usage grammar visible.
  function wirePalette() {
    const input = document.getElementById('cmdk-input');
    const list = document.getElementById('cmdk-list');
    if (!input || !list || !window.__qcPalette) return;

    window.__qcPalette.register(QC_COMMANDS.map(c => ({
      id: 'qc-' + c.pattern.replace(/\W+/g, '-'),
      name: c.name,
      keys: c.usage,
      group: c.group,
      tone: c.dangerous ? 'warn' : 'run',
      action: async () => {
        const r = await QC.exec(c.usage, { silent: false });
        if (!r.__cancelled && !r.__error) showConsole();
      },
    })));
  }

  // ——— Command bar ———
  // Typing "/" at the top of any page opens the palette straight into command
  // mode, in the same way a shell drops you at a prompt.
  function wireCommandMode() {
    const input = document.getElementById('cmdk-input');
    if (!input) return;
    input.addEventListener('input', () => {
      const isCmd = input.value.trim().startsWith('/') || input.value.trim().length === 0 && false;
      input.classList.toggle('is-command', isCmd);
    });
    document.addEventListener('keydown', (e) => {
      const tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
      if (e.key === '/') {
        e.preventDefault();
        window.__qcPalette?.open('/');
        const i = document.getElementById('cmdk-input');
        if (i) { i.value = '/'; setTimeout(() => i.setSelectionRange(1, 1), 0); }
      }
    });
  }

  // ——— Audit chip ———
  function wireAuditChip() {
    const chip = document.getElementById('footer-audit');
    const text = document.getElementById('footer-audit-text');
    if (!chip || !text) return;

    const fire = () => verifyAudit(false);
    chip.addEventListener('click', fire);
    chip.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); fire(); } });

    QC.auditChip = {
      set(state, label, title) {
        chip.dataset.state = state;
        text.textContent = label;
        if (title) chip.title = title;
      },
    };
  }

  // Verify the audit chain. `quiet` runs on boot without a toast so the chip
  // fills in silently; explicit clicks report.
  async function verifyAudit(quiet) {
    const chip = QC.auditChip;
    if (chip) chip.set('checking', 'AUDIT…', 'Verifying hash chain…');
    const r = await QC.exec('verify', { silent: true });
    const el = document.getElementById('footer-latency');
    if (el && QC.latency != null) el.textContent = QC.latency + 'ms';
    if (!r || r.__error) {
      if (chip) chip.set('broken', 'AUDIT ?', 'verification failed: ' + (r && r.__error));
      if (!quiet) window.toast?.('ledger verification failed', 'error');
      return;
    }
    if (chip) {
      const head = QC.fmt.hash(r.head);
      if (r.valid) {
        chip.set('ok', `AUDIT ✓ ${QC.fmt.int(r.entries)}`, `chain verified · head ${r.head}\n${r.algorithm}`);
      } else {
        chip.set('broken', `AUDIT ✗ ${QC.fmt.int(r.chain_breaks)}w`,
          `chain broken · ${QC.fmt.int(r.anomaly_count)} anomalies · ${QC.fmt.int(r.chain_breaks)} chain breaks\n${r.diagnosis}`);
      }
      chip.dataset.head = r.head || '';
    }
    if (!quiet) {
      window.toast?.(r.valid
        ? `chain verified · ${QC.fmt.int(r.entries)} entries`
        : `chain broken · ${QC.fmt.int(r.anomaly_count)} anomalies · ${QC.fmt.int(r.chain_breaks)} chain breaks`,
        r.valid ? 'success' : 'error');
      showConsole();
      QC.renderCommandResult({ pattern: 'verify', name: 'verify ledger' }, [], r);
    }
  }

  // ——— Tape ———
  function wireTape() {
    const wrap = document.getElementById('qc-tape');
    const row = document.getElementById('qc-tape-row');
    const msgsEl = document.getElementById('qc-tape-msgs');
    const rttEl = document.getElementById('qc-tape-rtt');
    if (!wrap || !row) return;

    QC.tape.onChange((item) => {
      const span = document.createElement('span');
      span.className = 'qc-tape-item ' + (item.tone || '');
      if (item.kind === 'fill') {
        const t = new Date(item.at).toISOString().substring(11, 19);
        span.textContent = `${t}  ${item.symbol} ${item.side} ${QC.fmt.int(item.qty)} @ ${item.price}` +
          (item.slip != null ? `  ${QC.fmt.bps(item.slip)}` : '');
      } else {
        span.textContent = `${new Date(item.at).toISOString().substring(11, 19)}  ${item.text}`;
      }
      row.prepend(span);
      while (row.children.length > 12) row.lastChild.remove();
      wrap.classList.add('live');
    });

    setInterval(() => {
      if (msgsEl) msgsEl.textContent = QC.fmt.int(QC.tape.msgs);
      if (rttEl) rttEl.textContent = (QC.latency != null ? QC.latency : '—') + 'ms';
    }, 1000);

    QC.tape.connect();
  }

  function showConsole() {
    const wrap = document.getElementById('qc-console-wrap');
    const box = document.getElementById('qc-console');
    if (!wrap || !box) return;
    QC.consoleEl = box;
    wrap.classList.remove('hidden');
    const close = document.getElementById('qc-console-close');
    if (close) close.onclick = () => wrap.classList.add('hidden');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
  window.qcConsoleBoot = boot;
})();
