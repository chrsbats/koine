#include "koine.h"
#include "grammar.h"
#include "transpiler.h"

#include <nlohmann/json.hpp>
#include <pcre2.h>
#include <peglib.h>

#include <algorithm>
#include <cctype>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <charconv>
#include <cmath>
#include <functional>
#include <iterator>
#include <map>
#include <memory>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <tuple>
#include <vector>

namespace {
using koine::Json;
using Ope = std::shared_ptr<peg::Ope>;

struct Token {
    std::string type, value;
    size_t line, col;
    size_t stream_start = 0;
};

struct ParseContext {
    std::string_view source;
    std::optional<size_t> failure_offset;
    std::string expected_terminal;
    // PCRE2 validates the whole subject on a call unless told otherwise. The first
    // match covers the entire subject, so later attempts can safely skip the scan.
    bool check_utf = true;
};

std::string_view input(const char *data, size_t size) {
    if (!data && size) throw std::invalid_argument("NULL input with nonzero size");
    return {data ? data : "", size};
}

std::pair<size_t, size_t> location(std::string_view source, size_t end) {
    size_t line = 1, col = 1;
    for (size_t i = 0; i < end; ++i) {
        const auto c = static_cast<unsigned char>(source[i]);
        if (c == '\n') { ++line; col = 1; }
        else if ((c & 0xc0) != 0x80) { ++col; }
    }
    return {line, col};
}

// Line starts plus one-based code-point columns for every byte, built once per
// parse. Shaping systems look up many positions; rescanning from byte zero per
// node made large inputs quadratic.
struct SourceIndex {
    std::vector<size_t> lines{0};
    std::vector<uint32_t> columns;

    explicit SourceIndex(std::string_view source) : columns(source.size() + 1) {
        uint32_t col = 1;
        for (size_t i = 0; i < source.size(); ++i) {
            columns[i] = col;
            const auto c = static_cast<unsigned char>(source[i]);
            if (c == '\n') { lines.push_back(i + 1); col = 1; }
            else if ((c & 0xc0) != 0x80) ++col;
        }
        columns[source.size()] = col;
    }

    std::pair<size_t, size_t> location(size_t end) const {
        end = std::min(end, columns.size() - 1);
        auto line = std::upper_bound(lines.begin(), lines.end(), end) - lines.begin();
        return {static_cast<size_t>(line), static_cast<size_t>(columns[end])};
    }
};

size_t codepoints(std::string_view text) {
    return std::count_if(text.begin(), text.end(), [](unsigned char c) { return (c & 0xc0) != 0x80; });
}

// The complete UTF-8 sequence containing byte `position`. cpp-peglib scans error
// tokens with locale-dependent ctype, which can stop mid-sequence on Windows.
std::string codepoint_at(std::string_view text, size_t position) {
    if (position >= text.size()) return "";
    while (position && (static_cast<unsigned char>(text[position]) & 0xc0) == 0x80) --position;
    const auto lead = static_cast<unsigned char>(text[position]);
    const size_t length = lead < 0x80 ? 1 : (lead & 0xe0) == 0xc0 ? 2 : (lead & 0xf0) == 0xe0 ? 3 :
        (lead & 0xf8) == 0xf0 ? 4 : 0;
    if (!length || position + length > text.size()) return "\xEF\xBF\xBD";
    return std::string(text.substr(position, length));
}

// JSON strings must be UTF-8. Replace any malformed sequence (for example a
// snippet cut inside a character) instead of failing the whole result.
std::string valid_utf8(std::string_view text) {
    std::string out;
    out.reserve(text.size());
    for (size_t i = 0; i < text.size();) {
        const auto lead = static_cast<unsigned char>(text[i]);
        const size_t length = lead < 0x80 ? 1 : (lead & 0xe0) == 0xc0 ? 2 : (lead & 0xf0) == 0xe0 ? 3 :
            (lead & 0xf8) == 0xf0 ? 4 : 0;
        bool complete = length && i + length <= text.size() && lead != 0xc0 && lead != 0xc1 && lead <= 0xf4;
        for (size_t j = 1; complete && j < length; ++j)
            complete = (static_cast<unsigned char>(text[i + j]) & 0xc0) == 0x80;
        if (complete && length == 3) {
            const auto second = static_cast<unsigned char>(text[i + 1]);
            complete = !(lead == 0xe0 && second < 0xa0) && !(lead == 0xed && second > 0x9f);
        }
        if (complete && length == 4) {
            const auto second = static_cast<unsigned char>(text[i + 1]);
            complete = !(lead == 0xf0 && second < 0x90) && !(lead == 0xf4 && second > 0x8f);
        }
        if (complete) {
            out.append(text.substr(i, length));
            i += length;
        } else {
            out += "\xEF\xBF\xBD";
            ++i;
        }
    }
    return out;
}

// Python's end assertion is absolute; PCRE2 spells that assertion \z.
std::string regex_pattern(std::string_view pattern) {
    std::string out;
    bool in_class = false;
    for (size_t i = 0; i < pattern.size(); ++i) {
        char c = pattern[i];
        out += c;
        if (c == '\\' && i + 1 < pattern.size()) {
            c = pattern[++i];
            out += c == 'Z' && !in_class ? 'z' : c;
        } else if (c == '[') { in_class = true; }
        else if (c == ']') { in_class = false; }
    }
    return out;
}

struct Regex {
    std::unique_ptr<pcre2_code, decltype(&pcre2_code_free)> code;
    // Reused across attempts. Parsing one handle is serialized by Parser::mutex,
    // and each prepared parser owns its own Regex instances.
    mutable std::unique_ptr<pcre2_match_data, decltype(&pcre2_match_data_free)> data{
        nullptr, pcre2_match_data_free};

