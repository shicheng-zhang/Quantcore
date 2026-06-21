#pragma once
#include "types.h"
#include <duckdb.hpp>
#include <string>
#include <vector>
#include <memory>

namespace quantcore {
    class DataEngine {
    public:
        explicit DataEngine(const std::string& db_path = ":memory:");
        void load_parquet_directory(const std::string& name, const std::string& dir);
        std::vector<FeatureRow> query_features(const std::string& sql);
        duckdb::Connection& connection();
    private:
        std::unique_ptr<duckdb::DuckDB> db_;
        std::unique_ptr<duckdb::Connection> conn_;
    };
}
