This document outlines future work and potential major feature additions for the Koine parser system.

## Feature: Integrated Stateful Lexer

**Status:** `Future Work / R&D`
**Priority:** `Medium`
**Dependencies:** None

### 1. The Problem: Handling Context-Sensitive Syntax

The current pure PEG parser cannot natively handle context-sensitive syntax like Python's indentation rules. The standard solution is a two-phase process involving a lexer and a parser.

### 2. The Goal: A Seamless, Unified Grammar

Instead of requiring the user to manage two separate processes or files, we will integrate the lexer definition directly into the main grammar file. This will allow the grammar writer to define everything about their language—from low-level tokens to high-level grammar—in a **single source of truth**.

The `Parser` engine will be smart enough to detect when a lexer is defined and will automatically engage the two-phase pipeline. The complexity of this process will be completely hidden from the user.

### 3. Proposed Design

#### A. The Unified Grammar File

We will introduce a new, optional top-level key to the grammar file: `lexer`. If this key is present, the parser will operate in the new "tokenizing" mode.

**`python_like_grammar.yaml` Example:**
```yaml
# NEW: Optional top-level key for lexer definitions.
lexer:
  # The order of this list is important.
  tokens:
    # Skip non-newline whitespace and comments
    - { regex: "[ \\t]+", action: "skip" }
    - { regex: "#.*", action: "skip" }

    # The newline is now a special action that triggers indentation logic
    - { regex: "\\n[ \\t]*", action: "handle_indent" }

    # Keywords and Operators
    - { regex: "def", token: "DEF" }
    - { regex: ":", token: "COLON" }
    # ... etc ...

    # General Tokens
    - { regex: "[a-zA-Z_][a-zA-Z0-9_]*", token: "NAME" }
    - { regex: "[0-9]+", token: "NUMBER" }

# --- The existing grammar rules now work with tokens, not raw text ---

start_rule: program

rules:
  program:
    one_or_more: { rule: function_definition }

  function_definition:
    sequence:
      - { token: "DEF" } # Match the DEF token, not the literal "def"
      - { token: "NAME" }
      - { token: "COLON" }
      - { rule: function_body }

  function_body:
    sequence:
      - { token: "INDENT" } # Use the magic INDENT token
      - { rule: statements }
      - { token: "DEDENT" } # And the magic DEDENT token
```

#### B. The New `Parser` Pipeline

The `Parser` class will be updated to orchestrate the following steps automatically:

1.  **Initialization:** When the `Parser` is initialized with a grammar dictionary, it will check for the presence of the `lexer` key. If found, it will enable the tokenizing pipeline.
2.  **Lexing:** Inside the `parse()` method, if the tokenizing pipeline is enabled, a `StatefulLexer` will scan the raw source code. Its `handle_indent` action will manage an indentation stack and emit `INDENT` and `DEDENT` tokens. The output is a list of rich `Token` objects (e.g., `[Token(type='NAME', value='my_func', ...)]`).
3.  **String Reconstruction:** A simple string is created for Parsimonious by joining the `type` of each token (e.g., `"DEF NAME COLON INDENT ..."`).
4.  **Grammar Rule Update:** The grammar rules will now support a `{ token: "NAME" }` directive. The engine will treat this as a match for the literal token name in the reconstructed string.
5.  **Parsing:** Parsimonious parses the reconstructed token string.
6.  **AST Visitor Enhancement:** The `AstBuilderVisitor` will be initialized with both the Parsimonious tree and the original list of `Token` objects. When it builds an AST node for a `NAME` or `NUMBER`, it will use the token list to look up the original `value` (e.g., "my_func") and attach it to the AST node.

#### C. Benefits

*   **Single Source of Truth:** The entire language, from its low-level tokens to its high-level grammar, is defined in a single, cohesive file.
*   **Massively Simplified Grammars:** Grammar `rules` will become cleaner and more abstract, as they will no longer contain regexes for whitespace or literal keywords.
*   **First-Class Indentation Support:** Handling indentation-based languages becomes trivial from the grammar writer's perspective.
*   **Backward Compatibility:** Grammars without a `lexer` block will continue to work exactly as they do now.