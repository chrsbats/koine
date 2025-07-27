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

## Why Koine?

Koine is designed for people building DSLs, not compilers. If you've struggled with Lark's lookahead limitations or ANTLR's codegen overhead, Koine offers a different model: fully declarative grammar, AST, and transpilation—defined entirely as JSON/YAML.

It was built for environments where you want to **write, modify, or interpret grammars at runtime**—such as agent scripting, game modding, or interactive systems that evolve on the fly.

➡️ [Read the full rationale](RATIONALE.md)

### Philosophy and When to Use Koine

Koine is designed to be an exceptionally fast tool for **prototyping Domain-Specific Languages (DSLs)** and other custom parsers. Its "configuration-over-code" approach makes it ideal for tasks where clarity, portability of the grammar, and development speed are more important than raw parsing performance.

**Use Koine When:**

- **You are building a DSL:** For query languages, configuration formats, or command languages.
- **You need to parse complex but small-to-medium sized data:** Where the cost of building a traditional parser is too high.
- **You value a declarative, data-driven grammar:** The grammar can be stored as simple data (JSON/YAML) and is portable to other potential Koine engine implementations.
- **You are prototyping language ideas:** The entire lex->parse->transpile pipeline can be defined and modified quickly.

**Consider Other Tools When:**

- **You need extreme performance:** Koine is not designed to compete with high-performance compilers like `gcc` or `ANTLR` for parsing millions of lines of code.
- **You require complex semantic analysis:** If your transpilation logic requires deep, stateful analysis (e.g., advanced type inference, complex symbol tables), a traditional visitor pattern in a general-purpose language may be more suitable.
- **You need sophisticated error recovery:** Koine reports the first syntax error it finds and stops.

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
    # A grammar that handles precedence (* before +) and parentheses.
    start_rule: expression
    rules:
      expression:
        ast: { structure: "left_associative_op" }
        sequence:
          - { rule: term }
          - zero_or_more:
              sequence:
                [{ rule: _ }, { rule: add_op }, { rule: _ }, { rule: term }]
      term:
        ast: { structure: "left_associative_op" }
        sequence:
          - { rule: factor }
          - zero_or_more:
              sequence:
                [{ rule: _ }, { rule: mul_op }, { rule: _ }, { rule: factor }]
      factor:
        ast: { promote: true }
        choice:
          - { rule: number }
          - sequence:
              - { literal: "(", ast: { discard: true } }
              - { rule: _ }
              - { rule: expression }
              - { rule: _ }
              - { literal: ")", ast: { discard: true } }
      add_op:
        ast: { promote: true }
        choice:
          - { literal: "+", ast: { tag: "add_op" } }
          - { literal: "-", ast: { tag: "add_op" } }
      mul_op:
        ast: { promote: true }
        choice:
          - { literal: "*", ast: { tag: "mul_op" } }
          - { literal: "/", ast: { tag: "mul_op" } }
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
    source_code = "2 * (3 + 4)"
    parse_result = parser.parse(source_code)

    if parse_result['status'] == 'success':
        # The parser produces a structured AST (as a dictionary)
        ast = parse_result['ast']
        print("Intermediate AST:")
        import json
        print(json.dumps(ast, indent=2))

        # The transpiler consumes the AST to produce the final string
        translation = transpiler.transpile(ast)
        print(f"\nInput: '{source_code}'")
        print(f"Output: {translation}")
    else:
        print(f"Error: {parse_result['message']}")
    ```

4.  **Run it:**

    ```
    Intermediate AST:
    {
      "tag": "binary_op",
      "op": {
        "tag": "mul_op",
        "text": "*",
        "line": 1,
        "col": 3
      },
      "left": {
        "tag": "number",
        "text": "2",
        "line": 1,
        "col": 1,
        "value": 2
      },
      "right": {
        "tag": "binary_op",
        "op": {
          "tag": "add_op",
          "text": "+",
          "line": 1,
          "col": 8
        },
        "left": {
          "tag": "number",
          "text": "3",
          "line": 1,
          "col": 6,
          "value": 3
        },
        "right": {
          "tag": "number",
          "text": "4",
          "line": 1,
          "col": 10,
          "value": 4
        }
      }
    }

    Input: '2 * (3 + 4)'
    Output: (mul 2 (add 3 4))
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

The parser produces the following AST, which becomes the input for the transpiler. Note the `op` node with `"text": "-"` which will be handled by the `cases` directive in the transpiler.

