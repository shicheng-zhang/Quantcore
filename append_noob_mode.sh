#!/bin/bash
# ============================================================================
# QuantCore: Universal Pro/Edu Mode Toggle
# Adds an interactive educational layer across the entire application
# ============================================================================
set -euo pipefail

echo "=========================================="
echo " Installing Universal Edu Mode Toggle"
echo "=========================================="

source .venv/bin/activate

python << 'EOF'
import os
import re

print("[1/3] Injecting Global Toggle, Drawer, and Dictionary into base.html...")
with open("web/templates/base.html", "r") as f:
    base_html = f.read()

# 1. CSS for the toggle, drawer, and mode-specific visibility
css_injection = """
<style>
    /* Toggle Switch */
    .mode-switch { position: relative; display: inline-block; width: 44px; height: 24px; }
    .mode-switch input { opacity: 0; width: 0; height: 0; }
    .mode-slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #374151; transition: .4s; border-radius: 24px; }
    .mode-slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: .4s; border-radius: 50%; }
    input:checked + .mode-slider { background-color: #3b82f6; }
    input:checked + .mode-slider:before { transform: translateX(20px); }

    /* Educational Drawer */
    #edu-drawer { transition: transform 0.3s ease-in-out; }
    #edu-drawer.open { transform: translateX(0); }
    #edu-overlay { transition: opacity 0.3s ease-in-out; }
    #edu-overlay.open { opacity: 1; pointer-events: auto; }

    /* Mode Visibility Rules */
    body.mode-pro .edu-only { display: none !important; }
    body.mode-edu .pro-only { display: none !important; }

    /* Interactive Term Highlights in Edu Mode */
    body.mode-edu [data-term] {
        position: relative;
        cursor: help;
        border-bottom: 1px dashed #60a5fa;
        color: #93c5fd;
    }
    body.mode-edu [data-term]:hover { color: #bfdbfe; }
</style>
"""

# 2. The Toggle Switch HTML (Injected into the Nav Bar)
toggle_html = """
    <div class="flex items-center space-x-3 border-l border-gray-700 pl-4 ml-4">
        <span class="text-xs text-gray-400 pro-only">PRO</span>
        <span class="text-xs text-blue-400 font-bold edu-only">LEARN</span>
        <label class="mode-switch">
            <input type="checkbox" id="global-mode-toggle">
            <span class="mode-slider"></span>
        </label>
    </div>
"""

# 3. The Slide-Out Drawer HTML (Injected before </body>)
drawer_html = """
<!-- Edu Mode Overlay -->
<div id="edu-overlay" class="fixed inset-0 bg-black/50 z-40 opacity-0 pointer-events-none" onclick="closeEduDrawer()"></div>

<!-- Edu Mode Drawer -->
<div id="edu-drawer" class="fixed top-0 right-0 h-full w-96 bg-gray-900 border-l border-gray-700 shadow-2xl transform translate-x-full z-50 overflow-y-auto">
    <div class="p-6">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-xl font-bold text-blue-400" id="drawer-title">Concept</h2>
            <button onclick="closeEduDrawer()" class="text-gray-400 hover:text-white text-2xl">&times;</button>
        </div>

        <div class="mb-6">
            <h3 class="text-sm font-bold text-green-400 uppercase tracking-wider mb-2">📈 In Trading (Wall Street)</h3>
            <p class="text-gray-300 text-sm leading-relaxed" id="drawer-trading"></p>
        </div>

        <div class="bg-gray-800 p-4 rounded-lg border border-gray-700">
            <h3 class="text-sm font-bold text-purple-400 uppercase tracking-wider mb-2">⚙️ In QuantCore (Your Stack)</h3>
            <p class="text-gray-400 text-sm leading-relaxed font-mono" id="drawer-software"></p>
        </div>
    </div>
</div>
"""

