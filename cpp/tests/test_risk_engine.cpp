// Unit tests for the session-aware RiskEngine.
//
// Build standalone (no DuckDB/pybind11 needed — only spdlog headers):
//   cmake -S cpp/tests -B build-cpptests && cmake --build build-cpptests
//   ctest --test-dir build-cpptests --output-on-failure
//
// Or directly with a compiler:
//   c++ -std=c++20 -O2 -Wall -Wextra -o test_risk_engine
//       cpp/tests/test_risk_engine.cpp cpp/src/risk_engine.cpp cpp/src/event_bus.cpp
//       -I cpp/include -I <spdlog>/include
#include "quantcore/risk_engine.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <string>

using namespace quantcore;

namespace {

constexpr int64_t NS_PER_SEC = 1000000000LL;
constexpr int64_t NS_PER_DAY = 86400LL * NS_PER_SEC;
constexpr int64_t FLAT_DEADLINE_NS = (15 * 3600 + 55 * 60) * NS_PER_SEC;  // 15:55 ET
constexpr int64_t AFTER_DEADLINE_NS = 16 * 3600 * NS_PER_SEC;             // 16:00 ET
constexpr int64_t BEFORE_DEADLINE_NS = 15 * 3600 * NS_PER_SEC;            // 15:00 ET

int g_checks = 0;

#define CHECK(cond)                                                            \
    do {                                                                       \
        ++g_checks;                                                            \
        if (!(cond)) {                                                         \
            std::cerr << "FAILED: " << #cond << "\n  at " << __FILE__ << ":"   \
                      << __LINE__ << std::endl;                                \
            return 1;                                                          \
        }                                                                      \
    } while (0)

RiskConfig make_config() {
    RiskConfig cfg;  // library defaults
    cfg.flat_deadline_ns = FLAT_DEADLINE_NS;
    return cfg;
}

PortfolioSnapshot make_portfolio(int64_t ts, double equity = 100000.0) {
    PortfolioSnapshot p;
    p.timestamp_ns = ts;
    p.total_equity = equity;
    p.cash = equity;
    p.daily_pnl = 0.0;
    p.drawdown_pct = 0.0;
    return p;
}

Order make_order(Side side, double qty, double price = 100.0) {
    Order o;
    o.id = 1;
    o.symbol = "AAPL";
    o.side = side;
    o.type = OrderType::MARKET;
    o.quantity = qty;
    o.limit_price = price;
    return o;
}

void add_long(PortfolioSnapshot& p, double qty, double cost = 100.0) {
    Position pos;
    pos.symbol = "AAPL";
    pos.quantity = qty;
    pos.average_cost = cost;
    pos.unrealized_pnl = 0.0;
    pos.entry_time_ns = 0;  // 0 disables the hold-time check in these tests
    p.positions.push_back(pos);
}

// ---------------------------------------------------------------- flat deadline

int test_flat_deadline_rejects_new_position() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);

    auto res = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("no new positions") != std::string::npos);
    return 0;
}

// Regression test: the flat deadline used to allow *adding* to an existing
// long position (the "is_closing" flag was computed and then never used), so a
// strategy could still be long-heavy at the close.
int test_flat_deadline_rejects_pyramid_add() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, 100);

    auto res = engine.check_order(make_order(Side::BUY, 50), pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("only reducing") != std::string::npos);
    return 0;
}

int test_flat_deadline_allows_closing_long() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, 100);

    auto res = engine.check_order(make_order(Side::SELL, 100), pf);
    CHECK(res.decision == RiskDecision::APPROVE);
    return 0;
}

int test_flat_deadline_allows_partial_close() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, 20);  // 2% of book, leaves headroom under the 5% cap

    auto res = engine.check_order(make_order(Side::SELL, 10), pf);
    CHECK(res.decision == RiskDecision::APPROVE);
    return 0;
}

// Overselling flips the position to short, which is new exposure, not a close.
int test_flat_deadline_rejects_over_close() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, 100);

    auto res = engine.check_order(make_order(Side::SELL, 150), pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("only reducing") != std::string::npos);
    return 0;
}

int test_flat_deadline_allows_covering_short() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, -100);

    auto res = engine.check_order(make_order(Side::BUY, 100), pf);
    CHECK(res.decision == RiskDecision::APPROVE);
    return 0;
}