    explicit Regex(const std::string &pattern) : code(nullptr, pcre2_code_free) {
        auto translated = regex_pattern(pattern);
        int error;
        PCRE2_SIZE offset;
        code.reset(pcre2_compile(reinterpret_cast<PCRE2_SPTR>(translated.data()),
            translated.size(), PCRE2_UTF | PCRE2_UCP, &error, &offset, nullptr));
        if (!code) {
            PCRE2_UCHAR message[256];
            pcre2_get_error_message(error, message, sizeof(message));
            throw std::invalid_argument("Invalid regex at byte " + std::to_string(offset) +
                ": " + reinterpret_cast<const char *>(message));
        }
    }

    size_t match(std::string_view source, size_t offset, bool &check_utf) const {
        if (!data) {
            data.reset(pcre2_match_data_create_from_pattern(code.get(), nullptr));
            if (!data) throw std::bad_alloc();
        }
        const uint32_t options = PCRE2_ANCHORED | (check_utf ? 0 : PCRE2_NO_UTF_CHECK);
        int rc = pcre2_match(code.get(), reinterpret_cast<PCRE2_SPTR>(source.data()),
            source.size(), offset, options, data.get(), nullptr);
        if (rc < 0 && rc != PCRE2_ERROR_NOMATCH)
            throw std::runtime_error("Regex matching failed: " + std::to_string(rc));
        // Any completed match validated the entire subject (or was told not to).
        check_utf = false;
        if (rc == PCRE2_ERROR_NOMATCH) return peg::kFail;
        auto spans = pcre2_get_ovector_pointer(data.get());
        return spans[1] - spans[0];
    }

    bool nullable() const {
        uint32_t empty = 0;
        pcre2_pattern_info(code.get(), PCRE2_INFO_MATCHEMPTY, &empty);
        return empty != 0;
    }
};

struct LexError : std::runtime_error { using std::runtime_error::runtime_error; };

struct Lexer {
    struct Spec {
        Regex regex;
        std::string type, action;
    };
    std::vector<Spec> specs;
    std::map<std::string, Json> configs;
    bool indentation = false;

    explicit Lexer(const Json &config) {
        const auto definitions = config.value("tokens", Json::array());
        if (!definitions.is_array()) throw std::invalid_argument("Lexer tokens must be an array");
        for (const auto &spec : definitions) {
            std::string action = spec.value("action", Json()).is_null() ? "" : spec.at("action").get<std::string>();
            std::string type = spec.contains("token") ? spec.at("token").get<std::string>() : "";
            if (type.empty() && action != "skip" && action != "handle_indent")
                throw std::invalid_argument("Lexer token specification must have a token name or action");
            specs.push_back({Regex(spec.at("regex").get<std::string>()), type, action});
            if (!type.empty()) configs.emplace(type, spec.value("ast", Json::object()));
            if (action == "handle_indent") indentation = true;
        }
        configs.emplace("INDENT", Json::object());
        configs.emplace("DEDENT", Json::object());
    }

    static std::string normalize(std::string_view source) {
        std::string out;
        size_t col = 0;
        for (size_t i = 0; i < source.size(); ++i) {
            unsigned char c = source[i];
            if (c == '\r') {
                if (i + 1 < source.size() && source[i + 1] == '\n') ++i;
                c = '\n';
            }
            if (c == '\t') {
                auto width = 8 - col % 8;
                out.append(width, ' ');
                col += width;
            } else {
                out += static_cast<char>(c);
                if (c == '\n') col = 0;
                else if ((c & 0xc0) != 0x80) ++col;
            }
        }
        return out;
    }

