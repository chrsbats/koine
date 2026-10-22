#pragma once

#include <nlohmann/json.hpp>
#include <filesystem>
#include <string_view>

namespace koine {
using Json = nlohmann::ordered_json;
Json document(std::string_view source);
Json load_document(const std::filesystem::path &path);
Json prepare_grammar(Json grammar, const std::filesystem::path &base, bool placeholders);
}
