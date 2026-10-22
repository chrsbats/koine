#pragma once

#include "grammar.h"

#include <mutex>
#include <string>

namespace koine {
class Transpiler {
public:
    explicit Transpiler(const Json &grammar);
    std::string transpile(const Json &node);
    Json state();

private:
    Json rules_;
    std::string indent_;
    Json state_ = Json::object();
    std::mutex mutex_;

    std::string render(const Json &node, size_t level);
};
}