    std::vector<Token> tokenize(std::string_view source) const {
        auto text = normalize(source);
        std::vector<Token> tokens;
        std::vector<size_t> indents{0};
        size_t pos = 0, line = 1, col = 1;
        bool check_utf = true;
        while (pos < text.size()) {
            const Spec *best = nullptr;
            size_t longest = 0;
            for (const auto &spec : specs) {
                auto size = spec.regex.match(text, pos, check_utf);
                if (peg::success(size) && (!best || size > longest)) { best = &spec; longest = size; }
            }
            if (!best) {
                size_t end = pos + 1;
                while (end < text.size() && (static_cast<unsigned char>(text[end]) & 0xc0) == 0x80) ++end;
                throw LexError("Unexpected character in input text at L" + std::to_string(line) + ":C" +
                    std::to_string(col) + ": '" + text.substr(pos, end - pos) + "'");
            }
            if (!longest) throw LexError("Lexer rule matched empty input at L" + std::to_string(line) + ":C" + std::to_string(col));
            auto value = text.substr(pos, longest);
            if (best->action == "handle_indent") {
                const auto level = codepoints(value) - 1;
                size_t next = pos + longest;
                while (next < text.size() && (text[next] == ' ' || text[next] == '\t')) ++next;
                bool blank = next == text.size() || text[next] == '\n';
                if (!blank) {
                    if (level > indents.back()) { indents.push_back(level); tokens.push_back({"INDENT", "", line + 1, 1}); }
                    while (level < indents.back()) { indents.pop_back(); tokens.push_back({"DEDENT", "", line + 1, 1}); }
                    if (level != indents.back())
                        throw LexError("Indentation error in input text at L" + std::to_string(line + 1) + ":C1");
                }
            } else if (best->action != "skip") tokens.push_back({best->type, value, line, col});
            for (unsigned char c : value) {
                if (c == '\n') { ++line; col = 1; }
                else if ((c & 0xc0) != 0x80) ++col;
            }
            pos += longest;
        }
        if (indentation) while (indents.size() > 1) {
            indents.pop_back();
            tokens.push_back({"DEDENT", "", line, 1});
        }
        return tokens;
    }
};

void flatten(const Json &value, Json &out) {
    if (value.is_array()) {
        for (const auto &child : value) flatten(child, out);
    } else if (!value.is_null()) { out.push_back(value); }
}

Json typed(std::string_view text, const std::string &type) {
    if (type == "null") return nullptr;
    if (type == "bool") {
        std::string lower(text);
        for (char &c : lower) c = static_cast<char>(std::tolower(static_cast<unsigned char>(c)));
        return lower == "true";
    }
    if (type != "number") return std::string(text);
    // Unicode 15.0 Nd blocks: each zero begins ten consecutive decimal digits.
    static constexpr char32_t zeroes[] = {
        0x30, 0x660, 0x6f0, 0x7c0, 0x966, 0x9e6, 0xa66, 0xae6, 0xb66, 0xbe6,
        0xc66, 0xce6, 0xd66, 0xde6, 0xe50, 0xed0, 0xf20, 0x1040, 0x1090,
        0x17e0, 0x1810, 0x1946, 0x19d0, 0x1a80, 0x1a90, 0x1b50, 0x1bb0,
        0x1c40, 0x1c50, 0xa620, 0xa8d0, 0xa900, 0xa9d0, 0xa9f0, 0xaa50,
        0xabf0, 0xff10, 0x104a0, 0x10d30, 0x11066, 0x110f0, 0x11136,
        0x111d0, 0x112f0, 0x11450, 0x114d0, 0x11650, 0x116c0, 0x11730,
        0x118e0, 0x11950, 0x11c50, 0x11d50, 0x11da0, 0x11f50, 0x16a60,
        0x16ac0, 0x16b50, 0x1d7ce, 0x1d7d8, 0x1d7e2, 0x1d7ec, 0x1d7f6,
        0x1e140, 0x1e2f0, 0x1e4f0, 0x1e950, 0x1fbf0,
    };
    std::string normalized;
    if (std::any_of(text.begin(), text.end(), [](unsigned char c) { return c >= 0x80; })) {
        normalized.reserve(text.size());
        for (size_t offset = 0; offset < text.size();) {
            char32_t cp;
            auto size = peg::decode_codepoint(text.data() + offset, text.size() - offset, cp);
            if (!size) throw std::invalid_argument("Invalid UTF-8 number token");
            auto end = std::upper_bound(std::begin(zeroes), std::end(zeroes), cp);
            if (end != std::begin(zeroes) && cp - *(end - 1) < 10)
                normalized += static_cast<char>('0' + cp - *(end - 1));
            else normalized.append(text.substr(offset, size));
            offset += size;
        }
        text = normalized;
    }
    while (!text.empty() && std::isspace(static_cast<unsigned char>(text.front()))) text.remove_prefix(1);
    while (!text.empty() && std::isspace(static_cast<unsigned char>(text.back()))) text.remove_suffix(1);
    if (!text.empty() && text.front() == '+') text.remove_prefix(1);
    auto invalid = [] { throw std::invalid_argument("Invalid number token"); };
    if (text.empty()) invalid();
    if (text.find_first_of(".eE") == std::string_view::npos) {
        if (text.front() == '-') {
            int64_t value = 0;
            auto result = std::from_chars(text.data(), text.data() + text.size(), value);
            if (result.ec == std::errc::result_out_of_range) throw std::out_of_range("Number exceeds int64 range");
            if (result.ec != std::errc() || result.ptr != text.data() + text.size()) invalid();
            return value;
        }
        uint64_t value = 0;
        auto result = std::from_chars(text.data(), text.data() + text.size(), value);
        if (result.ec == std::errc::result_out_of_range) throw std::out_of_range("Number exceeds uint64 range");
        if (result.ec != std::errc() || result.ptr != text.data() + text.size()) invalid();
        return value;
    }
    double value = 0;
    auto result = std::from_chars(text.data(), text.data() + text.size(), value);
    if (result.ec == std::errc::result_out_of_range || !std::isfinite(value)) throw std::out_of_range("Number exceeds float64 range");
    if (result.ec != std::errc() || result.ptr != text.data() + text.size()) invalid();
    if (std::trunc(value) == value) {
        if (value >= -std::ldexp(1.0, 63) && value < std::ldexp(1.0, 63)) return static_cast<int64_t>(value);
        if (value >= 0 && value < std::ldexp(1.0, 64)) return static_cast<uint64_t>(value);
    }
    return value;
}

struct Rule {
    peg::Definition definition;
    Json node;
    Json config;
    std::string name, kind;
    std::vector<Rule *> parts;
    bool nullable = false;
};

struct Match {
    const Rule *rule;
    size_t start, size;
    std::vector<std::shared_ptr<Match>> children;
};
using Tree = std::shared_ptr<Match>;

bool bare_reference(const Json &node) {
    if (!node.contains("rule")) return false;
    if (!node.contains("ast")) return true;
    const auto &config = node.at("ast");
    return config.size() == 1 && config.contains("name");
}

bool absent(const Json &node) { return node.is_null() || (node.is_array() && node.empty()); }

Json cleanup(Json node) {
    auto internal = [](const Json &item) {
        return item.is_object() && item.value("tag", std::string()).find("__") != std::string::npos;
    };
    if (node.is_array()) {
        Json out = Json::array();
        for (auto &item : node) if (!internal(item)) out.push_back(cleanup(std::move(item)));
        return out;
    }
    if (node.is_object()) {
        if (node.contains("tag")) {
            if (node.contains("children")) node["children"] = cleanup(std::move(node["children"]));
        } else {
            for (auto it = node.begin(); it != node.end();) {
                if (internal(it.value())) it = node.erase(it);
                else { it.value() = cleanup(std::move(it.value())); ++it; }
            }
        }
    }
    return node;
}

struct Parser {
    std::map<std::string, std::unique_ptr<Rule>> rules;
    std::vector<std::unique_ptr<Rule>> expressions;
    std::string start;
    std::optional<Lexer> lexer;
    std::mutex mutex;

