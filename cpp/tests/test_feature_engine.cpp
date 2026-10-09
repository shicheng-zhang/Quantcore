// Unit tests for the C++ FeatureEngine (microstructure + analytics math).
//
// These are pure functions over doubles, so they compile with nothing but the
// project headers + OpenMP — no DuckDB/pybind11 required.
//
//   cmake -S cpp/tests -B <builddir> && cmake --build <builddir>
//   ctest --test-dir <builddir> --output-on-failure
#include "quantcore/feature_engine.h"

#include <cassert>
#include <cmath>
#include <iostream>
#include <vector>

using namespace quantcore;

namespace {

int g_checks = 0;

#define CHECK(cond)                                                            \
    do {                                                                       \
        ++g_checks;                                                            \
        if (!(cond)) {                                                         \
            std::cerr << "FAILED: " << #cond << "\n  at " << __FILE__ << ":"   \
                      << __LINE__ << std::endl;                                \
            return 1;                                                          \
        }                                                                      \
    } while (0)

#define CHECK_NEAR(a, b, tol)                                                  \
    do {                                                                       \
        ++g_checks;                                                            \
        if (std::fabs((a) - (b)) > (tol)) {                                    \
            std::cerr << "FAILED: |" << (a) << " - " << (b) << "| > " << (tol) \
                      << "\n  at " << __FILE__ << ":" << __LINE__ << std::endl;\
            return 1;                                                          \
        }                                                                      \
    } while (0)

// ------------------------------------------------------------------ rolling

int test_rolling_mean() {
    const std::vector<double> d{1, 2, 3, 4, 5};
    auto r = FeatureEngine::rolling_mean(d, 3);

    CHECK(r.size() == d.size());
    CHECK(std::isnan(r[0]));  // window-1 NaN prefix
    CHECK(std::isnan(r[1]));
    CHECK_NEAR(r[2], 2.0, 1e-12);
    CHECK_NEAR(r[3], 3.0, 1e-12);
    CHECK_NEAR(r[4], 4.0, 1e-12);

    // Degenerate windows must not crash or divide by zero.
    auto bad = FeatureEngine::rolling_mean(d, 0);
    CHECK(bad.size() == d.size());
    for (double v : bad) CHECK(std::isnan(v));

    auto empty = FeatureEngine::rolling_mean({}, 3);
    CHECK(empty.empty());
    return 0;
}

int test_rolling_std_and_zscore() {
    // Non-monotonic series so the z-score changes sign across the window.
    const std::vector<double> d{1, 2, 3, 2, 1};
    auto s = FeatureEngine::rolling_std(d, 3);
    auto z = FeatureEngine::rolling_zscore(d, 3);

    CHECK(std::isnan(s[1]));
    CHECK_NEAR(s[2], 1.0, 1e-12);      // {1,2,3}
    CHECK_NEAR(s[3], 0.577350269, 1e-9);  // {2,3,2}
    CHECK_NEAR(s[4], 1.0, 1e-12);      // {3,2,1}

    CHECK(std::isnan(z[1]));
    CHECK_NEAR(z[2], 1.0, 1e-12);   // last point above the window mean
    CHECK_NEAR(z[3], -0.577350269, 1e-9);
    CHECK_NEAR(z[4], -1.0, 1e-12);  // last point below the window mean

    // A flat series has zero variance: z must be defined 0, never NaN/Inf.
    auto flat = FeatureEngine::rolling_zscore({7, 7, 7, 7}, 2);
    for (size_t i = 1; i < flat.size(); ++i) CHECK_NEAR(flat[i], 0.0, 1e-12);
    return 0;
}

// ------------------------------------------------------------ microstructure

int test_order_book_imbalance() {
    auto r = FeatureEngine::order_book_imbalance({3}, {1});
    CHECK(r.size() == 1);
    CHECK_NEAR(r[0], 0.5, 1e-12);  // (3-1)/(3+1)

    // Empty book on both sides must yield 0, not NaN.
    auto z = FeatureEngine::order_book_imbalance({0, 0}, {0, 0});
    CHECK(z.size() == 2);
    CHECK_NEAR(z[0], 0.0, 1e-12);
    CHECK_NEAR(z[1], 0.0, 1e-12);
    return 0;
}

int test_cumulative_delta() {
    auto r = FeatureEngine::cumulative_delta({1, -1, 1, -1});
    CHECK(r.size() == 4);
    CHECK_NEAR(r[0], 1.0, 1e-12);
    CHECK_NEAR(r[1], 0.0, 1e-12);
    CHECK_NEAR(r[2], 1.0, 1e-12);
    CHECK_NEAR(r[3], 0.0, 1e-12);
    return 0;
}

int test_delta_imbalance() {
    auto r = FeatureEngine::delta_imbalance({70, 30}, {30, 70});
    CHECK_NEAR(r[0], 0.4, 1e-12);
    CHECK_NEAR(r[1], -0.4, 1e-12);
    return 0;
}

int test_kyle_lambda() {
    // dP = 0.5 * dV exactly, so lambda must recover 0.5.
    const std::vector<double> dp{1, 1, 1, 1};
    const std::vector<double> dv{2, 2, 2, 2};
    auto r = FeatureEngine::kyle_lambda(dp, dv, 4);
    CHECK(r.size() == 4);
    CHECK(std::isnan(r[0]));
    CHECK_NEAR(r[3], 0.5, 1e-12);

    // No volume / no relationship must yield 0, never a division by zero.
    auto flat = FeatureEngine::kyle_lambda(dp, {0, 0, 0, 0}, 4);
    CHECK_NEAR(flat[3], 0.0, 1e-12);

    // Window longer than the series returns all NaN instead of partial work.
    auto short_series = FeatureEngine::kyle_lambda({1, 1}, {1, 1}, 5);
    CHECK(short_series.size() == 2);
    for (double v : short_series) CHECK(std::isnan(v));
    return 0;
}

int test_effective_spread_bps() {
    auto r = FeatureEngine::effective_spread_bps({101}, {100});
    CHECK(r.size() == 1);
    CHECK_NEAR(r[0], 200.0, 1e-9);  // 2 * 1 / 100 * 1e4

    auto zero_mid = FeatureEngine::effective_spread_bps({101}, {0});
    CHECK_NEAR(zero_mid[0], 0.0, 1e-12);
    return 0;
}

int test_vpin() {
    // Perfect imbalance in every bucket saturates to 1.
    CHECK_NEAR(FeatureEngine::vpin({10, 20}, {0, 0}, 2), 1.0, 1e-12);
    // Balanced flow is 0.
    CHECK_NEAR(FeatureEngine::vpin({10, 10}, {10, 10}, 2), 0.0, 1e-12);
    // Degenerate inputs must not divide by zero.
    CHECK_NEAR(FeatureEngine::vpin({}, {}, 5), 0.0, 1e-12);
    CHECK_NEAR(FeatureEngine::vpin({1, 2}, {3, 4}, 0), 0.0, 1e-12);
    return 0;
}

// ------------------------------------------------------------- volume profile

int test_intraday_volume_profile() {
    // Two price bins: heavy volume low, light volume high.
    const std::vector<double> prices{10, 10, 20};
    const std::vector<double> volumes{100, 100, 100};
    auto vp = FeatureEngine::intraday_volume_profile(prices, volumes, 2);

    CHECK(vp.levels.size() == 2);
    CHECK_NEAR(vp.poc, 12.5, 1e-12);
    CHECK(vp.levels[0].is_poc);
    CHECK_NEAR(vp.levels[0].volume, 200.0, 1e-12);
    CHECK_NEAR(vp.levels[1].volume, 100.0, 1e-12);
    // Value area expands until >= 70% of volume is enclosed (200/300 needed
    // exactly one extra bin here).
    CHECK_NEAR(vp.val, 12.5, 1e-12);
    CHECK_NEAR(vp.vah, 17.5, 1e-12);
    CHECK(vp.levels[0].in_value_area);
    CHECK(vp.levels[1].in_value_area);

    // Flat session: no range to bin, must collapse rather than emit NaN.
    auto flat = FeatureEngine::intraday_volume_profile({50, 50}, {10, 10}, 4);
    CHECK_NEAR(flat.poc, 50.0, 1e-12);
    CHECK_NEAR(flat.val, 50.0, 1e-12);
    CHECK_NEAR(flat.vah, 50.0, 1e-12);

    // Empty input must not crash.
    auto empty = FeatureEngine::intraday_volume_profile({}, {}, 4);
    CHECK(empty.levels.empty());
    return 0;
}

int test_rvol() {
    auto r = FeatureEngine::rvol({100}, {50});
    CHECK_NEAR(r[0], 2.0, 1e-12);
    // Missing historical volume defaults to 1.0 (no data, no opinion).
    auto d = FeatureEngine::rvol({100}, {0});
    CHECK_NEAR(d[0], 1.0, 1e-12);
    return 0;
}

// ---------------------------------------------------------- tick aggregation

int test_aggregate_ticks_to_bars() {
    const int64_t s = 1000000000LL;  // 1s bars
    std::vector<Tick> ticks(4);
    ticks[0] = {"AAPL", 0,        100.0, 1};
    ticks[1] = {"AAPL", s / 2,    101.0, 2};
    ticks[2] = {"AAPL", s,        102.0, 1};
    ticks[3] = {"AAPL", 5 * s / 2, 105.0, 3};

    auto bars = FeatureEngine::aggregate_ticks_to_bars(ticks, s);
    CHECK(bars.size() == 3);

    CHECK(bars[0].timestamp_ns == 0);
    CHECK_NEAR(bars[0].open, 100.0, 1e-12);
    CHECK_NEAR(bars[0].high, 101.0, 1e-12);
    CHECK_NEAR(bars[0].low, 100.0, 1e-12);
    CHECK_NEAR(bars[0].close, 101.0, 1e-12);
    CHECK_NEAR(bars[0].volume, 3.0, 1e-12);

    CHECK(bars[1].timestamp_ns == s);
    CHECK_NEAR(bars[1].high, 102.0, 1e-12);
    CHECK_NEAR(bars[1].volume, 1.0, 1e-12);

    CHECK(bars[2].timestamp_ns == 2 * s);
    CHECK_NEAR(bars[2].close, 105.0, 1e-12);
    CHECK_NEAR(bars[2].volume, 3.0, 1e-12);

    CHECK(FeatureEngine::aggregate_ticks_to_bars({}, s).empty());
    CHECK(FeatureEngine::aggregate_ticks_to_bars(ticks, 0).empty());
    return 0;
}

// -------------------------------------------------------------- volatility

int test_parkinson() {
    // Zero range is zero vol.
    CHECK_NEAR(FeatureEngine::parkinson_volatility({100}, {100}, 1), 0.0, 1e-12);

    // Single bar: hl / sqrt(4 ln2).
    const double hl = std::log(101.0 / 100.0);
    const double expected = hl / std::sqrt(4.0 * std::log(2.0));
    CHECK_NEAR(FeatureEngine::parkinson_volatility({101}, {100}, 1), expected, 1e-12);

    // Non-positive prices are skipped, not log() of a negative number.
    CHECK_NEAR(FeatureEngine::parkinson_volatility({-1, 0}, {-1, 0}, 2), 0.0, 1e-12);
    return 0;
}

int test_garman_klass() {
    const double o = 100.0, h = 101.0, l = 99.0, c = 100.5;
    const double hl = std::log(h / l);
    const double co = std::log(c / o);
    const double per_bar = 0.5 * hl * hl - (2.0 * std::log(2.0) - 1.0) * co * co;
    const double expected = std::sqrt(per_bar);

    auto v = FeatureEngine::garman_klass_volatility({o}, {h}, {l}, {c}, 1);
    CHECK_NEAR(v, expected, 1e-12);
    CHECK(v >= 0.0);

    // Degenerate windows and mismatched lengths must not crash.
    CHECK_NEAR(FeatureEngine::garman_klass_volatility({1}, {1}, {1}, {1}, 5), 0.0, 1e-12);
    CHECK_NEAR(FeatureEngine::garman_klass_volatility({}, {}, {}, {}, 1), 0.0, 1e-12);
    return 0;
}

}  // namespace

int main() {
    int failed = 0;
    failed += test_rolling_mean();
    failed += test_rolling_std_and_zscore();
    failed += test_order_book_imbalance();
    failed += test_cumulative_delta();
    failed += test_delta_imbalance();
    failed += test_kyle_lambda();
    failed += test_effective_spread_bps();
    failed += test_vpin();
    failed += test_intraday_volume_profile();
    failed += test_rvol();
    failed += test_aggregate_ticks_to_bars();
    failed += test_parkinson();
    failed += test_garman_klass();

    if (failed) {
        std::cerr << failed << " test(s) FAILED" << std::endl;
        return 1;
    }
    std::cout << "[OK] all feature engine tests passed (" << g_checks << " assertions)" << std::endl;
    return 0;
}
