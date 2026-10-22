#include "grammar.h"

#include <algorithm>
#include <cctype>
#include <fstream>
#include <functional>
#include <iterator>
#include <map>
#include <set>
#include <stdexcept>
#include <vector>

namespace koine {
namespace fs = std::filesystem;

Json load_document(const fs::path &path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) throw std::invalid_argument("Could not open grammar file: " + path.string());
    return document(std::string(std::istreambuf_iterator<char>(stream), {}));
}

namespace {
const Json empty_config = Json::object();
const Json &ast(const Json &node) {
    return node.is_object() && node.contains("ast") ? node.at("ast") : empty_config;
}

// Visit matching data only; AST metadata and placeholder definitions are not dependencies.
void walk(Json &node, const std::function<bool(Json &)> &visit) {
    if (node.is_object()) {
        if (!visit(node)) return;
        for (auto &item : node.items())
            if (item.key() != "ast" && item.key() != "transpile" && item.key() != "subgrammar")
                walk(item.value(), visit);
    } else if (node.is_array()) {
        for (auto &item : node) walk(item, visit);
    }
}

std::set<std::string> references(Json node) {
    std::set<std::string> refs;
    walk(node, [&](Json &part) {
        if (part.contains("rule") && part.at("rule").is_string()) refs.insert(part.at("rule").get<std::string>());
        return true;
    });
    return refs;
}

std::string namespace_for(const fs::path &path) {
    if (path.filename() == "_.yaml") return "";
    std::string out;
    bool capital = true;
    for (unsigned char c : path.stem().string()) {
        if (c == '-' || c == '_') { capital = true; continue; }
        out += static_cast<char>(capital ? std::toupper(c) : std::tolower(c));
        capital = false;
    }
    return out;
}

std::string qualified(const fs::path &path, const std::string &name) {
    auto ns = namespace_for(path);
    return ns.empty() ? name : ns + "_" + name;
}

Json compose(Json initial, const fs::path &base) {
    const auto main = fs::weakly_canonical(base / "_.yaml");
    std::map<fs::path, Json> documents;
    std::vector<fs::path> paths{main};
    documents.emplace(main, initial);
    for (size_t i = 0; i < paths.size(); ++i) {
        const auto path = paths[i];
        auto &content = documents.at(path);
        auto &rules = content.at("rules");
        if (!rules.is_object()) throw std::invalid_argument("Grammar must have a rules object");
        for (auto &entry : rules.items()) {
            bool has_subgrammar = false;
            walk(entry.value(), [&](Json &part) {
                if (!part.contains("subgrammar")) return true;
                has_subgrammar = true;
                return false;
            });
            if (ast(entry.value()).value("leaf", false) && has_subgrammar)
                throw std::invalid_argument("Rule '" + entry.key() + "' is defined as a 'leaf' node but contains a 'subgrammar' directive. These are mutually exclusive.");
        }
        for (auto &entry : rules.items()) walk(entry.value(), [&](Json &part) {
            if (!part.contains("subgrammar")) return true;
            auto dep = fs::weakly_canonical(path.parent_path() / part.at("subgrammar").at("file").get<std::string>());
            if (!documents.count(dep)) {
                documents.emplace(dep, load_document(dep));
                paths.push_back(dep);
            }
            return false;
        });
    }
    std::map<std::string, fs::path> namespaces;
    for (const auto &path : paths) {
        auto ns = namespace_for(path);
        if (!ns.empty() && !namespaces.emplace(ns, path).second)
            throw std::invalid_argument("Namespace collision: files resolve to the same namespace '" + ns + "'");
    }
    Json rules = Json::object();
    std::set<std::string> entries;
    for (const auto &path : paths) {
        const auto &content = documents.at(path);
        const auto &local = content.at("rules");
        if (content.contains("start_rule")) entries.insert(qualified(path, content.at("start_rule").get<std::string>()));
        for (const auto &entry : local.items()) {
            Json node = entry.value();
            walk(node, [&](Json &part) {
                if (part.contains("subgrammar")) {
                    auto config = part.at("subgrammar");
                    auto file = config.at("file").get<std::string>();
                    auto dep = fs::weakly_canonical(path.parent_path() / file);
                    std::string start = config.value("rule", std::string());
                    if (start.empty()) start = documents.at(dep).value("start_rule", std::string());
                    if (start.empty()) throw std::invalid_argument("Subgrammar '" + file + "' must have a 'start_rule' or a 'rule' must be specified.");
                    auto target = qualified(dep, start);
                    entries.insert(target);
                    part.erase("subgrammar");
                    part["rule"] = target;
                    return false;
                }
                if (part.contains("rule")) {
                    auto ref = part.at("rule").get<std::string>();
                    if (local.contains(ref)) part["rule"] = qualified(path, ref);
                }
                return true;
            });
            rules[qualified(path, entry.key())] = std::move(node);
        }
    }
    for (const auto &ref : references(rules)) {
        auto end = ref.find('_');
        if (!ref.empty() && std::isupper(static_cast<unsigned char>(ref[0])) && end != std::string::npos &&
            std::all_of(ref.begin(), ref.begin() + end, [](unsigned char c) { return std::isalnum(c); }))
            entries.insert(ref);
    }
    initial["rules"] = std::move(rules);
    initial["_external_refs"] = entries;
    return initial;
}

bool inline_ast(const Json &node) {
    if (!node.is_object() || !node.contains("ast") || node.contains("rule")) return false;
    const auto &config = node.at("ast");
    if (config.size() == 1 && config.contains("name")) return false;
    for (auto key : {"literal", "regex", "token", "choice", "sequence", "zero_or_more", "one_or_more", "optional", "positive_lookahead", "negative_lookahead"})
        if (node.contains(key)) return true;
    return false;
}

void normalize(Json &grammar) {
    auto &rules = grammar.at("rules");
    std::set<std::string> processed;
    for (;;) {
        std::vector<std::string> pending;
        for (const auto &entry : rules.items()) if (!processed.count(entry.key())) pending.push_back(entry.key());
        if (pending.empty()) break;
        for (const auto &name : pending) {
            size_t counter = 0;
            std::vector<std::pair<std::string, Json>> additions;
            std::function<void(Json &)> walker = [&](Json &node) {
                if (node.is_object() && node.contains("sequence") && node.at("sequence").is_array() && node.at("sequence").size() == 1 && !node.contains("ast")) {
                    auto &child = node["sequence"][0];
                    if (inline_ast(child)) {
                        auto config = child.at("ast");
                        child.erase("ast");
                        node["ast"] = std::move(config);
                    }
                }
                if (!node.is_structured()) return;
                for (auto &item : node.items()) {
                    if (node.is_object() && (item.key() == "ast" || item.key() == "transpile")) continue;
                    auto &value = item.value();
                    if (inline_ast(value)) {
                        auto generated = name + "__" + std::to_string(++counter);
                        auto config = value.at("ast");
                        value.erase("ast");
                        // Append later: ordered_json insertion can invalidate references into rules.
                        additions.emplace_back(generated, Json{{"ast", config}, {"sequence", Json::array({value})}});
                        value = {{"rule", generated}};
                    } else walker(value);
                }
            };
            walker(rules[name]);
            for (auto &item : additions) rules[item.first] = std::move(item.second);
            processed.insert(name);
        }
    }
}

std::string join(const std::set<std::string> &names) {
    std::string out;
    for (const auto &name : names) { if (!out.empty()) out += ", "; out += name; }
    return out;
}

void lint(const Json &grammar) {
    const auto &rules = grammar.at("rules");
    auto start = grammar.at("start_rule").get<std::string>();
    std::set<std::string> reachable;
    std::vector<std::string> queue{start};
    for (const auto &ref : grammar.at("_external_refs")) queue.push_back(ref.get<std::string>());
    bool missing = !rules.contains(start);
    for (size_t i = 0; !missing && i < queue.size(); ++i) {
        auto name = queue[i];
        if (!reachable.insert(name).second) continue;
        if (!rules.contains(name)) { missing = true; break; }
        for (const auto &ref : references(rules.at(name))) queue.push_back(ref);
    }
    if (!missing) {
        std::set<std::string> unreachable;
        for (const auto &entry : rules.items())
            if (!reachable.count(entry.key()) && entry.key().find("__") == std::string::npos) unreachable.insert(entry.key());
        if (!unreachable.empty()) throw std::invalid_argument("Unreachable rules detected: " + join(unreachable));
    }
    std::map<std::string, bool> memo;
    std::function<bool(const Json &)> empty;
    std::function<bool(const std::string &)> empty_rule = [&](const std::string &name) {
        if (!rules.contains(name)) return false;
        if (memo.count(name)) return memo.at(name);
        memo[name] = false;
        return memo[name] = empty(rules.at(name));
    };
    empty = [&](const Json &node) {
        if (!node.is_object()) return false;
        const auto &config = ast(node);
        if (config.value("discard", false)) return true;
        if (config.contains("structure")) return false;
        if (node.contains("rule")) return empty_rule(node.at("rule").get<std::string>());
        if (grammar.contains("lexer") && node.contains("token")) {
            for (const auto &spec : grammar.at("lexer").value("tokens", Json::array()))
                if (spec.value("token", Json()) == node.at("token"))
                    return spec.value("action", Json()) == "skip" || ast(spec).value("discard", false);
            return false;
        }
        if (node.contains("literal") || node.contains("regex") || config.value("leaf", false)) return false;
        if (node.contains("positive_lookahead") || node.contains("negative_lookahead")) return true;
        for (auto key : {"sequence", "choice"}) if (node.contains(key) && node.at(key).is_array()) {
            for (const auto &child : node.at(key)) if (ast(child).contains("name")) return false;
            for (const auto &child : node.at(key)) if (!empty(child)) return false;
            return true;
        }
        for (auto key : {"one_or_more", "zero_or_more", "optional"}) if (node.contains(key)) return empty(node.at(key));
        return false;
    };
    std::set<std::string> implicitly_empty;
    for (const auto &entry : rules.items()) {
        const auto &node = entry.value();
        if (!ast(node).value("discard", false) && !node.contains("positive_lookahead") && !node.contains("negative_lookahead") && empty_rule(entry.key())) implicitly_empty.insert(entry.key());
    }
    if (!implicitly_empty.empty()) throw std::invalid_argument("The following rules will always produce an empty AST node. If intended, add ast: { discard: true }. Rules: " + join(implicitly_empty));
    for (const auto &entry : rules.items()) {
        const auto &config = ast(entry.value());
        if (config.value("promote", false) && config.contains("structure"))
            throw std::invalid_argument("In rule '" + entry.key() + "': 'promote' and 'structure' directives are mutually exclusive.");
        if (config.value("promote", false) && config.value("discard", false))
            throw std::invalid_argument("In rule '" + entry.key() + "': 'promote: true' is redundant when 'discard: true' is also present.");
    }
}
} // namespace

Json prepare_grammar(Json grammar, const fs::path &base, bool placeholders) {
    if (!grammar.is_object() || !grammar.contains("rules") || !grammar["rules"].is_object() || grammar["rules"].empty())
        throw std::invalid_argument("Grammar must have a nonempty rules object");
    if (placeholders) {
        walk(grammar["rules"], [](Json &node) {
            if (!node.contains("subgrammar")) return true;
            auto replacement = node["subgrammar"].value("placeholder", Json{{"sequence", Json::array()}});
            node.erase("subgrammar");
            node.update(replacement);
            return false;
        });
        if (!grammar.contains("start_rule")) grammar["start_rule"] = "start";
    } else {
        if (!grammar.contains("start_rule")) throw std::invalid_argument("The main grammar must have a 'start_rule'");
        grammar = compose(std::move(grammar), base);
    }
    normalize(grammar);
    if (!placeholders) lint(grammar);
    grammar.erase("_external_refs");
    return grammar;
}
} // namespace koine