    Parser(Json grammar, const std::filesystem::path &base, bool placeholders) {
        grammar = koine::prepare_grammar(std::move(grammar), base, placeholders);
        if (grammar.contains("lexer")) lexer.emplace(grammar.at("lexer"));
        if (!grammar.contains("start_rule") || !grammar["start_rule"].is_string())
            throw std::invalid_argument("Grammar must have a start_rule string");
        start = grammar["start_rule"].get<std::string>();
        for (const auto &entry : grammar["rules"].items()) {
            auto definition = std::make_unique<Rule>();
            definition->name = entry.key();
            definition->definition.name = entry.key();
            definition->definition.enablePackratParsing = true;
            definition->definition.eoi_check = false;
            rules.emplace(entry.key(), std::move(definition));
        }
        if (lexer) for (const auto &entry : lexer->configs)
            if (!rules.count(entry.first)) rules.emplace(entry.first, std::make_unique<Rule>());
        for (const auto &entry : grammar["rules"].items())
            define(*rules.at(entry.key()), entry.value(), entry.key().substr(0, entry.key().find("__")));
        if (lexer) for (const auto &entry : lexer->configs) {
            // Token definitions replace same-named grammar rules in the reference.
            auto &rule = *rules.at(entry.first);
            rule.name = entry.first;
            rule.kind = "token_terminal";
            rule.node = {{"token", entry.first}};
            rule.config = entry.second;
            rule.parts.clear();
            rule.nullable = false;
            rule.definition.name = entry.first;
            rule.definition.enablePackratParsing = true;
            rule.definition.eoi_check = false;
            rule.definition <= peg::usr([name = entry.first](const char *s, size_t n, peg::SemanticValues &, std::any &context) {
                auto &state = std::any_cast<ParseContext &>(context);
                if (std::string_view(s, n).substr(0, name.size()) != name) {
                    auto offset = static_cast<size_t>(s - state.source.data());
                    if (!state.failure_offset || offset > *state.failure_offset) {
                        state.failure_offset = offset;
                        state.expected_terminal = "token '" + name + "'";
                    }
                    return peg::kFail;
                }
                size_t length = name.size();
                while (length < n && s[length] == ' ') ++length;
                return length;
            });
            rule.definition.action = [&rule](const peg::SemanticValues &values, std::any &context) -> Tree {
                auto span = values.sv();
                auto source = std::any_cast<ParseContext &>(context).source;
                return std::make_shared<Match>(Match{&rule, static_cast<size_t>(span.data() - source.data()), span.size(), {}});
            };
        }
        check_recursion();
    }

    Rule *expression(const Json &node, const std::string &owner) {
        auto definition = std::make_unique<Rule>();
        auto *ptr = definition.get();
        expressions.push_back(std::move(definition));
        define(*ptr, node, owner);
        return ptr;
    }

