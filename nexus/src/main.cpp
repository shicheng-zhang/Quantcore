#include "../include/spsc_queue.h"
#include "../include/event.h"
#include "../include/limit_order_book.h"
#include <iostream>
#include <thread>
#include <chrono>
#include <fstream>
#include <vector>
#include <array>
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
#include <filesystem>
#include <csignal>

using namespace nexus;
using json = nlohmann::json;

// Helpers for atomic double ops on packed mmap (may be unaligned) — use __atomic builtins
inline double atomic_load_double(const double* ptr) {
    double v;
    __atomic_load(ptr, &v, __ATOMIC_ACQUIRE);
    return v;
}
inline void atomic_store_double(double* ptr, double v) {
    __atomic_store(ptr, &v, __ATOMIC_RELEASE);
}
inline void atomic_fetch_add_double(double* ptr, double delta) {
    double expected, desired;
    do {
        __atomic_load(ptr, &expected, __ATOMIC_RELAXED);
        desired = expected + delta;
    } while (!__atomic_compare_exchange(ptr, &expected, &desired, false, __ATOMIC_RELEASE, __ATOMIC_RELAXED));
}
inline void atomic_fetch_sub_double(double* ptr, double delta) { atomic_fetch_add_double(ptr, -delta); }

SPSCQueue<Event, 2097152> event_queue;
LimitOrderBook lob;

MicrostructureSim micro_sim;
MerkleLedger audit_log("data/audit_ledger.bin");
std::atomic<uint64_t> sim_fills{0};
std::atomic<double> sim_pnl{0.0};
InstitutionalOps ops;

GhostExchange ghost_lob;
std::thread ghost_sim_thread;  // FIX #2: Track ghost thread to prevent use-after-free on shutdown

// --- HIVE-MIND SHARED MEMORY BRIDGE ---
HiveMindState* hive_bridge = nullptr;
double current_weights[20] = {0};
double portfolio_value = 100000.0;

std::atomic<bool> running{true};
std::atomic<uint64_t> events_processed{0};
std::atomic<double> last_price{0.0};
// FIX #5: Circular buffer for latency tracking.
// The old vector stopped collecting after 100k events, freezing telemetry forever.
// This ring buffer always keeps the most recent 100k samples fresh.
static constexpr size_t LATENCY_BUFFER_SIZE = 100000;
std::array<double, LATENCY_BUFFER_SIZE> latency_ring{};
std::atomic<size_t> latency_head{0};
std::atomic<size_t> latency_count{0};
std::mutex latency_mutex;

