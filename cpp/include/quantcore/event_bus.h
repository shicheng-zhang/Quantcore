#pragma once
#include <functional>
#include <unordered_map>
#include <vector>
#include <mutex>
#include <any>
#include <typeindex>
#include <algorithm> // REQUIRED for std::remove_if

namespace quantcore {
    class EventBus {
    public:
        using CallbackId = uint64_t;
        template<typename T>
        CallbackId subscribe(std::function<void(const T&)> callback) {
            std::lock_guard<std::mutex> lock(mutex_);
            auto id = next_id_++;
            subscribers_[std::type_index(typeid(T))].push_back({id, [callback](const std::any& e){ callback(std::any_cast<const T&>(e)); }});
            return id;
        }
        template<typename T>
        void publish(const T& event) {
            std::lock_guard<std::mutex> lock(mutex_);
            auto key = std::type_index(typeid(T));
            if (auto it = subscribers_.find(key); it != subscribers_.end()) {
                for (auto& [id, cb] : it->second) { try { cb(event); } catch (...) {} }
            }
        }
        void unsubscribe(CallbackId id) {
            std::lock_guard<std::mutex> lock(mutex_);
            for (auto& [k, subs] : subscribers_) {
                subs.erase(std::remove_if(subs.begin(), subs.end(), [id](auto& s){ return s.id == id; }), subs.end());
            }
        }
    private:
        struct Subscriber { CallbackId id; std::function<void(const std::any&)> callback; };
        std::mutex mutex_;
        std::unordered_map<std::type_index, std::vector<Subscriber>> subscribers_;
        CallbackId next_id_ = 1;
    };
}
