#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <optional>

namespace quantcore {
    enum class Side : uint8_t { BUY = 0, SELL = 1 };
    enum class OrderType : uint8_t { MARKET, LIMIT, STOP };
    struct Tick { std::string symbol; int64_t timestamp_ns; double price, volume; };
    struct Order { uint64_t id; std::string symbol; Side side; OrderType type; double quantity; std::optional<double> limit_price; };
    struct FeatureRow { std::string symbol; int64_t timestamp_ns; std::vector<float> features; std::optional<double> target; };
    struct Position { std::string symbol; double quantity, average_cost, unrealized_pnl; };
    struct PortfolioSnapshot { int64_t timestamp_ns; double total_equity, cash, daily_pnl, drawdown_pct; std::vector<Position> positions; };
}
