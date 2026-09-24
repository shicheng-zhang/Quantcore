#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <optional>

namespace quantcore {
    enum class Side : uint8_t { BUY = 0, SELL = 1 };
    enum class OrderType : uint8_t { MARKET, LIMIT, STOP };
    struct Tick { std::string symbol; int64_t timestamp_ns; double price, volume; };
    struct Bar { int64_t timestamp_ns; double open, high, low, close, volume; };
    struct Order { uint64_t id; std::string symbol; Side side; OrderType type; double quantity; std::optional<double> limit_price; };
    struct FeatureRow { std::string symbol; int64_t timestamp_ns; std::vector<float> features; std::optional<double> target; };
    struct Position { std::string symbol; double quantity, average_cost, unrealized_pnl; int64_t entry_time_ns = 0; };
    struct PortfolioSnapshot { int64_t timestamp_ns; double total_equity, cash, daily_pnl, drawdown_pct; std::vector<Position> positions; };
    struct VolumeProfileLevel { double price = 0.0; double volume = 0.0; bool is_poc = false; bool in_value_area = false; };
    struct VolumeProfile { double poc = 0.0; double vah = 0.0; double val = 0.0; std::vector<VolumeProfileLevel> levels; };
    struct MicrostructureFeatures {
        double obi = 0.0;                    // (bid-av)/(bid+av) [-1,1]
        double queue_imbalance = 0.0;        // (bid_size - ask_size)/(bid+ask) at BBO
        double cumulative_delta = 0.0;       // sum(signed volume)
        double delta_imbalance = 0.0;        // (buy_vol - sell_vol)/total_vol
        double kyle_lambda = 0.0;            // price impact per volume
        double effective_spread_bps = 0.0;   // 2*|price-mid|/mid *1e4
        double realized_spread_bps = 0.0;    // price change vs mid after 5s
        double vpin = 0.0;                   // order flow toxicity [0,1]
        double spread_bps = 0.0;
    };
}
