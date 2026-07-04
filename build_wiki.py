import re
import os
import shutil
from datetime import datetime

def build_mini_wiki():
    base_file = "web/templates/base.html"
    backup_dir = "ui_backups"
    os.makedirs(backup_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    print("="*60)
    print(" MINI-WIKI & DAY TRADER TRANSLATION ENGINE")
    print("="*60)
    
    shutil.copy2(base_file, os.path.join(backup_dir, f"base_{timestamp}.html"))
    
    with open(base_file, "r") as f:
        content = f.read()

    # 1. Replace the Drawer HTML
    old_drawer_pattern = re.compile(r'<!-- Edu Mode Drawer -->.*?</div>\s*</div>\s*</div>', re.DOTALL)
    new_drawer_html = """<!-- Edu Mode Drawer (Mini Wiki) -->
<div id="edu-drawer" class="fixed top-0 right-0 h-full w-[550px] bg-gray-900 border-l border-gray-700 shadow-2xl transform translate-x-full z-50 overflow-y-auto">
    <div class="p-6">
        <div class="flex justify-between items-center mb-6">
            <h2 class="text-2xl font-bold text-blue-400" id="drawer-title">Concept</h2>
            <button onclick="closeEduDrawer()" class="text-gray-400 hover:text-white text-2xl">&times;</button>
        </div>
        <div class="mb-6 bg-blue-900/20 p-4 rounded-lg border border-blue-500/30">
            <h3 class="text-sm font-bold text-blue-300 uppercase tracking-wider mb-2 flex items-center">🧑‍💻 The Day Trader Translation</h3>
            <p class="text-gray-200 text-sm leading-relaxed" id="drawer-retail"></p>
        </div>
        <div class="mb-6 bg-green-900/20 p-4 rounded-lg border border-green-500/30">
            <h3 class="text-sm font-bold text-green-300 uppercase tracking-wider mb-2 flex items-center">🏛️ Wall Street Reality</h3>
            <p class="text-gray-300 text-sm leading-relaxed" id="drawer-wallstreet"></p>
        </div>
        <div class="mb-6 bg-purple-900/20 p-4 rounded-lg border border-purple-500/30">
            <h3 class="text-sm font-bold text-purple-300 uppercase tracking-wider mb-2 flex items-center">⚙️ In QuantCore (Your Stack)</h3>
            <p class="text-gray-400 text-sm leading-relaxed font-mono" id="drawer-software"></p>
        </div>
        <div class="bg-red-900/20 p-4 rounded-lg border border-red-500/30">
            <h3 class="text-sm font-bold text-red-300 uppercase tracking-wider mb-2 flex items-center">💸 P&L Impact (Why you care)</h3>
            <p class="text-gray-300 text-sm leading-relaxed" id="drawer-pnl"></p>
        </div>
    </div>
</div>

<!-- Wiki Index Modal -->
<div id="wiki-modal" class="fixed inset-0 bg-black/80 z-[60] hidden flex items-center justify-center p-8">
    <div class="bg-gray-900 border border-gray-700 rounded-xl max-w-4xl w-full max-h-[80vh] overflow-y-auto p-6">
        <div class="flex justify-between items-center mb-4">
            <h2 class="text-2xl font-bold text-blue-400">📖 QuantCore Mini-Wiki</h2>
            <button onclick="document.getElementById('wiki-modal').classList.add('hidden')" class="text-gray-400 hover:text-white text-2xl">&times;</button>
        </div>
        <p class="text-gray-400 mb-6">Click any term to open its deep-dive wiki page. Switch to <b>LEARN</b> mode to see these terms highlighted dynamically on the dashboard.</p>
        <div id="wiki-grid" class="grid grid-cols-1 md:grid-cols-2 gap-4"></div>
    </div>
</div>"""
    content = old_drawer_pattern.sub(new_drawer_html, content)
    print("[✓] Replaced Drawer HTML with 4-Section Wiki Layout")

    # 2. Add Wiki Button to Navbar
    old_toggle = """<span class="text-xs text-gray-400 pro-only">PRO</span>
                    <span class="text-xs text-blue-400 font-bold edu-only">LEARN</span>
                    <label class="mode-switch">"""
    new_toggle = """<span class="text-xs text-gray-400 pro-only">PRO</span>
                    <span class="text-xs text-blue-400 font-bold edu-only">LEARN</span>
                    <button onclick="openWikiIndex()" class="ml-2 px-2 py-1 text-xs font-bold bg-blue-600 hover:bg-blue-500 text-white rounded edu-only">📖 WIKI</button>
                    <label class="mode-switch">"""
    if old_toggle in content:
        content = content.replace(old_toggle, new_toggle)
        print("[✓] Injected Wiki Index Button")

    # 3. Replace EDU_TERMS and openEduDrawer function
    terms_pattern = re.compile(r'const EDU_TERMS = \{.*?function openEduDrawer\(data\) \{.*?\}', re.DOTALL)
    
    new_js_block = """const EDU_TERMS = {
    z_score: {
        title: "Z-Score (Mean Reversion)",
        retail: "Think of this as a rubber band. If a stock usually trades around $100, and it suddenly spikes to $110 without any real news, the Z-score tells you how 'stretched' the rubber band is. A Z-score over 2.0 means it's stretched to the extreme and is highly likely to snap back. Day traders use this to fade (short) overextended pumps or buy panic dumps.",
        wallstreet: "Institutional quants use Z-scores to build market-neutral Statistical Arbitrage portfolios. They look at the Z-score of the *spread* between two cointegrated assets (like Coke and Pepsi). When the spread hits +2.0, they short the outperformer and buy the underperformer, mathematically guaranteeing a profit when the spread converges.",
        software: "Computed in the C++ AVX-512 Feature Engine using vectorized rolling standard deviations for sub-microsecond latency. Formula: (Current_Price - Rolling_Mean) / Rolling_StdDev.",
        pnl: "If you buy a breakout without checking the Z-score, you are likely buying the exact top of a statistical anomaly, and you will get crushed when the algorithmic mean-reversion bots step in to fade the move."
    },
    vwap: {
        title: "VWAP (Volume-Weighted Average Price)",
        retail: "This is the ultimate 'fair value' line on your intraday chart. It's the average price paid for the stock all day, weighted by how many shares traded at each price. Retail traders use it as a dynamic support/resistance level to bounce trades off of.",
        wallstreet: "Institutions use VWAP as an *execution benchmark*. If a mutual fund needs to buy 1 million shares, they mandate the desk to 'Beat the VWAP'. The desk uses algorithms to slice the order into tiny pieces, matching the natural volume profile of the day so they don't spike the price against themselves.",
        software: "Simulated in Python by downloading 5 days of intraday volume profiles and proportionally allocating target shares to the most liquid time-of-day buckets. The Paper Broker tracks your VWAP slippage.",
        pnl: "If you use Market Orders instead of VWAP slicing for large size, you will suffer massive slippage. You might think you bought at $150, but your actual average fill was $151.50 because your own order pushed the price up."
    },
    slippage: {
        title: "Slippage & Market Impact",
        retail: "The difference between the price you saw on the screen and the price you actually got filled at. You click 'Buy' at $50.00, but because the market is moving fast or the order book is thin, you get filled at $50.10. That 10 cents is slippage.",
        wallstreet: "Institutions call this 'Market Impact'. When you buy a large block, your demand consumes all the cheap limit orders on the book, forcing you to buy higher up the book. HFT algorithms detect your large order and instantly front-run you, pulling liquidity before your order reaches the exchange.",
        software: "Modeled in basis points (bps) using the Almgren-Chriss framework in the C++ Ghost Exchange. It calculates temporary impact (queue consumption) and permanent impact (information leakage).",
        pnl: "A strategy that looks profitable in a backtest will often lose money in live trading if it doesn't account for slippage. If your average win is 5 bps, but your slippage is 6 bps, you are bleeding to death one trade at a time."
    },
    sharpe_ratio: {
        title: "Sharpe Ratio (Risk-Adjusted Return)",
        retail: "A way to tell if a trader is actually good, or just taking insane risks. If Trader A makes 20% a year by holding crypto through 50% drawdowns, and Trader B makes 15% a year with barely any drawdowns, Trader B has a much higher Sharpe Ratio. It measures return per unit of pain.",
        wallstreet: "The holy grail metric for hedge fund allocation. A Sharpe > 2.0 is excellent. > 3.0 is institutional grade. Funds use it to determine how much leverage to apply. A high Sharpe strategy can be levered 5x to yield massive returns with acceptable volatility.",
        software: "Calculated as (CAGR / Annualized Volatility) using daily returns from the Polars backtester. We assume a risk-free rate of 0% for the simulation.",
        pnl: "Chasing high absolute returns with a low Sharpe ratio guarantees you will eventually hit a drawdown so deep you either blow up your account or panic-sell at the absolute bottom."
    },
    max_drawdown: {
        title: "Max Drawdown (The Pain Metric)",
        retail: "The biggest drop from a peak to a trough in your account history. If your account went from $10k to $15k, then dropped to $9k, your max drawdown is 40% (from the $15k peak). It tells you the worst-case scenario pain you would have had to stomach.",
        wallstreet: "Risk managers use Max Drawdown to set hard stop-outs. If a portfolio manager hits a 15% drawdown, the risk desk automatically liquidates their book. It is the primary constraint in portfolio optimization algorithms like Hierarchical Risk Parity.",
        software: "Calculated by tracking the running maximum of the equity curve (using numpy.maximum.accumulate) and finding the largest percentage deviation below that peak.",
        pnl: "Math is brutal: If you suffer a 50% drawdown, you need a 100% gain just to break even. Protecting your drawdown is infinitely more important than maximizing your upside."
    },
    cointegration: {
        title: "Cointegration (The StatArb Holy Grail)",
        retail: "Correlation means two stocks move in the same direction. Cointegration means two stocks are tied together by an invisible bungee cord. They might wander apart temporarily, but they are mathematically bound to snap back together. Think of a drunk man walking his dog.",
        wallstreet: "The foundation of Pairs Trading. Quants use the Engle-Granger test to find cointegrated pairs. They trade the *spread* between them, which is stationary, rather than the directional price, making the strategy market-neutral (immune to overall market crashes).",
        software: "Computed in the Python StatArb Crucible using statsmodels.tsa.stattools.coint. We reject any pair with a p-value > 0.05.",
        pnl: "If you trade pairs that are merely correlated but not cointegrated, the spread can blow out and never come back. Cointegration proves the mean-reversion is statistically binding."
    },
    half_life: {
        title: "Half-Life (Speed of Mean Reversion)",
        retail: "Once a stock gets overextended, how long does it take to get back to normal? The half-life tells you the exact number of days (or hours) it takes for the anomaly to decay by 50%.",
        wallstreet: "Calculated using an Ornstein-Uhlenbeck process. It dictates the holding period of a StatArb trade. If the half-life is too short, transaction costs eat the profit. If it's too long, capital is exposed to regime changes.",
        software: "Derived via OLS regression on the lagged spread vs. spread returns in the StatArb Crucible. Formula: -ln(2) / slope.",
        pnl: "Holding a mean-reversion trade too long turns a winning strategy into a losing one. The edge decays exponentially. You must exit when the mathematical edge is gone."
    },
    lead_lag: {
        title: "Lead-Lag Effect (Information Flow)",
        retail: "When one asset moves first, and another follows later. For example, Bitcoin might pump, and Ethereum follows 2 hours later. If you spot the leader moving, you can front-run the lagger.",
        wallstreet: "Quants use Cross-Correlation Functions (CCF) to map the exact time-delay of information flow across global markets. HFTs exploit micro-second lead-lags; macro funds exploit multi-day lead-lags.",
        software: "Computed in the Alpha Lab using SciPy's signal.correlate across a Polars dataframe, scanning lags from -24 to +24 hours.",
        pnl: "If you are trading the 'lagger' asset without watching the 'leader', you are always one step behind the market and buying the top of the move."
    },
    p99_latency: {
        title: "p99 Latency (Tail Risk Execution)",
        retail: "Average latency is how fast your broker usually is. p99 latency is how slow your broker is during the worst 1% of market chaos. If your p99 is 2 seconds, your stop-loss will sit in the queue while the price drops $50.",
        wallstreet: "The only latency metric that matters to HFTs. Firms spend millions on FPGAs and microwave towers just to shave microseconds off their p99 tail, ensuring they never get stuck in a slow queue during a volatility spike.",
        software: "Measured via std::chrono::steady_clock inside the Nexus C++ hot path. Tracks exact nanoseconds from WebSocket ingest to LOB update.",
        pnl: "If your execution infrastructure has a bad p99, your backtested stop-losses will fail in live markets. You will experience 'slippage through the stop'."
    },
    spsc: {
        title: "SPSC Queue (Lock-Free Speed)",
        retail: "Imagine a relay race where the baton handoff requires both runners to stop and sign a legal document (a Mutex Lock). SPSC is a handoff where the runner just drops the baton in a bucket and keeps running.",
        wallstreet: "In HFT, standard mutex locks cause thread context switches (microseconds of delay). SPSC (Single-Producer Single-Consumer) queues allow threads to communicate using atomic CPU instructions with zero locks.",
        software: "Implemented in nexus/include/spsc_queue.h using C++20 std::atomic with 64-byte alignas padding to prevent CPU cache-line false sharing.",
        pnl: "If your engine uses locks, you will be front-run by firms that don't. In a fast market, the locked thread misses the price."
    },
    lob: {
        title: "Limit Order Book (LOB)",
        retail: "The list of all pending limit orders on an exchange. It shows the 'bids' and 'asks'. Day traders watch 'Level 2' data to see where the big buy/sell walls are.",
        wallstreet: "Quants model the entire depth to calculate Order Book Imbalance (OBI) and predict micro-second price direction. They also detect 'spoofing' (fake walls).",
        software: "Reconstructed in O(1) time inside the Nexus C++ engine using pre-allocated flat arrays, avoiding the heap allocations of standard std::map structures.",
        pnl: "Trading without looking at the LOB is like driving blindfolded. You might market-buy right into a massive hidden ask wall."
    },
    dark_pools: {
        title: "Dark Pools (Hidden Liquidity)",
        retail: "Private exchanges where institutions trade massive blocks of shares away from the public eye. You won't see these orders on your Level 2 screen.",
        wallstreet: "Institutions use Smart Order Routers (SOR) to fragment orders. They send 30% to Dark Pools to get filled quietly, and 70% to Lit exchanges to hide their footprint.",
        software: "Simulated in the Institutional Ops tab. The C++ SOR routes simulated volume to the dark pool and tracks the basis points of price improvement achieved.",
        pnl: "If you trade large size on lit exchanges only, HFTs will see your footprint and front-run you. Dark pools save you massive slippage."
    },
    hrp: {
        title: "Hierarchical Risk Parity (HRP)",
        retail: "Instead of putting 20% into 5 random stocks, HRP groups similar stocks together (clustering tech, energy, etc). It allocates money so no single 'cluster' can blow up your account.",
        wallstreet: "Developed by Marcos Lopez de Prado. Uses machine learning to cluster correlated assets and allocates risk inversely to cluster variance. Bypasses the unstable matrix inversions of Markowitz Mean-Variance.",
        software: "Implemented via SciPy's hierarchical clustering and recursive bisection in python/quantcore/portfolio/hrp.py.",
        pnl: "Standard diversification is a lie during a crash (everything correlates to 1). HRP protects your downside by recognizing hidden correlations beforehand."
    },
    dsr: {
        title: "Deflated Sharpe Ratio (DSR)",
        retail: "The 'BS Detector' for backtests. If you test 100 moving average crossovers, one will look like a genius strategy purely by luck. DSR penalizes your Sharpe based on how many strategies you tested.",
        wallstreet: "The primary defense against Backtest Overfitting. CIOs will reject a 3.0 Sharpe if the quant ran 500 trials to find it. DSR calculates the probability that the alpha is just statistical noise.",
        software: "Calculated using the Euler-Mascheroni constant approximation for the expected maximum of a normal distribution.",
        pnl: "If you deploy an overfit strategy, it will work perfectly in simulation and immediately lose money in live markets. DSR saves you from deploying luck."
    },
    adverse_selection: {
        title: "Adverse Selection (Toxic Flow)",
        retail: "When you place a limit order to buy at $50, and you instantly get filled, but the price immediately drops to $49. You were 'picked off' by someone who knew bad news was coming.",
        wallstreet: "The primary risk of passive market making. Quants use VPIN to detect toxic flow and widen their spreads to protect themselves from informed traders.",
        software: "Simulated in the Level 4 Sim Lab. The Microstructure Sim flags fills that result in immediate adverse price movement within 5 ticks.",
        pnl: "If you blindly place limit orders without monitoring for adverse selection, you will consistently catch falling knives."
    }
};

function openEduDrawer(data) {
    document.getElementById('drawer-title').innerText = data.title;
    document.getElementById('drawer-retail').innerText = data.retail;
    document.getElementById('drawer-wallstreet').innerText = data.wallstreet;
    document.getElementById('drawer-software').innerText = data.software;
    document.getElementById('drawer-pnl').innerText = data.pnl;
    drawer.classList.add('open');
    overlay.classList.add('open');
}"""
    
    content = terms_pattern.sub(new_js_block, content)
    print("[✓] Injected 15-term Deep-Dive Wiki Dictionary")

    # 4. Inject openWikiIndex function
    if "function openWikiIndex()" not in content:
        wiki_func = """
function openWikiIndex() {
    const grid = document.getElementById('wiki-grid');
    grid.innerHTML = '';
    for (const [key, val] of Object.entries(EDU_TERMS)) {
        grid.innerHTML += `<button onclick="openEduDrawer(EDU_TERMS['${key}']); document.getElementById('wiki-modal').classList.add('hidden');" class="text-left p-4 bg-gray-800 hover:bg-gray-700 rounded-lg border border-gray-700 transition-colors">
            <span class="block text-blue-400 font-bold">${val.title}</span>
            <span class="block text-xs text-gray-500 mt-1 truncate">${val.retail.substring(0, 60)}...</span>
        </button>`;
    }
    document.getElementById('wiki-modal').classList.remove('hidden');
}
"""
        content = content.replace("function openEduDrawer(data)", wiki_func + "\nfunction openEduDrawer(data)")
        print("[✓] Injected Wiki Index Modal Logic")

    with open(base_file, "w") as f:
        f.write(content)
        
    print("\n" + "="*60)
    print(" [DEPLOYMENT COMPLETE]")
    print(" 1. Save and exit Nano (Ctrl+O, Enter, Ctrl+X).")
    print(" 2. Run: python3 build_wiki.py")
    print(" 3. Hard-refresh browser (Ctrl+F5).")
    print(" 4. Toggle to 'LEARN' mode, click the new '📖 WIKI' button, or click any highlighted term!")
    print("="*60)

if __name__ == "__main__":
    build_mini_wiki()
