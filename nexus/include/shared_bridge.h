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

// CRITICAL: Compile-time verification that struct layout matches Python ctypes.
// If this fails, the Python HiveMindState in quant_daemon.py is out of sync.
// Expected layout (pack=1):
//   [0]   sequence        uint64  (8)
//   [8]   py_timestamp    uint64  (8)
//   [16]  num_assets      uint32  (4)
//   [20]  symbols         char[20][16] (320)
//   [340] target_weights  double[20]   (160)
//   [500] regime_vol      double  (8)
//   [508] statarb_signal  int8    (1)
//   [509] statarb_hedge_ratio double (8)
//   [517] statarb_spread_z    double (8)
//   [525] statarb_pair_s1 char[16] (16)
//   [541] statarb_pair_s2 char[16] (16)
//   [557] cpp_timestamp   uint64  (8)
//   [565] portfolio_value double  (8)
//   [573] total_slippage  double  (8)
//   [581] realized_pnl    double  (8)
//   [589] orders_sent     uint32  (4)
//   [593] orders_filled   uint32  (4)
//   TOTAL = 597 bytes
static_assert(sizeof(HiveMindState) == 597,
    "HiveMindState size mismatch! Python ctypes struct is out of sync. "
    "Update python/quantcore/hivemind/quant_daemon.py to match.");

#pragma pack(pop)
