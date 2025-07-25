# Koine: Rationale

Koine exists to solve a common but underserved problem: **rapidly building small-to-medium-sized domain-specific languages (DSLs)** where grammar, AST, and code generation need to be **expressive, composable, and declarative**—without the overhead and rigidity of traditional compiler tools.

## Why Another Parser?

Existing parser tools fall into two camps:

- **Too complex for rapid iteration** (ANTLR, Bison, Menhir)
- **Too limited or inflexible** (Lark, PEG.js, Ohm, PLY)

As a language/tool designer, I found myself wanting:

- A parser I could describe entirely in **data structures**, not host-language code
- A pipeline I could embed inside a scripting language to let _programs define and interpret grammars at runtime_
- The ability to **transpile** DSLs to other languages or bytecode formats—without writing visitors or walking trees by hand

Nothing fit. So I built Koine.

## Why Not [X]?

### Lark

- Designed for 1-token lookahead; PEG-like constructs are difficult to express.
- Embeds semantic logic in Python methods—not composable or portable.
- Better suited for static parsing than dynamic DSL composition.

### ANTLR

- Heavy toolchain, grammar files, and codegen pipeline.
- Code/grammar coupling makes it hard to experiment or embed.
- Overkill for embedded scripting or agent control flows.

### Janet, Red, PEG.js

- Janet’s PEG parser is powerful, but coupled to Lisp data structures and assumptions.
- Red’s `parse` is elegant, but is restricted to Rebol dialects.
- PEG.js lacks AST tooling and formal transpiler pipeline.

## What Koine Does Differently

Koine separates concerns explicitly:

- **Grammar**: defined as data (YAML/JSON/TOML)
- **AST rules**: declarative shape transformations (`promote`, `structure`, `leaf`)
- **Transpiler**: templated output with conditional logic and internal state
- **Embedding**: Koine grammars are just lists and dicts—ready to be loaded or generated by another language.

This makes Koine ideal for:

- Scripting languages
- Interactive fiction systems
- Agent behavior languages
- Game modding DSLs
- Lightweight transpilers (e.g., math notation → custom format)

## Inspirations

- **Red/Rebol**: minimalistic and expressive parsing dialects.
- **Janet**: embedded DSL support, PEG-first design.
- **Ohm**: grammar-first design.

## Not a Good Fit If…

- You need ultra-fast parsing of gigabyte-scale source trees.
- Your language requires multiple passes of semantic analysis or deep type inference.
- You need precise error recovery for production IDE tooling.

## Final Word

Koine is a parser built for designers—**not compiler engineers**. It prioritizes expressiveness, iteration speed, and embeddability. If you need to build a custom language fast—and want to keep grammars as editable data rather than code—Koine might be exactly what you're looking for.
