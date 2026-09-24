// QuantCore 1.1 — App Core for Power Users
// Hotkeys, Command Palette, Preferences, Realtime, Tables, Toasts

console.log('QuantCore 1.1 loaded');

// ——— Preferences (persisted) ———
const QC = {
  store(key, val) { if (val === undefined) return JSON.parse(localStorage.getItem(key) || 'null'); localStorage.setItem(key, JSON.stringify(val)); },
  prefs: JSON.parse(localStorage.getItem('qc_prefs') || '{"density":"comfortable","theme":"dark","sidebar":true,"mode":"pro"}'),
  save() { localStorage.setItem('qc_prefs', JSON.stringify(QC.prefs)); }
};

// ——— Apply prefs on load ———
document.addEventListener('DOMContentLoaded', () => {
  document.documentElement.setAttribute('data-density', QC.prefs.density || 'comfortable');
  document.documentElement.setAttribute('data-theme', QC.prefs.theme || 'dark');
  document.body.setAttribute('data-mode', QC.prefs.mode || 'pro');
  document.getElementById('global-mode-toggle').checked = QC.prefs.mode === 'learn';
  // Active nav
  const path = location.pathname;
  document.querySelectorAll('.qc-nav-link').forEach(a => {
    if (a.getAttribute('href') === path) { a.classList.add('active'); a.setAttribute('aria-current','page'); }
  });
  initDensity();
  initTheme();
  initSidebar();
  initCommandPalette();
  initHotkeys();
  initTables();
  initClocks();
  initQuickSymbol();
  initSidebarFilter();
  initFavorites();
  initToasts();
});

// ——— Density ———
function initDensity() {
  document.querySelectorAll('[data-density]').forEach(btn => {
    if (btn.getAttribute('data-density') === QC.prefs.density) btn.classList.add('active');
    btn.addEventListener('click', () => {
      QC.prefs.density = btn.getAttribute('data-density');
      document.documentElement.setAttribute('data-density', QC.prefs.density);
      document.querySelectorAll('[data-density]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      QC.save(); toast(`Density: ${QC.prefs.density}`, 'info');
    });
  });
  document.getElementById('footer-density')?.addEventListener('click', (e) => {
    e.stopPropagation();
    const order = ['compact','comfortable','spacious'];
    let idx = order.indexOf(QC.prefs.density);
    QC.prefs.density = order[(idx+1)%order.length];
    document.documentElement.setAttribute('data-density', QC.prefs.density);
    document.querySelectorAll('[data-density]').forEach(b => b.classList.toggle('active', b.getAttribute('data-density')===QC.prefs.density));
    QC.save(); toast(`Density: ${QC.prefs.density}`, 'info');
  });
}

// ——— Theme ———
function initTheme() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  btn.addEventListener('click', () => {
    QC.prefs.theme = QC.prefs.theme === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', QC.prefs.theme);
    QC.save(); toast(`Theme: ${QC.prefs.theme}`, 'info');
  });
  document.getElementById('global-mode-toggle')?.addEventListener('change', e => {
    QC.prefs.mode = e.target.checked ? 'learn' : 'pro';
    document.body.setAttribute('data-mode', QC.prefs.mode);
    QC.save();
  });
}

// ——— Sidebar ———
function initSidebar() {
  const toggle = document.getElementById('sidebar-toggle');
  const sidebar = document.getElementById('app-sidebar');
  const backdrop = document.getElementById('sidebar-backdrop');
  if (!toggle || !sidebar) return;
  const set = (open) => {
    QC.prefs.sidebar = open;
    QC.save();
    toggle.setAttribute('aria-expanded', String(open));
    if (window.innerWidth >= 1024) {
      sidebar.classList.toggle('hidden', !open);
      sidebar.classList.toggle('lg:flex', open);
    } else {
      sidebar.classList.toggle('hidden', !open);
      if (backdrop) backdrop.classList.toggle('hidden', !open);
      if (open) sidebar.classList.add('fixed','inset-y-0','left-0','z-30','w-[280px]','top-14','h-[calc(100vh-3.5rem)]');
      else sidebar.classList.remove('fixed','inset-y-0','left-0','z-30','w-[280px]','top-14','h-[calc(100vh-3.5rem)]');
    }
  };
  // Initialize
  if (window.innerWidth < 1024) set(false); else set(QC.prefs.sidebar !== false);
  toggle.addEventListener('click', () => set(!QC.prefs.sidebar));
  backdrop?.addEventListener('click', () => set(false));
}

