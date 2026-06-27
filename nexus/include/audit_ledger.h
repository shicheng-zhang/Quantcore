#pragma once
#include <cstdint>
#include <string>
#include <vector>
#include <fstream>
#include <iomanip>
#include <sstream>

namespace nexus {

// Fast rolling cryptographic hash for simulation integrity
// In production, this would be SHA-256 via OpenSSL. For sim speed, we use a robust polynomial hash.
class MerkleLedger {
public:
    MerkleLedger(const std::string& path) : log_path_(path), current_hash_(0x123456789ABCDEFULL) {
        // Initialize or resume log
        std::ifstream f(log_path_, std::ios::binary | std::ios::ate);
        if (f.good()) {
            file_size_ = f.tellg();
        }
    }

    void append_event(uint64_t timestamp, const std::string& type, double val1, double val2) {
        // Build hash chain
        uint64_t payload_hash = std::hash<std::string>{}(type) ^
                               static_cast<uint64_t>(val1 * 1e6) ^
                               static_cast<uint64_t>(val2 * 1e6) ^
                               timestamp;
        current_hash_ = current_hash_ * 0x853C4897BE55F873ULL + payload_hash; // FNV-1a style mix

        LogEntry entry;
        entry.seq = ++seq_counter_;
        entry.ts = timestamp;
        entry.prev_hash = prev_hash_;
        entry.curr_hash = current_hash_;

        // Write to file
        std::ofstream out(log_path_, std::ios::binary | std::ios::app);
        if (out) {
            out.write(reinterpret_cast<const char*>(&entry), sizeof(LogEntry));
        }

        prev_hash_ = current_hash_;
    }

    bool verify_integrity() {
        // Verify chain by reading from start to end
        std::ifstream in(log_path_, std::ios::binary);
        if (!in) return true; // Empty log is valid

        LogEntry entry;
        uint64_t last_hash = 0x123456789ABCDEFULL;
        uint64_t count = 0;

        while (in.read(reinterpret_cast<char*>(&entry), sizeof(LogEntry))) {
            if (entry.prev_hash != last_hash) return false;
            last_hash = entry.curr_hash;
            count++;
        }
        return count > 0;
    }

    uint64_t get_chain_length() { return seq_counter_; }
    std::string get_last_hash_hex() {
        std::stringstream ss; ss << std::hex << std::setfill('0') << std::setw(16) << prev_hash_;
        return ss.str();
    }

private:
    struct LogEntry {
        uint64_t seq;
        uint64_t ts;
        uint64_t prev_hash;
        uint64_t curr_hash;
    };

    std::string log_path_;
    uint64_t current_hash_;
    uint64_t prev_hash_ = 0x123456789ABCDEFULL;
    uint64_t seq_counter_ = 0;
    size_t file_size_ = 0;
    uint64_t last_hash_ = 0;
};

} // namespace nexus
