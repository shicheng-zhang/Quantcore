#include "quantcore/risk_engine.h"
#include <spdlog/spdlog.h>

namespace quantcore {
    RiskEngine::RiskEngine(const RiskConfig& config, EventBus& bus) : config_(config), bus_(bus) {}

    RiskResult RiskEngine::check_order(const Order& order, const PortfolioSnapshot& portfolio) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (halted_.load()) return {RiskDecision::REJECT, "Trading halted"};
        double daily_loss_pct = (day_start_equity_ > 0) ? (day_start_equity_ - portfolio.total_equity) / day_start_equity_ : 0.0;
        if (daily_loss_pct >= config_.max_daily_loss_pct) { halt("Daily loss limit"); return {RiskDecision::HALT_TRADING, "Daily loss"}; }
        double position_value = order.quantity * order.limit_price.value_or(0);
        if (portfolio.total_equity > 0 && (position_value / portfolio.total_equity) > config_.max_position_pct) return {RiskDecision::REJECT, "Position too large"};
        return {RiskDecision::APPROVE, ""};
    }

    void RiskEngine::update_portfolio(const PortfolioSnapshot& snapshot) {
        std::lock_guard<std::mutex> lock(mutex_);
        if (snapshot.total_equity > peak_equity_) peak_equity_ = snapshot.total_equity;
        if (peak_equity_ > 0 && ((peak_equity_ - snapshot.total_equity) / peak_equity_) >= config_.max_drawdown_pct) halt("Max drawdown");
    }

    void RiskEngine::halt(const std::string& reason) { halted_.store(true); spdlog::critical("HALT: {}", reason); }
    bool RiskEngine::is_halted() const { return halted_.load(); }
}