    void define(Rule &rule, const Json &node, const std::string &owner) {
        if (!node.is_object()) throw std::invalid_argument("Rule definition must be an object (in rule '" + owner + "')");
        Json config = node.value("ast", Json::object());
        if (!config.is_object()) throw std::invalid_argument("ast must be an object");
        for (const auto &entry : config.items()) {
            if (entry.key() == "structure") continue;
            const bool flag = entry.key() == "leaf" || entry.key() == "discard" || entry.key() == "promote";
            // The reference permits extra AST metadata; only known directives act.
            if (!flag && entry.key() != "tag" && entry.key() != "name" && entry.key() != "type") continue;
            if (flag ? !entry.value().is_boolean() : !entry.value().is_string())
                throw std::invalid_argument("Invalid AST directive type: " + entry.key());
        }
        std::string kind;
        for (const auto &entry : node.items()) {
            if (entry.key() == "ast" || entry.key() == "transpile") continue;
            if (!kind.empty()) throw std::invalid_argument("Rule must have exactly one matching key");
            kind = entry.key();
        }
        Ope body;
        rule.node = node;
        rule.config = config;
        rule.kind = kind;
        auto child = [&](const Json &part) {
            auto *value = expression(part, owner);
            rule.parts.push_back(value);
            return static_cast<Ope>(value->definition);
        };
        if (kind == "literal") {
            body = peg::lit(node.at(kind).get<std::string>());
            rule.nullable = node.at(kind).get_ref<const std::string &>().empty();
        } else if (kind == "regex") {
            auto regex = std::make_shared<Regex>(node.at(kind).get<std::string>());
            rule.nullable = regex->nullable();
            body = peg::usr([regex, pattern = node.at(kind).get<std::string>()](const char *s, size_t, peg::SemanticValues &, std::any &context) {
                auto &state = std::any_cast<ParseContext &>(context);
                const auto offset = static_cast<size_t>(s - state.source.data());
                const auto length = regex->match(state.source, offset, state.check_utf);
                if (peg::fail(length) && (!state.failure_offset || offset > *state.failure_offset)) {
                    state.failure_offset = offset;
                    state.expected_terminal = "regex matching r\"" + pattern + "\"";
                }
                return length;
            });
        } else if (kind == "rule" || kind == "token") {
            if (kind == "token" && !lexer) throw std::invalid_argument("Token matching requires a lexer definition");
            auto ref = node.at(kind).get<std::string>();
            if (!rules.count(ref)) throw std::invalid_argument("Rule '" + ref + "' is not defined in grammar.");
            rule.parts.push_back(rules.at(ref).get());
            body = static_cast<Ope>(rules.at(ref)->definition);
        } else if (kind == "sequence" || kind == "choice") {
            const auto &parts = node.at(kind);
            if (!parts.is_array()) throw std::invalid_argument(kind + " must be an array");
            if (kind == "choice" && parts.empty()) throw std::invalid_argument("Choice cannot be empty");
            std::vector<Ope> children;
            for (const auto &part : parts) children.push_back(child(part));
            if (kind == "sequence") body = std::make_shared<peg::Sequence>(std::move(children));
            else body = std::make_shared<peg::PrioritizedChoice>(std::move(children));
        } else if (kind == "zero_or_more") body = peg::zom(child(node.at(kind)));
        else if (kind == "one_or_more") body = peg::oom(child(node.at(kind)));
        else if (kind == "optional") body = peg::opt(child(node.at(kind)));
        else if (kind == "positive_lookahead") body = peg::apd(child(node.at(kind)));
        else if (kind == "negative_lookahead") body = peg::npd(child(node.at(kind)));
        else throw std::invalid_argument("Unsupported matching key in this native slice: " + kind);

        if (lexer && (kind == "literal" || kind == "regex"))
            throw std::invalid_argument("'" + kind + "' is not supported when a lexer is defined. Use 'token' instead.");
        // A single choice is the underlying expression in the reference backend.
        if (kind == "choice" && rule.parts.size() == 1)
            body = rule.parts[0]->definition.get_core_operator();
        rule.definition <= body;
        rule.definition.action = [&rule](const peg::SemanticValues &values, std::any &context) -> Tree {
            auto span = values.sv();
            auto source = std::any_cast<ParseContext &>(context).source;
            auto result = std::make_shared<Match>(Match{&rule, static_cast<size_t>(span.data() - source.data()), span.size(), {}});
            for (const auto &value : values) result->children.push_back(std::any_cast<Tree>(value));
            if ((bare_reference(rule.node) || rule.kind == "token") && result->children.size() == 1) return result->children[0];
            if (rule.kind == "choice" && rule.parts.size() == 1 &&
                (bare_reference(rule.parts[0]->node) || rule.parts[0]->kind == "token") && result->children.size() == 1)
                return result->children[0];
            return result;
        };
    }

    void check_recursion() {
        std::vector<Rule *> all;
        for (auto &entry : rules) all.push_back(entry.second.get());
        for (auto &entry : expressions) all.push_back(entry.get());
        bool changed;
        do {
            changed = false;
            for (auto *rule : all) {
                bool nullable = rule->nullable;
                if (rule->kind == "optional" || rule->kind == "zero_or_more" || rule->kind.find("lookahead") != std::string::npos) nullable = true;
                else if (rule->kind == "sequence") nullable = std::all_of(rule->parts.begin(), rule->parts.end(), [](Rule *part) { return part->nullable; });
                else if (rule->kind == "choice") nullable = std::any_of(rule->parts.begin(), rule->parts.end(), [](Rule *part) { return part->nullable; });
                else if (!rule->parts.empty()) nullable = rule->parts[0]->nullable;
                if (nullable && !rule->nullable) { rule->nullable = true; changed = true; }
            }
        } while (changed);
        std::map<Rule *, int> state;
        std::function<void(Rule *)> visit = [&](Rule *rule) {
            if (state[rule] == 1) throw std::invalid_argument("Left-recursion detected in grammar: " + rule->name);
            if (state[rule] == 2) return;
            state[rule] = 1;
            for (auto *part : rule->parts) {
                visit(part);
                if (rule->kind == "sequence" && !part->nullable) break;
            }
            state[rule] = 2;
        };
        for (auto *rule : all) visit(rule);
    }

