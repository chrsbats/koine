# Native Koine: runtime parser and transpiler

The C++ library builds and runs on the tested Linux x86-64 environment. It uses
actual runtime cpp-peglib definitions, PCRE2 regex terminals, native YAML/JSON
loading, a C interface, and Python `ctypes` / Nim `importc` packages named `koine`.

**Status: parser, lexer, transpiler and shared SLIP grammar checks pass on Linux x86-64.**
The loader uses rapidyaml 0.16.0 with explicit YAML 1.2 core scalar resolution.
The Python package exposes `Parser`, `PlaceholderParser` and `Transpiler`.
Nim exposes the same capabilities as ordinary procedures over `JsonNode`.

## Build and check

Requirements: C/C++17 compiler (GCC 15 recommended, GCC 12+ required for GCC builds),
CMake 3.22+, and Python for tests. Conformance checks also
need `pytest`, `pytest-subtests`, `parsimonious`, `regex`, `safer-yaml` and `pyyaml`
from the development environment.

From the repository root:

```bash
CC=gcc-15 CXX=g++-15 cmake -S native -B native/build -DCMAKE_BUILD_TYPE=Debug
cmake --build native/build --target koine_c_test koine_lexer_c_test koine_transpiler_c_test koine_document_test -j 4
ctest --test-dir native/build --output-on-failure
```

Set CMake's `Python3_EXECUTABLE` to an existing development interpreter if needed.
Dependencies are fetched into the build tree at configure time. cpp-peglib is
pinned to v1.22.0's commit, rapidyaml to the 0.16.0 source release and SHA256,
and nlohmann/json to v3.11.3. rapidyaml and PCRE2 10.39 are linked privately and
statically into `libkoine`; no system PCRE2 development package is needed.

Use a fresh build directory when changing compilers. GCC versions before 12 are
rejected because [GCC bug 66139](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=66139)
leaks temporaries when AST conversion throws. GCC 15.2 passes the native suites
and C ASan/UBSan/leak checks, including numeric overflow and recovery. Both Nim
backends also pass eight API cases under ASan/UBSan with leak detection. Wrapper
references are constructed only after native construction succeeds, avoiding
Nim 2.2.12's C++ failed-result cleanup defect through the approved construction
order. No special exception mode or runtime patch is needed.

The library and Python package are staged together in `native/build/python/koine`.
The test scripts import that package using `PYTHONPATH`. The shipping pure-Python
implementation under `python/koine` also supplies the behavioral reference; its
off-root location prevents it from shadowing an installed native package:

```bash
PYTHONPATH=native/build/python python3 native/tests/test_native.py
```

An ordinary consumer uses:

```python
from koine import Parser

parser = Parser({
    "start_rule": "word",
    "rules": {"word": {"regex": "[a-z]+", "ast": {"leaf": True}}},
})
assert parser.validate("hello") == (True, "success")
ast = parser.parse("hello")["ast"]
```

`Parser.from_file(path)` accepts YAML 1.2 / JSON and resolves subgrammars relative
to each declaring file. Input beginning with `{` or `[` is parsed as strict JSON
(duplicate keys rejected) before falling back to YAML flow syntax. For in-memory
grammars, use `Parser(grammar, base_path=directory)` when relative dependency
paths need a specific directory.
`PlaceholderParser.from_file(path)` and `PlaceholderParser(grammar)` replace
subgrammars with their local placeholders without opening dependency files.

`parse(text, start_rule=...)` selects another rule. Construction prepares the
grammar once; `validate(text)` returns `(True, "success")` or `(False, message)`.
When the caller only needs generated text, `parse_transpile(text, transpiler,
start_rule=...)` performs both steps behind one native call and avoids returning
and re-encoding the AST. It returns the same success/error dictionaries as
`parse`. Native objects and result buffers are released automatically by the
wrapper. C consumers use [include/koine.h](include/koine.h), initialize outputs
to zero, and call the declared release functions. `koine_parser_prepare` and
`koine_parser_prepare_file` expose base-path and placeholder construction;
`koine_parser_parse_transpile` is the combined C entry point.

Parsing validates UTF-8 once per input, indexes source lines and code-point
columns once, and reuses match state, so cost scales linearly with work rather
than with input size per attempt.

## Python and Nim packages

From the checkout, the root project builds the pure-Python package; build this
native subproject explicitly:

```bash
CC=gcc-15 CXX=g++-15 python3 -m pip install ./native
```

