#include "transpiler.h"

#include <charconv>
#include <stdexcept>
#include <string_view>
#include <vector>

namespace koine {
namespace {
const Json empty = Json::object();
const Json null;

bool truth(const Json &value) {
    if (value.is_null()) return false;
    if (value.is_boolean()) return value.get<bool>();
    if (value.is_number()) return value != 0;
    if (value.is_string()) return !value.get_ref<const std::string &>().empty();
    return !value.empty();
}

std::string quote(std::string_view text) {
    const char delimiter = text.find('\'') != text.npos && text.find('"') == text.npos ? '"' : '\'';
    std::string result(1, delimiter);
    const char *hex = "0123456789abcdef";
    for (unsigned char c : text) {
        if (c == '\\' || c == delimiter) { result += '\\'; result += c; }
        else if (c == '\n') result += "\\n";
        else if (c == '\r') result += "\\r";
        else if (c == '\t') result += "\\t";
        else if (c < 0x20 || c == 0x7f) { result += "\\x"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += c;
    }
    return result + delimiter;
}

// Python's scalar spelling is observable in use:value, fallbacks and cases.
std::string text(const Json &value, bool repr = false) {
    if (value.is_string()) return repr ? quote(value.get_ref<const std::string &>()) : value.get<std::string>();
    if (value.is_null()) return "None";
    if (value.is_boolean()) return value.get<bool>() ? "True" : "False";
    if (value.is_number_float()) {
        char buffer[64];
        auto converted = std::to_chars(buffer, buffer + sizeof(buffer), value.get<double>(), std::chars_format::scientific);
        if (converted.ec != std::errc()) throw std::runtime_error("Could not format number");
        std::string scientific(buffer, converted.ptr);
        auto e = scientific.find('e');
        int exponent = std::stoi(scientific.substr(e + 1));
        if (exponent < -4 || exponent >= 16) return scientific;
        bool negative = scientific.front() == '-';
        auto digits = scientific.substr(negative ? 1 : 0, e - (negative ? 1 : 0));
        if (auto dot = digits.find('.'); dot != digits.npos) digits.erase(dot, 1);
        auto point = exponent + 1;
        std::string fixed;
        if (point <= 0) fixed = "0." + std::string(-point, '0') + digits;
        else if (static_cast<size_t>(point) >= digits.size()) fixed = digits + std::string(point - digits.size(), '0') + ".0";
        else fixed = digits.substr(0, point) + "." + digits.substr(point);
        return (negative ? "-" : "") + fixed;
    }
    if (value.is_number()) return value.dump();
    std::string result = value.is_array() ? "[" : "{";
    bool first = true;
    for (const auto &entry : value.items()) {
        if (!first) result += ", ";
        first = false;
        if (value.is_object()) result += quote(entry.key()) + ": ";
        result += text(entry.value(), true);
    }
    return result + (value.is_array() ? "]" : "}");
}

std::string substitute(std::string_view pattern, const Json &values, const std::string &where) {
    std::string result;
    for (size_t i = 0; i < pattern.size();) {
        char c = pattern[i++];
        if (c != '{' && c != '}') { result += c; continue; }
        if (i < pattern.size() && pattern[i] == c) { result += c; ++i; continue; }
        if (c == '}') throw std::invalid_argument("Single '}' in format string");
        auto end = pattern.find('}', i);
        if (end == pattern.npos) throw std::invalid_argument("Unmatched '{' in format string");
        std::string field(pattern.substr(i, end - i));
        if (field.find_first_of("{}:!.[") != field.npos)
            throw std::invalid_argument("Unsupported format expression: {" + field + "}");
        if (!values.contains(field)) throw std::invalid_argument("Missing placeholder '" + field + "' in " + where);
        result += text(values.at(field));
        i = end + 1;
    }
    return result;
}

const Json &path(const Json &context, std::string_view name) {
    const Json *value = &context;
    for (;;) {
        auto dot = name.find('.');
        std::string key(name.substr(0, dot));
        if (!value->is_object() || !value->contains(key)) return null;
        value = &value->at(key);
        if (dot == name.npos) return *value;
        name.remove_prefix(dot + 1);
    }
}

void set_path(Json &state, std::string_view name, const Json &value) {
    Json *current = &state;
    for (;;) {
        if (!current->is_object()) throw std::invalid_argument("State path crosses a non-object value");
        auto dot = name.find('.');
        std::string key(name.substr(0, dot));
        if (dot == name.npos) { (*current)[key] = value; return; }
        if (!current->contains(key)) (*current)[key] = Json::object();
        current = &(*current)[key];
        name.remove_prefix(dot + 1);
    }
}

bool condition(const Json &config, const Json &context) {
    if (!config.contains("path")) throw std::invalid_argument("Condition must have a 'path' key: " + config.dump());
    auto name = substitute(config.at("path").get<std::string>(), context, "condition path");
    const auto &actual = path(context, name);
    bool result = config.contains("equals") ? text(actual) == text(config.at("equals")) : truth(actual);
    return truth(config.value("negate", Json(false))) ? !result : result;
}

std::string join(const std::vector<std::string> &parts, const std::string &separator) {
    std::string out;
    for (size_t i = 0; i < parts.size(); ++i) { if (i) out += separator; out += parts[i]; }
    return out;
}
} // namespace

Transpiler::Transpiler(const Json &grammar) {
    if (!grammar.is_object()) throw std::invalid_argument("Transpiler grammar must be an object");
    rules_ = grammar.value("rules", Json::object());
    if (!rules_.is_object()) throw std::invalid_argument("Transpiler rules must be an object");
    indent_ = grammar.value("transpiler", Json::object()).value("indent", std::string("    "));
}

std::string Transpiler::transpile(const Json &node) {
    if (!node.is_object() || !node.contains("tag")) throw std::invalid_argument("Transpilation must start from a valid AST node.");
    std::lock_guard<std::mutex> lock(mutex_);
    state_ = Json::object();
    return render(node, 0);
}

Json Transpiler::state() {
    std::lock_guard<std::mutex> lock(mutex_);
    return state_;
}

std::string Transpiler::render(const Json &node, size_t level) {
    if (node.is_array()) {
        std::vector<std::string> parts;
        for (const auto &child : node)
            if (!child.is_null() && !(child.is_array() && child.empty())) parts.push_back(render(child, level));
        return join(parts, " ");
    }
    if (!node.is_object()) return truth(node) ? text(node) : "";
    auto tag = node.contains("tag") ? text(node.at("tag")) : "None";
    const auto &config = rules_.contains(tag) ? rules_.at(tag) : empty;
    const bool indented = truth(config.value("indent", Json(false)));
    if (indented) ++level;
    std::string indentation;
    for (size_t i = 0; i < level; ++i) indentation += indent_;
    Json subs = Json::object();
    const auto children = node.value("children", Json::array());
    if (children.is_object()) {
        for (const auto &child : children.items()) subs[child.key()] = render(child.value(), level);
    } else if (children.is_array()) {
        auto separator = config.value("join_children_with", std::string(" "));
        for (size_t i = 0; (i = separator.find('\n', i)) != separator.npos; i += 1 + indentation.size())
            separator.insert(i + 1, indentation);
        std::vector<std::string> parts;
        for (const auto &child : children) {
            auto part = render(child, level);
            if (!part.empty()) parts.push_back(std::move(part));
        }
        auto joined = join(parts, separator);
        subs["children"] = indented && !joined.empty() ? indentation + joined : joined;
    }
    for (auto field : {"op", "left", "right"}) if (node.contains(field)) subs[field] = render(node.at(field), level);
    Json selected;
    if (config.contains("cases")) {
        Json context = {{"node", node}, {"state", state_}};
        context.update(subs);
        for (const auto &item : config.at("cases")) {
            if (item.contains("if")) {
                if (condition(item.at("if"), context)) { selected = item.at("then"); break; }
            } else if (item.contains("default")) { selected = item.at("default"); break; }
        }
    } else if (config.contains("template")) selected = config.at("template");
    std::string output;
    if (!selected.is_null()) output = substitute(selected.get<std::string>(), subs, "template for tag '" + tag + "'");
    else if (config.value("use", Json()) == "value") output = text(node.value("value", Json("")));
    else if (config.value("use", Json()) == "text") output = node.at("text").get<std::string>();
    else if (config.contains("value")) output = config.at("value").get<std::string>();
    else if (node.contains("value")) output = text(node.at("value"));
    else if (node.contains("text")) output = node.at("text").get<std::string>();
    else throw std::invalid_argument("Don't know how to transpile node: " + node.dump());
    if (config.contains("state_set")) for (const auto &entry : config.at("state_set").items()) {
        auto key = substitute(entry.key(), subs, "state_set key for tag '" + tag + "'");
        auto value = entry.value();
        if (value.is_string()) value = substitute(value.get<std::string>(), subs, "state_set value for tag '" + tag + "'");
        set_path(state_, key, value);
    }
    return output;
}
} // namespace koine
