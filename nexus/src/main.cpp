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

#include "../include/microstructure_sim.h"
#include "../include/audit_ledger.h"
#include "../include/institutional_ops.h"


#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include "../include/shared_bridge.h"

#include "../include/ghost_exchange.h"
#include "../include/rl_policy.h"

#include <ixwebsocket/IXNetSystem.h>
#include <ixwebsocket/IXWebSocket.h>
#include <ixwebsocket/IXWebSocketServer.h>
#include <nlohmann/json.hpp>

using namespace nexus;
using json = nlohmann::json;

SPSCQueue<Event, 2097152> event_queue;
LimitOrderBook lob;

MicrostructureSim micro_sim;
MerkleLedger audit_log("data/audit_ledger.bin");
std::atomic<uint64_t> sim_fills{0};
std::atomic<double> sim_pnl{0.0};
InstitutionalOps ops;

GhostExchange ghost_lob;

// --- HIVE-MIND SHARED MEMORY BRIDGE ---
HiveMindState* hive_bridge = nullptr;
double current_weights[20] = {0};
double portfolio_value = 100000.0;

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

            
            // --- HIVE-MIND IPC READER ---
            if (hive_bridge) {
                uint64_t seq = *(volatile uint64_t*)&hive_bridge->sequence;
                static uint64_t last_seq = 0;
                if (seq != last_seq) {
                    last_seq = seq;
                    uint32_t n = hive_bridge->num_assets;
                    double vol = hive_bridge->regime_vol;
                    if (vol == 0.0) vol = 0.05; // Fallback

                    // --- MODULE 1: STATARB PAIR EXECUTION ---
                    int8_t arb_sig = *(volatile int8_t*)&hive_bridge->statarb_signal;
                    if (arb_sig != 0) {
                        double beta = *(volatile double*)&hive_bridge->statarb_hedge_ratio;
                        double z = *(volatile double*)&hive_bridge->statarb_spread_z;

                        // Simulate Pair Trade: Long S1, Short S2 (or vice versa)
                        double price_s1 = 100.0 + (rand() % 500) / 100.0; // Synthetic price
                        double price_s2 = 100.0 + (rand() % 500) / 100.0;

                        uint64_t qty_s1 = 1000;
                        uint64_t qty_s2 = static_cast<uint64_t>(qty_s1 * beta);

                        // Execute Leg 1
                        double fill1 = micro_sim.simulate_fill(1, price_s1, qty_s1,
                            arb_sig > 0 ? Side::BUY : Side::SELL, price_s1, vol);

                        // Execute Leg 2 (Hedged)
                        double fill2 = micro_sim.simulate_fill(2, price_s2, qty_s2,
                            arb_sig > 0 ? Side::SELL : Side::BUY, price_s2, vol);

                        // PnL is the convergence of the spread minus slippage
                        double spread_pnl = (fill1 - fill2) * (arb_sig > 0 ? 1 : -1);

                        *(volatile double*)&hive_bridge->realized_pnl += spread_pnl;
                        *(volatile uint32_t*)&hive_bridge->orders_sent += 2;
                        *(volatile uint32_t*)&hive_bridge->orders_filled += 2;

                        // Audit the pair trade
                        audit_log.append_event(get_nanos(), "STATARB_PAIR_EXEC", z, spread_pnl);
                    }

                    for (uint32_t i = 0; i < n && i < 20; ++i) {
                        double target_w = hive_bridge->target_weights[i];
                        double delta_w = target_w - current_weights[i];

                        if (std::abs(delta_w) > 0.001) {
                            double target_value = portfolio_value * target_w;
                            double current_value = portfolio_value * current_weights[i];
                            double delta_value = target_value - current_value;

                            double price = last_price.load();
                            if (price > 0) {
                                uint64_t shares = static_cast<uint64_t>(std::abs(delta_value) / price);
                                if (shares > 10) {
                                    // Ghost Exchange Slippage Physics
                                    double eta = 0.15;
                                    double slip_bps = eta * vol * std::sqrt(static_cast<double>(shares) / 10000.0) * 10000.0;
                                    double slip_price = price * (slip_bps / 10000.0);
                                    double fill_price = price + (delta_w > 0 ? slip_price : -slip_price);

                                    double slippage_usd = std::abs(fill_price - price) * shares;

                                    // Write Feedback to Python
                                    *(volatile double*)&hive_bridge->total_slippage += slippage_usd;
                                    *(volatile double*)&hive_bridge->realized_pnl -= slippage_usd; // Slippage is a cost
                                    *(volatile uint32_t*)&hive_bridge->orders_sent += 1;
                                    *(volatile uint32_t*)&hive_bridge->orders_filled += 1;
                                    *(volatile uint64_t*)&hive_bridge->cpp_timestamp = get_nanos();

                                    current_weights[i] = target_w;
                                }
                            }
                        }
                    }
                    *(volatile double*)&hive_bridge->portfolio_value = portfolio_value;
                }
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

        json telemetry_json;
    telemetry_json["status"] = "LIVE";
    telemetry_json["symbol"] = "BTCUSDT";
    telemetry_json["events_processed"] = total;
    telemetry_json["last_price"] = last_price.load();
    telemetry_json["latency_ns_mean"] = mean;
    telemetry_json["latency_ns_p99"] = p99;
    telemetry_json["latency_ns_max"] = max_lat;
    telemetry_json["best_bid"] = lob.get_best_bid();
    telemetry_json["best_ask"] = lob.get_best_ask();
    telemetry_json["spread_bps"] = lob.get_spread_bps();
    telemetry_json["ghost_active"] = ghost_lob.reality.is_active.load();
    telemetry_json["ghost_target"] = ghost_lob.reality.target_shares.load();
    telemetry_json["ghost_filled"] = ghost_lob.reality.filled_shares.load();
    telemetry_json["ghost_theo"] = ghost_lob.reality.theoretical_price.load();
    telemetry_json["ghost_actual"] = ghost_lob.reality.actual_avg_price.load();
    telemetry_json["ghost_slippage_usd"] = ghost_lob.reality.total_slippage_usd.load();
    telemetry_json["ghost_queue"] = ghost_lob.reality.queue_ahead.load();
    telemetry_json["ghost_partial_fills"] = ghost_lob.reality.partial_fills.load();
    telemetry_json["sim_fills"] = sim_fills.load();
    telemetry_json["sim_pnl"] = sim_pnl.load();
    telemetry_json["adverse_sel_rate"] = micro_sim.metrics.adverse_selection_rate.load();
    telemetry_json["avg_temp_impact"] = micro_sim.metrics.avg_temp_impact.load();
    telemetry_json["avg_perm_impact"] = micro_sim.metrics.avg_perm_impact.load();
    telemetry_json["latency_jitter_ns"] = micro_sim.metrics.latency_jitter_mean.load();
    telemetry_json["audit_chain_len"] = audit_log.get_chain_length();
    telemetry_json["audit_last_hash"] = audit_log.get_last_hash_hex();
    telemetry_json["lit_fills"] = ops.lit_venue_fills.load();
    telemetry_json["dark_fills"] = ops.dark_pool_fills.load();
    telemetry_json["dark_improvement"] = ops.dark_pool_improvement_bps.load();
    
    std::ofstream out("data/nexus_live.json");
    out << telemetry_json.dump(4);
    out.close();
    }
}


