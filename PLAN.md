# Koine implementation plan

## Status and current scope

**Completed authorized increment: Windows x64 native build (MSVC).**
The user requested a Windows version, then chose the sibling recollector workflow:
a Windows virtual environment in the repo, built and tested on the Windows host
(WSL interop), not cross-compiled and not run under Wine for acceptance.

Implemented:

- `native/CMakeLists.txt` supports MSVC: `/utf-8`, `/Zc:__cplusplus` (cpp-peglib
  requires a correct `__cplusplus`), `/permissive-`, and a static MSVC runtime
  (`CMAKE_MSVC_RUNTIME_LIBRARY`). The GCC-version guard remains GCC-only.
- Multi-config output directories place `koine.dll` beside `parser.py`, and the
  C test executables get the DLL directory on `PATH`.
- `native/pyproject.toml` excludes `.lib` and `.exp` files from wheels.
- `nim/koine.nim` links `koine.lib` with MSVC, errors on non-`vcc` Windows
  builds, and uses a forward-slash include path.
- Syntax errors are guaranteed valid UTF-8 before JSON serialization. cpp-peglib
  scans the unexpected character with locale-dependent ctype, which truncated
  multibyte characters on Windows; the integration layer rebuilds the complete
  character from the source position and sanitizes malformed snippets.
- `compare_documents.py` forces UTF-8 for its subprocess pipes (Windows defaults
  to the ANSI code page). Conformance runs with `--capture=no`.
- `.venvs/win` is a Windows CPython 3.12.12 venv created by Windows `uv`; from
  WSL, `.venvs/win/Scripts/python.exe` runs directly against the Windows host.

Verification evidence (native Windows, MSVC 2022):

- `python -m build native` with the Visual Studio generator produces
  `koine-0.11.0-py3-none-win_amd64.whl`; clean `check_installed` passes with that
  injected wheel before test-only dependencies are installed.
- All **11 CTest suites pass natively on Windows**, including 85 document
  comparisons, 141 raw AST/status comparisons, regex, lexer, transpiler and the
  shared conformance suite (95 cases + 1 skipped loader test + 2 subtests).
- The 4 non-grammar edge cases pass separately on Windows.
- The wheel contains `koine/koine.dll` and no import library or Python
  dependencies. The DLL is PE/AMD64 with all 13 `koine_*` exports and imports only
  `KERNEL32.dll` (static C++/CRT runtime; no VC++ redistributable).
- Linux remains at 11/11 CTest suites in Debug and ASan/UBSan, 104 pure cases,
  95 + 2 native subtests plus the 4 edge cases, and the saved-source Nimble
  install with 8 cases per backend and `$ORIGIN` deployment.
- `koine.nimble` now passes `--config Release` to `cmake --build`/`--install`, so
  the Visual Studio generator installs the Release DLL and `koine.lib` instead of
  the default configuration. A saved-source Nimble install under MSVC 2022 then
  compiles and runs 8/8 cases with both `nim c --cc:vcc` and `nim cpp --cc:vcc`.
- Windows Nim requires the MSVC backend; compiling without `--cc:vcc` raises an
  explicit error. MinGW/llvm-mingw Windows tooling was removed as an unsupported
  second toolchain.
- `.github/workflows/ci.yml` runs a `windows-latest` MSVC job (wheel build, clean
  install, all CTest suites, edge tests, Nimble install and both `--cc:vcc`
  backends, wheel artifact), alongside the pure matrix, native Linux CTest, and
  manylinux artifact verification.

Final 0.11.0 artifacts in `dist/`:

- `koine-0.11.0.tar.gz`
  SHA256 `cf043c350555ba949e4626c54d977aa6466725411cb227af2583c94dd007a751`
- `koine-0.11.0-py3-none-any.whl`
  SHA256 `46398be74b7b3892c2d53ffd57e97330c789b19111de9cd121f9267f11f4c900`
- `koine-0.11.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`
  SHA256 `7a9059b9e6cccbf132b2fe01f8a614272a8d8d5b7f1fecd31590eeafb1ecdac5`
- `koine-0.11.0-py3-none-win_amd64.whl`
  SHA256 `c64701071526306a5760964387c922081b8f2a70d5b7f6a80786e8c17338b9b8`

The Windows venv, toolchains and all build trees live under the repository
(`.venvs/win`, `build/`); no Wine or cross-compiler is used for acceptance.

**Completed follow-up: pure-grammar load caching.**
The pure implementation re-read and re-parsed each subgrammar file for every
`subgrammar:` directive during rewrite, while step 1 had already loaded the same
content. `_rewrite_subgrammar_directives_in_place` now receives the loaded
`grammars` mapping, and step 1 tracks queued paths so duplicate directives do not
load twice. Loading the three cyclic SLIP grammars fell from 37 YAML loads to 4
(the main file is still loaded once as its own cycle target) and the new regression
test asserts one load per distinct file. The pure wheel passes 104 cases + 2
subtests; the native package skips the loader-specific test and remains 95 + 2
subtests plus 4 edge cases. Native wheels are unaffected.

**Completed authorized increment: dual pure/native distribution.**
The user approved a single `koine` distribution where `pip install koine` uses the
native package when a compatible wheel exists and the pure-Python implementation
otherwise, with `--no-binary=koine` as the explicit pure-only path. Version bumped
to 0.11.0; pure installs accept `parsimonious` and `safer-yaml`; at the end of that increment native
wheels were published for Linux x86-64 only; Windows followed in the increment
above, and macOS still uses the universal wheel.

Implemented:

- Root `pyproject.toml` is now the pure package (setuptools, `reference/koine`,
  runtime dependencies); its sdist builds pure by default, so source installs need
  no compiler and stay cross-platform.
- `native/pyproject.toml` is the scikit-build-core native subproject with no
  runtime dependencies. Release tooling moved to `native/tools/`
  (`prepare_linux_sdk.py`, `linux-gcc15.cmake`); the GCC 15/glibc 2.28 SDK is
  provisioned under `build/`, not `/tmp`.
- Added `Parser.parse_transpile` and `Transpiler.from_file` to `reference/koine`
  so both variants expose the same API.
- Added `check_versions.py` (11th CTest suite) asserting the version matches in
  all three project configs.

Verification evidence:

- Artifacts at the end of this increment (hashes below are superseded by the
  Windows rebuild recorded above; `check_distribution.py` verifies contents,
  tags and dependency metadata):
  - `koine-0.11.0.tar.gz` SHA256 `ed4d06db56e96cf17e2d4b5edfea7bc99e4c36b2f9706751c74cfa74ec18f43e`
  - `koine-0.11.0-py3-none-any.whl` SHA256 `565c8988e722b1b4c5bbfdce557c12c3e7788653d99456a7ffd7d884c1a2c466`
  - `koine-0.11.0-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`
    SHA256 `07e0828c5ffa15dcb47be8a6aeea8cdcf2cf47b33dcda6a6b88d1c768ee4d8d8`
- Wheel selection with `pip download --platform`: `manylinux_2_27`/`2_28`
  x86-64 selects the native wheel; `manylinux_2_26`, macOS arm64 and Windows
  select the universal wheel.
- `pip wheel --no-binary=koine` builds a `py3-none-any` wheel from the sdist; the
  resulting install passes the pure checks.
- Pure wheel installs and checks pass on Python 3.9.23, 3.12.11 and 3.13.7; the
  native wheel passes on the same versions, including under the glibc 2.28 loader
  with the SDK runtimes.
- Test results: 11/11 CTest suites pass in Debug and ASan/UBSan; shared suite
  passes 104 cases + 2 subtests against the pure wheel and 95 + 2 subtests plus
  the 4 native edge cases against the native wheel. Both Nim backends pass 8/8
  under ASan/UBSan and from the saved-source Nimble install with deployed copies.
- Nothing is published or committed; `build/` and `dist/` are gitignored.

**Completed authorized increment: native throughput and reduced boundary path.**
The user approved fixing the measured superlinear costs and adding a combined
parse+transpile path that avoids AST re-serialization, including in Python.

Reproduced before the change (installed portable wheel, GCC 15):

- Holding ~65 KB input constant and varying terminal attempts gave 17.1, 71.4,
  333 and 1,133 ms for 1k, 4k, 16k and 65k attempts; ~17.5 us per attempt. A single
  regex matching the whole 32 KB input takes 0.17 ms. PCRE2 was validating the
  entire subject on every `pcre2_match` call because `PCRE2_NO_UTF_CHECK` was not
  used.
- Keeping 16k AST nodes took ~150 ms versus ~7 ms when nodes were discarded, and
  time grew with node offset. `location()` rescanned from byte 0 for every node.
- `root.slip` (9,889 bytes, 2,748 AST nodes) parsed in ~216 ms; the Python
  reference took ~302 ms. Native scaling was superlinear while the reference was
  near-linear.
- Packrat parsing was already enabled, so it was not a cause.

Implemented mechanisms: UTF-8 is validated once per parse and subsequent matches
use `PCRE2_NO_UTF_CHECK`; `SourceIndex` builds line starts and code-point columns
once per parse; AST shaping moves child nodes (kept intact when the grammar uses
`structure`); PCRE2 match data is reused (parse calls are serialized);
`koine_parser_parse_transpile`, Python `Parser.parse_transpile` and Nim
`parseTranspile` run parse and transpile behind one boundary call.

Outcome:

- Per-attempt cost on the fixed ~65 KB input fell from ~17.5 us to ~0.5-0.6 us
  (~30x), and time now scales linearly with attempts instead of with subject size.
- Keeping 16k AST nodes fell from ~150 ms to ~52 ms; locations are indexed so
  retention cost no longer grows with node offset.
- `root.slip` (2,748 AST nodes) fell from ~216 ms to ~80 ms; the reference is
  ~269 ms.
- Combined vs separate calls (Python, Release host): math 0.072 vs 0.111 ms,
  tokenized Python 0.143 vs 0.227 ms. Nim combined: 0.054 and 0.139 ms.
- A loader defect exposed by the new C test was fixed: grammar input beginning
  with `{`/`[` is parsed as strict JSON first (duplicate keys rejected), so
  compact JSON no longer makes rapidyaml recover silently into a partial
  grammar; only genuine non-JSON flow YAML falls back to rapidyaml.

Verification evidence:

- All CTest suites pass with the host GCC 15.2 Debug core, the host
  ASan/UBSan build, and the GCC 15.2.1/glibc 2.28 Release build used for release;
  the packaging increment added the version-consistency suite (11 total).
- Both Nim backends pass eight API cases (including combined parse+transpile)
  under ASan/UBSan with leak detection and from the saved-source Nimble install.
- The rebuilt portable wheel passes 95 native tests + 2 subtests; together with
  the four non-grammar edge tests this is 99 behaviors + 2 subtests (the combined
  test was added in this increment). Fresh installs pass on Python 3.9.23,
  3.12.11 and 3.13.7; the Python 3.9 install also passes under the glibc 2.28
  loader with the SDK's old libstdc++/libgcc.
- Native/reference checks: 141 raw AST/status comparisons, 85 YAML document
  comparisons (including compact-JSON and duplicate-key cases), 7,437 regex
  comparisons across 13 grammar files, and 6 saved math-to-SLIP evaluations.
- `root.slip` and other grammar loading remain byte-identical to the reference.
  The SLIP test suite was intentionally not rerun because SLIP itself is being
  modified.
- Nothing is published or committed.

**Completed authorized increment: Linux Nim bindings and native distribution.**
The authorized increment provides ordinary Python/Nim packages over the C ABI,
retaining the approved runtime parser/lexer/transpiler and numeric/template
contracts. GCC 15 is used throughout; Ubuntu remains 22.04. Docker is not required
and no Docker software, daemon or system RPM packages were installed for this work.

Completion evidence:

- All ten CTest suites pass with the host GCC 15.2 Debug core and with the GCC
  15.2.1/glibc 2.28 Release core. The three C ownership suites pass host ASan/UBSan
  with leak detection, including repeated numeric-overflow errors and recovery.
- Both default Nim backends pass eight API cases under the same sanitizers.
  The user-approved constructor order avoids the isolated Nim C++ failed-result
  allocation leak. The original JSON exception leak is fixed through GCC 15;
  dependencies remain pinned and unmodified. GCC 11 rejection was checked.
- A saved source archive builds the native wheel. Auditwheel validates and tags
  it `py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64`. Archive checks verify
  native sources, reference retention, bundled notices, absent generated source
  binaries, and absent Python runtime dependency requirements.
- The repaired saved wheel installs normally in fresh Python 3.9.23 and 3.12.11
  environments. Parser/lexer/placeholder/transpiler checks pass before adding
  development dependencies. The installed Python 3.9 package also passes with
  the glibc 2.28 loader, old libstdc++ and libgcc from the SDK.