Published `pip install koine` prefers a native platform wheel and falls back to the
pure package elsewhere. `pip install --no-binary=koine koine` forces the pure
package from source. The native package uses ordinary dictionaries/lists/scalars
and has no runtime dependency on Parsimonious, `regex` or a Python YAML library.
Wheels bundle the shared core and dependency notices. Source builds fetch the
pinned native dependencies; loading new grammars after installation never invokes
a compiler.

Build release artifacts from the repository with `tools/build.py` (pure
sdist/universal wheel at the root, portable native wheel from `native/`). Pass a
Windows wheel built on Windows with `--windows-wheel`. The native wheel is repaired
with auditwheel and receives the `manylinux_2_27`/`manylinux_2_28` tags. Validate
and publish saved artifacts with `tools/publish.py`; see the root README for the
release commands.

For Nim 2 with ARC/ORC, install once from the repository root:

```bash
CC=gcc-15 CXX=g++-15 nimble install
```

Nimble builds the shared core and C header during installation. Programs then use
`import koine`, without library-search or linker flags:

```nim
import std/json
import koine

let parser = newParser(%* {"start_rule": "word", "rules": {
  "word": {"regex": "[a-z]+", "ast": {"leaf": true}}
}})
doAssert parser.validate("hello") == (true, "success")
let ast = parser.parse("hello")["ast"]
doAssert newTranspiler().transpile(ast) == "hello"
```

Both `nim c app.nim` and `nim cpp app.nim` work with an installed package. If GCC
15 is installed alongside an older default compiler, select it explicitly:

```bash
nim c --gcc.exe:gcc-15 --gcc.linkerexe:gcc-15 app.nim
nim cpp --gcc.cpp.exe:g++-15 --gcc.cpp.linkerexe:g++-15 app.nim
```

The public procedures are:

| Capability | Nim API |
| --- | --- |
| In-memory grammar | `newParser(grammar, basePath = "")` |
| YAML/JSON grammar file | `parserFromFile(path)` |
| Isolated placeholders | `newPlaceholderParser(grammar)`, `placeholderParserFromFile(path)` |
| Parse / validate | `parser.parse(source, startRule = "")`, `parser.validate(source)` |
| Parse and generate text | `parser.parseTranspile(transpiler, source, startRule = "")` |
| Output rules | `newTranspiler(grammar = nil)`, `transpilerFromFile(path)` |
| Generate text / inspect state | `transpiler.transpile(ast)`, `transpiler.state` |

Parser/transpiler references share automatic native ownership. Returned ASTs and
state are independent `JsonNode` values; state inspection returns a snapshot.
Syntax errors return a JSON error result, while invalid construction/API calls
raise `ValueError`. Standard `std/json` preserves uint64 values above int64 as raw
JSON numbers: use `ast["value"].to(uint64)` to retrieve them and `$ast` to serialize
them without quotes or precision loss.

On Linux, deploy `libkoine.so` beside the executable (with its bundled dependency
notices). The binding provides `$ORIGIN` and installed-package rpaths. On Windows,
deploy `koine.dll` beside the executable. The MSVC DLL statically links the C++
and C runtimes, so it needs no Visual C++ redistributable. Windows Nim consumers
must use the MSVC backend (`--cc:vcc`); the binding then links `koine.lib`. MinGW
on Windows is not supported. Linux x86-64 with GCC 15.2 and Windows x86-64 with
MSVC 2022/Nim 2.2.12 are tested; other architectures are not.

### Portable Linux wheels

The verified x86-64 wheel has `py3-none-manylinux_2_27_x86_64` and
`py3-none-manylinux_2_28_x86_64` tags. It installs normally on Ubuntu 22.04; clean
Python 3.9, 3.12 and 3.13 environments pass the dependency-free API checks.
Python 3.9 also passes those checks with the older glibc 2.28 loader and C/C++
runtimes.

Release wheels use GCC 15 against an older glibc 2.28 sysroot, with the released
AlmaLinux 8 GCC 15 toolset. This was built directly, without containers or system
RPM installation. The toolset supplies its standard C++ runtime compatibility
support; no dependency or runtime source was patched. Ordinary source installs
use the host toolchain shown above and do not need this release SDK.

Use standard CMake compiler/sysroot settings in a release toolchain file, then
build from a saved source distribution and check the resulting binary with
auditwheel. For an already prepared SDK, a toolchain file looks like:

