#pragma once
#include <algorithm>
namespace nexus {
    enum class RLAction { AGGRESSIVE_MARKET, PASSIVE_LIMIT, WAIT };
    /**
     * Heuristic surrogate for a learned PPO policy. Thresholds are documented
     * and match GhostExchangeEnv training distribution (spread 0.05-0.5 bps scaled,
     * vol 0.1-0.5, toxicity 0-1). For production, replace with exported ONNX model
     * via python/quantcore/rl/export_cpp.py.
     *
     * Features are normalized to [0,1] as in Gym env:
     *   spread_norm = spread_bps / 10.0  (0.5-5 bps -> 0.05-0.5)
     *   vol_norm    = vol / 0.1         (0.01-0.05 -> 0.1-0.5)
     */
    inline RLAction get_rl_action(double spread_bps, double vol, double toxicity, double rem_shares, double time_rem) {
        // Clamp inputs to [0,1] expected range
        spread_bps = std::clamp(spread_bps, 0.0, 10.0);
        toxicity = std::clamp(toxicity, 0.0, 1.0);
        rem_shares = std::clamp(rem_shares, 0.0, 1.0);
        time_rem = std::clamp(time_rem, 0.0, 1.0);

        // Urgency: must finish before time runs out
        if (time_rem < 0.2 && rem_shares > 0.1) return RLAction::AGGRESSIVE_MARKET;
        // Toxic flow: don't provide liquidity when adverse selection high
        if (toxicity > 0.7) return RLAction::AGGRESSIVE_MARKET;
        // Wide spread + plenty of time: be passive to capture spread
        if (spread_bps > 3.0 && time_rem > 0.5) return RLAction::PASSIVE_LIMIT;
        // Default: passive if time remains, aggressive near deadline
        if (time_rem < 0.35 && rem_shares > 0.05) return RLAction::AGGRESSIVE_MARKET;
        return RLAction::PASSIVE_LIMIT;
    }
    // Normalized variant matching Gym observation space
    inline RLAction get_rl_action_normalized(double spread_norm, double vol_norm, double toxicity, double rem_shares, double time_rem) {
        return get_rl_action(spread_norm * 10.0, vol_norm * 0.1, toxicity, rem_shares, time_rem);
    }
}
