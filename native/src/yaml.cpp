#include "grammar.h"

#include <ryml.hpp>

#include <charconv>
#include <cmath>
#include <regex>
#include <set>
#include <stdexcept>
#include <vector>

namespace koine {
namespace {
std::string string(ryml::csubstr value) {
    return std::string(value.str ? value.str : "", value.len);
}

Json scalar(ryml::csubstr value, bool plain, ryml::csubstr tag) {
    std::string text = string(value);
    const auto type = ryml::to_tag(tag);
    if (tag == "!" || type == ryml::TAG_STR) return text;
    if (!tag.empty() && type != ryml::TAG_BOOL && type != ryml::TAG_NULL &&
        type != ryml::TAG_INT && type != ryml::TAG_FLOAT)
        throw std::invalid_argument("Unsupported YAML scalar tag: " + string(tag));
    if (!plain && tag.empty()) return text;

    // YAML 1.2 core schema, also used by safer-yaml's yamlcore loader.
    if (type == ryml::TAG_NONE || type == ryml::TAG_BOOL) {
        if (text == "true" || text == "True" || text == "TRUE") return true;
        if (text == "false" || text == "False" || text == "FALSE") return false;
    }
    if ((type == ryml::TAG_NONE || type == ryml::TAG_NULL) &&
        (text.empty() || text == "~" || text == "null" || text == "Null" || text == "NULL")) return nullptr;
    static const std::regex integer(R"(([-+]?[0-9]+|0o[0-7]+|0x[0-9a-fA-F]+))");
    static const std::regex real(R"(([-+]?(\.[0-9]+|[0-9]+(\.[0-9]*)?)([eE][-+]?[0-9]+)?))");
    if (std::regex_match(text, integer) && (type == ryml::TAG_NONE || type == ryml::TAG_INT)) {
        std::string_view digits(text);
        bool negative = digits.front() == '-';
        if (digits.front() == '+' || negative) digits.remove_prefix(1);
        int base = 10;
        if (digits.substr(0, 2) == "0o") { base = 8; digits.remove_prefix(2); }
        else if (digits.substr(0, 2) == "0x") { base = 16; digits.remove_prefix(2); }
        uint64_t magnitude = 0;
        auto converted = std::from_chars(digits.data(), digits.data() + digits.size(), magnitude, base);
        if (converted.ec != std::errc() || (negative && magnitude > (uint64_t(1) << 63)))
            throw std::out_of_range("YAML integer exceeds int64/uint64 range");
        if (!negative) return magnitude;
        if (!magnitude) return int64_t(0);
        return -static_cast<int64_t>(magnitude - 1) - 1;
    }
    if (std::regex_match(text, real) && (type == ryml::TAG_NONE || type == ryml::TAG_FLOAT)) {
        std::string_view digits(text);
        if (digits.front() == '+') digits.remove_prefix(1);
        double number = 0;
        auto converted = std::from_chars(digits.data(), digits.data() + digits.size(), number);
        if (converted.ec != std::errc() || !std::isfinite(number))
            throw std::out_of_range("YAML number exceeds float64 range");
        return number;
    }
    if (!tag.empty()) throw std::invalid_argument("Invalid value for YAML tag: " + string(tag));
    if (text == ".inf" || text == ".Inf" || text == ".INF" || text == "-.inf" || text == "-.Inf" || text == "-.INF" ||
        text == "+.inf" || text == "+.Inf" || text == "+.INF" || text == ".nan" || text == ".NaN" || text == ".NAN")
        throw std::invalid_argument("Non-finite YAML numbers are not JSON-compatible");
    return text;
}

Json convert(ryml::ConstNodeRef node) {
    if (node.is_stream()) {
        if (node.num_children() != 1) throw std::invalid_argument("Expected one YAML document");
        return convert(node.first_child());
    }
    if (node.is_map()) {
        Json result = Json::object();
        for (auto child : node.children()) {
            auto key = scalar(child.key(), child.is_key_plain(), child.has_key_tag() ? child.key_tag() : ryml::csubstr{});
            if (!key.is_string()) throw std::invalid_argument("Grammar mapping keys must be strings");
            const auto &name = key.get_ref<const std::string &>();
            if (result.contains(name)) throw std::invalid_argument("Duplicate YAML mapping key: " + name);
            result[name] = convert(child);
        }
        return result;
    }
    if (node.is_seq()) {
        Json result = Json::array();
        for (auto child : node.children()) result.push_back(convert(child));
        return result;
    }
    if (!node.has_val()) return nullptr;
    return scalar(node.val(), node.is_val_plain(), node.has_val_tag() ? node.val_tag() : ryml::csubstr{});
}
} // namespace

// Strict JSON with duplicate-key rejection. ryml's lenient flow parser accepts
// most compact JSON but recovers silently on constructs such as `{"a":{}}`,
// producing a partial grammar. Grammar files documented as JSON take this path.
Json parse_json(std::string_view source) {
    std::vector<std::set<std::string>> open;
    auto callback = [&open](int, Json::parse_event_t event, Json &parsed) -> bool {
        if (event == Json::parse_event_t::object_start) {
            open.emplace_back();
        } else if (event == Json::parse_event_t::object_end) {
            if (!open.empty()) open.pop_back();
        } else if (event == Json::parse_event_t::key && !open.empty()) {
            const auto &key = parsed.get_ref<const std::string &>();
            if (!open.back().insert(key).second)
                throw std::invalid_argument("Duplicate JSON object key: " + key);
        }
        return true;
    };
    return Json::parse(source.begin(), source.end(), callback);
}

Json document(std::string_view source) {
    const auto first = source.find_first_not_of(" \t\r\n");
    if (first != std::string_view::npos && (source[first] == '{' || source[first] == '[')) {
        try {
            return parse_json(source);
        } catch (const Json::parse_error &) {
            // Not strict JSON (for example a YAML flow mapping); try YAML below.
        }
    }
    auto tree = ryml::parse_in_arena(ryml::csubstr(source.data(), source.size()));
    tree.resolve();
    return convert(tree.crootref());
}
} // namespace koine
