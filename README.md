# Koine

_A declarative, data-driven parser generator for creating languages, ASTs, and transpilers._

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Koine allows you to define a complete language pipeline—from lexing and validation to Abstract Syntax Tree (AST) generation to final code transpilation—using a simple, human-readable, and JSON-compatible data structure. This means you can write your grammars in YAML, JSON, TOML, or any other format that can be loaded into a nested dictionary structure. The engine consumes these definitions and produces clean, JSON-compatible ASTs.

This approach separates the _what_ (your language definition) from the _how_ (the parsing engine).

### Core Features

- **Declarative:** Define complex grammars entirely in a data format like YAML. No code generation step is required.
- **Pipeline-based:** Use Koine for simple validation, structured AST generation, or full transpilation.
- **Powerful:** Handles operator precedence, left/right associativity, lookaheads, and features an integrated stateful lexer for indentation-based syntax.
- **Language Agnostic:** The Koine format is a specification. The engine can be implemented in any language (current implementation is Python).

### Philosophy and When to Use Koine

Koine is designed to be an exceptionally fast tool for **prototyping Domain-Specific Languages (DSLs)** and other custom parsers. Its "configuration-over-code" approach makes it ideal for tasks where clarity, portability of the grammar, and development speed are more important than raw parsing performance.

**Use Koine When:**

*   **You are building a DSL:** For query languages, configuration formats, or command languages.
*   **You need to parse complex but small-to-medium sized data:** Where the cost of building a traditional parser is too high.
*   **You value a declarative, data-driven grammar:** The grammar can be stored as simple data (JSON/YAML) and is portable to other potential Koine engine implementations.
*   **You are prototyping language ideas:** The entire lex->parse->transpile pipeline can be defined and modified quickly.

**Consider Other Tools When:**

*   **You need extreme performance:** Koine is not designed to compete with high-performance compilers like `gcc` or `ANTLR` for parsing millions of lines of code.
*   **You require complex semantic analysis:** If your transpilation logic requires deep, stateful analysis (e.g., advanced type inference, complex symbol tables), a traditional visitor pattern in a general-purpose language may be more suitable.
*   **You need sophisticated error recovery:** Koine reports the first syntax error it finds and stops.

---

## Installation

```bash
pip install koine
```

---

## Quick Start

Let's build a simple calculator that can parse `2 + 3` and transpile it to `(add 2 3)`.

1.  **Create your parser grammar, `parser_calc.yaml`:** This defines the language syntax and how to build an AST.
    ```yaml
    start_rule: expression
    rules:
      expression:
        ast: { structure: "left_associative_op" }
        sequence:
          - { rule: number }
          - zero_or_more:
              sequence:
                - { rule: _ }
                - { rule: add_op }
                - { rule: _ }
                - { rule: number }
      add_op:
        ast: { leaf: true }
        literal: "+"
      number:
        ast: { leaf: true, type: "number" }
        regex: "\\d+"
      _:
        ast: { discard: true }
        regex: "[ \\t]*"
    ```

2.  **Create your transpiler grammar, `transpiler_calc.yaml`:** This defines how to convert the AST into a new string.
    ```yaml
    rules:
      binary_op:
        template: "({op} {left} {right})"
      add_op:
        value: "add"
      number:
        use: "value"
    ```

3.  **Use the Koine engine in `main.py`:**
    ```python
    import yaml
    from koine.parser import Parser, Transpiler

    # 1. Load the grammars
    with open("parser_calc.yaml", "r") as f:
        parser_grammar = yaml.safe_load(f)
    with open("transpiler_calc.yaml", "r") as f:
        transpiler_grammar = yaml.safe_load(f)

    # 2. Instantiate the tools
    parser = Parser(parser_grammar)
    transpiler = Transpiler(transpiler_grammar)

    # 3. Run the pipeline
    source_code = "2 + 3"
    parse_result = parser.parse(source_code)

    if parse_result['status'] == 'success':
        translation = transpiler.transpile(parse_result['ast'])
        print(f"Input: '{source_code}'")
        print(f"Output: {translation}")
    else:
        print(f"Error: {parse_result['message']}")
    ```