```json
{
  "tag": "binary_op",
  "op": { "tag": "power_op", "text": "^", "line": 1, "col": 17 },
  "left": {
    "tag": "binary_op",
    "op": { "tag": "mul_op", "text": "*", "line": 1, "col": 11 },
    "left": {
      "tag": "binary_op",
      "op": { "tag": "add_op", "text": "-", "line": 1, "col": 5 },
      "left": { "tag": "number", "text": "2", "line": 1, "col": 3, "value": 2 },
      "right": {
        "tag": "number",
        "text": "3",
        "line": 1,
        "col": 7,
        "value": 3
      },
      "line": 1,
      "col": 5
    },
    "right": { "tag": "number", "text": "4", "line": 1, "col": 13, "value": 4 },
    "line": 1,
    "col": 11
  },
  "right": { "tag": "number", "text": "5", "line": 1, "col": 19, "value": 5 },
  "line": 1,
  "col": 17
}
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

Parsing the Python code with `py_parser.yaml` yields the following AST. This structure, with its named children like `iterator`, `limit`, and `body`, is what the transpiler will transform.

```json
{
  "tag": "function_definition",
  "children": {
    "name": { "tag": "NAME", "text": "f", "line": 1, "col": 5 },
    "params": {
      "tag": "parameters",
      "children": [
        { "tag": "NAME", "text": "x", "line": 1, "col": 7 },
        { "tag": "NAME", "text": "y", "line": 1, "col": 10 }
      ]
    },
    "body": [
      {
        "tag": "assignment",
        "children": {
          "target": { "tag": "NAME", "text": "a", "line": 2, "col": 5 },
          "value": { "tag": "NUMBER", "value": 0, "line": 2, "col": 9 }
        }
      },
      {
        "tag": "for_loop",
        "children": {
          "iterator": { "tag": "NAME", "text": "i", "line": 3, "col": 9 },
          "limit": { "tag": "NAME", "text": "y", "line": 3, "col": 21 },
          "body": [
            {
              "tag": "assignment",
              "children": {
                "target": { "tag": "NAME", "text": "a", "line": 4, "col": 9 },
                "value": {
                  "tag": "binary_op",
                  "left": { "tag": "NAME", "text": "a", "line": 4, "col": 13 },
                  "right": { "tag": "NAME", "text": "x", "line": 4, "col": 17 }
                }
              }
            }
          ]
        }
      },
      {
        "tag": "return",
        "children": {
          "value": { "tag": "NAME", "text": "a", "line": 5, "col": 12 }
        }
      }
    ]
  }
}
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
      - if: { path: "state.vars.{target}", negate: true }
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

Parsing the JavaScript code with `js_parser.yaml` yields an AST. The `js_to_py_transpiler.yaml` will use the `indent` directive when processing the `statements` nodes to create a correctly indented Python code block.

```json
{
  "tag": "function_definition",
  "children": {
    "name": { "tag": "NAME", "text": "f" },
    "params": {
      "tag": "parameters",
      "children": [
        { "tag": "NAME", "text": "x" },
        { "tag": "NAME", "text": "y" }
      ]
    },
    "body": {
      "tag": "statements",
      "children": [
        {
          "tag": "assignment",
          "children": {
            "target": { "tag": "NAME", "text": "a" },
            "value": { "tag": "NUMBER", "value": 0 }
          }
        },
        {
          "tag": "for_loop",
          "children": {
            "limit": { "tag": "NAME", "text": "y" },
            "body": {
              "tag": "statements",
              "children": [
                {
                  "tag": "assignment",
                  "children": {
                    "target": { "tag": "NAME", "text": "a" },
                    "value": {
                      "tag": "binary_op",
                      "left": { "tag": "NAME", "text": "a" },
                      "right": { "tag": "NAME", "text": "x" }
                    }
                  }
                }
              ]
            }
          }
        },
        {
          "tag": "return",
          "children": {
            "value": { "tag": "NAME", "text": "a" }
          }
        }
      ]
    }
  }
}
```

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

## Documentation

For a complete guide to Koine's features, including detailed explanations and examples for every directive, please see the dedicated documentation files:

- **[PARSING.md](./PARSING.md)**: Covers everything related to parsing text into an AST, from grammar basics to advanced features like lookaheads and lexer-based tokenization.

- **[TRANSPILING.md](./TRANSPILING.md)**: Covers everything related to transforming an AST into text, including conditional logic, state management, and generating indented output.

## Author

The Koine engine was developed by **Chris Bates**.

- https://github.com/chrsbats

## Acknowledgements

This project was made possible by the foundational ideas and early conceptual prototypes developed by **Adam Griffiths**. Their insights into creating a fully data-driven parsing pipeline were instrumental in shaping the final architecture and philosophy of Koine.

- https://github.com/adamlwgriffiths

## License

This project is licensed under the MIT License. See the `LICENSE` file for details.
