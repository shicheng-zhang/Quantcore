#pragma once

#include "event.h"

#include <cmath>
#include <cstddef>
#include <functional>
#include <iterator>
#include <limits>
#include <map>

namespace nexus {

struct PriceLevel {
    double price = 0.0;
    double total_volume = 0.0;
    bool is_active = false;
};

// Corrected Limit Order Book.
//
// The previous implementation hashed prices into a fixed array:
//
//     int idx = static_cast<int>((ev.price * 100)) % MAX_LEVELS;
//     bids_[idx] = {ev.price, ev.quantity, true};
//
// That design had four correctness bugs:
//   1. Hash collisions: BTC prices 50.00 apart (65000.00 vs 65050.00)
//      map to the same slot and silently overwrite each other.
//   2. Volume was overwritten, never aggregated, at a price level.
//   3. Cancels (quantity = 0) stored an "active" zero-volume level
//      instead of removing the level.
//   4. best_bid_ only ratcheted up and best_ask_ only ratcheted down,
//      so after the best level was consumed the book reported a stale
//      best price forever.
//
// This version keys levels by exact price in ordered maps:
//   - bids_ sorted descending: bids_.begin() is always the best bid
//   - asks_ sorted ascending:  asks_.begin() is always the best ask
// Best prices are always derived from surviving levels, so they walk
// back correctly. Complexity is O(log n) per update instead of the
// previous fictional O(1): correctness first, micro-optimisation second.
class LimitOrderBook {
public:
    // Synthetic generators random-walk forever; bound memory per side.
    static constexpr std::size_t MAX_LEVELS_PER_SIDE = 1024;

    LimitOrderBook() = default;

    void reset() {
        bids_.clear();
        asks_.clear();
    }

    void update(const Event& ev) {
        if (!std::isfinite(ev.price) || ev.price <= 0.0) return;

        if (ev.side == Side::BUY) {
            apply(bids_, ev);
            prune_tail(bids_);
        } else {
            apply(asks_, ev);
            prune_tail(asks_);
        }
    }

    double get_best_bid() const {
        return bids_.empty() ? 0.0 : bids_.begin()->first;
    }

    double get_best_ask() const {
        return asks_.empty() ? std::numeric_limits<double>::max()
                             : asks_.begin()->first;
    }

    double get_spread_bps() const {
        if (bids_.empty() || asks_.empty()) return 0.0;
        const double bid = bids_.begin()->first;
        const double ask = asks_.begin()->first;
        // Synthetic generators can produce a crossed book; report 0
        // rather than a negative spread.
        if (bid <= 0.0 || ask <= bid) return 0.0;
        return ((ask - bid) / bid) * 10000.0;
    }

    std::size_t bid_levels() const { return bids_.size(); }
    std::size_t ask_levels() const { return asks_.size(); }

private:
    // Bids sorted descending (begin() == highest); asks ascending
    // (begin() == lowest).
    std::map<double, PriceLevel, std::greater<double>> bids_;
    std::map<double, PriceLevel> asks_;

    // Quantize price to tick size (1 cent) to avoid floating epsilon collisions
    // where 100.01 != 100.0100000001 creates duplicate levels.
    static double quantize_price(double p) {
        return std::round(p * 100.0) / 100.0;
    }

    template <typename Book>
    static void apply(Book& book, const Event& ev) {
        double qprice = quantize_price(ev.price);
        auto it = book.find(qprice);
        if (ev.quantity <= 0.0) {
            // Cancel: remove the level entirely.
            if (it != book.end()) book.erase(it);
            return;
        }
        if (it == book.end()) {
            book.emplace(qprice, PriceLevel{qprice, ev.quantity, true});
        } else {
            // Aggregate volume at an existing price level.
            it->second.total_volume += ev.quantity;
            it->second.is_active = true;
        }
    }

    // Both maps are ordered from best price towards worst, so erasing
    // from the end always drops the level furthest from the touch.
    template <typename Book>
    static void prune_tail(Book& book) {
        while (book.size() > MAX_LEVELS_PER_SIDE) {
            book.erase(std::prev(book.end()));
        }
    }
};

} // namespace nexus