- Installed portable-wheel checks pass **98 public behaviors + 2 subtests**,
  plus **16 parser, 9 lexer and 11 transpiler API cases**. The four Parsimonious
  grammar-string tests pass separately through `reference/koine`.
  The complete Python reference suite passes **102 cases + 2 subtests** with
  **93.78% coverage**, preserving the 90% gate. Its explicit relocated-source
  command is `PYTHONPATH="$PWD/reference" python3 -m pytest -q tests --cov=reference/koine --cov-fail-under=90`.
- The portable build passes the C API callers under the actual glibc 2.28 loader.
  Its dynamic dependencies are only standard C/C++ system runtimes, with no
  private SDK rpath, Python, separate PCRE2 or rapidyaml dependency.
- Nimble installs from saved source; both installed C/C++ consumers pass eight
  cases without module/library search flags. Deployed consumers load the adjacent
  core via `$ORIGIN`, including when using the portable wheel's library. ARC is
  additionally checked through the C backend. The installed binding matches the
  final saved source archive exactly.
- The pre-optimization artifact passed **169 unchanged SLIP checks**. The SLIP
  suite was not rerun for this artifact because SLIP is being modified; the
  rebuilt wheel passes all six saved/reloaded math-to-SLIP evaluations. GCC 15
  checks also pass 141 raw AST/status comparisons, 85 YAML document comparisons
  (including compact-JSON and duplicate-key cases) and 7,437 regex comparisons
  across 13 grammar files.

The final portable-package benchmark asserts equal raw outputs and reports
medians of three samples, including C JSON emission/host conversion and excluding
preparation:

| Case | Reference ms | Native Python ms | Native Nim ms | Python decode ms | Nim decode ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Math parse + transpile (200 calls/sample) | 0.095739 | 0.110938 | 0.078087 | 0.006324 | 0.006956 |
| Tokenized Python parse + transpile (100 calls/sample) | 0.294512 | 0.226544 | 0.179420 | 0.008667 | 0.011007 |
| Complete SLIP root parse (3 calls/sample) | 268.819563 | 75.204920 | 80.308227 | 2.076777 | 2.848546 |

Combined parse+transpile (one boundary call, same samples):

| Case | Native Python ms | Native Nim ms |
| --- | ---: | ---: |
| Math parse + transpile | 0.071973 | 0.053676 |
| Tokenized Python parse + transpile | 0.143056 | 0.138940 |

Python uses the installed portable wheel and Nim the source-installed Release
core, both compiled by GCC 15. Decode columns are standalone measurements, not an
attribution of total conversion overhead. Results are mixed; no general speedup
claim is made beyond the measured combined-call reduction.

Final saved artifacts:

- Source: `/tmp/opencode/koine-final-dist/koine-0.10.3.tar.gz`;
  SHA256 `f72aacb203a3d4fb4b37bd30708353701acdc4f32815e3f2959012f9cef838d1`.
- Wheel: `/tmp/opencode/koine-final-wheelhouse/koine-0.10.3-py3-none-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`;
  SHA256 `44ecd2dd264f46429c5c35678e0d296f13d5f8be34305f1d618757bfc05207cd`.

The final wheel installs in fresh Python 3.9.23, 3.12.11 and 3.13.7 environments;
all three dependency-free checks pass, and the Python 3.9 package also passes
under the glibc 2.28 loader with the SDK's old libstdc++/libgcc. Archive inspection
verifies all six project/dependency notices. The final source archive also installs
through Nimble into
`/tmp/opencode/koine-final-nimble/pkgs2/koine-0.10.3-ea7e9acc9d2c2d3fb69c75d70960cc1fc8660eb9`;
both installed backends and deployed copies pass eight cases each, and the binding
and project license match saved source. The source/wheel are implementation
snapshots; this completion evidence was recorded after their verification.

The SDK/toolchain and scratch provisioning script remain under
`/tmp/opencode/koine-alma8-gcc15`, `/tmp/opencode/koine-linux-gcc15.cmake` and
`/tmp/opencode/koine_prepare_linux_sdk.py`. These are release-verification tooling,
not Koine installation dependencies. Native dependency sources were reused from
the verified FetchContent cache. No Docker installation or daemon is needed.
Documentation, examples and installed-package instructions are updated;
`git diff --check` passes. Nothing is published or committed.

**Subsequent completed increment: Windows x64 native build.** The cross-compiled
DLL, wheel and Nim import library are described in the Windows section above.
Physical Windows hardware and macOS remain unverified.

## Historical distribution bring-up checkpoints

The
user selected GCC 15.x as the current toolchain and installed Ubuntu's GCC/G++
15.2.0 packages alongside GCC 11. Ubuntu remains 22.04.
Use fresh CMake directories with `CC=gcc-15 CXX=g++-15`, select the same compilers
for both Nim backends, and retain the pinned, unmodified native dependencies.

Acceptance for this checkpoint: the standalone JSON throwing-initializer
reproducer and a permanent C numeric-overflow/recovery regression must pass
ASan/UBSan with leak detection. Then run the existing native behavior suites and
both Nim backends under sanitizers, rebuild/inspect/install saved artifacts, check
runtime compatibility, rerun equal-output release benchmarks, and finish docs.

The GCC 15 sdist and wheel now build successfully from saved source, archive
inspection passes, and the raw Linux wheel passes a fresh dependency-free Python
install. Auditwheel identifies `manylinux_2_39_x86_64` because of newer C++ runtime
symbols, instead of the earlier GCC 11 artifact's `manylinux_2_34` tag. That
portable tag cannot be installed ordinarily on this Ubuntu 22.04/glibc 2.35 host.
The raw Linux install is local-package evidence, not verification of a repaired
portable wheel on its declared baseline.

Confirmed direction: retain GCC 15 for development and release builds. The
manylinux image's bundled GCC 14 is a default, not a compiler restriction. A
released GCC 15 toolset is available for the AlmaLinux 8 base (the official
`gcc-toolset-15-gcc-c++-15.2.1-7.1.el8_10.x86_64.rpm` URL was verified). Build with
that toolset against the older runtime, audit/repair the wheel and test the saved
artifact through ordinary installation on the host. No compiler downgrade or
wheel-baseline increase was agreed. The user rejected a Docker requirement; no
Docker software was installed and no daemon was started. Use the GCC toolset's
normal sysroot mechanism directly: eleven released AlmaLinux RPMs were unpacked
under `/tmp/opencode/koine-alma8-gcc15` without system installation, using the host
libarchive library. The compiler reports GCC 15.2.1; the target C runtime is glibc
2.28. CMake uses `/tmp/opencode/koine-linux-gcc15.cmake` and the same cached native
dependency sources. Verify resulting runtime symbols, audit/repair the wheel,
and install the saved artifact normally.

