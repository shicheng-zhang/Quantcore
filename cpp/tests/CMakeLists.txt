cmake_minimum_required(VERSION 3.24)

# Standalone build target for the analytics-core unit tests.
#
# Deliberately independent of the root project: the full quantcore_cpp module
# pulls in DuckDB + pybind11 (a very long build), which is not needed to test
# the pure-logic engines. spdlog is header-only and cheap to fetch.
#
#   cmake -S cpp/tests -B <builddir>
#   cmake --build <builddir>
#   ctest --test-dir <builddir> --output-on-failure

project(QuantCoreCppTests LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

include(FetchContent)
FetchContent_Declare(spdlog GIT_REPOSITORY https://github.com/gabime/spdlog.git GIT_TAG v1.14.1)
FetchContent_MakeAvailable(spdlog)

enable_testing()

# Risk engine is pure logic (only spdlog + EventBus), so the sources under test
# compile directly — no DuckDB linkage required.
add_executable(test_risk_engine
    test_risk_engine.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../src/risk_engine.cpp
    ${CMAKE_CURRENT_LIST_DIR}/../src/event_bus.cpp
)
target_include_directories(test_risk_engine PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../include)
target_link_libraries(test_risk_engine PRIVATE spdlog::spdlog pthread)
target_compile_options(test_risk_engine PRIVATE -Wall -Wextra)

add_test(NAME risk_engine COMMAND test_risk_engine)

# Feature engine is also dependency-free (OpenMP only) and holds the
# microstructure math, so it gets its own target under the same runner.
find_package(OpenMP QUIET)
if(OpenMP_CXX_FOUND)
    add_executable(test_feature_engine
        test_feature_engine.cpp
        ${CMAKE_CURRENT_LIST_DIR}/../src/feature_engine.cpp
    )
    target_include_directories(test_feature_engine PRIVATE ${CMAKE_CURRENT_LIST_DIR}/../include)
    target_link_libraries(test_feature_engine PRIVATE OpenMP::OpenMP_CXX)
    target_compile_options(test_feature_engine PRIVATE -Wall -Wextra)
    add_test(NAME feature_engine COMMAND test_feature_engine)
endif()
