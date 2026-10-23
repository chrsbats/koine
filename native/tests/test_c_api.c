#include "koine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "Failed at line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

int main(int argc, char **argv)
{
    koine_parser *parser = NULL;
    koine_buffer result = {0}, error = {0};
    const char *grammar = "{\"start_rule\":\"word\",\"rules\":{\"word\":{\"regex\":\"[a-z]+\",\"ast\":{\"leaf\":true}}}}";
    char *owned = malloc(strlen(grammar) + 1);
    CHECK(owned != NULL);
    strcpy(owned, grammar);
    CHECK(koine_parser_create(owned, strlen(owned), &parser, &error) == 0);
    free(owned);

    char source[] = "hello";
    CHECK(koine_parser_parse(parser, source, 5, NULL, 0, &result, &error) == 0);
    memset(source, 'x', 5);
    CHECK(strstr(result.data, "\"text\":\"hello\"") != NULL);
    koine_parser_destroy(parser);
    CHECK(strstr(result.data, "\"status\":\"success\"") != NULL);
    koine_buffer_free(&result);
    CHECK(result.data == NULL && result.size == 0);
    koine_buffer_free(&result);
    koine_buffer_free(NULL);
    koine_parser_destroy(NULL);

    CHECK(koine_parser_create("{", 1, &parser, &error) == 1);
    CHECK(parser == NULL && error.data != NULL);
    koine_buffer_free(&error);
    CHECK(koine_parser_parse(NULL, "", 0, NULL, 0, &result, &error) == 1);
    CHECK(error.data != NULL && result.data == NULL);
    koine_buffer_free(&error);

    for (int i = 0; i < 100; ++i) {
        CHECK(koine_parser_create(grammar, strlen(grammar), &parser, &error) == 0);
        CHECK(koine_parser_parse(parser, "!", 1, NULL, 0, &result, &error) == 0);
        CHECK(strstr(result.data, "\"status\":\"error\"") != NULL);
        CHECK(strstr(result.data, "Syntax error") != NULL);
        koine_buffer_free(&result);
        CHECK(koine_parser_parse(parser, "again", 5, NULL, 0, &result, &error) == 0);
        koine_parser_destroy(parser);
        koine_buffer_free(&result);
    }
    const char *numeric = "{\"start_rule\":\"n\",\"rules\":{\"n\":{\"regex\":\"[0-9]+\",\"ast\":{\"type\":\"number\"}}}}";
    parser = NULL;
    CHECK(koine_parser_create(numeric, strlen(numeric), &parser, &error) == 0);
    for (int i = 0; i < 10; ++i) {
        CHECK(koine_parser_parse(parser, "18446744073709551616", 20, NULL, 0, &result, &error) == 1);
        CHECK(result.data == NULL && result.size == 0);
        CHECK(error.data != NULL && error.size > 0);
        koine_buffer_free(&error);
    }
    CHECK(koine_parser_parse(parser, "18446744073709551615", 20, NULL, 0, &result, &error) == 0);
    koine_parser_destroy(parser);
    CHECK(strstr(result.data, "\"value\":18446744073709551615") != NULL);
    koine_buffer_free(&result);

    const char *placeholder = "{\"start_rule\":\"main\",\"rules\":{\"main\":{\"subgrammar\":{\"file\":\"missing.yaml\",\"placeholder\":{\"literal\":\"local\"}}}}}";
    CHECK(koine_parser_prepare(placeholder, strlen(placeholder), NULL, 0,
                              KOINE_PARSER_PLACEHOLDER, &parser, &error) == 0);
    CHECK(koine_parser_parse(parser, "local", 5, NULL, 0, &result, &error) == 0);
    koine_parser_destroy(parser);
    CHECK(strstr(result.data, "\"text\":\"local\"") != NULL);
    koine_buffer_free(&result);
    CHECK(argc == 2);
    CHECK(koine_parser_from_file(argv[1], strlen(argv[1]), &parser, &error) == 0);
    CHECK(koine_parser_parse(parser, "2 + 3", 5, "expression", 10, &result, &error) == 0);
    koine_parser_destroy(parser);
    CHECK(strstr(result.data, "\"tag\":\"binary_op\"") != NULL);
    koine_buffer_free(&result);
    CHECK(koine_parser_prepare_file(argv[1], strlen(argv[1]), KOINE_PARSER_PLACEHOLDER,
                                   &parser, &error) == 0);
    koine_parser_destroy(parser);

    // Invalid UTF-8 still fails through the one-time subject validation.
    const char *dot = "{\"start_rule\":\"x\",\"rules\":{\"x\":{\"regex\":\".\"}}}";
    parser = NULL;
    CHECK(koine_parser_create(dot, strlen(dot), &parser, &error) == 0);
    CHECK(koine_parser_parse(parser, "\xff", 1, NULL, 0, &result, &error) == 1);
    CHECK(result.data == NULL && error.data != NULL);
    CHECK(strstr(error.data, "Regex matching failed") != NULL);
    koine_buffer_free(&error);
    CHECK(koine_parser_parse(parser, "a", 1, NULL, 0, &result, &error) == 0);
    koine_buffer_free(&result);
    koine_parser_destroy(parser);

    // Literal-only grammars report malformed unconsumed snippets as parse errors,
    // not as JSON serialization failures. Include every invalid UTF-8 lead range.
    const char *literal = "{\"start_rule\":\"x\",\"rules\":{\"x\":{\"literal\":\"x\"}}}";
    const char *snippets[] = {
        "x\xff", "x\xc0\x80", "x\xed\xa0\x80", "x\xf0\x80\x80\x80",
        "x\xf4\x90\x80\x80", "x\xf5\x80\x80\x80", "x\xf6\x80\x80\x80",
        "x\xf7\xbf\xbf\xbf", "x\xe2\x82",
    };
    CHECK(koine_parser_create(literal, strlen(literal), &parser, &error) == 0);
    for (size_t i = 0; i < sizeof(snippets) / sizeof(snippets[0]); ++i) {
        CHECK(koine_parser_parse(parser, snippets[i], strlen(snippets[i]), NULL, 0, &result, &error) == 0);
        CHECK(error.data == NULL);
        CHECK(strstr(result.data, "\"status\":\"error\"") != NULL);
        CHECK(strstr(result.data, "L1:C2") != NULL);
        CHECK(strstr(result.data, "\xef\xbf\xbd") != NULL);
        koine_buffer_free(&result);
    }
    CHECK(koine_parser_parse(parser, "x", 1, NULL, 0, &result, &error) == 0);
    CHECK(strstr(result.data, "\"status\":\"success\"") != NULL);
    koine_buffer_free(&result);
    koine_parser_destroy(parser);
    return 0;
}