# 4. The JavaScript Dictionary and Logic
js_injection = """
<script>
const EDU_TERMS = {
    sharpe_ratio: {
        title: "Sharpe Ratio",
        trading: "Measures how much excess return you are getting for the extra volatility you endure. A Sharpe > 1.0 is good, > 2.0 is excellent, and > 3.0 is institutional grade. It tells you if your returns are due to skill or just taking massive risks.",
        software: "Calculated as (CAGR / Annualized Volatility). We use daily returns from the backtester to compute this, assuming a risk-free rate of 0%."
    },
    max_drawdown: {
        title: "Max Drawdown",
        trading: "The largest peak-to-trough drop in your portfolio's history. It measures the worst-case scenario pain you would have endured. Institutional funds usually have strict mandates to keep this under 15%.",
        software: "Calculated by tracking the running maximum of the equity curve and finding the largest percentage deviation below that peak."
    },
    z_score: {
        title: "Z-Score",
        trading: "A statistical measurement of how far a price is from its mean (average), measured in standard deviations. A Z-score > 2.0 means the asset is statistically overextended and likely to revert to the mean.",
        software: "Computed in the C++ AVX-512 Feature Engine using vectorized rolling standard deviations for sub-microsecond latency."
    },
    sma: {
        title: "Simple Moving Average (SMA)",
        trading: "The average price of an asset over a specific number of periods. It smooths out noise to reveal the underlying trend. Prices above the SMA indicate a bullish trend.",
        software: "Calculated via the C++ `rolling_mean_avx512` function, which utilizes OpenMP SIMD directives to process 8 doubles per CPU clock cycle."
    },
    p99_latency: {
        title: "p99 Latency",
        trading: "The 99th percentile of execution delay. If your average latency is 10ms, but your p99 is 500ms, it means 1% of your trades are suffering massive delays, allowing HFTs to front-run you during volatile moments.",
        software: "Measured via `std::chrono::steady_clock` inside the Nexus C++ hot path. It tracks the exact nanoseconds from WebSocket ingest to Limit Order Book update."
    },
    spsc: {
        title: "SPSC Ring Buffer",
        trading: "In HFT, standard mutex locks cause thread context switches (microseconds of delay). SPSC (Single-Producer Single-Consumer) queues allow the network thread and trading thread to communicate using atomic CPU instructions with zero locks.",
        software: "Implemented in `nexus/include/spsc_queue.h` using C++20 `std::atomic` with 64-byte `alignas` padding to prevent CPU cache-line false sharing."
    },
    lob: {
        title: "Limit Order Book (LOB)",
        trading: "The real-time list of all pending buy and sell orders for an asset, organized by price level. The 'spread' is the gap between the highest bid and lowest ask.",
        software: "Reconstructed in O(1) time inside the Nexus C++ engine using pre-allocated flat arrays, avoiding the heap allocations of standard `std::map` structures."
    },
    vwap: {
        title: "VWAP (Volume-Weighted Average Price)",
        trading: "The average price a stock has traded at throughout the day, weighted by volume. Institutional traders use VWAP algorithms to slice large orders into tiny pieces, hiding their footprint from the market.",
        software: "Simulated in Python by downloading 5 days of intraday volume profiles and proportionally allocating target shares to the most liquid time-of-day buckets."
    },
    slippage: {
        title: "Slippage / Market Impact",
        trading: "The difference between the expected price of a trade and the actual executed price. When you buy a large amount of shares, your own demand pushes the price up against you.",
        software: "Modeled in basis points (bps). The execution simulator assumes 15bps impact for retail market orders, and <2bps for institutional VWAP slicing."
    },
    hrp: {
        title: "Hierarchical Risk Parity (HRP)",
        trading: "A portfolio allocation method that uses machine learning (graph theory) to cluster correlated assets. It allocates risk evenly across clusters, preventing a crash in one sector from blowing up the whole portfolio.",
        software: "Implemented via SciPy's hierarchical clustering and recursive bisection in `python/quantcore/portfolio/hrp.py`, bypassing the unstable matrix inversions of Markowitz Mean-Variance."
    },
    dsr: {
        title: "Deflated Sharpe Ratio (DSR)",
        trading: "A statistical test that penalizes your Sharpe Ratio based on how many strategies you tested. If you test 100 random strategies, one will look good by pure luck. DSR tells you if your Alpha is real or just overfitting.",
        software: "Calculated using the Euler-Mascheroni constant approximation for the expected maximum of a normal distribution, implemented in `research/validation.py`."
    },
    lead_lag: {
        title: "Lead-Lag Information Flow",
        trading: "The phenomenon where price movements in a 'leader' asset (like Bitcoin) predict movements in a 'lagger' asset (like Ethereum) with a measurable time delay, creating an arbitrage opportunity.",
        software: "Computed using SciPy's Cross-Correlation Function (CCF) across a Polars dataframe of hourly returns, scanning lags from -24 to +24 hours."
    },
    turnover: {
        title: "Portfolio Turnover",
        trading: "How much of the portfolio is bought and sold in a given period. High turnover means high transaction costs, which can easily turn a profitable paper strategy into a losing real-world strategy.",
        software: "Calculated as the L1 norm of daily weight changes divided by 2. Multiplied by the slippage parameter to deduct realistic transaction costs from the equity curve."
    },
    cagr: {
        title: "CAGR (Compound Annual Growth Rate)",
        trading: "The mean annual growth rate of an investment over a specified period of time longer than one year. It smooths out the volatility of yearly returns to show the true geometric growth.",
        software: "Calculated as `(Ending Value / Beginning Value)^(1 / Years) - 1`."
    }
};

const toggle = document.getElementById('global-mode-toggle');
const drawer = document.getElementById('edu-drawer');
const overlay = document.getElementById('edu-overlay');

function setMode(isEdu) {
    document.body.classList.toggle('mode-edu', isEdu);
    document.body.classList.toggle('mode-pro', !isEdu);
    localStorage.setItem('quantcore_mode', isEdu ? '1' : '0');
}

toggle.addEventListener('change', (e) => setMode(e.target.checked));

// Initialize from localStorage
const savedMode = localStorage.getItem('quantcore_mode') === '1';
toggle.checked = savedMode;
setMode(savedMode);

// Event delegation for term clicks
document.body.addEventListener('click', (e) => {
    const target = e.target.closest('[data-term]');
    if (target && document.body.classList.contains('mode-edu')) {
        const term = target.getAttribute('data-term');
        if (EDU_TERMS[term]) openEduDrawer(EDU_TERMS[term]);
    }
});

function openEduDrawer(data) {
    document.getElementById('drawer-title').innerText = data.title;
    document.getElementById('drawer-trading').innerText = data.trading;
    document.getElementById('drawer-software').innerText = data.software;
    drawer.classList.add('open');
    overlay.classList.add('open');
}

function closeEduDrawer() {
    drawer.classList.remove('open');
    overlay.classList.remove('open');
}
</script>
"""

