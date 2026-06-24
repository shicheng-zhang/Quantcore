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
#include <mutex>

#include <ixwebsocket/IXNetSystem.h>
#include <ixwebsocket/IXWebSocket.h>
#include <nlohmann/json.hpp>

using namespace nexus;
using json = nlohmann::json;

SPSCQueue<Event, 2097152> event_queue;
LimitOrderBook lob;

std::atomic<bool> running{true};
std::atomic<uint64_t> events_processed{0};
std::atomic<double> last_price{0.0};
std::vector<double> latencies;
std::mutex latency_mutex;

uint64_t get_nanos() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
}

// --- CONSUMER THREAD (The Hot Path) ---
// THIS IS WHERE PATH B (ALPHA) WILL BE INJECTED LATER
void engine_loop() {
    std::cout << "[NEXUS] Engine loop started. Waiting for live data...\n";
    Event event;

    while (running.load(std::memory_order_relaxed)) {
        if (event_queue.pop(event)) {
            uint64_t process_time = get_nanos();

            // 1. Update LOB (O(1))
            lob.update(event);
            last_price.store(event.price, std::memory_order_relaxed);

            // 2. Evaluate Alpha (Placeholder for Path B)
            // double spread = lob.get_spread_bps();
            // if (spread > 0.5) { trigger_signal(); }

            // 3. Measure Ingest-to-Process Latency
            uint64_t latency = process_time - event.timestamp_ns;
            {
                std::lock_guard<std::mutex> lock(latency_mutex);
                if (latencies.size() < 100000) latencies.push_back(static_cast<double>(latency));
            }

            events_processed.fetch_add(1, std::memory_order_relaxed);
        } else {
            #if defined(__x86_64__)
                __builtin_ia32_pause();
            #endif
        }
    }
}

// --- PRODUCER THREAD (Live Network Ingestor) ---
void live_data_ingestor() {
    ix::initNetSystem();
    ix::WebSocket webSocket;

    // Binance Live Trade Stream
    webSocket.setUrl("wss://stream.binance.com:9443/ws/btcusdt@trade");

    webSocket.setOnMessageCallback([&](const ix::WebSocketMessagePtr& msg) {
        if (msg->type == ix::WebSocketMessageType::Message) {
            uint64_t ingest_time = get_nanos();

            try {
                json j = json::parse(msg->str);
                Event ev;
                ev.type = EventType::ORDER_BOOK_UPDATE;
                ev.timestamp_ns = ingest_time;
                ev.order_id = j["t"].get<uint64_t>();

                // Binance sends strings for precision, we parse to double
                ev.price = std::stod(j["p"].get<std::string>());
                ev.quantity = std::stod(j["q"].get<std::string>());

                // m = true means buyer is market maker (so this was a SELL market order)
                ev.side = j["m"].get<bool>() ? Side::SELL : Side::BUY;

                while (!event_queue.push(ev)) {
                    #if defined(__x86_64__)
                        __builtin_ia32_pause();
                    #endif
                }
            } catch (const std::exception& e) {
                // Drop malformed packets silently (Institutional standard)
            }
        } else if (msg->type == ix::WebSocketMessageType::Open) {
            std::cout << "[NEXUS] Connected to Binance Live Feed!\n";
        } else if (msg->type == ix::WebSocketMessageType::Error) {
            std::cerr << "[NEXUS] WebSocket Error: " << msg->errorInfo.reason << "\n";
        }
    });

    webSocket.start();

    // Keep thread alive while WebSocket runs
    while(running.load()) {
        std::this_thread::sleep_for(std::chrono::seconds(1));
    }

    webSocket.stop();
    ix::uninitNetSystem();
}

// --- TELEMETRY WRITER ---
void telemetry_loop() {
    while(running.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        std::vector<double> current_latencies;
        {
            std::lock_guard<std::mutex> lock(latency_mutex);
            current_latencies = latencies;
        }

        double mean = 0, p99 = 0, max_lat = 0;
        if (!current_latencies.empty()) {
            std::sort(current_latencies.begin(), current_latencies.end());
            mean = std::accumulate(current_latencies.begin(), current_latencies.end(), 0.0) / current_latencies.size();
            p99 = current_latencies[static_cast<size_t>(current_latencies.size() * 0.99)];
            max_lat = current_latencies.back();
        }

        uint64_t total = events_processed.load();

        std::ofstream out("data/nexus_live.json");
        out << "{\n";
        out << "  \"status\": \"LIVE\",\n";
        out << "  \"symbol\": \"BTCUSDT\",\n";
        out << "  \"events_processed\": " << total << ",\n";
        out << "  \"last_price\": " << last_price.load() << ",\n";
        out << "  \"latency_ns_mean\": " << mean << ",\n";
        out << "  \"latency_ns_p99\": " << p99 << ",\n";
        out << "  \"latency_ns_max\": " << max_lat << ",\n";
        out << "  \"best_bid\": " << lob.get_best_bid() << ",\n";
        out << "  \"best_ask\": " << lob.get_best_ask() << ",\n";
        out << "  \"spread_bps\": " << lob.get_spread_bps() << "\n";
        out << "}\n";
        out.close();
    }
}

int main() {
    std::cout << "=== NEXUS LIVE TRADING ENGINE ===\n";

    std::thread consumer(engine_loop);
    std::thread producer(live_data_ingestor);
    std::thread telemetry(telemetry_loop);

    // Run until killed by the OS or FastAPI
    producer.join();
    consumer.join();
    telemetry.join();

    return 0;
}
