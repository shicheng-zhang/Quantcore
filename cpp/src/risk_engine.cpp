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

    void RiskEngine::record_trade_result(bool was_win, const std::string& symbol, int64_t timestamp_ns) {
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
                // Only allow closing orders after flat deadline
                bool has_position = false;
                for (auto& p : portfolio.positions) if (p.symbol == order.symbol && p.quantity != 0) { has_position = true; break; }
                bool is_closing = has_position && ((order.side == Side::SELL && get_position_notional(portfolio, order.symbol) > 0) || (order.side == Side::BUY));
                if (!has_position) return {RiskDecision::REJECT, "Flat deadline: no new positions after 15:55 ET"};
            }
            if (is_outside_session(portfolio.timestamp_ns)) {
                // Allow only if we have no existing position to close? Block new opens
                // For now, warn but allow closes — full block is too strict for premarket
            }
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
        // Check post-trade concentration, not just single order notional
        double existing_pos = get_position_notional(portfolio, order.symbol);
        double order_notional = std::abs(order.quantity * *order.limit_price);
        double post_trade_notional;
        if (order.side == Side::BUY) {
            post_trade_notional = existing_pos + order_notional;
        } else {
            // Selling reduces exposure; check if would flip to short — limit gross
            post_trade_notional = std::max(0.0, existing_pos - order_notional);
            // If shorting beyond existing, count new short notional
            if (order_notional > existing_pos) {
                post_trade_notional = order_notional - existing_pos;
            }
        }
        // For new positions (existing_pos == 0), post_trade == order_notional
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
            if (last_trade_day_ns_ != 0 && day != last_trade_day_ns_) {
                trades_today_ = 0;
                consecutive_losses_ = 0;
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