# Apply injections to base.html
if "global-mode-toggle" not in base_html:
    base_html = base_html.replace("</head>", css_injection + "\n</head>")
    base_html = base_html.replace('<span class="text-sm text-green-400">● System Active</span>', '<span class="text-sm text-green-400">● System Active</span>' + toggle_html)
    base_html = base_html.replace("</body>", drawer_html + js_injection + "\n</body>")

    with open("web/templates/base.html", "w") as f:
        f.write(base_html)
    print("✅ base.html patched.")

print("[2/3] Tagging key metrics across all pages with data-term attributes...")

# Dictionary of files and the text replacements to add data-term tags
patches = {
    "web/templates/dashboard.html": [
        ('<h3 class="text-sm font-medium text-gray-400">Sharpe Ratio</h3>', '<h3 class="text-sm font-medium text-gray-400"><span data-term="sharpe_ratio">Sharpe Ratio</span></h3>'),
        ('<h3 class="text-sm font-medium text-gray-400">Max Drawdown</h3>', '<h3 class="text-sm font-medium text-gray-400"><span data-term="max_drawdown">Max Drawdown</span></h3>')
    ],
    "web/templates/trends.html": [
        ('<h3 class="text-sm font-medium text-gray-400">Z-Score</h3>', '<h3 class="text-sm font-medium text-gray-400"><span data-term="z_score">Z-Score</span></h3>'),
        ('name: \'SMA 20\'', 'name: \'<span data-term="sma">SMA 20</span>\'')
    ],
    "web/templates/nexus.html": [
        ('<h3 class="text-sm font-medium text-gray-400">p99 Latency</h3>', '<h3 class="text-sm font-medium text-gray-400"><span data-term="p99_latency">p99 Latency</span></h3>'),
        ('<h2 class="text-xl font-bold mb-4">Live Limit Order Book</h2>', '<h2 class="text-xl font-bold mb-4"><span data-term="lob">Live Limit Order Book</span></h2>'),
        ('SPSC Ring Buffer', '<span data-term="spsc">SPSC Ring Buffer</span>')
    ],
    "web/templates/execution.html": [
        ('<option value="VWAP" selected>VWAP (Volume-Weighted)</option>', '<option value="VWAP" selected data-term="vwap">VWAP (Volume-Weighted)</option>'),
        ('<h3 class="text-sm font-medium text-gray-400">Slippage (bps)</h3>', '<h3 class="text-sm font-medium text-gray-400"><span data-term="slippage">Slippage (bps)</span></h3>')
    ],
    "web/templates/research.html": [
        ('<h2 class="text-xl font-bold mb-4">Hierarchical Risk Parity (HRP) Allocation</h2>', '<h2 class="text-xl font-bold mb-4"><span data-term="hrp">Hierarchical Risk Parity (HRP)</span> Allocation</h2>'),
        ('<h2 class="text-xl font-bold mb-4">Model Integrity (DSR)</h2>', '<h2 class="text-xl font-bold mb-4">Model Integrity (<span data-term="dsr">DSR</span>)</h2>')
    ],
    "web/templates/alpha.html": [
        ('<h1 class="text-3xl font-bold text-purple-400">Alpha Lab: Information Flow</h1>', '<h1 class="text-3xl font-bold text-purple-400">Alpha Lab: <span data-term="lead_lag">Information Flow</span></h1>')
    ],
    "web/templates/backtest.html": [
        ('<h3 class="text-xs font-medium text-gray-400 uppercase">CAGR</h3>', '<h3 class="text-xs font-medium text-gray-400 uppercase"><span data-term="cagr">CAGR</span></h3>'),
        ('<h3 class="text-xs font-medium text-gray-400 uppercase">Avg Daily Turnover</h3>', '<h3 class="text-xs font-medium text-gray-400 uppercase">Avg Daily <span data-term="turnover">Turnover</span></h3>')
    ]
}

for file_path, replacements in patches.items():
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            content = f.read()

        changed = False
        for old, new in replacements:
            if old in content and new not in content:
                content = content.replace(old, new)
                changed = True

        if changed:
            with open(file_path, "w") as f:
                f.write(content)
            print(f"  ✅ Tagged metrics in {os.path.basename(file_path)}")

print("\n==========================================")
print(" ✅ UNIVERSAL EDU MODE INSTALLED!")
print("==========================================")
EOF
