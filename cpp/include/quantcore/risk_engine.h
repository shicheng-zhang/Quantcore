#pragma once
#include "types.h"
#include "event_bus.h"
#include <atomic>
#include <mutex>
#include <chrono>

namespace quantcore {
    struct RiskConfig {
        double max_position_pct = 0.05;
        double max_daily_loss_pct = 0.03;
        double max_drawdown_pct = 0.10;
        // Day-trading specific limits
        double max_intraday_loss_pct = 0.02;      // 2% session loss (tighter than daily)
        int max_trades_per_day = 50;              // throttle overtrading
        int max_consecutive_losses = 5;           // halt after N losing trades in a row
        int max_position_hold_minutes = 120;      // 2h max hold for day trades
        int64_t session_start_ns = 0;             // 09:30 ET in ns since midnight ET (set at runtime)
        int64_t session_end_ns = 0;               // 16:00 ET
        int64_t flat_deadline_ns = 0;             // 15:55 ET - must be flat
    };
    enum class RiskDecision { APPROVE, REJECT, HALT_TRADING };
    struct RiskResult { RiskDecision decision; std::string reason; };

    class RiskEngine {
    public:
        explicit RiskEngine(const RiskConfig& config, EventBus& bus);
        RiskResult check_order(const Order& order, const PortfolioSnapshot& portfolio);
        void update_portfolio(const PortfolioSnapshot& snapshot);
        void record_trade_result(bool was_win, const std::string& symbol, int64_t timestamp_ns);
        bool is_flat_deadline(int64_t timestamp_ns) const;
        bool is_outside_session(int64_t timestamp_ns) const;
        void halt(const std::string& reason);
        bool is_halted() const;
        void reset_day(double new_day_start_equity);
        void reset_halt();
        // Day trading state
        int trades_today() const { return trades_today_; }
        int consecutive_losses() const { return consecutive_losses_; }
    private:
        RiskConfig config_;
        EventBus& bus_;
        std::atomic<bool> halted_{false};
        mutable std::mutex mutex_;
        double peak_equity_ = 0.0;
        double day_start_equity_ = 0.0;
        double session_start_equity_ = 0.0;
        int64_t day_start_date_ns_ = 0;
        int64_t session_start_date_ns_ = 0;
        double get_position_notional(const PortfolioSnapshot& portfolio, const std::string& symbol) const;
        // Session tracking
        int trades_today_ = 0;
        int consecutive_losses_ = 0;
        int64_t last_trade_day_ns_ = 0;
    };
}
