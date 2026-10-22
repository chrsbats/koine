# Koine: native implementation

## Objective

Provide one reusable C++ implementation of Koine, with a small C-compatible
interface and ordinary Python and Nim packages named `koine`. Native source will
live under `native/`; the Python implementation remains the behavioral reference.
Execution steps and verification evidence live in [PLAN.md](PLAN.md).

Koine's grammar format and JSON-compatible AST are the interoperability contract.
Programs must be able to supply grammars after the host executable has been built,
prepare them once, and reuse them to validate or parse strings. The native runtime
must operate independently of Python and must not require a compiler when a
program supplies a grammar.

One motivating consumer is SLIP's standard library: scripts can define a DSL and
translate it into ordinary SLIP source. For example, a math grammar supplies
precedence so `10 + 5 * 2` can become `10 + (5 * 2)`. SLIP retains its existing
left-to-right evaluation; the supplied grammar and output rules express grouping.

## Behavioral contracts

Use the existing contracts rather than introduce a new grammar language:

- [PARSING.md](PARSING.md): matching constructs, AST directives, file/base-path
  handling, subgrammars, placeholders, lexer behavior, and source locations.
- [TRANSPILING.md](TRANSPILING.md): templates, conditions, state, indentation,
  and output selection.
- [tests/](tests/): executable API examples and regressions.
- [Python implementation](reference/koine/parser.py): reference where the written contract
  needs clarification. Surface disagreements or discovered defects before making
  them native behavior.

Preserve the public `Parser`, `PlaceholderParser`, and `Transpiler` entry points,
including file construction, selectable parse start rules, validation, parse
results, and AST-to-text transpilation. Python imports from both `koine` and
`koine.parser` should remain usable. Nim exposes the same capabilities using
idiomatic procedures and native data.

Matching includes ordered choice, sequence, literals, regex terminals, optional
and repeated terms, lookahead, and non-left-recursive rule references. Whole-input
parsing, empty matches, failure positions, and grammar validation are observable
behavior. AST compatibility includes discarded/promoted nodes, empty and singleton
lists, named children, typed leaves, associative operators, and custom structures.
Preserve original numeric text and one-based, Unicode-code-point source locations.

Native `type: number` uses exact signed/unsigned 64-bit integers for integer
tokens and float64 for fractional/exponent forms. Whole-number float64 values
normalize to integers when representable in int64/uint64. Overflow is an explicit
error; token `text` is always preserved. This is an approved difference from the
Python reference's float-first conversion: `9007199254740993` remains exact in the
native AST instead of rounding to `9007199254740992`.

Transpiler grammars are runtime data too. Preserve recursive child processing,
conditional template selection, state updates after a node, indentation, and the
reset of state and indentation between top-level transpilation calls.

The native transpiler preserves the common `Transpiler(grammar).transpile(ast)`
path, with an empty grammar by default. It prepares caller-supplied output rules
once and returns owned UTF-8 text. Python's `state` exposes a detached snapshot of
the most recent call's state; state updates within one traversal remain visible
to following siblings and parents. Failed calls must not leak indentation or state
into the next top-level call.

Approved native template scope: named substitutions (`{name}`) and doubled braces
(`{{` / `}}`) for literal braces, as documented in TRANSPILING.md. The Python
reference's additional `str.format` format specifications, conversions and field
access expressions are outside this increment and must produce explicit native
errors. This is a compatibility limitation, not a change to the Python backend.

## JSON and YAML

Accept JSON and YAML 1.2 grammar files through the same file-loading API, including
all referenced subgrammars. Both encodings feed one JSON-compatible data model.
Input beginning with `{` or `[` is parsed as strict JSON first, rejecting duplicate
object keys; only genuine non-JSON YAML flow syntax falls back to YAML parsing.
Compact JSON must never silently load a partial grammar.
Include native YAML support early so the existing grammar fixtures can be reused
without maintaining converted copies.