Installed Nim verification now passes from the saved GCC 15 source archive:
`/tmp/opencode/koine-gcc15-nimble/pkgs2/koine-0.10.3-50b91317f158bfd2f8cd8ae081d1a7656cbed485`.
Both C/C++ consumers pass seven cases without module/library search flags, and
deployed copies pass with the adjacent core loaded through `$ORIGIN`. The C
backend also passes under ARC in addition to default ORC.

Host Release benchmark (GCC 15.2, installed native wheel/Nim package, ordinary API
calls including JSON emission/conversion, median of three samples; equal raw
outputs asserted):

| Case | Python reference ms | Native Python ms | Native Nim ms | Python JSON decode ms | Nim JSON decode ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| Math parse + transpile (200 calls/sample) | 0.099426 | 0.110262 | 0.093635 | 0.006653 | 0.007294 |
| Tokenized Python parse + transpile (100 calls/sample) | 0.386237 | 0.320445 | 0.206570 | 0.013103 | 0.010796 |
| Complete SLIP root parse (3 calls/sample) | 333.830972 | 246.899797 | 265.223572 | 2.816735 | 4.808834 |

Preparation is excluded. Decode columns are standalone host JSON measurements,
not a subtraction-based attribution of the complete call. Performance is mixed;
there is no general speedup claim. These timings are for the host-runtime build,
not the pending portable build.

GCC 15.2.0 results: the standalone nlohmann/json 3.11.3 reproducer passes
ASan/UBSan/LSan unchanged. All ten native CTest suites pass; the three C API
sanitizer suites (including the new repeated overflow/recovery regression) pass,
and all 82 document comparisons over the 13 Koine/SLIP grammar files pass with
the instrumented document reader. Nim's C backend passes seven API cases under
ASan/UBSan/LSan. The historical GCC leak is resolved through the compiler upgrade.

Nim's C++ backend passes all seven API assertions but leaks three 24-byte Nim
reference objects on failed construction (72 bytes total). A standalone Nim
2.2.12 program with no Koine imports reproduces a 24-byte leak using only
`new(result)` followed by `raise newException(ValueError, ...)` in a ref-returning
procedure, compiled with `nim cpp`, default ORC and GCC 15. This is a separate
Nim C++ exception-cleanup defect, not the historical native JSON allocation leak.
The reproducer is `/tmp/opencode/koine_nim_result_exception.nim`.

The user explicitly approved the bounded local avoidance: construct the Nim
wrapper reference only after the native constructor succeeds, so failure cannot
leave a partially initialized reference in `result`. This is a scoped exception
to avoiding local upstream-defect workarounds. It preserves the public API and
native ownership contract and needs no Nim runtime/dependency patch or special
exception mode. Both default backends must still pass the existing unsuppressed
sanitizer gate before ownership sign-off. That gate now passes: both default
backends run all seven API cases under GCC 15 ASan/UBSan with leak detection,
including all four native construction failure paths. The C++ result-allocation
leaks are avoided by the approved construction order, with no sanitizer
suppression, special exception mode or runtime patch.

Fresh build trees: `/tmp/opencode/koine-native-gcc15`,
`/tmp/opencode/koine-native-gcc15-asan`, and
`/tmp/opencode/koine-native-gcc15-release`. The Release build succeeds (using the
same cached, unmodified dependency sources after an archive download stalled).
Its dynamic requirements include `GLIBCXX_3.4.32` and `CXXABI_1.3.15`; final wheel
runtime/tag inspection remains pending. Existing saved wheels/source archives
below predate this compiler checkpoint and are not final GCC 15 artifacts.

