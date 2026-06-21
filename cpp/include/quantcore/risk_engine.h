#pragma once
#include "types.h"
#include "event_bus.h"
#include <atomic>
#include <mutex>

namespace quantcore {
    struct RiskConfig { double max_position_pct = 0.05; double max_daily_loss_pct = 0.03; double max_drawdown_pct = 0.10; };
    enum class RiskDecision { APPROVE, REJECT, HALT_TRADING };
    struct RiskResult { RiskDecision decision; std::string reason; };

    class RiskEngine {
    public:
        explicit RiskEngine(const RiskConfig& config, EventBus& bus);
        RiskResult check_order(const Order& order, const PortfolioSnapshot& portfolio);
        void update_portfolio(const PortfolioSnapshot& snapshot);
        void halt(const std::string& reason);
        bool is_halted() const;
    private:
        RiskConfig config_;
        EventBus& bus_;
        std::atomic<bool> halted_{false};
        mutable std::mutex mutex_;
        double peak_equity_ = 0.0;
        double day_start_equity_ = 0.0;
    };
}
