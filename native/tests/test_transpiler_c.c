#include "koine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "Failed at line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

int main(int argc, char **argv)
{
    koine_transpiler *transpiler = NULL;
    koine_buffer output = {0}, state = {0}, error = {0};
    const char *grammar = "{\"rules\":{\"group\":{\"template\":\"{{{children}}}\",\"state_set\":{\"last\":\"{children}\"}}}}";
    const char *ast = "{\"tag\":\"group\",\"children\":[{\"tag\":\"leaf\",\"text\":\"a\\u0000b\u00e9\"}]}";
    const char expected[] = "{a\0b\xc3\xa9}";
    for (int i = 0; i < 100; ++i) {
        char *owned_grammar = malloc(strlen(grammar) + 1);
        char *owned_ast = malloc(strlen(ast) + 1);
        CHECK(owned_grammar && owned_ast);
        strcpy(owned_grammar, grammar);
        strcpy(owned_ast, ast);
        CHECK(koine_transpiler_create(owned_grammar, strlen(owned_grammar), &transpiler, &error) == 0);
        free(owned_grammar);
        CHECK(koine_transpiler_state(transpiler, &state, &error) == 0);
        CHECK(strcmp(state.data, "{}") == 0);
        koine_buffer_free(&state);
        CHECK(koine_transpiler_transpile(transpiler, owned_ast, strlen(owned_ast), &output, &error) == 0);
        memset(owned_ast, 'x', strlen(owned_ast));
        free(owned_ast);
        CHECK(output.size == sizeof(expected) - 1);
        CHECK(memcmp(output.data, expected, output.size) == 0);
        CHECK(koine_transpiler_state(transpiler, &state, &error) == 0);
        CHECK(strstr(state.data, "\\u0000") != NULL);
        koine_transpiler_destroy(transpiler);
        CHECK(memcmp(output.data, expected, output.size) == 0);
        CHECK(strstr(state.data, "\"last\"") != NULL);
        koine_buffer_free(&output);
        koine_buffer_free(&state);
    }
    koine_transpiler_destroy(NULL);
    CHECK(koine_transpiler_create("[", 1, &transpiler, &error) == 1);
    CHECK(!transpiler && error.data);
    koine_buffer_free(&error);
    CHECK(koine_transpiler_transpile(NULL, "{}", 2, &output, &error) == 1);
    CHECK(!output.data && error.data);
    koine_buffer_free(&error);
    CHECK(koine_transpiler_create("{}", 2, &transpiler, &error) == 0);
    CHECK(koine_transpiler_transpile(transpiler, "{}", 2, &output, &error) == 1);
    CHECK(strstr(error.data, "valid AST node") != NULL);
    koine_buffer_free(&error);
    const char *valid = "{\"tag\":\"number\",\"value\":18446744073709551615}";
    CHECK(koine_transpiler_transpile(transpiler, valid, strlen(valid), &output, &error) == 0);
    CHECK(strcmp(output.data, "18446744073709551615") == 0);
    koine_buffer_free(&output);
    koine_transpiler_destroy(transpiler);
    const char *yaml = "rules:\n  block:\n    template: '[{children}]'\n    state_set: {seen: true}\n";
    CHECK(koine_transpiler_create(yaml, strlen(yaml), &transpiler, &error) == 0);
    const char *block = "{\"tag\":\"block\",\"children\":[{\"text\":\"loaded\"}]}";
    CHECK(koine_transpiler_transpile(transpiler, block, strlen(block), &output, &error) == 0);
    CHECK(strcmp(output.data, "[loaded]") == 0);
    koine_buffer_free(&output);
    CHECK(koine_transpiler_state(transpiler, &state, &error) == 0);
    CHECK(strcmp(state.data, "{\"seen\":true}") == 0);
    koine_buffer_free(&state);
    koine_transpiler_destroy(transpiler);
    CHECK(argc == 2);
    CHECK(koine_transpiler_from_file(argv[1], strlen(argv[1]), &transpiler, &error) == 0);
    CHECK(koine_transpiler_transpile(transpiler, valid, strlen(valid), &output, &error) == 0);
    koine_transpiler_destroy(transpiler);
    CHECK(strcmp(output.data, "18446744073709551615") == 0);
    koine_buffer_free(&output);

    const char *number_parser =
        "{\"start_rule\":\"n\",\"rules\":{\"n\":{\"regex\":\"[0-9]+\","
        "\"ast\":{\"type\":\"number\",\"tag\":\"number\"}}}}";
    koine_parser *parser = NULL;
    CHECK(koine_parser_create(number_parser, strlen(number_parser), &parser, &error) == 0);
    CHECK(koine_transpiler_create("{}", 2, &transpiler, &error) == 0);
    for (int i = 0; i < 10; ++i) {
        CHECK(koine_parser_parse_transpile(parser, transpiler, "42", 2, NULL, 0, &output, &error) == 0);
        CHECK(strstr(output.data, "\"status\":\"success\"") != NULL);
        CHECK(strstr(output.data, "\"text\":\"42\"") != NULL);
        CHECK(strstr(output.data, "\"ast\"") == NULL);
        koine_buffer_free(&output);
    }
    CHECK(koine_parser_parse_transpile(parser, transpiler, "x", 1, NULL, 0, &output, &error) == 0);
    CHECK(strstr(output.data, "\"status\":\"error\"") != NULL);
    koine_buffer_free(&output);
    koine_transpiler_destroy(transpiler);
    const char *broken_output =
        "{\"rules\":{\"number\":{\"cases\":[{\"if\":{},\"then\":\"bad\"}]}}}";
    CHECK(koine_transpiler_create(broken_output, strlen(broken_output), &transpiler, &error) == 0);
    CHECK(koine_parser_parse_transpile(parser, transpiler, "42", 2, NULL, 0, &output, &error) == 1);
    CHECK(!output.data && error.data != NULL);
    koine_buffer_free(&error);
    CHECK(koine_parser_parse_transpile(NULL, transpiler, "42", 2, NULL, 0, &output, &error) == 1);
    koine_buffer_free(&error);
    koine_transpiler_destroy(transpiler);
    koine_parser_destroy(parser);
    return 0;
}
