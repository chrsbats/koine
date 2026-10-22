## Native runtime grammars, ordinary JsonNode ASTs, and automatic handle release.
import std/[json, os, strutils]

when not (defined(gcArc) or defined(gcOrc) or defined(gcAtomicArc)):
  {.error: "koine requires ARC/ORC, as used by default in Nim 2".}

const
  nativeDir = currentSourcePath().parentDir.replace('\\', '/') & "/koine"
  nativeHeader = "koine.h"

{.passC: "-I" & quoteShell(nativeDir).}

when defined(windows):
  when defined(vcc):
    {.passL: quoteShell(nativeDir & "/koine.lib").}
  else:
    {.error: "Koine on Windows requires the MSVC backend: compile with --cc:vcc".}
elif defined(macosx):
  {.passL: quoteShell(nativeDir & "/libkoine.dylib").}
  {.passL: "-Wl,-rpath,@loader_path -Wl,-rpath," & quoteShell(nativeDir).}
else:
  {.passL: quoteShell(nativeDir & "/libkoine.so").}
  {.passL: "-Wl,-rpath,'$ORIGIN' -Wl,-rpath," & quoteShell(nativeDir).}

type
  NativeParser {.importc: "koine_parser", header: nativeHeader, incompleteStruct.} = object
  NativeTranspiler {.importc: "koine_transpiler", header: nativeHeader, incompleteStruct.} = object
  Buffer {.importc: "koine_buffer", header: nativeHeader, bycopy.} = object
    data: cstring
    size: csize_t
  ParserMode {.importc: "koine_parser_mode", header: nativeHeader, size: sizeof(cint).} = enum
    KOINE_PARSER_FULL = 0, KOINE_PARSER_PLACEHOLDER = 1

const
  full = KOINE_PARSER_FULL
  placeholder = KOINE_PARSER_PLACEHOLDER

{.push importc, cdecl, header: nativeHeader.}
proc koine_parser_prepare(grammar: cstring; size: csize_t; base: cstring;
    baseSize: csize_t; mode: ParserMode; output: var ptr NativeParser; error: var Buffer): cint
proc koine_parser_prepare_file(path: cstring; size: csize_t; mode: ParserMode;
    output: var ptr NativeParser; error: var Buffer): cint
proc koine_parser_parse(parser: ptr NativeParser; source: cstring; size: csize_t;
    start: cstring; startSize: csize_t; output, error: var Buffer): cint
proc koine_parser_parse_transpile(parser: ptr NativeParser; transpiler: ptr NativeTranspiler;
    source: cstring; size: csize_t; start: cstring; startSize: csize_t;
    output, error: var Buffer): cint
proc koine_parser_destroy(parser: ptr NativeParser)
proc koine_transpiler_create(grammar: cstring; size: csize_t;
    output: var ptr NativeTranspiler; error: var Buffer): cint
proc koine_transpiler_from_file(path: cstring; size: csize_t;
    output: var ptr NativeTranspiler; error: var Buffer): cint
proc koine_transpiler_transpile(transpiler: ptr NativeTranspiler; ast: cstring;
    size: csize_t; output, error: var Buffer): cint
proc koine_transpiler_state(transpiler: ptr NativeTranspiler; output, error: var Buffer): cint
proc koine_transpiler_destroy(transpiler: ptr NativeTranspiler)
proc koine_buffer_free(buffer: var Buffer)
{.pop.}

type
  ParserObj = object
    handle: ptr NativeParser
  TranspilerObj = object
    handle: ptr NativeTranspiler
  Parser* = ref ParserObj
  Transpiler* = ref TranspilerObj

proc `=destroy`(value: ParserObj) =
  koine_parser_destroy(value.handle)

proc `=destroy`(value: TranspilerObj) =
  koine_transpiler_destroy(value.handle)

proc `=copy`(dest: var ParserObj; source: ParserObj) {.error: "Parser objects are reference-owned".}
proc `=copy`(dest: var TranspilerObj; source: TranspilerObj) {.error: "Transpiler objects are reference-owned".}

proc take(buffer: var Buffer): string =
  try:
    result = newString(int(buffer.size))
    if result.len > 0:
      copyMem(addr result[0], buffer.data, result.len)
  finally:
    koine_buffer_free(buffer)

proc check(status: cint; error: var Buffer) =
  let message = take(error)
  if status != 0:
    raise newException(ValueError, message)