    Json shape(const Tree &tree, std::string_view source, const SourceIndex &index,
        const std::vector<Token> *tokens = nullptr) const {
        const auto &rule = *tree->rule;
        const auto &node = rule.node;
        const auto &config = rule.config;
        const auto &kind = rule.kind;
        const bool token_input = tokens && !tokens->empty();
        if (kind == "token_terminal") {
            auto it = std::lower_bound(tokens->begin(), tokens->end(), tree->start,
                [](const Token &token, size_t offset) { return token.stream_start < offset; });
            if (it == tokens->end() || it->stream_start != tree->start || it->type != rule.name)
                throw std::invalid_argument("Internal lexer/parser token mismatch: " + rule.name);
            if (config.value("discard", false)) return nullptr;
            Json result = {{"tag", it->type}, {"text", it->value}, {"line", it->line}, {"col", it->col}};
            auto type = config.value("type", std::string());
            result["value"] = type == "number" || type == "bool" || type == "null" ? typed(it->value, type) : Json(it->value);
            return result;
        }
        const bool named = !rule.name.empty();
        auto text = source.substr(tree->start, tree->size);
        Json visited = Json::array();
        for (const auto &child : tree->children) visited.push_back(shape(child, source, index, tokens));
        if (!named) {
            if (kind.find("lookahead") != std::string::npos || (text.empty() && visited.empty())) return nullptr;
            if (kind == "optional") return visited.empty() ? Json(nullptr) : visited[0];
            if (kind == "literal" || kind == "regex") {
        const auto point = index.location(tree->start);
        size_t line = point.first;
        size_t col = point.second;
                return {{"tag", kind}, {"text", std::string(text)}, {"line", line}, {"col", col}};
            }
            Json children = Json::array();
            for (auto &child : visited) if (!child.is_null()) children.push_back(std::move(child));
            return children;
        }
        if (config.value("discard", false)) return nullptr;
        Json children = Json::array();
        if (config.contains("structure")) {
            // `structure` maps original child positions, so keep `visited` intact.
            for (const auto &child : visited) if (!child.is_null()) children.push_back(child);
        } else {
            for (auto &child : visited) if (!child.is_null()) children.push_back(std::move(child));
        }
        const auto start_point = index.location(tree->start);
        size_t line = start_point.first;
        size_t col = start_point.second;
        if (token_input) {
            line = col = 1;
            for (const auto &child : children) if (child.is_object() && child.contains("line")) {
                line = child.at("line").get<size_t>();
                col = child.at("col").get<size_t>();
                break;
            }
        }
        auto base = [&](const std::string &tag) -> Json {
            return {{"tag", tag}, {"text", std::string(text)}, {"line", line}, {"col", col}};
        };
        bool wrapped_leaf = kind == "sequence" && node.at(kind).size() == 1 &&
            !node.at(kind)[0].contains("ast") && (node.at(kind)[0].contains("literal") || node.at(kind)[0].contains("regex"));
        if ((!token_input && (kind == "literal" || kind == "regex")) || config.value("leaf", false) || wrapped_leaf) {
            Json result = base(config.value("tag", rule.name));
            std::string leaf_text(text);
            if (token_input && !children.empty()) {
                Json flat = Json::array();
                flatten(children, flat);
                std::string joined;
                bool has_text = false;
                for (const auto &child : flat) if (child.is_object() && child.contains("text")) {
                    joined += child.at("text").get<std::string>();
                    has_text = true;
                }
                if (has_text) leaf_text = std::move(joined);
            }
            result["text"] = leaf_text;
            if (config.contains("type")) result["value"] = typed(leaf_text, config.at("type").get<std::string>());
            return result;
        }
        if (config.value("promote", false)) {
            Json flat = Json::array();
            flatten(children, flat);
            Json promoted;
            if (flat.size() == 3 && flat[0].is_object() && flat[0].value("tag", "") == "literal" && flat[2].is_object() && flat[2].value("tag", "") == "literal") promoted = flat[1];
            else if (kind == "sequence" || kind == "one_or_more" || kind == "zero_or_more" || kind == "optional") promoted = flat;
            else if (flat.size() == 1) promoted = flat[0];
            else if (!flat.empty()) promoted = flat;
            if (promoted.is_object()) {
                if (config.contains("tag")) promoted["tag"] = config["tag"];
                if (config.contains("type")) {
                    try { promoted["value"] = typed(promoted.value("text", ""), config.at("type").get<std::string>()); }
                    catch (const std::invalid_argument &) { promoted["value"] = promoted.value("text", ""); }
                }
            } else if (promoted.is_array() && config.contains("tag")) {
                Json result = base(config.at("tag").get<std::string>());
                result["children"] = std::move(promoted);
                return result;
            }
            return promoted;
        }
        if (config.contains("structure")) {
            const auto &structure = config.at("structure");
            if (structure.is_string()) {
                auto binary = [](const Json &op, const Json &left, const Json &right) -> Json {
                    return {{"tag", "binary_op"}, {"op", op}, {"left", left}, {"right", right}, {"line", op.at("line")}, {"col", op.at("col")}};
                };
                Json left = children.at(0);
                if (children.size() < 2) return left;
                if (structure == "left_associative_op") {
                    for (const auto &group : children.at(1)) {
                        Json clean = Json::array();
                        for (const auto &item : group) if (!item.is_null()) clean.push_back(item);
                        if (!clean.empty()) left = binary(clean.at(0), left, clean.at(1));
                    }
                    return left;
                }
                if (structure == "right_associative_op") {
                    Json clean = Json::array();
                    for (const auto &item : children.at(1)) if (!item.is_null()) clean.push_back(item);
                    return clean.empty() ? left : binary(clean.at(0), left, clean.at(1));
                }
                throw std::invalid_argument("Unknown AST structure: " + structure.get<std::string>());
            }
            if (structure.is_object()) {
                Json result = base(structure.value("tag", rule.name));
                result["children"] = Json::object();
                const auto &parts = visited.size() == 1 && visited[0].is_array() ? visited[0] : visited;
                const auto mappings = structure.value("map_children", Json::object());
                for (const auto &mapping : mappings.items()) {
                    auto index = mapping.value().at("from_child").get<size_t>();
                    while (index < parts.size() && absent(parts[index])) ++index;
                    if (index < parts.size()) result["children"][mapping.key()] = parts[index];
                }
                return result;
            }
        }
        Json result = base(config.value("tag", rule.name));
        Json names = Json::object();
        size_t i = 0;
        if (kind == "sequence") for (const auto &part : node.at(kind)) {
            if (part.contains("positive_lookahead") || part.contains("negative_lookahead")) continue;
            auto part_config = part.value("ast", Json::object());
            bool discarded = part_config.value("discard", false);
            if (!discarded && part.contains("rule")) {
                const auto &ref = *rules.at(part.at("rule").get<std::string>());
                if (ref.kind != "token_terminal") discarded = ref.config.value("discard", false);
            }
            if (discarded) continue;
            if (part_config.contains("name")) names[part_config.at("name").get<std::string>()] = i < children.size() ? children[i] : Json::array();
            ++i;
        }
        if (!names.empty()) result["children"] = std::move(names);
        else { Json flat = Json::array(); flatten(children, flat); result["children"] = std::move(flat); }
        return result;
    }

