#pragma once
#include "event.h"
#include <atomic>
#include <mutex>
#include <vector>
#include <cmath>
#include <random>

namespace nexus {

struct ExecutionReality {
    std::atomic<bool> is_active{false};
    std::atomic<uint64_t> target_shares{0};
    std::atomic<uint64_t> filled_shares{0};
    std::atomic<double> theoretical_price{0.0};
    std::atomic<double> actual_avg_price{0.0};
    std::atomic<double> total_slippage_usd{0.0};
    std::atomic<int> queue_ahead{0};
    std::atomic<int> partial_fills{0};
    std::atomic<double> current_market_price{0.0};
};

class GhostExchange {
public:
    GhostExchange() : mt_(std::random_device{}()) {}

    // The core physics engine: Almgren-Chriss Market Impact + Queue Toxicity
    void simulate_execution(uint64_t shares, double base_price, double volatility) {
        reality.is_active.store(true);
        reality.target_shares.store(shares);
        reality.filled_shares.store(0);
        reality.theoretical_price.store(base_price);
        reality.actual_avg_price.store(0.0);
        reality.total_slippage_usd.store(0.0);
        reality.partial_fills.store(0);

        double cumulative_cost = 0.0;
        uint64_t remaining = shares;

        // Simulate the order being sliced into child orders by the EMS
        uint64_t child_size = std::max(uint64_t(100), shares / 50);

        while (remaining > 0 && reality.is_active.load()) {
            uint64_t current_child = std::min(child_size, remaining);

            // 1. Calculate Queue Position (Toxicity)
            // The larger your order relative to average volume, the further back you are
            int queue_pos = static_cast<int>((current_child / 1000.0) * (1.0 + volatility * 10));
            reality.queue_ahead.store(queue_pos);

            // 2. Simulate Partial Fills & Time Delay
            // The market doesn't give you everything at once. It bleeds you.
            uint64_t filled_this_tick = static_cast<uint64_t>(current_child * (0.1 + dist_(mt_) * 0.4));
            if (filled_this_tick > remaining) filled_this_tick = remaining;

            // 3. Almgren-Chriss Slippage Calculation
            // Slippage = eta * sigma * sqrt(Qty / Volume) * sign
            // We simulate a hostile eta (market impact coefficient)
            double eta = 0.15;
            double slip_bps = eta * volatility * std::sqrt(static_cast<double>(current_child) / 10000.0) * 10000.0;
            double slip_price = base_price * (slip_bps / 10000.0);

            // Add stochastic noise (the market is moving against you while you wait in queue)
            slip_price += (dist_(mt_) - 0.5) * base_price * volatility * 0.5;

            double fill_price = base_price + slip_price;

            // Update Reality Telemetry
            cumulative_cost += (fill_price * filled_this_tick);
            uint64_t total_filled = reality.filled_shares.load() + filled_this_tick;
            reality.filled_shares.store(total_filled);
            reality.actual_avg_price.store(cumulative_cost / total_filled);
            reality.total_slippage_usd.store((reality.actual_avg_price.load() - base_price) * total_filled);
            reality.partial_fills.fetch_add(1);

            remaining -= filled_this_tick;
            base_price += slip_price * 0.1; // The price permanently shifts against you (Permanent Impact)
            reality.current_market_price.store(base_price);

            // Simulate network/matching delay (microseconds to milliseconds)
            std::this_thread::sleep_for(std::chrono::milliseconds(50 + static_cast<int>(dist_(mt_) * 100)));
        }

        reality.queue_ahead.store(0);
        // Keep is_active true so the UI shows the final brutal result
    }

    void abort() {
        reality.is_active.store(false);
    }

    ExecutionReality reality;

private:
    std::mt19937 mt_;
    std::uniform_real_distribution<double> dist_{0.0, 1.0};
};

} // namespace nexus
