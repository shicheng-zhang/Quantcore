#include "quantcore/feature_engine.h"
#include <cmath>
#include <limits>
#include <omp.h>
#include <algorithm>

namespace quantcore {
    std::vector<double> FeatureEngine::rolling_mean_avx512(const std::vector<double>& data, int window) {
        size_t len = data.size();
        std::vector<double> result(len, std::numeric_limits<double>::quiet_NaN());
        if (window <= 0 || len == 0) return result;
        double sum = 0.0;
        for (size_t i = 0; i < std::min(static_cast<size_t>(window), len); i++) sum += data[i];
        for (size_t i = window - 1; i < len; i++) {
            if (i >= static_cast<size_t>(window)) sum += data[i] - data[i - window];
            result[i] = sum / window;
        }
        return result;
    }
    
    std::vector<double> FeatureEngine::rolling_std_avx512(const std::vector<double>& data, int window) {
        size_t len = data.size();
        std::vector<double> result(len, std::numeric_limits<double>::quiet_NaN());
        if (window <= 1 || len == 0) return result;
        auto means = rolling_mean_avx512(data, window);
        for (size_t i = window - 1; i < len; i++) {
            double sum_sq_diff = 0.0;
            double mean = means[i];
            #pragma omp simd reduction(+:sum_sq_diff)
            for (int j = static_cast<int>(i) - window + 1; j <= static_cast<int>(i); j++) {
                double diff = data[static_cast<size_t>(j)] - mean;
                sum_sq_diff += diff * diff;
            }
            result[i] = std::sqrt(sum_sq_diff / (window - 1));
        }
        return result;
    }
    
    std::vector<double> FeatureEngine::rolling_zscore_avx512(const std::vector<double>& data, int window) {
        auto means = rolling_mean_avx512(data, window);
        auto stds = rolling_std_avx512(data, window);
        size_t len = data.size();
        std::vector<double> result(len, std::numeric_limits<double>::quiet_NaN());
        for (size_t i = window - 1; i < len; i++) {
            if (std::isfinite(stds[i]) && stds[i] > 1e-10) result[i] = (data[i] - means[i]) / stds[i];
            else result[i] = 0.0;
        }
        return result;
    }

    // Institutional Microstructure Features
    std::vector<double> FeatureEngine::order_book_imbalance(const std::vector<double>& bid_vols, const std::vector<double>& ask_vols) {
        size_t len = std::min(bid_vols.size(), ask_vols.size());
        std::vector<double> result(len, 0.0);
        #pragma omp simd
        for (size_t i = 0; i < len; i++) {
            double bv = bid_vols[i];
            double av = ask_vols[i];
            double denom = bv + av;
            if (denom > 1e-10) result[i] = (bv - av) / denom;
        }
        return result;
    }

    std::vector<double> FeatureEngine::queue_imbalance(const std::vector<double>& bid_sizes, const std::vector<double>& ask_sizes) {
        size_t len = std::min(bid_sizes.size(), ask_sizes.size());
        std::vector<double> result(len, 0.0);
        #pragma omp simd
        for (size_t i = 0; i < len; i++) {
            double denom = bid_sizes[i] + ask_sizes[i];
            if (denom > 1e-10) result[i] = (bid_sizes[i] - ask_sizes[i]) / denom;
        }
        return result;
    }

    std::vector<double> FeatureEngine::cumulative_delta(const std::vector<double>& signed_volumes) {
        std::vector<double> result(signed_volumes.size(), 0.0);
        double cum = 0.0;
        for (size_t i = 0; i < signed_volumes.size(); i++) {
            cum += signed_volumes[i];
            result[i] = cum;
        }
        return result;
    }

    std::vector<double> FeatureEngine::delta_imbalance(const std::vector<double>& buy_vols, const std::vector<double>& sell_vols) {
        size_t len = std::min(buy_vols.size(), sell_vols.size());
        std::vector<double> result(len, 0.0);
        for (size_t i = 0; i < len; i++) {
            double denom = buy_vols[i] + sell_vols[i];
            if (denom > 1e-10) result[i] = (buy_vols[i] - sell_vols[i]) / denom;
        }
        return result;
    }