4.  **Run it:**
    ```
    Input: '2 + 3'
    Output: (add 2 3)
    ```

---

### Overview

This document describes the data-driven grammar format for the Koine parser. The system is designed as a flexible pipeline that can be used for simple validation, structured data extraction (AST generation), or full-scale language translation (transpilation).

The core philosophy is to separate the _what_ from the _how_. You define _what_ the language looks like and _what_ the output should be, and the Koine engine handles _how_ to parse and transform it.

This guide will walk through five primary use cases, showing how to add complexity at each stage:
1.  **Validation:** Checking if an input string conforms to a grammar.
2.  **AST Generation:** Parsing an input string into a clean, semantic Abstract Syntax Tree.
3.  **Transpilation:** Transforming the AST into a new string format (e.g., infix math to LISP).
4.  **Lexer-Based Parsing:** Handling context-sensitive syntax, like Python's indentation, by defining tokens.
5.  **Indented Output:** Transpiling an AST into an output format that requires proper indentation, like Python.

---

### Use Case 1: Validation

**Goal:** To answer the simple question, "Does this input string conform to my language's syntax?"

At this level, we only care about the structure of the language. We do not need an Abstract Syntax Tree (AST) or a transpiled output. Therefore, we only use the **Grammar Structure Keys**. The `ast` and `transpile` directives are not needed and can be omitted entirely.

#### Full Example: A Validation-Only Calculator Grammar

This grammar can successfully parse valid mathematical expressions, but it produces no useful output beyond "success" or "failure".

**`validation_calculator.yaml`**

```yaml
start_rule: expression

rules:
  expression:
    sequence:
      - { rule: term }
      - zero_or_more:
          sequence: [{ rule: _ }, { rule: add_op }, { rule: _ }, { rule: term }]

  term:
    sequence:
      - { rule: power }
      - zero_or_more:
          sequence:
            [{ rule: _ }, { rule: mul_op }, { rule: _ }, { rule: power }]

  power:
    sequence:
      - { rule: factor }
      - optional:
          sequence:
            [{ rule: _ }, { rule: power_op }, { rule: _ }, { rule: power }]

  factor:
    choice:
      - { rule: number }
      - sequence:
          - { literal: "(" }
          - { rule: _ }
          - { rule: expression }
          - { rule: _ }
          - { literal: ")" }

  add_op:
    choice: [{ literal: "+" }, { literal: "-" }]

  mul_op:
    choice: [{ literal: "*" }, { literal: "/" }]

  power_op:
    literal: "^"

  number:
    regex: "-?\\d+"

  _:
    regex: "[ \\t]*"
```

**Usage:**

```python
# Load the validation-only grammar
with open("validation_calculator.yaml", "r") as f:
    grammar = yaml.safe_load(f)

validator = Parser(grammar)
result = validator.parse("((2 + 3) * 4) ^ 5")

if result['status'] == 'success':
    # The 'ast' key will contain a raw, messy parse tree, which we ignore.
    print("Input string is a valid expression!")
else:
    print(f"Invalid: {result['message']}")
```

---

### Use Case 2: Parsing to a Semantic AST

**Goal:** To validate the input string AND convert it into a clean, structured, and meaningful data representation (an AST).

This is the most common use case for parsing complex data. To achieve this, we build on the validation grammar by adding the **`ast` directive block** to our rules. This block tells the parser how to transform the raw parse tree into a clean AST by discarding whitespace, promoting nodes, and building specific structures. The `transpile` block is still not needed.

#### Full Example: An AST-Generating Calculator Grammar

We now add directives like `discard`, `promote`, `leaf`, and `structure` to produce a useful tree.

**`ast_calculator.yaml`**

