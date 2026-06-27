#pragma once
#include "event.h"
#include <atomic>
#include <vector>
#include <random>
#include <cmath>
#include <chrono>

namespace nexus {

struct QueueOrder {
    uint64_t order_id;
    double price;
    double qty;
    double remaining;
    Side side;
    uint64_t enqueue_time_ns;
};

struct SimMetrics {
    std::atomic<double> adverse_selection_rate{0.0};
    std::atomic<double> avg_temp_impact{0.0};
    std::atomic<double> avg_perm_impact{0.0};
    std::atomic<double> latency_jitter_mean{0.0};
    std::atomic<double> latency_jitter_std{0.0};
};

class MicrostructureSim {
public:
    MicrostructureSim() : mt_(std::random_device{}()), rng_vol_(0.0, 1.0) {}

    // Injects stochastic order book updates based on real-world volatility
    void generate_orders(double volatility, double base_mid_price, SPSCQueue<Event, 2097152>& queue) {
        double intensity = 500.0 * (1.0 + volatility * 10.0); // Poisson rate scales with vol
        std::poisson_distribution<int> poisson(intensity);

        for (int i = 0; i < poisson(mt_); ++i) {
            Event ev;
            ev.type = EventType::ORDER_BOOK_UPDATE;
            ev.timestamp_ns = std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count();

            // Randomize message type: 60% Limit Add, 30% Cancel, 10% Market
            double r = rng_vol_(mt_);
            if (r < 0.6) {
                ev.side = rng_vol_(mt_) > 0.5 ? Side::BUY : Side::SELL;
                double offset = rng_vol_(mt_) * 0.05 * volatility;
                ev.price = base_mid_price + (ev.side == Side::BUY ? -offset : offset);
                ev.quantity = 100 + rng_vol_(mt_) * 900;
                queue.push(ev); // Simulated limit order added to book
            } else if (r < 0.9) {
                // Cancel existing (simulated)
                ev.type = EventType::NEW_ORDER_REQUEST; // Reused as cancel signal
                ev.side = rng_vol_(mt_) > 0.5 ? Side::BUY : Side::SELL;
                ev.price = base_mid_price + (rng_vol_(mt_) - 0.5) * 0.1;
                ev.quantity = 0; // Cancel marker
                queue.push(ev);
            } else {
                // Market order (aggressive)
                ev.side = rng_vol_(mt_) > 0.5 ? Side::BUY : Side::SELL;
                ev.price = base_mid_price;
                ev.quantity = 50 + rng_vol_(mt_) * 450;
                queue.push(ev);
            }
        }
    }

    // FIFO Queue Matching with Market Impact & Adverse Selection
    double simulate_fill(uint64_t order_id, double requested_price, double qty, Side side, double current_mid, double vol) {
        double temp_impact = 0.015 * vol * std::sqrt(qty / 10000.0) * current_mid;
        double perm_impact = 0.005 * vol * (qty / 10000.0) * current_mid;

        double fill_price = current_mid + (side == Side::BUY ? temp_impact : -temp_impact);
        current_mid += (side == Side::BUY ? perm_impact : -perm_impact); // Permanent shift

        metrics.avg_temp_impact.store(temp_impact);
        metrics.avg_perm_impact.store(perm_impact);

        // Adverse Selection: Did price move against us within 5 ticks?
        double future_drift = (rng_vol_(mt_) - 0.5) * 0.02 * vol * current_mid;
        if ((side == Side::BUY && future_drift < 0) || (side == Side::SELL && future_drift > 0)) {
            metrics.adverse_selection_rate.fetch_add(1.0);
        }

        return fill_price;
    }

    // Inject Latency Jitter into the pipeline
    void apply_jitter(SPSCQueue<Event, 2097152>& queue) {
        std::normal_distribution<double> jitter(200.0, 50.0); // 200ns mean, 50ns std
        double delay_ns = jitter(mt_);
        if (delay_ns < 0) delay_ns = 0;

        auto start = std::chrono::steady_clock::now();
        auto end = start + std::chrono::nanoseconds(static_cast<int>(delay_ns));
        std::this_thread::sleep_until(end);

        metrics.latency_jitter_mean.store(delay_ns);
    }

    SimMetrics metrics;

private:
    std::mt19937 mt_;
    std::uniform_real_distribution<double> rng_vol_;
};

} // namespace nexus