    std::vector<double> FeatureEngine::kyle_lambda(const std::vector<double>& price_changes, const std::vector<double>& signed_volumes, int window) {
        size_t len = std::min(price_changes.size(), signed_volumes.size());
        std::vector<double> result(len, std::numeric_limits<double>::quiet_NaN());
        if (window <= 1 || len < static_cast<size_t>(window)) return result;
        for (size_t i = window - 1; i < len; i++) {
            double sum_dp_dv = 0.0, sum_dv2 = 0.0;
            for (int j = static_cast<int>(i) - window + 1; j <= static_cast<int>(i); j++) {
                sum_dp_dv += price_changes[j] * signed_volumes[j];
                sum_dv2 += signed_volumes[j] * signed_volumes[j];
            }
            if (sum_dv2 > 1e-12) result[i] = sum_dp_dv / sum_dv2;
            else result[i] = 0.0;
        }
        return result;
    }

    std::vector<double> FeatureEngine::effective_spread_bps(const std::vector<double>& prices, const std::vector<double>& mids) {
        size_t len = std::min(prices.size(), mids.size());
        std::vector<double> result(len, 0.0);
        for (size_t i = 0; i < len; i++) {
            if (mids[i] > 1e-10) result[i] = 2.0 * std::abs(prices[i] - mids[i]) / mids[i] * 10000.0;
        }
        return result;
    }

    double FeatureEngine::vpin(const std::vector<double>& buy_volumes, const std::vector<double>& sell_volumes, int buckets) {
        size_t len = std::min(buy_volumes.size(), sell_volumes.size());
        if (len < static_cast<size_t>(buckets) || buckets <= 0) return 0.0;
        // Bucketize volumes
        double bucket_size = static_cast<double>(len) / buckets;
        double total_imbalance = 0.0, total_vol = 0.0;
        for (int b = 0; b < buckets; b++) {
            size_t start = static_cast<size_t>(b * bucket_size);
            size_t end = static_cast<size_t>((b + 1) * bucket_size);
            end = std::min(end, len);
            double bvol = 0, svol = 0;
            for (size_t i = start; i < end; i++) { bvol += buy_volumes[i]; svol += sell_volumes[i]; }
            total_imbalance += std::abs(bvol - svol);
            total_vol += bvol + svol;
        }
        if (total_vol < 1e-10) return 0.0;
        return total_imbalance / total_vol;
    }

    VolumeProfile FeatureEngine::intraday_volume_profile(const std::vector<double>& prices, const std::vector<double>& volumes, int bins) {
        VolumeProfile vp;
        if (prices.empty() || volumes.empty() || bins <= 0) return vp;
        size_t len = std::min(prices.size(), volumes.size());
        double min_p = *std::min_element(prices.begin(), prices.begin() + len);
        double max_p = *std::max_element(prices.begin(), prices.begin() + len);
        if (min_p == max_p) { vp.poc = min_p; vp.vah = min_p; vp.val = min_p; return vp; }
        double bin_width = (max_p - min_p) / bins;
        std::vector<double> bin_vol(bins, 0.0);
        std::vector<double> bin_price(bins, 0.0);
        for (int i = 0; i < bins; i++) bin_price[i] = min_p + (i + 0.5) * bin_width;
        for (size_t i = 0; i < len; i++) {
            int idx = static_cast<int>((prices[i] - min_p) / bin_width);
            idx = std::clamp(idx, 0, bins - 1);
            bin_vol[idx] += volumes[i];
        }
        int poc_idx = static_cast<int>(std::max_element(bin_vol.begin(), bin_vol.end()) - bin_vol.begin());
        vp.poc = bin_price[poc_idx];
        double total_vol = 0; for (double v : bin_vol) total_vol += v;
        double target = total_vol * 0.70;
        double accum = bin_vol[poc_idx];
        int left = poc_idx, right = poc_idx;
        while (accum < target && (left > 0 || right < bins - 1)) {
            double lv = left > 0 ? bin_vol[left - 1] : -1;
            double rv = right < bins - 1 ? bin_vol[right + 1] : -1;
            if (lv >= rv && left > 0) { left--; accum += lv; }
            else if (right < bins - 1) { right++; accum += rv; }
            else if (left > 0) { left--; accum += lv; }
            else break;
        }
        vp.val = bin_price[left];
        vp.vah = bin_price[right];
        vp.levels.reserve(bins);
        for (int i = 0; i < bins; i++) {
            vp.levels.push_back({bin_price[i], bin_vol[i], i == poc_idx, i >= left && i <= right});
        }
        return vp;
    }