// ——— Sidebar filter + favorites ———
function initSidebarFilter() {
  const input = document.getElementById('sidebar-filter');
  if (!input) return;
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    document.querySelectorAll('.qc-nav-link').forEach(a => {
      const txt = a.textContent.toLowerCase();
      a.style.display = txt.includes(q) ? '' : 'none';
    });
  });
  document.querySelectorAll('[data-nav-filter]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-nav-filter]').forEach(b=>b.classList.remove('active'));
      btn.classList.add('active');
      const f = btn.getAttribute('data-nav-filter');
      document.querySelectorAll('.qc-nav-link').forEach(a => {
        if (f==='all') a.style.display='';
        else if (f==='favorites') a.style.display = a.querySelector('.qc-fav-btn.active') ? '' : 'none';
        else if (f==='recent') {
          const recent = JSON.parse(localStorage.getItem('qc_recent')||'[]');
          a.style.display = recent.includes(a.getAttribute('href')) ? '' : 'none';
        }
      });
    });
  });
}
function initFavorites() {
  const favs = new Set(JSON.parse(localStorage.getItem('qc_favs')||'[]'));
  document.querySelectorAll('.qc-fav-btn').forEach(btn => {
    const link = btn.closest('.qc-nav-link');
    const href = link?.getAttribute('href');
    if (favs.has(href)) btn.classList.add('active');
    btn.textContent = btn.classList.contains('active') ? '★' : '☆';
    btn.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      if (favs.has(href)) favs.delete(href); else favs.add(href);
      localStorage.setItem('qc_favs', JSON.stringify([...favs]));
      btn.classList.toggle('active');
      btn.textContent = btn.classList.contains('active') ? '★' : '☆';
      toast(btn.classList.contains('active') ? 'Added to favorites' : 'Removed', 'info');
    });
  });
  // Track recent
  const path = location.pathname;
  let recent = JSON.parse(localStorage.getItem('qc_recent')||'[]');
  recent = [path, ...recent.filter(p=>p!==path)].slice(0,8);
  localStorage.setItem('qc_recent', JSON.stringify(recent));
}

// ——— Quick symbol jump ———
function initQuickSymbol() {
  const input = document.getElementById('quick-symbol');
  if (!input) return;
  input.addEventListener('keydown', async (e) => {
    if (e.key === 'Enter') {
      const sym = input.value.trim().toUpperCase();
      if (!sym) return;
      // Try to add symbol if not exists, then jump to trends
      try { await fetch('/api/symbols', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({symbol: sym})}); } catch {}
      location.href = `/trends?symbol=${sym}`;
    }
  });
}

