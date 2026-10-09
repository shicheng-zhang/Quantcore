#include "quantcore/risk_engine.h"
#include <spdlog/spdlog.h>
#include <cmath>

namespace quantcore {
    RiskEngine::RiskEngine(const RiskConfig& config, EventBus& bus) : config_(config), bus_(bus) {}

    double RiskEngine::get_position_notional(const PortfolioSnapshot& portfolio, const std::string& symbol) const {
        for (const auto& pos : portfolio.positions) {
            if (pos.symbol == symbol) {
                return std::abs(pos.quantity * pos.average_cost);
            }
        }
        return 0.0;
    }

    bool RiskEngine::is_outside_session(int64_t timestamp_ns) const {
        if (config_.session_start_ns == 0 || config_.session_end_ns == 0) return false;
        // Extract time-of-day in ET (assume timestamp is ET-aligned; production should use tz conversion)
        int64_t day_ns = timestamp_ns % (86400LL * 1000000000LL);
        return day_ns < config_.session_start_ns || day_ns > config_.session_end_ns;
    }

    bool RiskEngine::is_flat_deadline(int64_t timestamp_ns) const {
        if (config_.flat_deadline_ns == 0) return false;
        int64_t day_ns = timestamp_ns % (86400LL * 1000000000LL);
        return day_ns >= config_.flat_deadline_ns;
    }

    void RiskEngine::record_trade_result(bool was_win, [[maybe_unused]] const std::string& symbol, int64_t timestamp_ns) {
        std::lock_guard<std::mutex> lock(mutex_);
        // Reset daily counters on new day
        int64_t day = timestamp_ns / (86400LL * 1000000000LL);
        if (day != last_trade_day_ns_) {
            trades_today_ = 0;
            consecutive_losses_ = 0;
            last_trade_day_ns_ = day;
        }
        trades_today_++;
        if (was_win) consecutive_losses_ = 0;
        else consecutive_losses_++;
        if (consecutive_losses_ >= config_.max_consecutive_losses) {
            halt("Consecutive losses limit: " + std::to_string(consecutive_losses_));
        }
    }

    RiskResult RiskEngine::check_order(const Order& order, const PortfolioSnapshot& portfolio) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (halted_.load()) return {RiskDecision::REJECT, "Trading halted"};
        // Session checks first
        if (portfolio.timestamp_ns > 0) {
            if (is_flat_deadline(portfolio.timestamp_ns)) {
                // After the flat deadline only strictly risk-reducing orders
                // are permitted: closing a long (SELL) or covering a short
                // (BUY), up to the position size. Adding to a position, or
                // opening a new one, must be rejected — otherwise the intent
                // of "flat by 15:55 ET" is not enforced at all.
                double held_qty = 0.0;
                for (auto& p : portfolio.positions) {
                    if (p.symbol == order.symbol && p.quantity != 0.0) { held_qty = p.quantity; break; }
                }
                bool is_reducing = false;
                if (held_qty > 0.0 && order.side == Side::SELL) {
                    is_reducing = order.quantity <= held_qty;
                } else if (held_qty < 0.0 && order.side == Side::BUY) {
                    is_reducing = order.quantity <= -held_qty;
                }
                if (!is_reducing) {
                    return {RiskDecision::REJECT,
                            held_qty == 0.0
                                ? "Flat deadline: no new positions after 15:55 ET"
                                : "Flat deadline: only reducing positions allowed after 15:55 ET"};
                }
            }
            // is_outside_session() is intentionally not enforced: pre-market
            // opens are allowed by design. The flat deadline above is the
            // session gate; see RiskConfig::session_start_ns/end_ns.
        }
        // Overtrading guard
        if (trades_today_ >= config_.max_trades_per_day) {
            return {RiskDecision::REJECT, "Max trades per day (" + std::to_string(config_.max_trades_per_day) + ") reached"};
        }
        if (consecutive_losses_ >= config_.max_consecutive_losses) {
            return {RiskDecision::HALT_TRADING, "Consecutive losses halt"};
        }
        // Holding time check
        for (auto& pos : portfolio.positions) {
            if (pos.quantity != 0 && pos.entry_time_ns > 0 && portfolio.timestamp_ns > 0) {
                int64_t hold_ns = portfolio.timestamp_ns - pos.entry_time_ns;
                int64_t max_hold_ns = static_cast<int64_t>(config_.max_position_hold_minutes) * 60LL * 1000000000LL;
                if (hold_ns > max_hold_ns) {
                    // Force reduce, not new exposure on same symbol
                    if (order.symbol == pos.symbol && ((pos.quantity > 0 && order.side == Side::BUY) || (pos.quantity < 0 && order.side == Side::SELL))) {
                        return {RiskDecision::REJECT, "Position hold time exceeded " + std::to_string(config_.max_position_hold_minutes) + "min, only closing allowed"};
                    }
                }
            }
        }
        // Daily reset: detect new day via timestamp (86400s = 86400e9 ns)
        if (portfolio.timestamp_ns > 0 && day_start_date_ns_ > 0) {
            int64_t day_now = portfolio.timestamp_ns / (86400LL * 1000000000LL);
            int64_t day_start = day_start_date_ns_ / (86400LL * 1000000000LL);
            if (day_now != day_start) {
                day_start_equity_ = portfolio.total_equity > 0 ? portfolio.total_equity : day_start_equity_;
                session_start_equity_ = portfolio.total_equity > 0 ? portfolio.total_equity : session_start_equity_;
                day_start_date_ns_ = portfolio.timestamp_ns;
                session_start_date_ns_ = portfolio.timestamp_ns;
            }
        }
        if (day_start_equity_ <= 0 && portfolio.total_equity > 0) {
            day_start_equity_ = portfolio.total_equity;
            session_start_equity_ = portfolio.total_equity;
            day_start_date_ns_ = portfolio.timestamp_ns;
            session_start_date_ns_ = portfolio.timestamp_ns;
        }
        if (session_start_equity_ <= 0 && portfolio.total_equity > 0) session_start_equity_ = portfolio.total_equity;
        double daily_loss_pct = (day_start_equity_ > 0) ? (day_start_equity_ - portfolio.total_equity) / day_start_equity_ : 0.0;
        if (daily_loss_pct >= config_.max_daily_loss_pct) { halt("Daily loss limit"); return {RiskDecision::HALT_TRADING, "Daily loss"}; }
        double intraday_loss_pct = (session_start_equity_ > 0) ? (session_start_equity_ - portfolio.total_equity) / session_start_equity_ : 0.0;
        if (intraday_loss_pct >= config_.max_intraday_loss_pct) { halt("Intraday loss limit"); return {RiskDecision::HALT_TRADING, "Intraday loss"}; }
        if (!order.limit_price.has_value() || *order.limit_price <= 0) {
            return {RiskDecision::REJECT, "Missing market price for risk check"};
        }
        // Post-trade concentration. Work in signed share counts so covering a
        // short is recognised as *reducing* exposure: the previous version took
        // abs(quantity * avg_cost) for the existing side, so buying back a short
        // position was charged as if it added a second long position.
        double held_qty = 0.0;
        for (auto& p : portfolio.positions) {
            if (p.symbol == order.symbol) { held_qty = p.quantity; break; }
        }
        const double order_qty = (order.side == Side::BUY ? 1.0 : -1.0) * order.quantity;
        const double post_trade_qty = held_qty + order_qty;
        const double post_trade_notional = std::abs(post_trade_qty * *order.limit_price);

