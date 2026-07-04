def generate_cpp_header():
    cpp_code = """#pragma once
namespace nexus {
    enum class RLAction { AGGRESSIVE_MARKET, PASSIVE_LIMIT, WAIT };
    inline RLAction get_rl_action(double spread_bps, double vol, double toxicity, double rem_shares, double time_rem) {
        if (time_rem < 0.2 && rem_shares > 0.1) return RLAction::AGGRESSIVE_MARKET;
        if (toxicity > 0.7) return RLAction::AGGRESSIVE_MARKET;
        if (spread_bps > 3.0 && time_rem > 0.5) return RLAction::PASSIVE_LIMIT;
        return RLAction::PASSIVE_LIMIT;
    }
}
"""
    with open("nexus/include/rl_policy.h", "w") as f: f.write(cpp_code)
    print("[RL] Generated nexus/include/rl_policy.h")

if __name__ == "__main__":
    generate_cpp_header()