```yaml
start_rule: expression

rules:
  expression:
    ast: { structure: "left_associative_op" }
    sequence:
      - { rule: term }
      - zero_or_more:
          sequence: [{ rule: _ }, { rule: add_op }, { rule: _ }, { rule: term }]

  term:
    ast: { structure: "left_associative_op" }
    sequence:
      - { rule: power }
      - zero_or_more:
          sequence:
            [{ rule: _ }, { rule: mul_op }, { rule: _ }, { rule: power }]

  power:
    ast: { structure: "right_associative_op" }
    sequence:
      - { rule: factor }
      - optional:
          sequence:
            [{ rule: _ }, { rule: power_op }, { rule: _ }, { rule: power }]

  factor:
    ast: { promote: true }
    choice:
      - { rule: number }
      - sequence:
          - { literal: "(" }
          - { rule: _ }
          - { rule: expression }
          - { rule: _ }
          - { literal: ")" }

  add_op:
    ast: { leaf: true }
    choice: [{ literal: "+" }, { literal: "-" }]

  mul_op:
    ast: { leaf: true }
    choice: [{ literal: "*" }, { literal: "/" }]

  power_op:
    ast: { leaf: true }
    literal: "^"

  number:
    ast: { leaf: true, type: "number" }
    regex: "-?\\d+"

  _:
    ast: { discard: true }
    regex: "[ \\t]*"
```

**Usage:**

```python
# Load the AST-generating grammar
with open("ast_calculator.yaml", "r") as f:
    grammar = yaml.safe_load(f)

parser = Parser(grammar)
result = parser.parse("((2 + 3) * 4) ^ 5")

if result['status'] == 'success':
    print("Successfully parsed. AST:")
    # The result now contains a valuable 'ast' key with a clean tree
    print(json.dumps(result['ast'], indent=2))
```

**Output AST:**

```json
{
  "tag": "binary_op",
  "op": {
    "tag": "power_op",
    "text": "^",
    "line": 1,
    "col": 16
  },
  "left": {
    "tag": "binary_op",
    "op": {
      "tag": "mul_op",
      "text": "*",
      "line": 1,
      "col": 10
    },
    "left": {
      "tag": "binary_op",
      "op": {
        "tag": "add_op",
        "text": "+",
        "line": 1,
        "col": 5
      },
      "left": {
        "tag": "number",
        "text": "2",
        "line": 1,
        "col": 3,
        "value": 2
      },
      "right": {
        "tag": "number",
        "text": "3",
        "line": 1,
        "col": 7,
        "value": 3
      }
    },
    "right": {
      "tag": "number",
      "text": "4",
      "line": 1,
      "col": 12,
      "value": 4
    }
  },
  "right": {
    "tag": "number",
    "text": "5",
    "line": 1,
    "col": 18,
    "value": 5
  }
}
```

---

### Use Case 3: Full Transpilation

**Goal:** To validate the input, parse it to a clean AST, and then **transform that AST into a different string format** (e.g., from infix math to LISP-style s-expressions).

This is the full power of the pipeline. We use two separate grammar files: one for the `Parser` and one for the `Transpiler`. The `Parser` grammar defines the language and AST structure. The `Transpiler` grammar defines how to convert each AST node into an output string, including conditional logic.

#### Full Example: A Transpiling Calculator Grammar

First, we use the `ast_calculator.yaml` from Use Case 2 to produce the AST. Then, we create a new file to define the LISP transpilation rules.

**`lisp_transpiler.yaml`**
```yaml
rules:
  binary_op:
    template: "({op} {left} {right})"
  add_op:
    cases:
      - if: { path: "node.text", equals: "+" }
        then: "add"
      - default: "sub"
  mul_op:
    cases:
      - if: { path: "node.text", equals: "*" }
        then: "mul"
      - default: "div"
  power_op:
    value: "pow"
  number:
    use: "value"
```

**Usage:**

```python
import yaml
from koine.parser import Parser, Transpiler

# Load the parser and transpiler grammars
with open("ast_calculator.yaml", "r") as f:
    parser_grammar = yaml.safe_load(f)
with open("lisp_transpiler.yaml", "r") as f:
    transpiler_grammar = yaml.safe_load(f)

# Instantiate the tools
parser = Parser(parser_grammar)
transpiler = Transpiler(transpiler_grammar)

# Run the pipeline
parse_result = parser.parse("((2 - 3) * 4) ^ 5")

if parse_result['status'] == 'success':
    print("Parse successful. Transpiling AST...")
    translation = transpiler.transpile(parse_result['ast'])
    print(f"Final Output: {translation}")
```

**Final Output:**