    Json parse(std::string_view original, const char *rule, size_t rule_size) {
        std::lock_guard<std::mutex> lock(mutex);
        const std::string selected = rule ? std::string(rule, rule_size) : start;
        if (!rules.count(selected)) throw std::invalid_argument("Undefined start rule: " + selected);
        std::vector<Token> tokens;
        std::string token_stream;
        std::string_view source = original;
        if (lexer) {
            try { tokens = lexer->tokenize(original); }
            catch (const LexError &error) { return {{"status", "error"}, {"message", valid_utf8(error.what())}}; }
            for (auto &token : tokens) {
                if (!token_stream.empty()) token_stream += ' ';
                token.stream_start = token_stream.size();
                token_stream += token.type;
            }
            source = token_stream;
        }
        Tree tree;
        std::any context = ParseContext{source, std::nullopt, ""};
        std::string message;
        peg::Log logger = [&](size_t line, size_t col, const std::string &detail, const std::string &) {
            message = "Syntax error in input text at L" + std::to_string(line) +
                      ":C" + std::to_string(col) + " while parsing rule '" + selected + "': " + detail;
        };
        auto result = rules.at(selected)->definition.parse_and_get_value(
            source.data(), source.size(), context, tree, nullptr, logger);
        if (lexer && (!result.ret || result.len != source.size())) {
            auto &state = std::any_cast<ParseContext &>(context);
            size_t offset = result.ret ? result.len : state.failure_offset.value_or(0);
            if (!result.ret) for (const char *position : {result.error_info.error_pos, result.error_info.message_pos})
                if (position) offset = std::max(offset, static_cast<size_t>(position - source.data()));
            auto index = std::count(source.begin(), source.begin() + std::min(offset, source.size()), ' ');
            size_t line, col;
            std::string detail;
            if (static_cast<size_t>(index) < tokens.size()) {
                const auto &token = tokens[index];
                line = token.line; col = token.col;
                detail = "Unexpected token '" + token.type + "' ('" + token.value + "')";
            } else {
                if (tokens.empty()) std::tie(line, col) = location(original, original.size());
                else { line = tokens.back().line; col = tokens.back().col + codepoints(tokens.back().value); }
                detail = "Unexpected end of input";
            }
            return {{"status", "error"}, {"message", "Syntax error in input text at L" + std::to_string(line) + ":C" +
                std::to_string(col) + ". " + detail + " while parsing rule '" + selected + "'"}};
        }
        if (result.ret && result.len != source.size()) {
            auto [line, col] = location(source, result.len);
            auto snippet = source.substr(result.len, 20);
            snippet = snippet.substr(0, snippet.find('\n'));
            return {{"status", "error"}, {"message", valid_utf8("Parse Error in input text at L" + std::to_string(line) + ":C" + std::to_string(col) + ". Rule '" + selected + "' parsed successfully, but failed to consume the entire input. Unconsumed text begins with: '" + std::string(snippet) + "...'")}};
        }
        if (!result.ret) {
            peg::ErrorReporter report = [&](const peg::ErrorReport &error) {
                std::string detail = error.message;
                auto unexpected = error.unexpected_token;
                if (unexpected.empty() || valid_utf8(unexpected) != unexpected)
                    unexpected = codepoint_at(source, error.position);
                // message is only a custom error_message, not the formatted
                // diagnostic. Ordinary failures supply the structured fields.
                if (detail.empty()) {
                    detail = error.position == source.size() ? "Unexpected end of input" :
                        "Unexpected '" + unexpected + "'";
                    bool first = true;
                    auto expected = [&](const std::string &name) {
                        detail += first ? ". Expected one of: " : ", ";
                        detail += name;
                        first = false;
                    };
                    for (const auto &literal : error.expected_literals) expected("'" + literal + "'");
                    for (const auto &name : error.expected_rules) expected(name);
                }
                logger(error.line, error.col, detail, error.label);
            };
            result.error_info.output_log(peg::Log(), report, source.data(), source.size());
            auto &state = std::any_cast<ParseContext &>(context);
            size_t backend_offset = 0;
            for (const char *position : {result.error_info.error_pos, result.error_info.message_pos}) {
                if (position) backend_offset = std::max(backend_offset,
                    static_cast<size_t>(position - source.data()));
            }
            // Custom matchers do not populate cpp-peglib's expected-token list.
            if (state.failure_offset && (message.empty() || *state.failure_offset > backend_offset)) {
                auto [line, col] = location(source, *state.failure_offset);
                logger(line, col, "Expected " + state.expected_terminal, selected);
            }
            if (message.empty()) {
                auto [line, col] = location(source, result.len);
                logger(line, col, "No matching expression", selected);
            }
            auto failure = std::max(backend_offset, state.failure_offset.value_or(0));
            if (failure == source.size()) message += ". Unexpected end of input while parsing '" + std::string(source) + "'";
            return {{"status", "error"}, {"message", valid_utf8(message)}};
        }
        SourceIndex index(source);
        return {{"status", "success"}, {"ast", cleanup(shape(tree, source, index, lexer ? &tokens : nullptr))}};
    }
};

void buffer(koine_buffer *out, std::string_view text) {
    char *copy = static_cast<char *>(std::malloc(text.size() + 1));
    if (!copy) throw std::bad_alloc();
    std::memcpy(copy, text.data(), text.size());
    copy[text.size()] = '\0';
    out->data = copy;
    out->size = text.size();
}

template<class F> int boundary(koine_buffer *error, F operation) noexcept {
    if (!error) return 1;
    try { operation(); return 0; }
    catch (const std::exception &e) {
        try { buffer(error, e.what()); } catch (...) {}
    } catch (...) {
        try { buffer(error, "Unknown native Koine error"); } catch (...) {}
    }
    return 1;
}
} // namespace

