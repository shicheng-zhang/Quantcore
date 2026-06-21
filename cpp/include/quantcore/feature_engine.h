#pragma once
#include "types.h"
#include <vector>
#include <string>

namespace quantcore {
    class FeatureEngine {
    public:
        FeatureEngine() = default;
        
        static std::vector<double> rolling_mean_avx512(const std::vector<double>& data, int window);
        static std::vector<double> rolling_std_avx512(const std::vector<double>& data, int window);
        static std::vector<double> rolling_zscore_avx512(const std::vector<double>& data, int window);
        
        // Institutional Microstructure Feature
        static std::vector<double> order_book_imbalance(const std::vector<double>& bid_vols, const std::vector<double>& ask_vols);
    };
}
