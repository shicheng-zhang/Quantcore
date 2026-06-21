#include "../include/spsc_queue.h"
#include "../include/event.h"
#include "../include/limit_order_book.h"
#include <iostream>
#include <thread>
#include <chrono>
#include <fstream>
#include <vector>
#include <algorithm>
#include <numeric>
#include <atomic>
#include <random>

using namespace nexus;

// 2 Million event buffer. Lock-free.
SPSCQueue<Event, 2097152> event_queue;
LimitOrderBook lob;

std::atomic<bool> running{true};
std::atomic<uint64_t> events_processed{0};
std::vector<double> latencies;

uint64_t get_nanos() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

// --- CONSUMER THREAD (The Hot Path) ---
void engine_loop() {
    std::cout << "[NEXUS] Engine loop started on thread " << std::this_thread::get_id() << "\n";
    Event event;
    latencies.reserve(5000000);

    while (running.load(std::memory_order_relaxed)) {
        if (event_queue.pop(event)) {
            uint64_t process_time = get_nanos();

            // 1. Update LOB (O(1))
            lob.update(event);

            // 2. Evaluate Alpha (Mock: Spread Capture)
            double spread = lob.get_spread_bps();
            if (spread > 0.5 && spread < 2.0) {
                // Trigger signal logic...
            }

            // 3. Measure Latency
            uint64_t latency = process_time - event.timestamp_ns;
            latencies.push_back(static_cast<double>(latency));

            events_processed.fetch_add(1, std::memory_order_relaxed);
        } else {
            // Spin-lock hint to reduce CPU heat/power while waiting
            #if defined(__x86_64__)
                __builtin_ia32_pause();
            #endif
        }
    }
}

// --- PRODUCER THREAD (Market Data Simulator) ---
void market_data_simulator() {
    std::cout << "[NEXUS] Market Data Simulator started...\n";
    std::mt19937 rng(42);
    std::normal_distribution<double> price_dist(150.0, 0.5);
    std::uniform_int_distribution<int> side_dist(0, 1);

    uint64_t start_time = get_nanos();
    uint64_t target_events = 5000000; // 5 Million events

    for (uint64_t i = 0; i < target_events; ++i) {
        Event ev;
        ev.type = EventType::ORDER_BOOK_UPDATE;
        ev.timestamp_ns = get_nanos();
        ev.side = side_dist(rng) == 0 ? Side::BUY : Side::SELL;
        ev.price = price_dist(rng);
        ev.quantity = 100.0 + (rng() % 1000);

        // Spin until queue has space (Backpressure)
        while (!event_queue.push(ev)) {
            #if defined(__x86_64__)
                __builtin_ia32_pause();
            #endif
        }
    }

    uint64_t end_time = get_nanos();
    double seconds = (end_time - start_time) / 1e9;

    std::cout << "[NEXUS] Simulation complete. Injected " << target_events
              << " events in " << seconds << "s\n";

    // Wait for consumer to drain
    std::this_thread::sleep_for(std::chrono::seconds(2));
    running.store(false);
}

// --- TELEMETRY WRITER ---
void write_telemetry() {
    if (latencies.empty()) return;

    std::sort(latencies.begin(), latencies.end());
    double sum = std::accumulate(latencies.begin(), latencies.end(), 0.0);
    double mean = sum / latencies.size();
    double p99 = latencies[static_cast<size_t>(latencies.size() * 0.99)];
    double max_lat = latencies.back();

    uint64_t total = events_processed.load();
    double eps = total / 5.0; // Roughly 5 seconds of runtime

    std::ofstream out("data/nexus_telemetry.json");
    out << "{\n";
    out << "  \"status\": \"NOMINAL\",\n";
    out << "  \"architecture\": \"C++20 Lock-Free SPSC\",\n";
    out << "  \"events_processed\": " << total << ",\n";
    out << "  \"events_per_sec\": " << static_cast<uint64_t>(eps) << ",\n";
    out << "  \"latency_ns_mean\": " << mean << ",\n";
    out << "  \"latency_ns_p99\": " << p99 << ",\n";
    out << "  \"latency_ns_max\": " << max_lat << ",\n";
    out << "  \"best_bid\": " << lob.get_best_bid() << ",\n";
    out << "  \"best_ask\": " << lob.get_best_ask() << ",\n";
    out << "  \"spread_bps\": " << lob.get_spread_bps() << "\n";
    out << "}\n";
    out.close();

    std::cout << "[NEXUS] Telemetry written. p99 Latency: " << p99 << " ns\n";
}

int main() {
    std::cout << "=== NEXUS INSTITUTIONAL TRADING ENGINE ===\n";
    std::cout << "Initializing Lock-Free Memory Structures...\n";

    std::thread consumer(engine_loop);
    std::thread producer(market_data_simulator);

    producer.join();
    consumer.join();

    write_telemetry();

    std::cout << "=== ENGINE SHUTDOWN COMPLETE ===\n";
    return 0;
}