// ——— Command Palette ———
function initCommandPalette() {
  const cmdk = document.getElementById('cmdk');
  const input = document.getElementById('cmdk-input');
  const list = document.getElementById('cmdk-list');
  const trigger = document.getElementById('cmdk-trigger');
  const backdrop = document.getElementById('cmdk-backdrop');
  if (!cmdk || !input || !list) return;

  const commands = [
    { id:'go-dashboard', name:'Go to Dashboard', keys:'G D', action:()=> location.href='/' , group:'Navigate' },
    { id:'go-paper', name:'Go to Paper Desk', keys:'G P', action:()=> location.href='/paper', group:'Navigate' },
    { id:'go-day', name:'Go to Day Trading Desk', keys:'G T', action:()=> location.href='/day_trading', group:'Navigate' },
    { id:'go-nexus', name:'Go to Nexus HFT', keys:'G N', action:()=> location.href='/nexus', group:'Navigate' },
    { id:'go-signals', name:'Go to Signals', keys:'G S', action:()=> location.href='/signals', group:'Navigate' },
    { id:'go-trends', name:'Go to Trends', action:()=> location.href='/trends', group:'Navigate' },
    { id:'go-predict', name:'Go to Predictions', action:()=> location.href='/predictions', group:'Navigate' },
    { id:'go-backtest', name:'Go to Backtest Lab', action:()=> location.href='/backtest', group:'Navigate' },
    { id:'go-vol', name:'Go to Volatility Desk', action:()=> location.href='/volatility', group:'Navigate' },
    { id:'go-alpha', name:'Go to Alpha Lab', action:()=> location.href='/alpha', group:'Navigate' },
    { id:'go-statarb', name:'Go to StatArb Crucible', action:()=> location.href='/statarb', group:'Navigate' },
    { id:'go-cio', name:'Go to CIO War Room', action:()=> location.href='/cio', group:'Navigate' },
    { id:'go-macro', name:'Go to Macro Desk', action:()=> location.href='/macro', group:'Navigate' },
    { id:'action-copy-link', name:'Copy current page link', action:()=> { navigator.clipboard.writeText(location.href); toast('Link copied','success'); }, group:'Actions' },
    { id:'action-toggle-theme', name:'Toggle theme', action:()=> document.getElementById('theme-toggle')?.click(), group:'Actions' },
    { id:'action-toggle-sidebar', name:'Toggle sidebar', action:()=> document.getElementById('sidebar-toggle')?.click(), group:'Actions' },
    { id:'action-toggle-density', name:'Toggle density', action:()=> document.getElementById('footer-density')?.click(), group:'Actions' },
    { id:'action-help', name:'Show shortcuts', action:()=> document.getElementById('shortcuts-help')?.click(), group:'Actions' },
  ];

  let filtered = [...commands];
  let idx = 0;

  function render() {
    list.innerHTML = '';
    let lastGroup = '';
    filtered.forEach((c,i) => {
      if (c.group !== lastGroup) {
        const h = document.createElement('div');
        h.className = 'qc-nav-heading px-2 pt-2';
        h.textContent = c.group;
        list.appendChild(h);
        lastGroup = c.group;
      }
      const div = document.createElement('div');
      div.className = 'qc-cmd-item' + (i===idx ? ' active' : '');
      div.setAttribute('role','option');
      div.setAttribute('aria-selected', String(i===idx));
      div.innerHTML = `<span class="flex-1 text-sm text-white">${c.name}</span><span class="text-xs text-slate-500 font-mono">${c.keys||''}</span>`;
      div.addEventListener('click', () => { c.action(); close(); });
      list.appendChild(div);
    });
    document.getElementById('cmdk-count').textContent = `${filtered.length} commands`;
  }

  function open() {
    cmdk.classList.remove('hidden');
    input.value = '';
    filtered = [...commands];
    // Inject symbols dynamically
    fetch('/api/symbols').then(r=>r.json()).then(syms => {
      if (Array.isArray(syms)) {
        syms.slice(0,10).forEach(s => commands.push({ id:`sym-${s}`, name:`Jump to ${s} → Trends`, action:()=> location.href=`/trends?symbol=${s}`, group:'Symbols' }));
      }
    }).catch(()=>{});
    idx = 0; render(); setTimeout(()=>input.focus(), 50);
  }
  function close() { cmdk.classList.add('hidden'); }

  trigger?.addEventListener('click', open);
  backdrop?.addEventListener('click', close);
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase()==='k') { e.preventDefault(); open(); }
    if (e.key==='Escape' && !cmdk.classList.contains('hidden')) { e.preventDefault(); close(); }
  });
  input.addEventListener('input', () => {
    const q = input.value.toLowerCase();
    if (q.startsWith('>')) {
      const qq = q.slice(1).trim();
      filtered = commands.filter(c=> c.name.toLowerCase().includes(qq) || c.id.includes(qq));
    } else if (!q) filtered = [...commands];
    else filtered = commands.filter(c=> c.name.toLowerCase().includes(q) || (c.keys&&c.keys.toLowerCase().includes(q)));
    idx = 0; render();
  });
  input.addEventListener('keydown', (e) => {
    if (e.key==='ArrowDown') { e.preventDefault(); idx = Math.min(idx+1, filtered.length-1); render(); }
    if (e.key==='ArrowUp') { e.preventDefault(); idx = Math.max(idx-1, 0); render(); }
    if (e.key==='Enter') { e.preventDefault(); filtered[idx]?.action(); close(); }
  });
}

// ——— Hotkeys ———
function initHotkeys() {
  let gPending = false;
  let gTimer = null;
  document.addEventListener('keydown', (e) => {
    const tag = document.activeElement?.tagName?.toLowerCase();
    const inInput = tag==='input' || tag==='textarea' || document.activeElement?.isContentEditable;
    if (inInput) {
      if (e.key==='Escape') document.activeElement.blur();
      return;
    }
    if (e.key==='?') { e.preventDefault(); document.getElementById('shortcuts-modal')?.classList.remove('hidden'); return; }
    if (e.key==='Escape') { document.getElementById('shortcuts-modal')?.classList.add('hidden'); document.getElementById('cmdk')?.classList.add('hidden'); }
    // Power-user hotkeys below require no typing context; single-letter keys now require Alt to avoid accidental triggers
    if (e.key==='/' && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); document.getElementById('quick-symbol')?.focus(); }
    if (e.altKey && e.key.toLowerCase()==='t') { e.preventDefault(); document.getElementById('theme-toggle')?.click(); }
    if (e.altKey && e.key.toLowerCase()==='d') { e.preventDefault(); document.getElementById('footer-density')?.click(); }
    if (e.altKey && e.key.toLowerCase()==='y') { e.preventDefault(); navigator.clipboard.writeText(location.href); toast('Link copied','success'); }
    if (e.altKey && e.key==='[') { e.preventDefault(); document.getElementById('sidebar-toggle')?.click(); }
    if (e.altKey && e.key===']') { e.preventDefault(); document.getElementById('sidebar-toggle')?.click(); }
    // G + second key
    if (e.key.toLowerCase()==='g' && !gPending) {
      gPending = true;
      clearTimeout(gTimer); gTimer = setTimeout(()=> gPending=false, 800);
      return;
    }
    if (gPending) {
      const k = e.key.toLowerCase();
      gPending = false; clearTimeout(gTimer);
      if (k==='d') location.href='/';
      else if (k==='p') location.href='/paper';
      else if (k==='t') location.href='/day_trading';
      else if (k==='n') location.href='/nexus';
      else if (k==='s') location.href='/signals';
      else if (k==='r') location.href='/research';
      else if (k==='c') location.href='/cio';
    }
  });
  document.querySelectorAll('[data-close-shortcuts]').forEach(el => el.addEventListener('click', ()=> document.getElementById('shortcuts-modal')?.classList.add('hidden')));
  document.getElementById('shortcuts-help')?.addEventListener('click', ()=> document.getElementById('shortcuts-modal')?.classList.remove('hidden'));
}