struct koine_parser {
    Parser value;
    koine_parser(Json grammar, const std::filesystem::path &base, bool placeholders)
        : value(std::move(grammar), base, placeholders) {}
};

struct koine_transpiler {
    koine::Transpiler value;
    explicit koine_transpiler(const Json &grammar) : value(grammar) {}
};

extern "C" {
int koine_parser_create(const char *grammar, size_t size, koine_parser **out, koine_buffer *error) {
    return koine_parser_prepare(grammar, size, nullptr, 0, KOINE_PARSER_FULL, out, error);
}

int koine_parser_prepare(const char *grammar, size_t size, const char *base, size_t base_size,
    koine_parser_mode mode, koine_parser **out, koine_buffer *error) {
    if (out) *out = nullptr;
    return boundary(error, [&] {
        if (!out) throw std::invalid_argument("Parser output must not be NULL");
        if (mode != KOINE_PARSER_FULL && mode != KOINE_PARSER_PLACEHOLDER) throw std::invalid_argument("Invalid parser mode");
        auto path = std::string(input(base, base_size));
        if (path.find('\0') != std::string::npos) throw std::invalid_argument("NUL in base path");
        *out = new koine_parser(koine::document(input(grammar, size)),
            path.empty() ? std::filesystem::current_path() : std::filesystem::absolute(std::filesystem::u8path(path)), mode == KOINE_PARSER_PLACEHOLDER);
    });
}

int koine_parser_from_file(const char *path, size_t size, koine_parser **out, koine_buffer *error) {
    return koine_parser_prepare_file(path, size, KOINE_PARSER_FULL, out, error);
}

int koine_parser_prepare_file(const char *path, size_t size, koine_parser_mode mode,
    koine_parser **out, koine_buffer *error) {
    if (out) *out = nullptr;
    return boundary(error, [&] {
        if (!out) throw std::invalid_argument("Parser output must not be NULL");
        if (mode != KOINE_PARSER_FULL && mode != KOINE_PARSER_PLACEHOLDER) throw std::invalid_argument("Invalid parser mode");
        std::string filename(input(path, size));
        if (filename.find('\0') != std::string::npos) throw std::invalid_argument("NUL in grammar filename");
        auto resolved = std::filesystem::weakly_canonical(std::filesystem::absolute(std::filesystem::u8path(filename)));
        *out = new koine_parser(koine::load_document(resolved), resolved.parent_path(), mode == KOINE_PARSER_PLACEHOLDER);
    });
}

int koine_parser_parse(koine_parser *parser, const char *source, size_t size,
    const char *start_rule, size_t start_rule_size, koine_buffer *result, koine_buffer *error) {
    return boundary(error, [&] {
        if (!parser || !result) throw std::invalid_argument("Parser and result must not be NULL");
        input(start_rule, start_rule_size);
        buffer(result, parser->value.parse(input(source, size), start_rule, start_rule_size).dump());
    });
}

int koine_parser_parse_transpile(koine_parser *parser, koine_transpiler *transpiler,
    const char *source, size_t size, const char *start_rule, size_t start_rule_size,
    koine_buffer *result, koine_buffer *error) {
    return boundary(error, [&] {
        if (!parser || !transpiler || !result)
            throw std::invalid_argument("Parser, transpiler and result must not be NULL");
        input(start_rule, start_rule_size);
        Json parsed = parser->value.parse(input(source, size), start_rule, start_rule_size);
        if (parsed.at("status") != "success") { buffer(result, parsed.dump()); return; }
        Json report = {{"status", "success"},
            {"text", transpiler->value.transpile(parsed.at("ast"))}};
        buffer(result, report.dump());
    });
}

void koine_parser_destroy(koine_parser *parser) { delete parser; }

int koine_transpiler_create(const char *grammar, size_t size, koine_transpiler **out, koine_buffer *error) {
    if (out) *out = nullptr;
    return boundary(error, [&] {
        if (!out) throw std::invalid_argument("Transpiler output must not be NULL");
        *out = new koine_transpiler(koine::document(input(grammar, size)));
    });
}

int koine_transpiler_from_file(const char *path, size_t size, koine_transpiler **out, koine_buffer *error) {
    if (out) *out = nullptr;
    return boundary(error, [&] {
        if (!out) throw std::invalid_argument("Transpiler output must not be NULL");
        std::string filename(input(path, size));
        if (filename.find('\0') != std::string::npos) throw std::invalid_argument("NUL in grammar filename");
        *out = new koine_transpiler(koine::load_document(std::filesystem::u8path(filename)));
    });
}

int koine_transpiler_transpile(koine_transpiler *transpiler, const char *ast, size_t size,
    koine_buffer *result, koine_buffer *error) {
    return boundary(error, [&] {
        if (!transpiler || !result) throw std::invalid_argument("Transpiler and result must not be NULL");
        auto source = input(ast, size);
        buffer(result, transpiler->value.transpile(Json::parse(source.begin(), source.end())));
    });
}

int koine_transpiler_state(koine_transpiler *transpiler, koine_buffer *result, koine_buffer *error) {
    return boundary(error, [&] {
        if (!transpiler || !result) throw std::invalid_argument("Transpiler and result must not be NULL");
        buffer(result, transpiler->value.state().dump());
    });
}

void koine_transpiler_destroy(koine_transpiler *transpiler) { delete transpiler; }

void koine_buffer_free(koine_buffer *value) {
    if (value) { std::free(value->data); value->data = nullptr; value->size = 0; }
}
}
