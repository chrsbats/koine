#ifndef KOINE_H
#define KOINE_H

#include <stddef.h>

#if defined(_WIN32)
#if defined(KOINE_BUILD)
#define KOINE_API __declspec(dllexport)
#else
#define KOINE_API __declspec(dllimport)
#endif
#else
#define KOINE_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

typedef struct koine_parser koine_parser;
typedef struct koine_transpiler koine_transpiler;
typedef enum koine_parser_mode {
    KOINE_PARSER_FULL = 0,
    KOINE_PARSER_PLACEHOLDER = 1
} koine_parser_mode;
typedef struct koine_buffer {
    char *data;
    size_t size;
} koine_buffer;

/* Initialize outputs to NULL / {0}; release buffers before reusing them.
 * All byte strings have explicit lengths. Inputs are borrowed for the call.
 * Return 0 on success, 1 on an API/construction error (error is UTF-8 text).
 * parse() returns a JSON success/error result for ordinary syntax failures.
 * Successful outputs are library-owned and require the matching release call.
 */
KOINE_API int koine_parser_create(const char *grammar, size_t size,
                                 koine_parser **parser, koine_buffer *error);
KOINE_API int koine_parser_from_file(const char *path, size_t size,
                                    koine_parser **parser, koine_buffer *error);
/* Advanced construction: NULL base_path uses the current directory. File loading
 * resolves dependencies relative to each declaring file. Placeholder mode uses
 * local placeholder definitions without opening dependency files.
 */
KOINE_API int koine_parser_prepare(const char *grammar, size_t size,
                                  const char *base_path, size_t base_path_size,
                                  koine_parser_mode mode,
                                  koine_parser **parser, koine_buffer *error);
KOINE_API int koine_parser_prepare_file(const char *path, size_t size,
                                       koine_parser_mode mode,
                                       koine_parser **parser, koine_buffer *error);
/* NULL start_rule selects the grammar's default; otherwise use its byte length.
 * Results own their contents independently of source storage and parser lifetime.
 * Calls on a live parser are serialized internally; callers own its lifetime.
 */
KOINE_API int koine_parser_parse(koine_parser *parser, const char *source, size_t size,
                                const char *start_rule, size_t start_rule_size,
                                koine_buffer *result, koine_buffer *error);
/* Parse and transpile in one call without exposing or re-serializing the AST.
 * Returns a JSON object: {status:"success", text:...} or the ordinary parse error
 * object. transpiler may be reused concurrently with other calls; both handles are
 * locked independently and only held one at a time.
 */
KOINE_API int koine_parser_parse_transpile(koine_parser *parser,
                                          koine_transpiler *transpiler,
                                          const char *source, size_t size,
                                          const char *start_rule, size_t start_rule_size,
                                          koine_buffer *result, koine_buffer *error);
KOINE_API void koine_parser_destroy(koine_parser *parser);
/* Prepare runtime YAML/JSON output rules. transpile() borrows a JSON AST and
 * returns owned UTF-8 text. Every top-level call resets state/indentation;
 * state() returns an owned JSON snapshot of the most recent call's state.
 * Calls on one live handle are serialized. Errors use the same return convention
 * as parser creation; input/output lifetimes follow the buffer contract above.
 */
KOINE_API int koine_transpiler_create(const char *grammar, size_t size,
                                     koine_transpiler **transpiler, koine_buffer *error);
KOINE_API int koine_transpiler_from_file(const char *path, size_t size,
                                        koine_transpiler **transpiler, koine_buffer *error);
KOINE_API int koine_transpiler_transpile(koine_transpiler *transpiler,
                                        const char *ast, size_t size,
                                        koine_buffer *result, koine_buffer *error);
KOINE_API int koine_transpiler_state(koine_transpiler *transpiler,
                                    koine_buffer *result, koine_buffer *error);
KOINE_API void koine_transpiler_destroy(koine_transpiler *transpiler);
KOINE_API void koine_buffer_free(koine_buffer *buffer);

#ifdef __cplusplus
}
#endif
#endif