**Historical ownership blocker:** the expanded Nim ASan/LSan run passes its seven API
assertions but detects a 152-byte native leak on numeric overflow. A standalone
C caller reproduces it, and a minimal C++ program using only nlohmann/json 3.11.3
and GCC 11.4 reproduces the same leak when an initializer expression throws:
`return {{"status", "success"}, {"ast", fail()}};`. A bounded follow-up identifies
the known [GCC bug 66139](https://gcc.gnu.org/bugzilla/show_bug.cgi?id=66139), linked
by the JSON maintainer discussion in
[nlohmann/json issue 3215](https://github.com/nlohmann/json/issues/3215).
Upstream reports the compiler fix in GCC 12.
The same standalone reproducer still leaks 152 bytes with the latest released
nlohmann/json 3.12.0 and GCC 11.4. Its downloaded header matches the upstream
SHA256 `aaf127c04cb31c406e5b04a63f1ae89369fccde6d8fa7cdda1ed4f32dfc5de63`;
Koine's pinned dependency remains unchanged. GCC 12.3 was the readily available
Ubuntu-repository upgrade; the user subsequently selected GCC 15 instead.

No dependency patch, local workaround or sanitizer suppression has been applied.
The agreed route is to verify GCC 15 and require GCC 12+ for GCC source builds,
recommending the tested GCC 15 toolchain. Installed wheel users do not need a
compiler. The GCC and both Nim backend ownership checks now pass as recorded above.

Progress evidence: the native Python sdist and wheel build with scikit-build-core;
auditwheel validates/re-tags the wheel as `py3-none-manylinux_2_34_x86_64`.
Archive checks confirm no generated binaries in source and no reference backend
in the wheel. A fresh environment installs only koine and passes a dependency-free
parser/lexer/placeholder/transpiler smoke check. Installed-wheel behavior checks
pass 98 cases + 2 subtests, plus 16 parser and 11 transpiler API cases. Nimble
installs from the checkout and the saved source archive; both `nim c` and `nim cpp`
consumers resolve the installed package without link/search flags and pass seven
cases each. Deployed copies pass the same cases with the adjacent library loaded
through `$ORIGIN`. The three pre-existing C sanitizer suites still pass; the new
numeric-overflow coverage exposes the additional leak above. Therefore those
earlier sanitizer checks are bounded evidence, not error-path ownership sign-off.

Current artifacts: `/tmp/opencode/koine-native-dist/koine-0.10.3.tar.gz` and
`/tmp/opencode/koine-wheelhouse/koine-0.10.3-py3-none-manylinux_2_34_x86_64.whl`.
They have not passed the expanded ownership gate and have not been published.
Temporary independent reproducers: `/tmp/opencode/koine-error-path.c` and
`/tmp/opencode/koine-json-exception.cpp`.

Execution and acceptance:

1. Make the root Python build native using scikit-build-core. Retain source parity
   code under `reference/koine`, avoiding accidental reference imports from the
   checkout. Bundle `libkoine` and dependency notices; build PCRE2 10.39 statically
   with its supported CMake API, preserving the already-tested version. Add
   component installs and disable native tests during consumer package builds.
2. Add the root `koine.nimble` package and a small `nim/koine.nim` binding using
   `importc`, ordinary `JsonNode` values, reference-owned prepared objects and
   automatic release. Nimble builds the core/header once at install time; both
   `nim c` and `nim cpp` consumers use `import koine` without linker flags.
   Standard std/json preserves large uint64 as raw numbers; exercise its uint64
   conversion and serialization explicitly. No custom numeric/AST schema.
3. Build wheel and sdist, rebuild from the saved sdist, inspect/re-tag the Linux
   wheel using standard packaging tools, then install in a fresh environment.
   Run installed parser/lexer/placeholder/transpiler APIs and existing behavior
   checks with package location verified. Install the Nimble package into a
   disposable directory; compile/run independent C/C++-backend consumers, using
   existing grammar files supplied after compilation. Verify Unicode/NUL,
   errors, exact int64/uint64, aliases/lifetimes, snapshots and repeated cleanup.
4. Measure release end-to-end parsing/transpilation including C JSON buffer and
   host data conversion, with equal inputs/outputs against the Python reference.
   Report timings rather than assume speedups; retain regression suites.

Tooling: Nim was absent; the official Nim 2.2.12 Linux x64 binary archive was
installed under `/tmp/opencode`, SHA256
`7df1611449a6842af69322aa2c1206942982650a5f6bc0d37bc8ec109932f638`.
Bundled Nimble is 0.24.1. No global toolchain configuration was changed.
Only Linux x86-64 artifacts can be verified in this environment; other platforms
remain explicit release gaps. Nothing has been published or committed.

**Completed authorized increment: native optional lexer/token parsing.** Implemented
the existing `lexer` branch through the current Parser C/Python entry points.
End-to-end checks feed source directly to native Parser without reference input
preparation.

Required mechanisms: PCRE2 matching against complete normalized source, ordered
longest-match token selection, skip actions, CRLF/CR and tab normalization,
INDENT/DEDENT with blank-line/dedent/EOF handling, token-level AST metadata,
runtime cpp-peglib token matching, and source-mapped ASTs/errors. Contract sources:
PARSING.md section 6, `StatefulLexer`, token branches of `AstBuilderVisitor` and
`_ParserCore`, plus unchanged lexer/Python/JavaScript tests and fixtures.

Verification: the missing branch was reproduced (5 lexer-dependent failures and
2 transpiler-only passes in `test_lexer_transpiler.py`). All 98 existing public
behavioral cases now run natively, with 2 subtests passing. The four Parsimonious
grammar-string tests remain separate and pass in the reference backend. Raw
AST/location/error comparisons, longest-match/tie/Unicode/normalization cases and
a standalone C caller pass. C ownership checks pass under ASan/UBSan with leak
detection. The supplied-AST Python/JavaScript check now parses natively and compares
raw ASTs, unnormalized output and state with independently generated reference
results. No reference implementation is loaded by the native conformance runner.
Reference raw structural text/parent-position defaults are preserved; the earlier
simplified example in PARSING.md has been corrected. Zero-progress matches get an
explicit native error. Native digit conversion also now accepts Unicode decimal
digits, retaining source text and exact integer values. The native parser/lexer/
transpiler increments are complete within their approved conformance scope.

Nim bindings and distribution are now authorized above. Current platform coverage
remains Linux x86-64.

The Python YAML 1.2 loading correction is implemented and verified. The agreed
native direction is recorded in [SPEC.md](SPEC.md).

**Completed authorized increment:** native parser/AST shaping, grammar
composition/validation, base-path and placeholder C/Python APIs, and unchanged
SLIP grammar conformance. Matching uses actual runtime cpp-peglib definitions
and full-subject PCRE2 terminals. AST shaping occurs after a successful match.

**Approved loader replacement completed:** rapidyaml 0.16.0 passed the bounded
compatibility check and replaces libfyaml. Its supported tree API feeds owned
`ordered_json` values directly, with explicit YAML 1.2 core scalar resolution.
The source-release SHA256 is
`a0ce80a8f4211580c8703e57acb813a28ca6ec80908f6eb926be94be8e98d39d`.
rapidyaml is linked statically and privately; no dependency patches were made.

**Current verification (Linux x86-64, Debug):**

- All ten CTest suites pass together: `c_api`, `lexer_c_api`, `transpiler_c_api`,
  `python_api`, `lexer_python`, `transpiler_python`, `parser_conformance`,
  `raw_asts`, `yaml_documents`, `regex_koine`.
- **98 existing public behavioral cases and 2 subtests pass natively**, plus
  **16 parser, 9 lexer and 10 transpiler native Python API cases**. Existing fixture
  data and expectations were retained. The native conformance runner imports no
  reference implementation. Its import-only backend helper stub fails if called;
  the four grammar-string tests are explicitly deselected from native behavior
  checks and pass separately in their Python backend.
- **82 document comparisons pass**, including all 10 Koine and 3 unchanged SLIP
  grammar files. Values, scalar types and mapping order match safer-yaml. Cases
  include quoted booleans/nulls, plain YAML 1.2 scalars, explicit tags, Unicode,
  NUL/other escapes, block scalars, aliases, duplicates and parse errors.
- **169 unchanged SLIP checks pass**: parser/path/signature/placeholder,
  transformer and root-comment integration, plus arithmetic initialization of
  the complete `root.slip` library through the native parser.
- **141 raw AST/status comparisons pass**, including complete `root.slip`, full
  and placeholder paths/signatures, empty containers, comments, Unicode, valid
  and invalid input. Raw success ASTs compare text, scalar types and locations.
  The approved exact-integer divergence is asserted separately without rounding
  away mismatches. Error statuses compare; backend diagnostic wording may differ.
- **7,992 regex comparisons pass**: 3,996 from each corpus (36 patterns each).
- C construction/parse/release checks exercise all construction entry points,
  selectable starts, placeholder mode, reuse and independently owned results.
  C and document checks pass under ASan/UBSan with leak detection enabled.
- `ldd` confirms no Python, libfyaml or separate rapidyaml runtime dependency.

Resolved local failures included invalidated ordered-json references during
normalization, a temporary child-mapping lifetime, and zero-width regex
nullability. Extra AST metadata follows the reference's ignored-key behavior;
this preserves malformed keys such as `discard:true` in existing shared fixtures.
Aliases and single-choice boundaries retain reference behavior. Direct full
construction from `slip_path.yaml` is rejected as unreachable by both backends;
integrated paths use the main grammar's namespaced entry points, and isolated
path checks use PlaceholderParser as in SLIP's own tests.

**Completed authorized increment: native transpiler first.** Implemented the documented
AST-to-text contract through the C interface and ordinary Python `Transpiler` API.
This advances the runtime-supplied DSL goal using the already-native parser.

Required mechanisms and acceptance (satisfied within the approved scope):

1. Port recursive named/list-child processing, binary-op fields, templates and
   escaped braces, `cases`/path truthiness/string equality, output fallbacks,
   post-node `state_set`, global indentation and per-call reset. Contract sources:
   `TRANSPILING.md`, reference `Transpiler` in `reference/koine/parser.py`, existing fixtures
   and transpiler tests. Use native traversal and formatting, never Python output
   generation behind the native entry point.
2. Add an opaque prepared transpiler, text output/state snapshots and explicit
   error/release operations to the C API. Python manages lifetimes and returns
   ordinary strings/dicts. Verify C ownership, reuse, Unicode/NUL and errors under
   ASan/UBSan, including returned output surviving handle/input destruction.
3. Run existing transpiler behavior tests using the native implementation. At the
   transpiler-only stage, test Python/JavaScript fixtures with supplied AST input;
   compare unnormalized output/state, repeated calls and failures. This isolated
   stage has since been extended to native end-to-end lexer/parser/transpiler tests.
4. Demonstrate a runtime-loaded math parser and transpiler producing parenthesized
   SLIP, evaluate generated code with the existing SLIP runtime, and assert both
   precedence and associativity. Keep the approved exact numeric values.

Confirmed scope decision: the user selected documented template syntax for the
native implementation. Named substitutions and doubled braces are supported;
broader Python `str.format` specs/conversions/field-access expressions explicitly
error. Do not build a Python-format compatibility layer for this increment.

The native lexer increment is also completed below. Nim and distribution follow
later. No later increment is started automatically.

### Native transpiler verification checkpoint

- Added `native/src/transpiler.{h,cpp}` with direct native JSON traversal, template
  substitution, conditions, post-node state updates and local indentation depth.
  Scalar text spelling, empty-string truthiness, cases precedence and literal
  inserted text are covered by differential/API checks.
- Added four C transpiler entry points and Python `Transpiler` exports from both
  `koine` and `koine.parser`. `Transpiler()` defaults to empty output rules; state
  inspection returns detached data. No new dependency was introduced.
- Removed the reference Transpiler injection from conformance tests. The 89-case
  run includes unchanged calculator/advanced output expectations, fallback,
  truthiness, dynamic state values, indentation configuration and error cases.
- Ten focused native Python cases cover scalar conversion, escaped braces/NUL,
  approved format errors, conditions, ordering/reset, detached state, exception
  recovery, nested indentation/lists, thread reuse and the runtime math pipeline.
  Both Python/JavaScript transpiler fixtures matched unnormalized reference output
  and state using supplied ASTs at this checkpoint. They now run native parsing
  too, with raw AST comparison, as part of the completed lexer increment.
- The independent C caller verifies all four entry points, runtime JSON and YAML
  grammars, 100 lifecycle iterations, Unicode/NUL output, state snapshots,
  malformed input/errors, reuse and output surviving input/handle destruction.
  It passes ASan/UBSan with leak detection enabled.
- `check_math_slip.py`, run in the existing sibling SLIP environment with native
  `PYTHONPATH`, evaluates six saved/reloaded generated programs successfully:
  precedence (`10 + 5 * 2` becomes `(10 + (5 * 2))`, value 20), explicit groups,
  left/right associativity (including `2 ^ 3 ^ 2`, value 512), and exact large
  integers. The ordinary ungrouped SLIP expression still evaluates to 30.
- All eight CTest suites pass, `ldd` still shows no Python runtime dependency,
  and `git diff --check` passes. Current native artifact:
  `/tmp/opencode/koine-native-build/python/koine/libkoine.so`.

Commands for this increment (in addition to the build/check commands below):

```bash
cmake --build /tmp/opencode/koine-native-build --target koine_c_test koine_lexer_c_test koine_transpiler_c_test koine_document_test -j 4
ctest --test-dir /tmp/opencode/koine-native-build --output-on-failure
```

From the sibling SLIP checkout:

```bash
PYTHONPATH=/tmp/opencode/koine-native-build/python uv run --no-sync python3 /mnt/x/mabandits/code/koine/native/tests/check_math_slip.py
```

### Historical: initial integration checkpoint

- Implemented `native/CMakeLists.txt`, `include/koine.h`, C++ parser/PCRE2 adapter,
  C YAML adapter, and a staged Python `koine` package using `ctypes`. The native
  library has no Python runtime dependency (`ldd` inspected).
- Built using GCC 11.4 / CMake 3.22.1 on Linux x86-64. Dependency versions:
  cpp-peglib v1.22.0 commit `94a76a05dc90a344fe4f6ab37f5410cab4881704`,
  nlohmann/json v3.11.3 (`ordered_json`), system PCRE2 10.39, and the pinned
  libfyaml v1.0.0-beta2 archive. libfyaml reflection and its own Python bindings
  are disabled; the prototype uses its generic YAML 1.2 core-schema API.
- C caller checks pass, including repeated create/parse/destroy, explicit errors,
  and returned buffers surviving source/parser destruction. The C source is
  compiled and linked with the C compiler.
- The same C checks pass under AddressSanitizer/UndefinedBehaviorSanitizer with
  leak detection enabled. This is bounded ownership evidence, not full coverage.
- Python wrapper: **11 of 11 cases pass** (matching composition, reuse, locations,
  recursive groups/backtracking, assertions, nullable repetition, threads,
  length-delimited source, YAML 1.2 scalars, JSON/UTF-8 files, and explicit errors).
  Equivalent JSON/YAML grammar files produce identical parse results. The
  embedded-NUL grammar regression remains enabled and now passes.
- All **3 CTest suites pass** (`c_api`, `python_api`, `regex_koine`). Regex-only
  failures are tracked by the custom matcher so failures include nonempty,
  code-point-correct diagnostics even when the PEG backend has no expected token.
- Regex differential checks pass: **3,996 comparisons over 36 regexes** from the
  10 Koine grammar fixtures, and **3,996 comparisons over 36 regexes** from the
  3 current SLIP grammars. Inputs cover success/failure, empty matches, Unicode,
  newlines, and nonzero byte/code-point offsets. This checks terminals, not full
  native SLIP AST or language conformance.
- The `\Z` adapter preserves Python's absolute-end assertion without editing
  grammar files; the escaped-literal case is tested separately.
- Adding `native/` exposed setuptools' automatic top-level package discovery.
  Explicit discovery now includes only `koine` / `koine.*`. The existing Python
  reference wheel builds and a clean isolated install successfully loads a YAML
  1.2 `on` literal with the declared safer-yaml dependency.

Superseded dependency decision: libfyaml's optimized generic emitter parses `"a\u0000b"`
and, in explicit JSON output mode, emits invalid `"a\0b"`. The user authorized
checking the documented `FYOPEF_EMIT_EVENTS` route. That route fixed NUL escaping
and passed the then-current API, corpus, and ownership checks, so it was selected
at that checkpoint. Further independent checks showed that the event route
emitted parsed strings `"true"` and `"null"` as JSON booleans/null, losing type.
The user approved the bounded rapidyaml replacement, now completed above. The
libfyaml adapter and its temporary reproducer target have been removed.

Commands used (development artifacts are outside the source tree):

```bash
cmake -S native -B /tmp/opencode/koine-native-build -DCMAKE_BUILD_TYPE=Debug -DPython3_EXECUTABLE=/mnt/x/mabandits/code/slip/.venv/bin/python3
cmake --build /tmp/opencode/koine-native-build --target koine_c_test koine_lexer_c_test koine_transpiler_c_test koine_document_test -j 4
ctest --test-dir /tmp/opencode/koine-native-build --output-on-failure
```

See [native/README.md](native/README.md) for current source-tree build commands,
supported behavior and explicit corpus commands. The initial gate alone did not
establish full parser conformance; current evidence is recorded at the top.
Nim and distribution were later work at that checkpoint; current Linux completion
evidence is recorded at the top. Additional platform coverage remains open.

## Completed: Python YAML 1.2 reference

- Replace the direct PyYAML dependency with `safer-yaml>=0.1.1`.
- Route all four grammar-file loading sites through `safer_yaml.load(path)`,
  retaining normalization, relative paths, and the existing public entry points.
- Update the loading examples and document YAML 1.2 core scalar behavior.
- Add temporary-file regressions for `Parser.from_file()` and
  `PlaceholderParser.from_file()`, JSON input, and nested relative subgrammars.
  The subgrammar case exercises an unquoted `off` start-rule name as well as a
  `no` literal, covering both discovery and entry-point loading.

### Verification evidence

Checks used this source checkout with safer-yaml 0.1.1 in the existing sibling
SLIP development environment:

- Before the fix: 9 new YAML loading cases failed; 2 JSON cases passed.
- After the fix: all 11 file-loading cases passed.
- Full Koine suite: **102 passed, 2 subtests passed**, **93.78% coverage**; the
  existing 90% coverage gate passed.
- SLIP parser/path/signature/placeholder, transformer, and root-comment checks,
  plus full `root.slip` initialization through its arithmetic integration test:
  **169 passed**.
- A separate loader comparison found identical decoded data, scalar types, and
  mapping order for all 10 Koine YAML fixtures and the 3 current shared SLIP
  grammar files. These were not edited.
- Saved SPEC/PLAN content and local links reviewed; `git diff --check` passed.

SLIP normally resolves an installed Koine package. For reproducible checks, set
`KOINE_SOURCE` to this checkout and run from the sibling SLIP checkout:

```bash
PYTHONPATH="$KOINE_SOURCE" uv run --no-sync python3 -m pytest -q "$KOINE_SOURCE/tests" --cov=koine --cov-fail-under=90
PYTHONPATH="$KOINE_SOURCE" uv run --no-sync python3 -m pytest -q tests/test_parser*.py tests/test_root_comment_and_sig_integration.py tests/test_slip_transformer.py tests/test_root_slip.py::test_core_arithmetic_and_operators
```

Confirm `koine.__file__` points into `KOINE_SOURCE`. Each command uses a fresh
process; the root integration therefore initializes and parses the complete root
library rather than reusing an in-process parser result. These checks establish
Python compatibility, not native implementation evidence.

## Completed: native dependency and C-interface integration gate

**Goal:** prove the actual runtime-loaded grammar mechanism and binding boundary
before porting the full engine.

Required mechanisms and sources:

- Runtime PEG construction and custom regex terminals using cpp-peglib's
  documented combinators and `usr` matcher hook ([upstream contract](https://github.com/yhirose/cpp-peglib)).
- Native JSON/YAML 1.2 loading into one grammar data representation, including
  core-schema scalar behavior from safer-yaml and `tests/test_file_loading.py`.
- A real regex-library adapter matching the full subject at a supplied offset;
  preserve the literal/regex behavior documented in [PARSING.md](PARSING.md).
- An opaque parser handle, explicit results/errors, and library-owned output
  release through the C ABI described in SPEC. Exercise it with a C caller and a
  small Python `ctypes` wrapper.

Use CMake under `native/`. Evaluate PCRE2 and libfyaml, select and record versions
after the focused checks, and keep the build limited to the features needed by
Koine. Current versions and evidence are recorded above, including the standard
event-emitter selection and the optimized-emitter regression.

Acceptance checks:

1. A native test loads a small caller-supplied grammar after compilation. Its
   regex terminal is embedded in PEG sequence/choice/repetition and lookahead.
   Assert consumed spans and structured output, plus rejection at a nonmatching
   current position. Repeat parsing with the same prepared handle.
2. Equivalent JSON and YAML files produce the same data and parse results.
   Exercise `yes`/`no`/`on`/`off`, actual booleans, and UTF-8 text.
3. Compare the actual Koine/SLIP regex patterns with the Python reference on
   success, failure, empty matches, and nonzero offsets. Include Unicode classes,
   newline behavior, and end-of-input assertions.
4. Results and error buffers survive temporary source storage until released;
   invalid grammar and parse failure cross the C ABI correctly. Link the C caller
   without exposing C++ classes or requiring its source to compile as C++.

Stop this gate when those decisions have evidence. A recognizer or a binding
smoke test alone does not establish AST, transpiler, lexer, or full SLIP parity.
Report an unsuitable dependency before replacing the selected mechanism.

## Parser and following milestones

### Completed: parser and SLIP grammar conformance

Implement the matching constructs, validation, normalization, subgrammar
namespaces/cycles, selectable start rules, placeholder parsing, all AST directives,
and source locations from PARSING.md. Extend the C API and Python wrapper to the
existing public parser contract so behavioral tests can run against the native
backend in a separate environment.

Acceptance: existing Koine parser/AST cases pass; the unchanged shared
[`../slip/grammar/`](../slip/grammar/) files parse representative valid and invalid
SLIP, including the complete `root.slip`, independently of Python parsing.
Compare raw AST data and code-point locations separately from SLIP's cleaned-AST
comparisons. Preserve numeric token text exactly.

Required mechanisms: runtime cpp-peglib matching and full-subject PCRE2 terminals
remain the engine; grammar discovery/namespacing and normalization run natively;
AST shaping follows `AstBuilderVisitor` and parser tests; placeholders replace
subgrammars without loading dependencies. The C/Python interfaces expose base-path
and placeholder construction. Transpilation and native lexing are now completed;
Nim and distribution followed that checkpoint and are verified for Linux above.

Approved numeric policy: exact int64/uint64 for integer tokens, float64 for other
numbers, integral float normalization where representable, explicit overflow, and
unchanged token text. Test integer limits, fractional/exponent forms and overflow
separately from Python parity, including the intentional `9007199254740993`
precision difference. Implementation and bounded conformance results are recorded
at the top of this plan; integer limits, fractional/exponent forms, overflow and
rejected-backtracking-branch conversion are checked explicitly.

### Completed: native lexer conformance

The native transpiler and runtime math-to-SLIP example are completed. Native
tokenization/indentation parsing is now implemented and verified.

Implement the stateful lexer, longest-match tokenization, token AST directives,
indentation and source/error locations from PARSING.md and the reference lexer.
Reuse the existing Python/JavaScript, promotion and error fixtures. Preserve
newline/tab normalization, blank-line behavior, INDENT/DEDENT, token-level
discard/type conversion and the approved numeric policy.

Acceptance: existing lexer and mixed parse/transpile cases run entirely natively;
compare raw token-based ASTs/locations and unnormalized output with the reference.
The earlier supplied-AST checks were not evidence of tokenization; current tests
run native tokenization, parsing and transpilation end-to-end.

Acceptance evidence:

- All nine previously excluded public lexer-dependent cases pass natively,
  including both complete Python↔JavaScript transformations, error locations,
  blank lines, inline token AST normalization and token-level discard/type.
  Together with the prior selection, all 98 public behavioral tests and 2 subtests
  pass. Four backend-specific grammar-string tests pass separately in Python.
- `native/tests/test_lexer.py` passes nine focused cases with raw token and AST
  comparisons, normalized Unicode/CRLF/CR/tab input, nested and EOF dedents,
  longest-match/ties, complete-subject regex assertions, empty streams, aliases,
  placeholders, alternate starts and source-mapped lexical/syntax/indent errors.
- Unicode digit checks reproduced an ASCII-only numeric conversion failure.
  Conversion now maps Unicode 15.0 decimal digit blocks using cpp-peglib's UTF-8
  decoder, preserving token text, exact integer values and overflow checks.
- `native/tests/test_transpiler.py` now creates both Python/JavaScript ASTs with
  native Parser before native Transpiler runs. Reference results are independent
  comparison oracles only; unnormalized output, raw ASTs and state match.
- A standalone C caller performs 50 create/error/parse/destroy cycles with runtime
  YAML lexer data, indentation, CRLF, tabs, Unicode and NUL. Output survives source
  mutation and parser destruction. All three C callers pass ASan/UBSan with leak
  detection. `ldd` still confirms no Python runtime dependency.
- All ten CTest suites pass. The unchanged SLIP selection still passes 169 checks,
  141 raw AST/status comparisons pass, and six saved math-to-SLIP programs evaluate
  correctly. Shared fixtures and existing assertions were retained.

The lexer documentation's raw AST example now reflects actual list wrappers,
token-name structural text and parent-position defaults in both implementations.
This corrects the example without changing reference parser behavior.

### Nim package and distribution

Add the ordinary Nim `koine` package using `importc`, automatic native lifetime
management, and `JsonNode` conversion. Verify the same cases through Python and
Nim wrappers, including repeated construction/release, Unicode, and errors.
Verify installed Python wheels and the Nim package from clean consumer examples.
Measure end-to-end performance, including JSON serialization/conversion, against
the Python reference with equal inputs and outputs.

## Open compatibility decisions

- Python's `regex` engine and PCRE2 have different behavior in places. In
  particular, Python `\Z` means absolute end, whereas PCRE2 `\Z` can precede a
  final newline; the adapter covers that difference and the corpus checks pass.
  Broader dialect/Unicode equivalence still needs checks as native conformance
  expands. Do not edit shared grammars merely to conceal an adapter mismatch.
- Python converts typed numbers through `float`; the user selected exact native
  64-bit values as recorded in SPEC and the completed increment above. Numerical
  conformance must distinguish that approved difference from unintended drift.
- Backend parse-tree optimization can erase rule boundaries needed by inline AST
  directives. Verify those boundaries rather than copying Parsimonious's no-op
  string workarounds into the native contract.
- The prototype uses nlohmann `ordered_json` to preserve mapping order. Final
  platform compatibility remains open. Keep ownership
  and conversions explicit without adding a cross-language AST object framework.

Nim was absent at the initial integration checkpoint; current tooling is Nim
2.2.12 with GCC 15. Native dependencies are built privately. Broader regex dialect
equivalence, complete arbitrary YAML coverage and other platforms remain bounded
compatibility gaps; installed Linux package checks are recorded at the top.
