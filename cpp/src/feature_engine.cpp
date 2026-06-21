#include "quantcore/feature_engine.h"
#include <cmath>
#include <omp.h>
#include <algorithm>

namespace quantcore {
    std::vector<double> FeatureEngine::rolling_mean_avx512(const std::vector<double>& data, int window) {
        size_t len = data.size();
        std::vector<double> result(len, 0.0);
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
        std::vector<double> result(len, 0.0);
        if (window <= 1 || len == 0) return result;
        auto means = rolling_mean_avx512(data, window);
        for (size_t i = window - 1; i < len; i++) {
            double sum_sq_diff = 0.0;
            double mean = means[i];
            #pragma omp simd reduction(+:sum_sq_diff)
            for (int j = i - window + 1; j <= i; j++) {
                double diff = data[j] - mean;
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
        std::vector<double> result(len, 0.0);
        for (size_t i = window - 1; i < len; i++) {
            if (stds[i] > 1e-10) result[i] = (data[i] - means[i]) / stds[i];
        }
        return result;
    }

    // Institutional Microstructure Feature
    std::vector<double> FeatureEngine::order_book_imbalance(const std::vector<double>& bid_vols, const std::vector<double>& ask_vols) {
        size_t len = std::min(bid_vols.size(), ask_vols.size());
        std::vector<double> result(len, 0.0);
        
        #pragma omp simd
        for (size_t i = 0; i < len; i++) {
            double bv = bid_vols[i];
            double av = ask_vols[i];
            double denom = bv + av;
            if (denom > 1e-10) {
                result[i] = (bv - av) / denom;
            }
        }
        return result;
    }
}
