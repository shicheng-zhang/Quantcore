#pragma once
#include "types.h"
#include <vector>
#include <string>

namespace quantcore {
    class FeatureEngine {
    public:
        FeatureEngine() = default;
        
        // NOTE: "_avx512" is a legacy name — implementation uses OMP SIMD, not AVX-512 intrinsics.
        // Kept for API backward compatibility. Returns NaN for insufficient history (window-1 prefix).
        static std::vector<double> rolling_mean_avx512(const std::vector<double>& data, int window);
        static std::vector<double> rolling_std_avx512(const std::vector<double>& data, int window);
        static std::vector<double> rolling_zscore_avx512(const std::vector<double>& data, int window);
        // Preferred aliases without misleading suffix
        static inline std::vector<double> rolling_mean(const std::vector<double>& d, int w) { return rolling_mean_avx512(d, w); }
        static inline std::vector<double> rolling_std(const std::vector<double>& d, int w) { return rolling_std_avx512(d, w); }
        static inline std::vector<double> rolling_zscore(const std::vector<double>& d, int w) { return rolling_zscore_avx512(d, w); }
        
        // Institutional Microstructure Features
        static std::vector<double> order_book_imbalance(const std::vector<double>& bid_vols, const std::vector<double>& ask_vols);
        static std::vector<double> queue_imbalance(const std::vector<double>& bid_sizes, const std::vector<double>& ask_sizes);
        static std::vector<double> cumulative_delta(const std::vector<double>& signed_volumes);
        static std::vector<double> delta_imbalance(const std::vector<double>& buy_vols, const std::vector<double>& sell_vols);
        static std::vector<double> kyle_lambda(const std::vector<double>& price_changes, const std::vector<double>& signed_volumes, int window = 20);
        static std::vector<double> effective_spread_bps(const std::vector<double>& prices, const std::vector<double>& mids);
        static double vpin(const std::vector<double>& buy_volumes, const std::vector<double>& sell_volumes, int buckets = 50);

        // Session-anchored Volume Profile (intraday)
        static VolumeProfile intraday_volume_profile(const std::vector<double>& prices, const std::vector<double>& volumes, int bins = 24);
        static std::vector<double> rvol(const std::vector<double>& today_volumes, const std::vector<double>& avg_volumes_at_time);
        static std::vector<Bar> aggregate_ticks_to_bars(const std::vector<Tick>& ticks, int64_t bar_interval_ns);
        static double parkinson_volatility(const std::vector<double>& highs, const std::vector<double>& lows, int window = 20);
        static double garman_klass_volatility(const std::vector<double>& opens, const std::vector<double>& highs, const std::vector<double>& lows, const std::vector<double>& closes, int window = 20);
    };
}
