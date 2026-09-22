#include <cctype>
#include <stdexcept>
#include "quantcore/data_engine.h"
#include <spdlog/spdlog.h>

// QuantCore Phase2 SQL safety helpers
namespace {
bool qc_is_safe_identifier(const std::string& s) {
    if (s.empty() || s.size() > 64) return false;
    unsigned char first = static_cast<unsigned char>(s[0]);
    if (!(std::isalpha(first) || s[0] == '_')) return false;
    for (char ch : s) {
        unsigned char c = static_cast<unsigned char>(ch);
        if (!(std::isalnum(c) || ch == '_')) return false;
    }
    return true;
}

bool qc_is_safe_path_fragment(const std::string& s) {
    if (s.empty() || s.size() > 4096) return false;
    if (s.find('\0') != std::string::npos) return false;
    if (s.find('\'') != std::string::npos) return false;
    if (s.find('"') != std::string::npos) return false;
    if (s.find("..") != std::string::npos) return false;
    return true;
}
} // namespace


namespace quantcore {
    DataEngine::DataEngine(const std::string& db_path) {
        duckdb::DBConfig config;
        config.options.maximum_threads = std::thread::hardware_concurrency();
        db_ = std::make_unique<duckdb::DuckDB>(db_path, &config);
        conn_ = std::make_unique<duckdb::Connection>(*db_);
    }

    void DataEngine::load_parquet_directory(const std::string& name, const std::string& dir) {
    if (!qc_is_safe_identifier(name)) {
        throw std::invalid_argument("Unsafe SQL view name rejected: " + name);
    }
    if (!qc_is_safe_path_fragment(dir)) {
        throw std::invalid_argument("Unsafe parquet directory rejected: " + dir);
    }

    // name is restricted to [A-Za-z_][A-Za-z0-9_]{0,63}.
    // dir rejects quotes, NUL bytes, and parent traversal.
    conn_->Query("CREATE OR REPLACE VIEW " + name +
                 " AS SELECT * FROM read_parquet('" + dir + "/*.parquet')");
}

    std::vector<FeatureRow> DataEngine::query_features(const std::string& sql) {
        auto result = conn_->Query(sql);
        std::vector<FeatureRow> rows;
        for (size_t i = 0; i < result->RowCount(); i++) {
            FeatureRow row;
            row.symbol = result->GetValue(0, i).ToString();
            row.timestamp_ns = result->GetValue(1, i).GetValue<int64_t>();
            for (idx_t col = 2; col < result->ColumnCount() - 1; col++) {
                row.features.push_back(static_cast<float>(result->GetValue(col, i).GetValue<double>()));
            }
            auto target_val = result->GetValue(result->ColumnCount() - 1, i);
            if (!target_val.IsNull()) row.target = target_val.GetValue<double>();
            rows.push_back(std::move(row));
        }
        return rows;
    }

    duckdb::Connection& DataEngine::connection() { return *conn_; }
}