        double concentration = portfolio.total_equity > 0 ? post_trade_notional / portfolio.total_equity : 0.0;
        if (portfolio.total_equity > 0 && concentration > config_.max_position_pct) {
            return {RiskDecision::REJECT, "Post-trade position " + std::to_string(concentration*100) + "% exceeds limit " + std::to_string(config_.max_position_pct*100) + "%"};
        }
        return {RiskDecision::APPROVE, ""};
    }

    void RiskEngine::update_portfolio(const PortfolioSnapshot& snapshot) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (snapshot.total_equity > peak_equity_) peak_equity_ = snapshot.total_equity;
        // Detect new day for equity reset
        if (day_start_date_ns_ == 0 && snapshot.timestamp_ns > 0) {
            day_start_date_ns_ = snapshot.timestamp_ns;
            session_start_date_ns_ = snapshot.timestamp_ns;
            if (day_start_equity_ <= 0) day_start_equity_ = snapshot.total_equity;
            if (session_start_equity_ <= 0) session_start_equity_ = snapshot.total_equity;
        }
        if (peak_equity_ > 0 && ((peak_equity_ - snapshot.total_equity) / peak_equity_) >= config_.max_drawdown_pct) halt("Max drawdown");
        // Reset daily trade counters if new day detected in snapshot
        if (snapshot.timestamp_ns > 0) {
            int64_t day = snapshot.timestamp_ns / (86400LL * 1000000000LL);
            if (last_trade_day_ns_ >= 0 && day != last_trade_day_ns_) {
                trades_today_ = 0;
                consecutive_losses_ = 0;
                last_trade_day_ns_ = day;
            }
        }
    }

    void RiskEngine::halt(const std::string& reason) { halted_.store(true); spdlog::critical("HALT: {}", reason); }
    bool RiskEngine::is_halted() const { return halted_.load(); }
    void RiskEngine::reset_day(double new_day_start_equity) {
        std::lock_guard<std::mutex> lock(mutex_);
        day_start_equity_ = new_day_start_equity;
        session_start_equity_ = new_day_start_equity;
        day_start_date_ns_ = 0;
        session_start_date_ns_ = 0;
        trades_today_ = 0;
        consecutive_losses_ = 0;
    }
    void RiskEngine::reset_halt() {
        halted_.store(false);
        std::lock_guard<std::mutex> lock(mutex_);
        consecutive_losses_ = 0;
    }
}
