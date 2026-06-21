#pragma once
#include "event.h"
#include <array>
#include <limits>
#include <cmath>

namespace nexus {

struct PriceLevel {
    double price;
    double total_volume;
    bool is_active;
};

class LimitOrderBook {
public:
    static constexpr int MAX_LEVELS = 5000;

    LimitOrderBook() : best_bid_(0.0), best_ask_(std::numeric_limits<double>::max()) {
        reset();
    }

    void reset() {
        for (auto& level : bids_) level = {0, 0, false};
        for (auto& level : asks_) level = {0, 0, false};
    }

    void update(const Event& ev) {
        if (ev.side == Side::BUY) {
            if (ev.price > best_bid_) best_bid_ = ev.price;
            // Simplified mapping for demo
            int idx = static_cast<int>((ev.price * 100)) % MAX_LEVELS;
            bids_[idx] = {ev.price, ev.quantity, true};
        } else {
            if (ev.price < best_ask_) best_ask_ = ev.price;
            int idx = static_cast<int>((ev.price * 100)) % MAX_LEVELS;
            asks_[idx] = {ev.price, ev.quantity, true};
        }
    }

    double get_spread_bps() const {
        if (best_bid_ <= 0.0 || best_ask_ >= std::numeric_limits<double>::max()) return 0.0;
        return ((best_ask_ - best_bid_) / best_bid_) * 10000.0;
    }

    double get_best_bid() const { return best_bid_; }
    double get_best_ask() const { return best_ask_; }

private:
    double best_bid_;
    double best_ask_;
    std::array<PriceLevel, MAX_LEVELS> bids_;
    std::array<PriceLevel, MAX_LEVELS> asks_;
};

} // namespace nexus
