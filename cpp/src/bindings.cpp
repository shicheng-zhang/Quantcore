#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/functional.h> // REQUIRED for std::function
#include "quantcore/event_bus.h"
#include "quantcore/data_engine.h"
#include "quantcore/feature_engine.h"
#include "quantcore/risk_engine.h"

namespace py = pybind11;
using namespace quantcore;

PYBIND11_MODULE(quantcore_cpp, m) {
    m.doc() = "QuantCore C++ Engine";
    m.def("version", []() { return "1.0.0"; });
    m.def("thread_count", []() { return std::thread::hardware_concurrency(); });

    py::enum_<Side>(m, "Side").value("BUY", Side::BUY).value("SELL", Side::SELL);
    py::enum_<OrderType>(m, "OrderType").value("MARKET", OrderType::MARKET).value("LIMIT", OrderType::LIMIT);
    py::enum_<RiskDecision>(m, "RiskDecision").value("APPROVE", RiskDecision::APPROVE).value("REJECT", RiskDecision::REJECT).value("HALT_TRADING", RiskDecision::HALT_TRADING);

    py::class_<Tick>(m, "Tick").def(py::init<>()).def_readwrite("symbol", &Tick::symbol).def_readwrite("price", &Tick::price);
    py::class_<Order>(m, "Order").def(py::init<>()).def_readwrite("id", &Order::id).def_readwrite("symbol", &Order::symbol).def_readwrite("side", &Order::side).def_readwrite("quantity", &Order::quantity).def_readwrite("limit_price", &Order::limit_price);
    py::class_<PortfolioSnapshot>(m, "PortfolioSnapshot").def(py::init<>()).def_readwrite("total_equity", &PortfolioSnapshot::total_equity).def_readwrite("daily_pnl", &PortfolioSnapshot::daily_pnl);

    py::class_<EventBus>(m, "EventBus").def(py::init<>()).def("publish_tick", &EventBus::publish<Tick>);

    py::class_<DataEngine>(m, "DataEngine")
        .def(py::init<const std::string&>(), py::arg("db_path") = ":memory:")
        .def("load_parquet_directory", &DataEngine::load_parquet_directory)
        .def("query_sql", [](DataEngine& self, const std::string& sql) {
            auto result = self.connection().Query(sql);
            py::list rows;
            for (size_t i = 0; i < result->RowCount(); i++) {
                py::dict row;
                for (idx_t col = 0; col < result->ColumnCount(); col++)
                    row[result->ColumnName(col).c_str()] = result->GetValue(col, i).ToString();
                rows.append(row);
            }
            return rows;
        });

    py::class_<FeatureEngine>(m, "FeatureEngine")
        .def(py::init<>())
        .def_static("rolling_mean", &FeatureEngine::rolling_mean_avx512)
        .def_static("rolling_std", &FeatureEngine::rolling_std_avx512)
        .def_static("rolling_zscore", &FeatureEngine::rolling_zscore_avx512)
        .def_static("order_book_imbalance", &FeatureEngine::order_book_imbalance);

    py::class_<RiskConfig>(m, "RiskConfig").def(py::init<>()).def_readwrite("max_position_pct", &RiskConfig::max_position_pct);
    py::class_<RiskResult>(m, "RiskResult").def_readonly("decision", &RiskResult::decision).def_readonly("reason", &RiskResult::reason);
    py::class_<RiskEngine>(m, "RiskEngine").def(py::init<const RiskConfig&, EventBus&>()).def("check_order", &RiskEngine::check_order).def("is_halted", &RiskEngine::is_halted);
}