    std::vector<double> FeatureEngine::rvol(const std::vector<double>& today_volumes, const std::vector<double>& avg_volumes_at_time) {
        size_t len = std::min(today_volumes.size(), avg_volumes_at_time.size());
        std::vector<double> result(len, 0.0);
        for (size_t i = 0; i < len; i++) {
            if (avg_volumes_at_time[i] > 1e-10) result[i] = today_volumes[i] / avg_volumes_at_time[i];
            else result[i] = 1.0;
        }
        return result;
    }

    std::vector<Bar> FeatureEngine::aggregate_ticks_to_bars(const std::vector<Tick>& ticks, int64_t bar_interval_ns) {
        std::vector<Bar> bars;
        if (ticks.empty() || bar_interval_ns <= 0) return bars;
        // Assumes ticks sorted by timestamp_ns
        int64_t cur_start = (ticks[0].timestamp_ns / bar_interval_ns) * bar_interval_ns;
        double o = ticks[0].price, h = ticks[0].price, l = ticks[0].price, c = ticks[0].price, v = ticks[0].volume;
        for (size_t i = 1; i < ticks.size(); i++) {
            int64_t bar_start = (ticks[i].timestamp_ns / bar_interval_ns) * bar_interval_ns;
            if (bar_start != cur_start) {
                bars.push_back({cur_start, o, h, l, c, v});
                cur_start = bar_start;
                o = h = l = c = ticks[i].price;
                v = ticks[i].volume;
            } else {
                h = std::max(h, ticks[i].price);
                l = std::min(l, ticks[i].price);
                c = ticks[i].price;
                v += ticks[i].volume;
            }
        }
        bars.push_back({cur_start, o, h, l, c, v});
        return bars;
    }

    double FeatureEngine::parkinson_volatility(const std::vector<double>& highs, const std::vector<double>& lows, int window) {
        size_t len = std::min(highs.size(), lows.size());
        if (len < static_cast<size_t>(window) || window <= 0) return 0.0;
        double sum = 0.0;
        for (size_t i = len - window; i < len; i++) {
            if (highs[i] > 0 && lows[i] > 0) {
                double hl = std::log(highs[i] / lows[i]);
                sum += hl * hl;
            }
        }
        return std::sqrt(sum / (4.0 * std::log(2.0) * window));
    }

    double FeatureEngine::garman_klass_volatility(const std::vector<double>& opens, const std::vector<double>& highs, const std::vector<double>& lows, const std::vector<double>& closes, int window) {
        size_t len = std::min({opens.size(), highs.size(), lows.size(), closes.size()});
        if (len < static_cast<size_t>(window) || window <= 0) return 0.0;
        double sum = 0.0;
        for (size_t i = len - window; i < len; i++) {
            if (opens[i] > 0 && highs[i] > 0 && lows[i] > 0 && closes[i] > 0) {
                double hl = std::log(highs[i] / lows[i]);
                double co = std::log(closes[i] / opens[i]);
                sum += 0.5 * hl * hl - (2 * std::log(2.0) - 1) * co * co;
            }
        }
        return std::sqrt(std::max(0.0, sum / window));
    }
}
