#include "koine.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(condition) do { if (!(condition)) { \
    fprintf(stderr, "Failed at line %d: %s\n", __LINE__, #condition); return 1; \
} } while (0)

int main(void)
{
    const char *grammar =
        "lexer:\n"
        "  tokens:\n"
        "    - {regex: '[ \\t]+', action: skip}\n"
        "    - {regex: '\\n[ \\t]*', action: handle_indent}\n"
        "    - {regex: '[a-z\u00e9]+', token: NAME}\n"
        "    - {regex: '\\x00', token: NUL}\n"
        "start_rule: main\n"
        "rules:\n"
        "  main:\n"
        "    sequence: [{token: NAME}, {token: INDENT}, {token: NAME}, {token: NUL}, {token: DEDENT}]\n";
    koine_parser *parser = NULL;
    koine_buffer output = {0}, error = {0};
    for (int i = 0; i < 50; ++i) {
        char *owned = malloc(strlen(grammar) + 1);
        CHECK(owned);
        strcpy(owned, grammar);
        CHECK(koine_parser_create(owned, strlen(owned), &parser, &error) == 0);
        free(owned);
        const char *invalid = "a\n    b\n  a";
        CHECK(koine_parser_parse(parser, invalid, strlen(invalid), NULL, 0, &output, &error) == 0);
        CHECK(strstr(output.data, "Indentation error in input text at L3:C1") != NULL);
        CHECK(error.data == NULL);
        koine_buffer_free(&output);

        char source[] = "a\r\n\t\xc3\xa9\0";
        CHECK(koine_parser_parse(parser, source, sizeof(source) - 1, NULL, 0, &output, &error) == 0);
        memset(source, 'x', sizeof(source) - 1);
        koine_parser_destroy(parser);
        CHECK(strstr(output.data, "\"status\":\"success\"") != NULL);
        CHECK(strstr(output.data, "NAME INDENT NAME NUL DEDENT") != NULL);
        CHECK(strstr(output.data, "\"line\":2,\"col\":9") != NULL);
        CHECK(strstr(output.data, "\"line\":2,\"col\":10") != NULL);
        CHECK(strstr(output.data, "\\u0000") != NULL);
        CHECK(error.data == NULL);
        koine_buffer_free(&output);
    }
    return 0;
}