```cmake
set(CMAKE_SYSTEM_NAME Linux)
set(CMAKE_SYSROOT "/path/to/sysroot")
set(toolset "${CMAKE_SYSROOT}/opt/rh/gcc-toolset-15/root/usr")
set(CMAKE_C_COMPILER "${toolset}/bin/gcc")
set(CMAKE_CXX_COMPILER "${toolset}/bin/g++")
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)
```

The repository ships a provisioning script and toolchain file, so no system RPMs
or containers are needed:

```bash
uv run --with libarchive-c python native/tools/prepare_linux_sdk.py build/sdk-alma8-gcc15
export KOINE_SDK_ROOT=$PWD/build/sdk-alma8-gcc15
export CMAKE_TOOLCHAIN_FILE=$PWD/native/tools/linux-gcc15.cmake
export LD_LIBRARY_PATH=$KOINE_SDK_ROOT/compiler-runtime/usr/lib64:$KOINE_SDK_ROOT/sysroot/opt/rh/gcc-toolset-15/root/usr/lib64
uv build native/ --wheel --out-dir build/portable-dist
uvx auditwheel repair --plat manylinux_2_28_x86_64 --wheel-dir build/wheelhouse \
  build/portable-dist/koine-*-linux_x86_64.whl
```

`patchelf` must be on `PATH` for auditwheel. Do not relabel a host-built wheel to
an older manylinux tag: the compiler's linked runtime symbols determine the actual
compatibility. Koine and dependency notices are included in both the Python wheel
and Nim runtime component.

### Windows x64

Release builds use MSVC (Visual Studio 2022) on Windows. The repository uses a
Windows virtual environment at `.venvs/win`, created by Windows `uv`; from WSL the
Windows interpreter can be invoked directly as `.venvs/win/Scripts/python.exe`.

```powershell
uv venv .venvs/win
.venvs\win\Scripts\python.exe -m pip install build scikit-build-core cmake
$env:CMAKE_GENERATOR = "Visual Studio 17 2022"
.venvs\win\Scripts\python.exe -m build native --wheel --no-isolation --outdir build\wheels
```

The build uses `/Zc:__cplusplus`, `/permissive-` and a static MSVC runtime; the
resulting `koine.dll` imports only `KERNEL32.dll`. The `win_amd64` wheel contains
`koine/koine.dll`, its notices, and no Python dependencies.

For the full native suite:

```powershell
cmake -S native -B build\native -G "Visual Studio 17 2022" -A x64 `
  -DBUILD_TESTING=ON -DPython3_EXECUTABLE=.venvs\win\Scripts\python.exe