int test_flat_deadline_rejects_adding_to_short() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(AFTER_DEADLINE_NS);
    add_long(pf, -100);

    auto res = engine.check_order(make_order(Side::SELL, 50), pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("only reducing") != std::string::npos);
    return 0;
}

int test_before_deadline_allows_new_position() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);

    auto res = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(res.decision == RiskDecision::APPROVE);
    return 0;
}

// ---------------------------------------------------------------- other guards

int test_consecutive_losses_halt() {
    EventBus bus;
    RiskConfig cfg = make_config();
    cfg.max_consecutive_losses = 5;
    RiskEngine engine(cfg, bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);

    for (int i = 0; i < 4; ++i) engine.record_trade_result(false, "AAPL", BEFORE_DEADLINE_NS);
    CHECK(engine.consecutive_losses() == 4);

    auto ok = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(ok.decision == RiskDecision::APPROVE);

    engine.record_trade_result(false, "AAPL", BEFORE_DEADLINE_NS);  // 5th loss
    CHECK(engine.is_halted());

    auto halted = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(halted.decision == RiskDecision::REJECT);
    return 0;
}

int test_max_trades_per_day() {
    EventBus bus;
    RiskConfig cfg = make_config();
    cfg.max_trades_per_day = 50;
    RiskEngine engine(cfg, bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);

    for (int i = 0; i < 50; ++i) engine.record_trade_result(true, "AAPL", BEFORE_DEADLINE_NS);
    CHECK(engine.trades_today() == 50);

    auto res = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("Max trades per day") != std::string::npos);
    return 0;
}

int test_concentration_limit() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);  // equity 100k, 5% cap = 5k

    auto small = engine.check_order(make_order(Side::BUY, 10, 100.0), pf);
    CHECK(small.decision == RiskDecision::APPROVE);

    auto big = engine.check_order(make_order(Side::BUY, 100, 100.0), pf);
    CHECK(big.decision == RiskDecision::REJECT);
    CHECK(big.reason.find("exceeds limit") != std::string::npos);
    return 0;
}

int test_daily_loss_halt() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS, 100000.0);
    CHECK(engine.check_order(make_order(Side::BUY, 10), pf).decision == RiskDecision::APPROVE);

    pf.total_equity = 96000.0;  // -4% vs day start, above the 3% daily cap
    auto res = engine.check_order(make_order(Side::BUY, 10), pf);
    CHECK(res.decision == RiskDecision::HALT_TRADING);
    CHECK(engine.is_halted());
    return 0;
}

int test_invalid_order_rejected() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);

    Order o = make_order(Side::BUY, 10);
    o.limit_price = std::nullopt;  // no reference price for the risk check
    auto res = engine.check_order(o, pf);
    CHECK(res.decision == RiskDecision::REJECT);
    CHECK(res.reason.find("Missing market price") != std::string::npos);
    return 0;
}

int test_trade_counters_reset_on_new_day() {
    EventBus bus;
    RiskEngine engine(make_config(), bus);
    auto pf = make_portfolio(BEFORE_DEADLINE_NS);

    for (int i = 0; i < 10; ++i) engine.record_trade_result(true, "AAPL", BEFORE_DEADLINE_NS);
    CHECK(engine.trades_today() == 10);

    auto next_day = make_portfolio(BEFORE_DEADLINE_NS + NS_PER_DAY);
    engine.update_portfolio(next_day);
    CHECK(engine.trades_today() == 0);
    return 0;
}

}  // namespace

int main() {
    int failed = 0;
    failed += test_flat_deadline_rejects_new_position();
    failed += test_flat_deadline_rejects_pyramid_add();
    failed += test_flat_deadline_allows_closing_long();
    failed += test_flat_deadline_allows_partial_close();
    failed += test_flat_deadline_rejects_over_close();
    failed += test_flat_deadline_allows_covering_short();
    failed += test_flat_deadline_rejects_adding_to_short();
    failed += test_before_deadline_allows_new_position();
    failed += test_consecutive_losses_halt();
    failed += test_max_trades_per_day();
    failed += test_concentration_limit();
    failed += test_daily_loss_halt();
    failed += test_invalid_order_rejected();
    failed += test_trade_counters_reset_on_new_day();

    if (failed) {
        std::cerr << failed << " test(s) FAILED" << std::endl;
        return 1;
    }
    std::cout << "[OK] all risk engine tests passed (" << g_checks << " assertions)" << std::endl;
    return 0;
}