```
Final Output: (pow (mul (sub 2 3) 4) 5)
```

---

### Use Case 4: Lexer-Based Parsing and Stateful Transpilation

**Goal:** To handle context-sensitive syntax (like Python's indentation) and perform stateful transformations (like emitting `let` only for the first variable assignment).

This requires two new features:
1.  **The `lexer` block:** A top-level key in the parser grammar that defines tokens, offloading work like whitespace and comment handling from the main parser rules. It can also emit special `INDENT`/`DEDENT` tokens.
2.  **Stateful transpiler directives:** `state_set` and conditional `cases` that can check the transpiler's internal state.

#### Example: Transpiling Python to JavaScript

**`py_parser.yaml` (Snippet)**
```yaml
# A top-level key to define tokens
lexer:
  tokens:
    - { regex: "[ \\t]+", action: "skip" }
    - { regex: "\\n[\\t ]*", action: "handle_indent" } # Magic action
    - { regex: "def", token: "DEF" }
    - { regex: "return", token: "RETURN" }
    - { regex: "[a-zA-Z_][a-zA-Z0-9_]*", token: "NAME" }
    - { regex: "=", token: "EQUALS" }

start_rule: function_definition

rules:
  function_definition:
    # Grammar rules now match abstract tokens, not raw text
    sequence: [ { token: "DEF" }, { rule: identifier }, ... ]
  ...
```

**`py_to_js_transpiler.yaml`**
```yaml
rules:
  function_definition:
    template: "function {name}({params}) {{\n{body}\n}}"
  NAME:
    use: "text"
  NUMBER:
    use: "value"
  parameters:
    join_children_with: ", "
    template: "{children}"
  suite:
    indent: true
    join_children_with: "\n"
    template: "{children}"
  assignment:
    cases:
      # If 'state.vars.{target}' does not exist...
      - if: { path: 'state.vars.{target}', negate: true }
        # ...then use the template with 'let'
        then: "let {target} = {value};"
      # Otherwise, use the default template without 'let'
      - default: "{target} = {value};"
    # After transpiling, set a state variable to remember the assignment
    state_set: { "vars.{target}": True }
  for_loop:
    template: "for (let {iterator} = 0; {iterator} < {limit}; {iterator}++) {{\n{body}\n}}"
  return:
    template: "return {value};"
  binary_op:
    template: "{left} + {right}"
```

**Usage:**

```python
# Load the py_parser.yaml and py_to_js_transpiler.yaml grammars
# and instantiate the Parser and Transpiler.
parse_result = parser.parse(python_code)
if parse_result['status'] == 'success':
    translation = transpiler.transpile(parse_result['ast'])
    # The 'translation' variable now holds the transpiled JavaScript code.
```

**Result:** The transpiler correctly handles indentation and uses `let` only for the first assignment to each variable.

**Input Python Code:**
```python
def f(x, y):
    a = 0
    for i in range(y):
        a = a + x
    return a
```

**Output JavaScript Code:**
```javascript
function f(x, y) {
    let a = 0;
    for (let i = 0; i < y; i++) {
        a = a + x;
    }
    return a;
}
```

---

### Use Case 5: Transpiling to Indented Languages

**Goal:** To generate output that requires correct indentation, like Python.

This is accomplished in the transpiler grammar using `indent: true` on rules that represent a new indentation block, and `join_children_with: "\n"` to place child nodes on new lines.

#### Example: Transpiling JavaScript to Python

**`js_to_py_transpiler.yaml`**
```yaml
rules:
  function_definition:
    template: "def {name}({params}):\n{body}"
  NAME:
    use: "text"
  NUMBER:
    use: "value"
  parameters:
    join_children_with: ", "
    template: "{children}"
  statements:
    indent: true
    join_children_with: "\n"
    template: "{children}"
  assignment:
    template: "{target} = {value}"
  for_loop:
    template: "for i in range({limit}):\n{body}"
  return:
    template: "return {value}"
  binary_op:
    template: "{left} + {right}"
```

**Usage:**

```python
# Load the js_parser.yaml and js_to_py_transpiler.yaml grammars
# and instantiate the Parser and Transpiler.
parse_result = parser.parse(js_code)
if parse_result['status'] == 'success':
    translation = transpiler.transpile(parse_result['ast'])
    # The 'translation' variable now holds the transpiled Python code.
```

**Result:** The transpiler correctly indents the body of the Python function.

**Input JavaScript Code:**
```javascript
function f(x, y) {
    let a = 0;
    for (let i = 0; i < y; i++) {
        a = a + x;
    }
    return a;
}
```

**Output Python Code:**
```python
def f(x, y):
    a = 0
    for i in range(y):
        a = a + x
    return a
```

---

### Full Grammar and Directive Reference

#### Grammar Structure Keys

These keys define the actual parsing logic.

| Key                  | Description                                                                               | Value Type      | Example                                    |
| :------------------- | :---------------------------------------------------------------------------------------- | :-------------- | :----------------------------------------- |
| `literal`            | Matches an exact string of text.                                                          | `string`        | `{ literal: "if" }`                        |
| `regex`              | Matches text against a regular expression.                                                | `string`        | `{ regex: "-?\\d+" }`                      |
| `rule`               | References another rule by its name.                                                      | `string`        | `{ rule: expression }`                     |
| `token`              | Matches a token by type name (used when a `lexer` is defined).                            | `string`        | `{ token: "NAME" }`                        |
| `sequence`           | Matches a series of rules in a specific order.                                            | `list` of rules | `{ sequence: [ {rule: A}, {rule: B} ] }`   |
| `choice`             | Matches one of several possible rules. Tries them in order.                               | `list` of rules | `{ choice: [ {rule: A}, {rule: B} }`       |
| `zero_or_more`       | Matches the given rule zero or more times (`*`).                                          | A single rule   | `{ zero_or_more: {rule: A} }`              |
| `one_or_more`        | Matches the given rule one or more times (`+`).                                           | A single rule   | `{ one_or_more: {rule: A} }`               |
| `optional`           | Matches the given rule zero or one time (`?`).                                            | A single rule   | `{ optional: {rule: A} }`                  |
| `positive_lookahead` | Asserts that the text ahead matches the rule, but does not consume text (`&`).            | A single rule   | `{ positive_lookahead: {literal: "TO"} }`  |
| `negative_lookahead` | Asserts that the text ahead does **not** match the rule, but does not consume text (`!`). | A single rule   | `{ negative_lookahead: {literal: "END"} }` |

#### The `lexer` Block (Parser Grammar)

A top-level key in the parser grammar that defines how to tokenize the input string before parsing.

| Key      | Description                                                                                              | Value Type     |
| :------- | :------------------------------------------------------------------------------------------------------- | :------------- |
| `tokens` | An ordered list of token specifications. The first one to match the longest string is chosen.            | `list` of dict |

Each item in the `tokens` list is a dictionary:

| Key      | Description                                                                        |
| :------- | :--------------------------------------------------------------------------------- |
| `regex`  | The regular expression to match a token.                                           |
| `token`  | The type name for the created token (e.g., `NAME`).                                |
| `action` | Special behavior. `skip` discards the token; `handle_indent` manages indentation.  |
| `ast`    | An `ast` block to attach properties (like `type: "number"`) directly to the token. |

#### The `ast` Block (Parser Grammar)

The `ast` block controls how the Abstract Syntax Tree is constructed for a given rule.

| Key         | Description                                                                                                                                         | Example                                     |
| :---------- | :-------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------------------------ |
| `tag`       | Renames the node in the final AST. Useful for creating cleaner, more abstract node types.                                                           | `ast: { tag: "clone_to" }`                  |
| `discard`   | Throws away the node created by this rule. It will not appear in the AST. Essential for whitespace, comments, and syntactic sugar.                  | `ast: { discard: true }`                    |
| `promote`   | Replaces the current node with its child node in the AST. This is used to simplify the tree by removing unnecessary intermediate nodes.             | `ast: { promote: true }`                    |
| `leaf`      | Marks this as a terminal node in the AST. It will have no children, even if it's composed of other rules. Its `text` and `value` are preserved.     | `ast: { leaf: true }`                       |
| `type`      | Adds a data type hint to a leaf node. Supported types: `number`, `bool`, `null`.                                                                    | `ast: { leaf: true, type: "number" }`       |
| `name`      | In a `sequence`, assigns a name to a specific child. This causes the parent's `children` attribute in the AST to be a dictionary instead of a list. | `{ rule: path, ast: { name: "repo" } }`     |
| `structure` | A powerful directive that automatically builds complex tree structures.                                                                             | `ast: { structure: "left_associative_op" }` |

##### Why Use `tag`?

The `tag` directive provides three powerful advantages: **decoupling, abstraction, and clarity**.

1.  **Decoupling Grammar from AST:** The name of a rule often describes its **syntactic role** (what it does for parsing, like `term` or `factor`), while the tag describes its **semantic meaning** (what it _is_, like a `binary_op`). This allows the grammar to be structured for correct parsing (e.g., operator precedence) while producing a simple, semantic AST for the next stage.

2.  **Creating Abstract Concepts:** A `tag` allows you to create a single, unified AST node type from multiple different syntactic forms. For example, a language might have `let_statement` and `const_statement` rules, but both can be given the tag `variable_declaration`, simplifying the code that consumes the AST.

3.  **Improving Grammar Readability:** Sometimes, a rule needs a long, descriptive name to be clear (e.g., `statement_ending_with_optional_semicolon`), but you want a short, concise name in your AST (e.g., `statement`).

##### `structure` Types:

- `"left_associative_op"`: Automatically builds a left-leaning binary operation tree.
- `"right_associative_op"`: Automatically builds a right-leaning binary operation tree.
- **Dictionary**: A dictionary defining a custom structure.
    - `tag`: The tag for the new node.
    - `map_children`: A dictionary mapping parts of the rule to named children in the new AST node. E.g., `map_children: { name: { from_child: 1 } }`. This makes the mapping robust against optional/discarded children.

#### The Transpiler Grammar

The transpiler grammar is a separate file that defines how to convert a finished AST into an output string. It contains a single top-level `rules` key. Each key under `rules` corresponds to an AST node `tag`.

| Key                  | Description                                                                                                                                                                     |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `template`           | Uses a Python f-string-like template for output. Placeholders like `{repo}` are filled in from the AST node's `children`, or special keys like `{left}`, `{right}`, and `{op}`. |
| `use`                | Uses a specific property from the AST node. `"use: "value"` for numbers/bools, `"use: "text"` for identifiers/strings.                                                          |
| `value`              | Provides a hardcoded string as the output for this node. Perfect for converting operators into function names.                                                                  |
| `cases`              | A list of conditional rules to select a template, providing if/else-if/else logic. See below for details.                                                                       |
| `state_set`          | A dictionary to set variables in the transpiler's state after the node is processed. E.g., `{ "vars.{name}": True }`.                                                            |
| `join_children_with` | For nodes with list-based children, specifies the separator (e.g., `", "` or `"\n"`).                                                                                            |
| `indent`             | If `true`, the output of this rule's children will be indented one level. Used for generating code for indented languages like Python.                                           |

##### Conditional Transpilation with `cases`

The `cases` block is a list of dictionaries, evaluated in order. The first one that matches is used.

-   A case dictionary can have an `if` and a `then` key, or a single `default` key.
-   The `if` key holds a **condition dictionary**:
    -   `path`: A dot-notation path to a value to check (e.g., `node.text` or `state.vars.{name}`).
    -   `equals`: (Optional) If present, checks for equality with the value at `path`. If omitted, checks for existence (truthiness).
    -   `negate`: (Optional) If `true`, inverts the result of the check.

Example:
```yaml
cases:
  - if: { path: 'state.vars.{target}', negate: true }
    then: "let {target} = {value};"
  - default: "{target} = {value};"
```

## Author

The Koine engine was developed by **Chris Bates**.

- https://github.com/chrsbats

## Acknowledgements

This project was made possible by the foundational ideas and early conceptual prototypes developed by **Adam Griffiths**. Their insights into creating a fully data-driven parsing pipeline were instrumental in shaping the final architecture and philosophy of Koine.

- https://github.com/adamlwgriffiths

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
