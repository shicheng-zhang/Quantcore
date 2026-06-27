#pragma once
#include <atomic>
#include <string>
#include <random>

namespace nexus {

class InstitutionalOps {
public:
    // Phase 1: Kill Switch Architecture
    std::atomic<bool> kill_switch{false};
    std::atomic<uint64_t> halt_timestamp{0};
    std::string halt_reason = "NOMINAL";

    // Phase 4: Smart Order Routing (SOR) & Dark Pools
    std::atomic<uint64_t> lit_venue_fills{0};
    std::atomic<uint64_t> dark_pool_fills{0};
    std::atomic<double> dark_pool_improvement_bps{0.0};

    // Phase 5: Regulatory Surveillance
    std::atomic<bool> regulatory_halt{false};
    std::atomic<uint64_t> spoofing_flags{0};

    // SOR Logic: Fragments order between Lit and Dark
    void route_order(uint64_t qty, double price) {
        if (kill_switch.load()) return;

        // 70% Lit, 30% Dark
        uint64_t dark_qty = static_cast<uint64_t>(qty * 0.30);
        uint64_t lit_qty = qty - dark_qty;

        lit_venue_fills.fetch_add(lit_qty);
        dark_pool_fills.fetch_add(dark_qty);

        // Dark pools provide price improvement (simulated)
        double improvement = 0.05 + (static_cast<double>(rand() % 100) / 10000.0);
        dark_pool_improvement_bps.store(improvement * 10000.0);
    }

    // Surveillance Check: Reads Python's halt flag
    void check_surveillance() {
        if (regulatory_halt.load()) return;

        // Check if Python surveillance daemon triggered a halt
        FILE* f = fopen("data/surveillance_halt.flag", "r");
        if (f) {
            fclose(f);
            regulatory_halt.store(true);
            kill_switch.store(true);
            halt_timestamp.store(std::chrono::duration_cast<std::chrono::nanoseconds>(
                std::chrono::steady_clock::now().time_since_epoch()).count());
            halt_reason = "REGULATORY_HALT: SPOOFING_DETECTED";
            remove("data/surveillance_halt.flag");
        }
    }

    void manual_kill(const std::string& reason) {
        kill_switch.store(true);
        halt_timestamp.store(std::chrono::duration_cast<std::chrono::nanoseconds>(
            std::chrono::steady_clock::now().time_since_epoch()).count());
        halt_reason = reason;
    }

    void reset() {
        kill_switch.store(false);
        regulatory_halt.store(false);
        halt_reason = "NOMINAL";
        spoofing_flags.fetch_add(1); // Log that we reset
    }
};

} // namespace nexus
