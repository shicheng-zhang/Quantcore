#pragma once
#include <cstdint>
#include <cstring>
#include <cmath>

#pragma pack(push, 1)
struct HiveMindState {
    uint64_t sequence;
    uint64_t py_timestamp;
    uint32_t num_assets;
    char symbols[20][16];
    double target_weights[20];
    double regime_vol;

    uint64_t cpp_timestamp;
    double portfolio_value;
    double total_slippage;
    double realized_pnl;
    uint32_t orders_sent;
    uint32_t orders_filled;
};
#pragma pack(pop)