proc prepare(grammar: JsonNode; basePath: string; mode: ParserMode): Parser =
  let data = $grammar
  var error: Buffer
  var handle: ptr NativeParser
  check(koine_parser_prepare(data.cstring, csize_t(data.len),
    (if basePath.len == 0: nil else: basePath.cstring), csize_t(basePath.len),
    mode, handle, error), error)
  Parser(handle: handle)

proc newParser*(grammar: JsonNode; basePath = ""): Parser =
  ## Prepare a grammar once. Relative dependencies use basePath (default: cwd).
  prepare(grammar, basePath, full)

proc newPlaceholderParser*(grammar: JsonNode): Parser =
  ## Use local subgrammar placeholders without opening dependency files.
  prepare(grammar, "", placeholder)

proc prepareFile(path: string; mode: ParserMode): Parser =
  var error: Buffer
  var handle: ptr NativeParser
  check(koine_parser_prepare_file(path.cstring, csize_t(path.len), mode,
    handle, error), error)
  Parser(handle: handle)

proc parserFromFile*(path: string): Parser =
  ## Load JSON/YAML and resolve dependencies relative to each declaring file.
  prepareFile(path, full)

proc placeholderParserFromFile*(path: string): Parser =
  prepareFile(path, placeholder)

proc parse*(parser: Parser; source: string; startRule = ""): JsonNode =
  ## Syntax/lexical errors are {status: error, message: ...}; API errors raise.
  if parser.isNil:
    raise newException(ValueError, "Parser must not be nil")
  var output, error: Buffer
  let status = koine_parser_parse(parser.handle, source.cstring, csize_t(source.len),
    (if startRule.len == 0: nil else: startRule.cstring), csize_t(startRule.len), output, error)
  if status != 0:
    koine_buffer_free(output)
  check(status, error)
  parseJson(take(output))

proc parseTranspile*(parser: Parser; transpiler: Transpiler; source: string;
    startRule = ""): JsonNode =
  ## One native parse+transpile call; avoids serializing the intermediate AST.
  if parser.isNil or transpiler.isNil:
    raise newException(ValueError, "Parser and Transpiler must not be nil")
  var output, error: Buffer
  let status = koine_parser_parse_transpile(parser.handle, transpiler.handle,
    source.cstring, csize_t(source.len),
    (if startRule.len == 0: nil else: startRule.cstring), csize_t(startRule.len), output, error)
  if status != 0:
    koine_buffer_free(output)
  check(status, error)
  parseJson(take(output))

proc validate*(parser: Parser; source: string): tuple[valid: bool, message: string] =
  let parsed = parser.parse(source)
  if parsed["status"].getStr == "success": (true, "success")
  else: (false, parsed["message"].getStr)

proc newTranspiler*(grammar: JsonNode = nil): Transpiler =
  ## Prepare output rules; nil uses value/text fallback behavior.
  let data = if grammar.isNil: "{}" else: $grammar
  var error: Buffer
  var handle: ptr NativeTranspiler
  check(koine_transpiler_create(data.cstring, csize_t(data.len), handle, error), error)
  Transpiler(handle: handle)

proc transpilerFromFile*(path: string): Transpiler =
  ## Load YAML/JSON output rules without a host YAML dependency.
  var error: Buffer
  var handle: ptr NativeTranspiler
  check(koine_transpiler_from_file(path.cstring, csize_t(path.len), handle, error), error)
  Transpiler(handle: handle)

proc transpile*(transpiler: Transpiler; ast: JsonNode): string =
  if transpiler.isNil:
    raise newException(ValueError, "Transpiler must not be nil")
  let data = $ast
  var output, error: Buffer
  let status = koine_transpiler_transpile(transpiler.handle, data.cstring,
    csize_t(data.len), output, error)
  if status != 0:
    koine_buffer_free(output)
  check(status, error)
  take(output)

proc state*(transpiler: Transpiler): JsonNode =
  ## A detached snapshot, independent of subsequent calls and handle lifetime.
  if transpiler.isNil:
    raise newException(ValueError, "Transpiler must not be nil")
  var output, error: Buffer
  let status = koine_transpiler_state(transpiler.handle, output, error)
  if status != 0:
    koine_buffer_free(output)
  check(status, error)
  parseJson(take(output))