// ——— Tables ———
function initTables() {
  document.querySelectorAll('table').forEach(table => {
    const headers = table.querySelectorAll('thead th');
    headers.forEach((th, colIdx) => {
      th.setAttribute('role','button');
      th.setAttribute('tabindex','0');
      th.setAttribute('aria-sort','none');
      th.addEventListener('click', () => sortTable(table, colIdx, th));
      th.addEventListener('keydown', e => { if (e.key==='Enter' || e.key===' ') { e.preventDefault(); sortTable(table,colIdx,th); }});
      // Copy helper on header
      th.title = 'Click to sort • Shift+click for multi-sort (power user)';
    });
    // Add copy buttons to rows
    table.querySelectorAll('tbody tr').forEach(tr => {
      tr.addEventListener('dblclick', () => {
        const text = [...tr.children].map(td=>td.textContent.trim()).join(' | ');
        navigator.clipboard.writeText(text); toast('Row copied','success');
      });
    });
  });
}
function sortTable(table, colIdx, th) {
  const tbody = table.querySelector('tbody');
  if (!tbody) return;
  const rows = [...tbody.querySelectorAll('tr')];
  const isNum = rows.every(r => !isNaN(parseFloat(r.children[colIdx]?.textContent.replace(/[$,%]/g,''))));
  const dir = th.getAttribute('aria-sort') === 'ascending' ? 'descending' : 'ascending';
  table.querySelectorAll('th').forEach(h=>h.setAttribute('aria-sort','none'));
  th.setAttribute('aria-sort', dir);
  th.classList.toggle('sorted', true);
  rows.sort((a,b) => {
    let av = a.children[colIdx]?.textContent.trim() || '';
    let bv = b.children[colIdx]?.textContent.trim() || '';
    if (isNum) { av = parseFloat(av.replace(/[$,%]/g,''))||0; bv = parseFloat(bv.replace(/[$,%]/g,''))||0; }
    return dir==='ascending' ? (av>bv?1:-1) : (av<bv?1:-1);
  });
  rows.forEach(r=> tbody.appendChild(r));
}

// ——— Clocks ———
function initClocks() {
  function tick() {
    const now = new Date();
    const utc = now.toISOString().substring(11,19) + ' UTC';
    const local = now.toLocaleTimeString();
    const el = document.getElementById('footer-time'); if (el) el.textContent = utc;
    const el2 = document.getElementById('sidebar-clock'); if (el2) el2.textContent = local;
    const el3 = document.getElementById('status-latency'); if (el3 && window.__qcLatency) el3.textContent = window.__qcLatency + ' ms';
  }
  setInterval(tick, 1000); tick();
}

// ——— Toasts ———
function toast(msg, type='info') {
  const c = document.getElementById('toast-container');
  if (!c) return;
  const div = document.createElement('div');
  div.className = `qc-toast ${type}`;
  div.setAttribute('role','status');
  div.innerHTML = `<span class="text-sm text-white">${msg}</span><button class="ml-auto text-slate-400 hover:text-white" aria-label="Dismiss">✕</button>`;
  c.appendChild(div);
  const btn = div.querySelector('button'); btn.addEventListener('click', ()=> div.remove());
  setTimeout(()=> { div.style.opacity='0'; div.style.transform='translateY(8px)'; setTimeout(()=>div.remove(),200); }, 4000);
}
window.toast = toast;

// ——— Realtime helper (polling fallback) ———
window.__qcLatency = null;
let __qcPoll = null;
window.qcPoll = (url, cb, interval=2000) => {
  clearInterval(__qcPoll);
  const run = async () => {
    const t0 = performance.now();
    try { const data = await fetch(url).then(r=>r.json()); window.__qcLatency = Math.round(performance.now()-t0); cb(data); } catch {}
  };
  run(); __qcPoll = setInterval(run, interval);
  return () => clearInterval(__qcPoll);
};