[safer-yaml](https://github.com/chrsbats/safer-yaml) is the YAML 1.2 core-schema
reference. In particular, unquoted `yes`, `no`, `on`, and `off` remain strings;
`true` and `false` are booleans. The Python reference uses its `load()` API for
root, placeholder, and subgrammar file loading.

Return ordinary structured AST data that callers can serialize as JSON or YAML.
Transpilation returns the target text. Existing native serialization libraries
should provide parsing/emission; YAML support is not another Koine parser.

## Native engine and dependency boundary

Use [cpp-peglib](https://github.com/yhirose/cpp-peglib) for runtime PEG construction
and matching, with its custom-matcher hook for Koine regex terminals. Its built-in
character classes and repetition syntax do not replace a general regex engine.
Regexes must match at the current position in the complete subject, retaining
the context needed by assertions and consuming only the matched prefix.

An existing regex engine supplies those terminals. PCRE2 supplies the current
adapter. The user approved replacing the libfyaml beta generic integration with
[rapidyaml](https://github.com/biojppm/rapidyaml), subject to a bounded compatibility
check of existing grammar data, YAML 1.2 scalar types, quoting, Unicode and NUL.
Use its supported tree API with an explicit YAML 1.2 core scalar adapter into the
existing JSON data model. Dependency repair is outside Koine's scope.
Exact versions and verification evidence belong in PLAN. If the
selected PEG mechanism proves insufficient, report the blocker before substituting
a custom PEG engine or changing grammar semantics.

Keep grammar loading/composition, matching, Koine AST shaping, and text generation
as direct components with inspectable data. Neither the core nor its AST depends
on Python objects, Nim runtime types, or SLIP runtime types.

## C interface and language packages

Use native library name `libkoine` on Unix-like systems / `koine.dll` on Windows,
with C symbols prefixed `koine_`. The interface covers prepared parser/transpiler
creation, validation, parsing, transpilation, and resource release. Exact function
signatures and ownership rules are defined in [native/include/koine.h](native/include/koine.h).

- Keep native objects behind opaque handles. Use length-delimited UTF-8 source
  and JSON buffers for the initial interchange boundary.
- The core owns its prepared objects and returned buffers, with explicit release
  operations. Input buffers remain caller-owned and are borrowed for the call.
- Errors cross the C boundary explicitly; C++ exceptions stay inside the library.
- A combined parse-and-transpile operation runs one prepared parser and one prepared
  transpiler over source text without exposing or re-serializing the intermediate
  AST. It returns a small JSON result: `status` plus `text` on success, or the
  ordinary parse error object. Ordinary syntax errors remain results; construction
  and API failures use the normal error status. Python and Nim wrappers expose this
  as the common pipeline path in addition to separate `parse`/`transpile` calls.
- Returned data must remain valid independently of temporary input strings and
  backend parse-tree views.
- Python and Nim wrappers manage native lifetimes and data conversions, so users
  work with normal dictionaries/lists/scalars or `JsonNode`, not manual handles.

Python uses `ctypes`; Nim uses `importc` with either `nim c` or `nim cpp`.
Package loading/linking details belong inside the packages. The distribution goal
is ordinary installation and `import koine`, with Python wheels bundling the native
library for supported platforms. Measure JSON conversion overhead as part of
native performance verification.

## Distribution variants

Ship one distribution name, `koine`, with these artifacts per release:

- A universal `py3-none-any` wheel containing the pure-Python implementation from
  `reference/koine`. It declares `parsimonious` and `safer-yaml` dependencies.
- Platform wheels built from the `native/` subproject containing the ctypes wrapper
  and bundled `libkoine`: Linux x86-64 (`manylinux_2_27`/`manylinux_2_28`) and
  Windows x86-64 (`win_amd64`). They declare no Python runtime dependencies. The
  Windows DLL is statically linked and imports only the Windows UCRT api-set
  (Windows 10+); it is deployed beside the executable.
- A source archive whose default build is the pure package, so source installs
  work without a compiler. Native sources remain present for explicit native builds.

`pip install koine` selects a platform wheel where one is compatible and otherwise
installs the universal wheel. `pip install --no-binary=koine koine` forces the pure
package from source on any platform. Both variants expose the same public API,
including combined `parse_transpile`, `Transpiler.from_file` and `validate`.

Keep the behavioral reference under `reference/koine` in the checkout. Build native
platform wheels with scikit-build-core; the Python ABI-independent library is
bundled beside the wrapper. Statically include the tested PCRE2 10.39 and rapidyaml
code in `libkoine`, using their supported unmodified build APIs. The distribution
version must match across the root `pyproject.toml`, `native/pyproject.toml` and
`koine.nimble`.

The selected Linux development and verification toolchain is GCC 15.x, with C++17
as the language standard. Select the compiler explicitly for builds; upgrading
the Ubuntu release is outside this increment. GCC versions before 12 are excluded
because GCC bug 66139 leaks temporaries during exception unwinding. Resolve that
compiler defect through the supported toolchain rather than dependency patches
or local exception-path workarounds. Portable Linux wheels also use GCC 15, in
an older-runtime environment with its released GCC 15 toolset and standard
compiler/sysroot settings. Source builds and installed packages require no Docker
installation or daemon. The
build environment, rather than a compiler downgrade or a raised wheel baseline,
provides compatibility with older supported Linux distributions. Windows x64 compilation and installed C,
Python and Nim consumers are the requested follow-up after Linux verification.

The Nimble package is named `koine`. Installation builds/bundles the shared core
and C header once; `import koine` supplies ordinary constructors/procedures and
automatic shared-handle lifetimes under Nim 2's default ARC/ORC model. Returned
ASTs/state use standard `JsonNode` data. In particular, std/json's raw-number
representation preserves uint64 values above int64; use its normal `to(uint64)`
conversion and unquoted numeric serialization, rather than a custom AST model.
Deploy the shared library beside a Nim executable; package linking also supports
the installed Nimble location. Grammar loading at runtime needs no compiler.
Construct a Nim wrapper reference only after native construction succeeds. The
user approved this bounded construction-order avoidance of Nim 2.2.12's C++
failed-result cleanup defect; it preserves ordinary `nim c`/`nim cpp` calls and
requires no compiler-runtime patch or special exception mode. Failed construction
must pass the same unsuppressed ownership checks as successful construction.
Native `Transpiler.from_file()` / Nim `transpilerFromFile()` load output grammars
through the same native YAML/JSON loader, without requiring a host YAML library.

## Compatibility and completion

Use the existing public behavior tests against both implementations. Tests of
Parsimonious-specific generated strings remain tests of the Python backend; their
user-visible matching and AST behavior still needs native coverage. Preserve the
Python tests and expected results while establishing the native suite.

Completion requires native parser, placeholder, lexer, and transpiler conformance;
unchanged SLIP grammar integration; ordinary Python/Nim imports; ownership/error
checks through the C interface; and packaged-install verification. Compare raw
ASTs and locations as well as consumer-normalized results. Report numerical,
regex, or error-contract discrepancies explicitly rather than silently accepting
different behavior as parity. Native performance is measured, not presumed.

Matching and AST shaping must scale roughly linearly with input and node count.
Validate UTF-8 once per parse and reuse the validated subject for terminal
matching; do not re-validate the whole subject for every terminal attempt.
Compute source line/column positions from an index built once per parse, not by
rescanning from the start for every node. Preserve exact one-based Unicode
code-point columns and the existing invalid-input behavior. Separately measured
boundary/JSON costs are not engine throughput and must be reported as such.
Error results must remain valid UTF-8 JSON even when the source or an upstream
error snippet contains a multibyte character or malformed bytes; a parse error
must never surface as a serialization failure.

Preparation must load each distinct grammar file once and reuse that content when
expanding subgrammar directives; do not re-open or re-parse the same file per
reference.

## Optional tokenization and indentation

A `lexer` block selects native tokenization before PEG parsing. Use longest-match
selection, with the first declared specification winning ties, skipped tokens,
and token-level discard/type directives. Normalize CRLF/CR to LF and expand tabs
at eight-code-point tab stops, matching the reference. `handle_indent` emits
INDENT/DEDENT, ignores blank-line indentation changes, validates dedent levels and
flushes remaining dedents at EOF. Matching still uses runtime cpp-peglib and PCRE2.

Preserve the reference's raw token-mode AST: structural `text` contains matched
token names, while token leaves contain normalized source values and source
line/column positions. Parent positions follow the existing direct-child rule
(or its 1:1 default); leaf wrappers concatenate child text. Token numbers use the
approved exact native numeric policy. Lexical/indentation/syntax failures remain
ordinary parse error results with source locations. Report zero-progress lexer
matches explicitly rather than allowing an infinite tokenization loop.