cmake --build build\native --config Release --parallel
ctest --test-dir build\native -C Release --output-on-failure
```

Nim consumers use the same Windows toolchain:

```powershell
nimble --nimbleDir:build\nimble install -y
nim c --cc:vcc --path:build\nimble\pkgs2\koine-0.11.1-* app.nim
nim cpp --cc:vcc --path:build\nimble\pkgs2\koine-0.11.1-* app.nim
```

The Nimble install builds `koine.dll` and `koine.lib` with the Visual Studio
generator and installs both beside the binding. Compiling without `--cc:vcc` on
Windows raises an explicit error; MinGW is not a supported Windows toolchain.

### Measured release performance

Milliseconds per ordinary API call, medians of three samples on Linux x86-64:

| Case | Python reference | Native Python wheel | Native Nim package |
| --- | ---: | ---: | ---: |
| Math parse + transpile | 0.096 | 0.111 | 0.078 |
| Tokenized Python parse + transpile | 0.295 | 0.227 | 0.179 |
| Complete SLIP `root.slip` parse | 268.820 | 75.205 | 80.308 |

Combined `parse_transpile` / `parseTranspile`, milliseconds per call:

| Case | Native Python wheel | Native Nim package |
| --- | ---: | ---: |
| Math parse + transpile | 0.072 | 0.054 |
| Tokenized Python parse + transpile | 0.143 | 0.139 |

Inputs and raw outputs are equal across all paths. Timings include C JSON
emission and host conversion; grammar preparation is excluded. Samples use 200,
100 and 3 calls respectively. Python uses the installed portable wheel; Nim uses
the source-installed Release core. Both are GCC 15 builds. Results are workload-
and environment-dependent, with no general speedup guarantee. The benchmark also
reports standalone host JSON decoding (about 2.08 ms Python / 2.85 ms Nim for the
complete root result); this is not an attribution of all serialization overhead.

## Supported parser behavior

- Literal and regex matching, rule references, sequence, ordered choice,
  optional/repeated terms, lookahead, and non-left-recursive grammar construction.
- `leaf`, `tag`, `discard`, `promote`, typed leaves, named children, custom
  structures, associative operators, and Unicode-code-point source locations.
- Inline AST normalization, subgrammar discovery/namespaces/cycles, qualified
  sibling and parent references, reachability/empty-AST checks, directive
  conflicts, and left-recursion checks (including zero-width regex terminals).
- PCRE2 matching at a byte offset in the **complete subject**, preserving
  lookbehind/anchors. The adapter translates Python's absolute-end `\Z` to
  PCRE2's `\z`; escaped literal `\\Z` remains literal.
  Unicode character classes are not identical to Python's `regex`: for example,
  `\w+` accepts decomposed `e` + U+0301 in the pure scannerless parser but not in
  PCRE2 10.39. Use an explicit class such as `[\p{L}\p{M}\p{N}_]+` when those
  combining marks are part of an identifier.
- Independent per-call results, serialized access to one parser from threads,
  C error reporting, and buffers that outlive source and parser storage.
- Optional token-based parsing using the existing `lexer` and `token` grammar
  keys, longest-match/first-specification tie selection, skip actions, and token
  discard/type directives. Native `handle_indent` supports INDENT/DEDENT,
  blank-line handling, dedent validation and EOF dedents.

Both `Parser` and `PlaceholderParser` accept lexer grammars through their normal
constructors and `from_file()`. The implementation normalizes CRLF/CR to LF and
expands tabs at eight-code-point tab stops, matching the reference. Lexical,
indentation and token syntax failures return ordinary parse errors with source
locations. Zero-progress token matches produce explicit errors.

Raw token-mode ASTs retain the reference representation: branch `text` contains
token names; token leaves contain normalized source values and source positions.
Parent positions use the first direct AST child with a location, or default to
1:1. Leaf wrappers concatenate child text. Unicode decimal digits are converted
without changing token text or the exact int64/uint64 numeric policy.

AST shaping runs after successful matching, so rejected backtracking branches
cannot trigger numeric conversions. Alias/single-choice boundaries, promoted
lists and cleanup follow the reference behavior. Extra AST metadata is ignored
as in the reference, including malformed keys already present in shared fixtures.

Native `type: number` preserves exact int64/uint64 integer tokens and uses float64
for fractional/exponent forms. Representable whole-number float values normalize
to integers; overflow is explicit. Token `text` is preserved. This intentionally
differs from the Python reference's float-first rounding for large integers:
`9007199254740993` remains exact in native output.

Native parsing, tokenization and transpilation do not
call the Python implementations. The conformance runner loads no reference
implementation. It supplies a failing import-only stub for a backend-specific
grammar-string helper; any accidental call fails the native run.

## Transpilation

```python
from koine import Transpiler

