#pragma once
#include <cstdint>

namespace nexus {

enum class EventType : uint8_t {
    ORDER_BOOK_UPDATE,
    NEW_ORDER_REQUEST,
    ORDER_FILL,
    ALPHA_SIGNAL
};

enum class Side : uint8_t { BUY, SELL };

// Fixed-size struct. Zero heap allocations.
struct Event {
    EventType type;
    uint64_t timestamp_ns; // Ingest time for latency measurement
    uint64_t order_id;
    char symbol[16];
    Side side;
    double price;
    double quantity;
};

} // namespace nexus