// --- GHOST EXCHANGE STRESS TEST THREAD ---
#include <fstream>
void trigger_ghost_execution(uint64_t, double, double);

void ghost_stress_test_loop() {
    while(running.load()) {
        if (ghost_lob.reality.is_active.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        } else {
            // Check for trigger file from FastAPI
            std::ifstream f("data/ghost_trigger.json");
            if (f.good()) {
                f.seekg(0, std::ios::end);
                size_t size = f.tellg();
                if (size > 10) {
                    f.seekg(0);
                    std::string content((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
                    // Crude JSON parse for speed (no external lib needed for this simple trigger)
                    size_t sh_pos = content.find("\"shares\":");
                    size_t vol_pos = content.find("\"vol\":");
                    if (sh_pos != std::string::npos && vol_pos != std::string::npos) {
                        uint64_t shares = std::stoull(content.substr(sh_pos + 9, content.find(",", sh_pos) - (sh_pos + 9)));
                        double vol = std::stod(content.substr(vol_pos + 6, content.find("}", vol_pos) - (vol_pos + 6)));
                        double price = ghost_lob.reality.current_market_price.load();
                        if (price == 0.0) price = last_price.load();
                        if (price > 0) {
                            std::remove("data/ghost_trigger.json");
                            trigger_ghost_execution(shares, price, vol);
                        }
                    }
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(500));
        }
    }
}

void trigger_ghost_execution(uint64_t shares, double price, double vol) {
    if (!ghost_lob.reality.is_active.load()) {
        std::thread sim(&GhostExchange::simulate_execution, &ghost_lob, shares, price, vol);
        sim.detach();
    }
}


void init_hivemind_bridge() {
    int fd = open("data/hivemind.dat", O_RDWR | O_CREAT, 0644);
    if (fd == -1) { perror("open"); return; }
    (void)ftruncate(fd, sizeof(HiveMindState));
    hive_bridge = static_cast<HiveMindState*>(mmap(nullptr, sizeof(HiveMindState), PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0));
    close(fd);
    if (hive_bridge == MAP_FAILED) { perror("mmap"); hive_bridge = nullptr; }
    else { std::cout << "[NEXUS] Hive-Mind Bridge mapped to data/hivemind.dat\n"; }
}


// --- LEVEL 4 MICROSTRUCTURE GENERATOR ---
void microstructure_generator_loop() {
    double mid_price = last_price.load();
    if (mid_price == 0.0) mid_price = 40000.0; // Fallback BTC default

    while(running.load()) {
        double vol = 0.02 + (rand() % 100) / 5000.0; // Simulated regime vol
        micro_sim.generate_orders(vol, mid_price, event_queue);
        micro_sim.apply_jitter(event_queue);
        
        // AUDIT THE SYNTHETIC MARKET GENERATION (Continuous Ledger Chaining)
        audit_log.append_event(get_nanos(), "SYNTHETIC_TICK", mid_price, vol);
        // Simulate institutional SOR routing for Ops dashboard
        if (rand() % 5 == 0) ops.route_order(100 + (rand() % 900), mid_price);
        
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
}

int main() {
    std::cout << "=== NEXUS LIVE TRADING ENGINE ===\n";
    init_hivemind_bridge();

    std::thread consumer(engine_loop);
    std::thread producer(live_data_ingestor);
    std::thread telemetry(telemetry_loop);
    std::thread ghost_thread(ghost_stress_test_loop);
    std::thread micro_thread(microstructure_generator_loop);

    // Run until killed by the OS or FastAPI
    producer.join();
    consumer.join();
    telemetry.join();
    ghost_thread.join();
    micro_thread.join();

    return 0;
}