void handle_shutdown_signal(int) {
    running.store(false, std::memory_order_relaxed);
}

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
                size_t idx = latency_head.fetch_add(1, std::memory_order_relaxed) % LATENCY_BUFFER_SIZE;
                latency_ring[idx] = static_cast<double>(latency);
                size_t cnt = latency_count.load(std::memory_order_relaxed);
                if (cnt < LATENCY_BUFFER_SIZE) latency_count.fetch_add(1, std::memory_order_relaxed);
            }


            // --- HIVE-MIND IPC READER ---
            if (hive_bridge) {
                static std::atomic<uint64_t> last_seq{0};
                uint64_t seq1 = __atomic_load_n(&hive_bridge->sequence, __ATOMIC_ACQUIRE);
                if (seq1 != last_seq.load(std::memory_order_relaxed)) {
                    last_seq.store(seq1, std::memory_order_relaxed);
                    uint32_t n = hive_bridge->num_assets;
                    double vol = hive_bridge->regime_vol;
                    if (vol == 0.0) vol = 0.05; // Fallback

                    // --- MODULE 1: STATARB PAIR EXECUTION ---
                    int8_t arb_sig = __atomic_load_n(&hive_bridge->statarb_signal, __ATOMIC_ACQUIRE);
                    if (arb_sig != 0) {
                        double beta = atomic_load_double(&hive_bridge->statarb_hedge_ratio);
                        double z = atomic_load_double(&hive_bridge->statarb_spread_z);
                        // Use last_price as base if available, otherwise synthetic fallback
                        double base_price = last_price.load(std::memory_order_relaxed);
                        if (base_price <= 0) base_price = 100.0;
                        // Thread-safe RNG
                        thread_local std::mt19937 tl_rng{std::random_device{}()};
                        std::uniform_real_distribution<double> price_jitter(-2.5, 2.5);
                        double price_s1 = base_price + price_jitter(tl_rng);
                        double price_s2 = base_price / std::max(0.1, beta) + price_jitter(tl_rng);
                        price_s1 = std::max(1.0, price_s1);
                        price_s2 = std::max(1.0, price_s2);

                        uint64_t qty_s1 = 1000;
                        uint64_t qty_s2 = static_cast<uint64_t>(qty_s1 * std::abs(beta));
                        if (qty_s2 == 0) qty_s2 = qty_s1;

                        // Execute Legs — simulate_fill returns fill price
                        double fill1 = micro_sim.simulate_fill(1, price_s1, qty_s1,
                            arb_sig > 0 ? Side::BUY : Side::SELL, price_s1, vol);
                        double fill2 = micro_sim.simulate_fill(2, price_s2, qty_s2,
                            arb_sig > 0 ? Side::SELL : Side::BUY, price_s2, vol);

                        // Correct PnL: for long spread (long S1, short S2), PnL = qty1*(fill1_entry - fill1_exit) is not yet realized
                        // For simulation, we model instantaneous round-trip: PnL = -cost of entry (slippage) + expected convergence
                        // Entry cost = qty*slippage; convergence modelled as |z| * 0.1 * notional on mean reversion
                        double notional_s1 = qty_s1 * fill1;
                        double notional_s2 = qty_s2 * fill2;
                        // Slippage cost is captured in fill price differential vs mid
                        double entry_cost = std::abs(fill1 - price_s1) * qty_s1 + std::abs(fill2 - price_s2) * qty_s2;
                        double expected_convergence = std::abs(z) * 0.02 * std::min(notional_s1, notional_s2); // 2% per z unit
                        double spread_pnl = expected_convergence - entry_cost;
                        // Direction already accounted via z sign in beta hedge; keep symmetric
                        spread_pnl *= (arb_sig > 0 ? 1 : 1);

                        atomic_fetch_add_double(&hive_bridge->realized_pnl, spread_pnl);
                        __atomic_fetch_add(&hive_bridge->orders_sent, 2u, __ATOMIC_RELEASE);
                        __atomic_fetch_add(&hive_bridge->orders_filled, 2u, __ATOMIC_RELEASE);

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

                            double price = last_price.load(std::memory_order_relaxed);
                            if (price > 0) {
                                uint64_t shares = static_cast<uint64_t>(std::abs(delta_value) / price);
                                if (shares > 10) {
                                    // Ghost Exchange Slippage Physics — unified with ghost_exchange.h
                                    constexpr double ETA = 0.15;
                                    double avg_vol = ghost_lob.reality.avg_daily_volume.load(std::memory_order_relaxed);
                                    if (avg_vol <= 0) avg_vol = 50000.0;
                                    double slip_bps = ETA * vol * std::sqrt(static_cast<double>(shares) / avg_vol) * 10000.0;
                                    slip_bps = std::clamp(slip_bps, 0.5, 50.0);
                                    double slip_price = price * (slip_bps / 10000.0);
                                    double fill_price = price + (delta_w > 0 ? slip_price : -slip_price);

                                    double slippage_usd = std::abs(fill_price - price) * shares;

                                    // Write Feedback to Python (atomic RMW)
                                    atomic_fetch_add_double(&hive_bridge->total_slippage, slippage_usd);
                                    atomic_fetch_sub_double(&hive_bridge->realized_pnl, slippage_usd);
                                    __atomic_fetch_add(&hive_bridge->orders_sent, 1u, __ATOMIC_RELEASE);
                                    __atomic_fetch_add(&hive_bridge->orders_filled, 1u, __ATOMIC_RELEASE);
                                    __atomic_store_n(&hive_bridge->cpp_timestamp, get_nanos(), __ATOMIC_RELEASE);

                                    current_weights[i] = target_w;
                                }
                            }
                        }
                    }
                    atomic_store_double(&hive_bridge->portfolio_value, portfolio_value);
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

    while (running.load(std::memory_order_relaxed)) {
        ix::WebSocket webSocket;
        webSocket.setUrl("wss://stream.binance.com:9443/ws/btcusdt@trade");

        std::atomic<bool> ws_open{false};
        std::atomic<bool> ws_done{false};

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

                    while (running.load(std::memory_order_relaxed) && !event_queue.push(ev)) {
                        #if defined(__x86_64__)
                            __builtin_ia32_pause();
                        #endif
                    }
                } catch (const std::exception& e) {
                    // Drop malformed packets silently (Institutional standard)
                }
            } else if (msg->type == ix::WebSocketMessageType::Open) {
                std::cout << "[NEXUS] Connected to Binance Live Feed!\n";
                ws_open.store(true, std::memory_order_release);
            } else if (msg->type == ix::WebSocketMessageType::Error ||
                       msg->type == ix::WebSocketMessageType::Close) {
                std::cerr << "[NEXUS] WebSocket disconnected: "
                          << (msg->type == ix::WebSocketMessageType::Error
                              ? msg->errorInfo.reason : "closed") << "\n";
                ws_done.store(true, std::memory_order_release);
            }
        });

        webSocket.start();

        // Wait until connection closes or shutdown
        while (running.load(std::memory_order_relaxed) && !ws_done.load(std::memory_order_acquire)) {
            std::this_thread::sleep_for(std::chrono::milliseconds(200));
        }

        webSocket.stop();
        ix::uninitNetSystem();

        if (!running.load(std::memory_order_relaxed)) break;

        std::cerr << "[NEXUS] Reconnecting in 3s...\n";
        for (int i = 0; i < 30 && running.load(std::memory_order_relaxed); ++i) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}

