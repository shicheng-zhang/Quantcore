#pragma once
#include <cstdint>
#include <cstring>
#include <cmath>

#pragma pack(push, 1)
struct HiveMindState {
    // Base Portfolio Weights (Inverse Vol)
    uint64_t sequence;
    uint64_t py_timestamp;
    uint32_t num_assets;
    char symbols[20][16];
    double target_weights[20];
    double regime_vol;

    // --- MODULE 1: STATARB OVERLAY ---
    int8_t statarb_signal;       // -1 (Short Spread), 0 (Flat), 1 (Long Spread)
    double statarb_hedge_ratio;  // Beta
    double statarb_spread_z;     // Current Z-Score
    char statarb_pair_s1[16];    // Asset A
    char statarb_pair_s2[16];    // Asset B

    // C++ Feedback
    uint64_t cpp_timestamp;
    double portfolio_value;
    double total_slippage;
    double realized_pnl;
    uint32_t orders_sent;
    uint32_t orders_filled;
};
#pragma pack(pop)