transpiler = Transpiler({
    "rules": {"greeting": {"template": "Hello, {name}!"}},
})
assert transpiler.transpile({
    "tag": "greeting", "children": {"name": {"text": "world"}},
}) == "Hello, world!"
```

`Transpiler.from_file(path)` loads YAML/JSON output rules natively, without a host
YAML dependency. `Transpiler()` uses the documented value/text fallbacks. Output
rules are prepared once; `transpile(ast)` returns ordinary text. Named and list children, binary-op
fields, `cases`, path conditions, `state_set`, indentation and global indentation
configuration follow [TRANSPILING.md](../TRANSPILING.md). Boolean/null values use
the reference's `True` / `False` / `None` spelling when converted to text.

Each top-level call resets state and indentation. Updates occur after a node's
output and are visible to subsequent siblings and parents. `transpiler.state`
returns a detached snapshot of the most recent call's state. Exceptions cannot
carry indentation or state into the next call. Calls on a handle are serialized.

Approved native template scope is named substitutions (`{name}`) and escaped
braces (`{{` / `}}`). Broader Python `str.format` specifications, conversions and
field-access expressions raise explicit native errors. Substituted child text
is inserted literally rather than interpreted as another template.

C callers use `koine_transpiler_create`, `koine_transpiler_from_file`, `koine_transpiler_transpile`,
`koine_transpiler_state` and `koine_transpiler_destroy`. Creation accepts runtime
YAML/JSON grammar data; transpilation borrows a length-delimited JSON AST and
returns owned UTF-8 text. State snapshots are owned JSON buffers. Release both
through `koine_buffer_free`; outputs survive input and handle destruction.

The runtime math example uses the existing calculator parser grammar and
[math_to_slip.yaml](tests/math_to_slip.yaml). For example:

```text
10 + 5 * 2  -> (10 + (5 * 2))  -> 20
2 ^ 3 ^ 2   -> (2 ** (3 ** 2)) -> 512
```

With the sibling SLIP project environment, run from its checkout with an absolute
native staging path and absolute test-script path:

```bash
PYTHONPATH=/path/to/koine/native/build/python uv run --no-sync python3 /path/to/koine/native/tests/check_math_slip.py
```

This saves/reloads generated programs and evaluates them using the existing SLIP
runtime. Ordinary SLIP evaluation remains left-to-right.

## YAML loading and verification

rapidyaml parses syntax, escaping and scalar styles; `src/yaml.cpp` converts its
tree directly into owned `ordered_json` data. Quoted and block scalars remain
strings; plain scalars use YAML 1.2 core types. Duplicate keys and values outside
the JSON-compatible model are rejected. Exceptions cross the C boundary as errors.
There is no intermediate YAML-to-JSON text emission step.

The former libfyaml beta generic adapter was removed after independent checks
exposed invalid NUL escaping in its optimized emitter and quoted-string type loss
in its event emitter. The replacement uses supported rapidyaml APIs without
dependency patches.

All eleven CTest suites pass. **99 public behavioral cases and 2 subtests run
through native entry points**, including every lexer-dependent case and both
complete Python↔JavaScript parse/transpile tests. Four Parsimonious grammar-string
tests remain separate Python-backend tests and pass in that backend. These are
not counted as native behavior tests. The pure wheel passes the full 104-case
suite shared with the reference.

Additional checks include 16 parser, 9 lexer and 11 transpiler Python API cases,
C ownership/API checks, 85 document comparisons including all 13 Koine/SLIP grammar
files, and 7,437 regex comparisons. The unchanged SLIP parser, placeholder and
integration selection passes 169 checks. Another 141 raw AST/status comparisons
include complete `root.slip`, text, scalar types and
locations, with the approved numeric difference asserted separately.

Lexer checks compare raw token values/locations, normalized source, ASTs and error
positions against the reference, including Unicode, NUL, tabs, blank lines,
lookbehind/end assertions, aliases and placeholders. Python/JavaScript fixture
checks now generate ASTs natively and compare raw ASTs, unnormalized output and
state with the independent reference results. Six generated math programs pass
actual SLIP evaluation, including saved-artifact round trips,
precedence, associativity and exact large integers.

With a sibling SLIP checkout, reproduce the additional corpus checks explicitly:

```bash
PYTHONPATH=native/build/python python3 native/tests/compare_asts.py --slip-root ../slip
python3 native/tests/compare_documents.py native/build/koine_document_test tests/*.yaml ../slip/grammar/*.yaml
PYTHONPATH=native/build/python python3 native/tests/compare_regex.py ../slip/grammar/*.yaml
```

C parser/lexer/transpiler ownership and document checks also pass under ASan/UBSan
with leak detection. Nim C/C++ checks exercise native construction failures,
numeric overflow, UTF-8/NUL, shared aliases, detached results/state and repeated
cleanup under the same sanitizers.

Install development dependencies with `python3 -m pip install '.[dev]'` (select
GCC 15 through `CC`/`CXX` as above). Native behavior and reference-only grammar-string
checks are separate:

```bash
PYTHONPATH=native/build/python python3 native/tests/conformance.py
PYTHONPATH="$PWD/python" python3 -m pytest -q tests/test_edges.py -k test_transpile_grammar
```

The distribution inspection/clean-install tools are `tests/check_distribution.py`
and `tests/check_installed.py`. `tests/check_nim_asan.py` honors `CC`/`CXX`, uses an
instrumented CMake build and tests both ordinary Nim backends. End-to-end release
measurements use `tests/benchmark.py` with `tests/benchmark_nim.nim`; JSON emission
and host conversion are included, and output equality is asserted before timing.
These are bounded conformance results; broader regex dialect equivalence and
other platforms remain explicit gaps. See [PLAN.md](../PLAN.md) for saved-artifact
verification, timings and the active platform step.