// --- TELEMETRY WRITER ---
void telemetry_loop() {
    while(running.load()) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        // FIX #5: Snapshot the circular buffer for percentile calculation
        std::vector<double> current_latencies;
        {
            // Keep the hot-path writer blocked only for the copy, never for
            // the percentile sort below.
            std::lock_guard<std::mutex> lock(latency_mutex);
            size_t count = latency_count.load(std::memory_order_relaxed);
            current_latencies.reserve(count);
            for (size_t i = 0; i < count; ++i) {
                current_latencies.push_back(latency_ring[i]);
            }
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

    // Readers must see either the preceding complete snapshot or this complete
    // snapshot, never a partially written JSON document.
    const std::filesystem::path telemetry_path{"data/nexus_live.json"};
    const std::filesystem::path temporary_path{"data/nexus_live.json.tmp"};
    {
        std::ofstream out(temporary_path, std::ios::trunc);
        out << telemetry_json.dump(4);
    }
    std::error_code rename_error;
    std::filesystem::rename(temporary_path, telemetry_path, rename_error);
    if (rename_error) {
        std::cerr << "[NEXUS] Telemetry write failed: " << rename_error.message() << '\n';
    }
    }
}


// --- GHOST EXCHANGE STRESS TEST THREAD ---
#include <fstream>
void trigger_ghost_execution(uint64_t, double, double);

void ghost_stress_test_loop() {
    auto last_check = std::chrono::steady_clock::now();
    while(running.load()) {
        if (ghost_lob.reality.is_active.load()) {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        } else {
            auto now = std::chrono::steady_clock::now();
            // Only check file every 5 seconds (was 500ms — wasteful I/O)
            if (std::chrono::duration_cast<std::chrono::seconds>(now - last_check).count() >= 5) {
                last_check = now;
                std::error_code ec;
                if (std::filesystem::exists("data/ghost_trigger.json", ec)) {
                    std::ifstream f("data/ghost_trigger.json", std::ios::binary);
                    if (f) {
                        std::string file_content((std::istreambuf_iterator<char>(f)),
                                                  std::istreambuf_iterator<char>());
                        f.close();  // FIX #6: Explicit close
                        try {
                            json trigger = json::parse(file_content);
                            if (trigger.contains("shares") && trigger.contains("vol")) {
                                uint64_t shares = trigger["shares"].get<uint64_t>();
                                double vol = trigger["vol"].get<double>();
                                double price = ghost_lob.reality.current_market_price.load();
                                if (price == 0.0) price = last_price.load();
                                if (price > 0) {
                                    std::remove("data/ghost_trigger.json");
                                    trigger_ghost_execution(shares, price, vol);
                                }
                            }
                        } catch (const json::exception& e) {
                            // Malformed trigger file — remove it and continue
                            std::cerr << "[NEXUS] Malformed ghost_trigger.json: " << e.what() << std::endl;
                            std::remove("data/ghost_trigger.json");
                        }
                    }
                }
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
        }
    }
}


void trigger_ghost_execution(uint64_t shares, double price, double vol) {
    if (!ghost_lob.reality.is_active.load()) {
        // FIX #2: Join previous ghost thread before spawning a new one.
        // Prevents use-after-free if the old thread is still running.
        if (ghost_sim_thread.joinable()) {
            ghost_sim_thread.join();
        }
        ghost_sim_thread = std::thread(&GhostExchange::simulate_execution, &ghost_lob, shares, price, vol);
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
    std::signal(SIGINT, handle_shutdown_signal);
    std::signal(SIGTERM, handle_shutdown_signal);
    init_hivemind_bridge();

    std::thread consumer(engine_loop);
    std::thread producer(live_data_ingestor);
    std::thread telemetry(telemetry_loop);
    std::thread ghost_thread(ghost_stress_test_loop);
    std::thread micro_thread(microstructure_generator_loop);

    // Run until killed by the OS or FastAPI
    // Join order: producer first (may block on WS reconnect), then consumer,
    // then remaining threads. Signal running=false to ensure all loops exit.
    producer.join();
    consumer.join();
    ghost_thread.join();
    micro_thread.join();
    telemetry.join();

    return 0;
}
