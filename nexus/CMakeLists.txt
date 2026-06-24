cmake_minimum_required(VERSION 3.24)
project(NexusEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Removed -fno-exceptions and -fno-rtti to support ixwebsocket internals
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -mtune=native -flto -DNDEBUG")

find_package(OpenSSL REQUIRED)
find_package(ZLIB REQUIRED)

include(FetchContent)

FetchContent_Declare(json GIT_REPOSITORY https://github.com/nlohmann/json.git GIT_TAG v3.11.3)
FetchContent_MakeAvailable(json)

FetchContent_Declare(ixwebsocket GIT_REPOSITORY https://github.com/machinezone/IXWebSocket.git GIT_TAG v11.4.4)
set(USE_TLS ON CACHE BOOL "" FORCE)
FetchContent_MakeAvailable(ixwebsocket)

add_executable(nexus_core src/main.cpp)
target_include_directories(nexus_core PRIVATE include)
target_link_libraries(nexus_core PRIVATE ixwebsocket nlohmann_json::nlohmann_json OpenSSL::SSL OpenSSL::Crypto ZLIB::ZLIB pthread)
