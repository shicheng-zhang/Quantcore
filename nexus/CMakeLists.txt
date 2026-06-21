cmake_minimum_required(VERSION 3.24)
project(NexusEngine LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Bare-metal optimization flags for 9950X
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -march=native -mtune=native -flto -DNDEBUG -fno-exceptions -fno-rtti")

add_executable(nexus_core src/main.cpp)
target_include_directories(nexus_core PRIVATE include)
