# Transpiling with Koine: From AST to Text

```python
import yaml
from koine.parser import Parser, Transpiler

# Assume 'ast' is a pre-existing Abstract Syntax Tree from a parser.
# For example, after running:
#
# with open("parser_calc.yaml", "r") as f:
#     parser_grammar = yaml.safe_load(f)
# parser = Parser(parser_grammar)
# ast = parser.parse("2 + 3")['ast']

# 1. Load the transpiler grammar
with open("transpiler_calc.yaml", "r") as f:
    transpiler_grammar = yaml.safe_load(f)

# 2. Instantiate the transpiler
transpiler = Transpiler(transpiler_grammar)

# 3. Transpile the AST
# output_string = transpiler.transpile(ast)
# output_string is now "(add 2 3)"
```

This document is a comprehensive guide to Koine's transpiling capabilities. It explains how to take a structured Abstract Syntax Tree (AST), as produced by a Koine parser, and transform it into a new string format.

This guide focuses _exclusively_ on the transpiling pipeline: **AST -> Text**. The process of generating an AST from source code is covered in `PARSING.md`. We will assume you already have a valid AST.

---

## 1. The Anatomy of a Transpiler Grammar

A Koine transpiler grammar is a dictionary (often written in YAML) that defines how to convert each type of AST node into a string.

Its structure is simple: a top-level `rules` key, where each sub-key corresponds to the `tag` of an AST node.

**Example: A "Hello, world!" AST**

Let's start with a simple AST representing a greeting.

**Input AST:**

```json
{
  "tag": "greeting",
  "children": [{ "tag": "target", "text": "world" }]
}
```

**`transpiler.yaml`**

```yaml
rules:
  greeting:
    template: "Hello, {children}!" # '{children}' will be replaced by the transpiled children
  target:
    use: "text" # Use the 'text' property of the 'target' node
```

**Resulting Output:**

```
Hello, world!
```

**How it Works:**

1.  The transpiler begins at the root of the AST, which has the tag `"greeting"`.
2.  It finds the matching `greeting` rule in the transpiler grammar.
3.  The rule specifies `template: "Hello, {children}!"`. To resolve the `{children}` placeholder, the engine must first transpile all the children of the `greeting` node.
4.  The only child is a node with the tag `"target"`. The engine finds the `target` rule in the grammar.
5.  This rule specifies `use: "text"`, which instructs the engine to take the literal value of the `text` property from the AST node. In this case, that value is `"world"`.
6.  This result (`"world"`) is passed back up and substituted for `{children}` in the parent template.
7.  The final result is the string `Hello, world!`.

---

### 1.1. Global Transpiler Configuration

You can add a top-level `transpiler` block to your grammar file to control global settings. This is useful for customizing behavior like the indentation string used by the `indent` directive.

**`transpiler.yaml`**

```yaml
transpiler:
  indent: "  " # Use 2 spaces for indentation instead of the default 4.

rules:
  # ... your rules here
```

---

## 2. Core Directives for String Generation

These are the fundamental building blocks for defining your output format.

| Key                  | Description                                                                                                |
| :------------------- | :--------------------------------------------------------------------------------------------------------- |
| `template`           | Generates output from an f-string-like template. Replaces placeholders with transpiled child node content. |
| `use`                | Directly uses a specific property from the AST node, such as `value` or `text`.                            |
| `value`              | Provides a hardcoded string as the output for a node.                                                      |
| `join_children_with` | For nodes with list-based children, specifies the separator to use (e.g., `", "` or `"\n"`).               |

**Example: Transpiling a Binary Operation**

Let's transpile a `binary_op` AST node into LISP-style s-expressions.

**Input AST:**

```json
{
  "tag": "binary_op",
  "op": { "tag": "add_op", "text": "+" },
  "left": { "tag": "number", "value": 2 },
  "right": { "tag": "number", "value": 3 }
}
```

**`transpiler.yaml`**

```yaml
rules:
  binary_op:
    # Special placeholders {left}, {right}, and {op} are available for these nodes.
    template: "({op} {left} {right})"

  add_op:
    # We want to convert the '+' symbol into the function name 'add'.
    value: "add"

  number:
    # We want the numeric value, not the raw text "2".
    use: "value"
```

**Resulting Output:**

```
(add 2 3)
```

**How it Works:**

1.  The transpiler starts at the `binary_op` node.
2.  It finds the `binary_op` rule, which has the template `({op} {left} {right})`. These special placeholders correspond to the named children of a `binary_op` node created by the parser.
3.  To resolve the placeholders, it recursively transpiles each child:
    - **`{op}`:** The `op` child node has the tag `add_op`. The `add_op` rule has a hardcoded `value: "add"`. The result is the string `"add"`.
    - **`{left}`:** The `left` child node has the tag `number`. The `number` rule says `use: "value"`, so the engine uses the `value` property from the AST node, which is the number `2`.
    - **`{right}`:** This is also a `number` node, which resolves to the number `3`.
4.  These results are substituted back into the template, producing `(add 2 3)`.

**Example: Joining List Children**

Let's transpile a function's parameter list.

**Input AST:**

```json
{
  "tag": "parameters",
  "children": [
    { "tag": "identifier", "text": "x" },
    { "tag": "identifier", "text": "y" }
  ]
}
```

**`transpiler.yaml`**

```yaml
rules:
  parameters:
    join_children_with: ", " # Use a comma and space to separate items
    template: "{children}" # '{children}' gets the joined string of all child nodes

  identifier:
    use: "text" # Each identifier just becomes its text
```

**Resulting Output:**

```
x, y
```

**How it Works:**

1.  The transpiler finds the `parameters` rule. This rule applies to an AST node whose `children` property is a list.
2.  The rule `join_children_with: ", "` tells the engine how to combine the results of transpiling each item in the children list.
3.  The engine iterates through the children:
    - The first child is an `identifier` node. Its rule is `use: "text"`, so it becomes the string `"x"`.
    - The second child is also an `identifier`, becoming the string `"y"`.
4.  The list of results `["x", "y"]` is joined together with `", "`, producing the string `"x, y"`.
5.  This joined string is then inserted into the `{children}` placeholder in the `template`.

#### Note on Fallback Behavior

If the transpiler encounters an AST node with a `tag` for which no rule is defined, it will not immediately fail. Instead, it attempts to find a suitable value on the node itself, in this order:

1. It looks for a `value` key (e.g., from a parser rule with `type: "number"`).
2. If not found, it looks for a `text` key.

This feature means you can omit simple rules. For example, if you have an AST node `{"tag": "identifier", "text": "my_var"}` and no `identifier` rule in your transpiler grammar, it will automatically resolve to `"my_var"`.

---

## 3. Conditional Logic with `cases`

The `cases` directive allows you to choose a template based on conditions, providing `if-elif-else` style logic. It is a list of rules, where the first one to match is used.

Each case can be an `if/then` block or a `default` block. The `if` block is a dictionary that defines the condition.

| Key      | Description                                                                                                                                                                                           |
| :------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `path`   | A dot-notation path to a value. The path can access node (the raw AST node) or state. It can also contain placeholders (e.g., {name}), which are resolved from transpiled children before evaluation. |
| `equals` | (Optional) Checks for equality. If omitted, the check is for existence/truthiness.                                                                                                                    |
| `negate` | (Optional) If `true`, inverts the result of the check.                                                                                                                                                |

**Example: Handling Multiple Operators**

Instead of a separate rule for `add_op` and `sub_op`, we can use one rule for both.

**Input AST:**

```json
{ "tag": "op", "text": "-" }
```

**`transpiler.yaml`**

```yaml
rules:
  op:
    cases:
      - if: { path: "node.text", equals: "+" }
        then: "add"
      - if: { path: "node.text", equals: "-" }
        then: "sub"
      - default: "unknown_op" # Fallback case
```

**Resulting Output:**

```
sub
```

**How it Works:**

1.  The transpiler starts at the `op` node.
2.  It finds the `op` rule and its `cases` block. It evaluates each case in order until one matches.
3.  It checks the first `if` condition: `path: "node.text", equals: "+"`. The `node.text` of our input AST is `"-"`, so this condition is false.
4.  It moves to the second `if` condition: `path: "node.text", equals: "-"`. This is true.
5.  The condition matches, so the transpiler uses the corresponding `then` value (`"sub"`) as the output for this node and stops evaluating further cases. If no cases had matched, it would have used the `default` value.

---

## 4. Stateful Transpilation

For some languages, the transpilation of a node depends on what has been transpiled before. Koine manages this with a `state` object that can be read by `cases` and modified by the `state_set` directive.

This is perfect for tasks like emitting `let` or `var` only for the first declaration of a variable.

- **`state`**: A dictionary available in `cases` conditions (e.g., `path: 'state.vars.{name}'`).
- **`state_set`**: A dictionary that sets values in the `state` object _after_ a node has been transpiled.

**Example: Declaring Variables with `let`**

We want to transpile Python `a = 1` to JavaScript `let a = 1;` but only the first time `a` is assigned. Subsequent assignments should be `a = 2;`.

**Input ASTs (processed in order):**

```json
{ "tag": "assignment", "children": { "target": {"text": "a"}, "value": {"value": 1} } }
{ "tag": "assignment", "children": { "target": {"text": "a"}, "value": {"value": 2} } }
```

**`transpiler.yaml`**

```yaml
rules:
  assignment:
    cases:
      # Check if 'state.vars.a' does NOT exist.
      # The {target} placeholder is filled before the path is evaluated.
      - if: { path: "state.vars.{target}", negate: true }
        then: "let {target} = {value};"

      # If it does exist, use the default template.
      - default: "{target} = {value};"

    # After transpiling, set 'state.vars.a' to True.
    state_set: { "vars.{target}": true }

  # Assume other rules for 'target' and 'value' exist...
```

**Resulting Output:**

```javascript
let a = 1;
a = 2;
```

**How it Works:**

This transpiler processes a sequence of AST nodes and maintains a `state` object across them.

**First AST Node (`a = 1`):**

1.  The `assignment` rule is found. Before evaluating the template, placeholders are resolved. `{target}` becomes `"a"` and `{value}` becomes `"1"`.
2.  The `cases` are evaluated. The first `if` condition checks `state.vars.a` (the path is formatted with the resolved placeholders).
3.  Initially, the `state` is empty, so `state.vars.a` does not exist. The `negate: true` directive inverts this non-existence, making the condition **true**.
4.  The `then` template is used, producing `let a = 1;`.
5.  _After_ the output is generated, the `state_set` directive runs. It sets the path `vars.a` in the internal state object to `True`. The state is now `{ "vars": { "a": true } }`.

**Second AST Node (`a = 2`):**

1.  The `assignment` rule is found again. Placeholders are resolved to `{target}`=`"a"` and `{value}`=`"2"`.
2.  The `cases` are evaluated. The `if` condition again checks for `state.vars.a`.
3.  This time, `state.vars.a` exists and is `True`. The `negate: true` inverts this, making the condition **false**.
4.  The first case fails, so the `default` case is used, producing `a = 2;`.
5.  The `state_set` directive runs again, simply re-setting `state.vars.a` to `True`.

---

## 5. Generating Indented Output

Koine can automatically handle indentation, which is essential when transpiling to languages like Python.

- **`indent: true`**: Specifies that the children of this node should be indented one level deeper.
- **`join_children_with: "\n"`**: Places each child on a new, correctly indented line.

**Example: Transpiling to a Python Function**

Let's generate a Python function, where the body must be indented.

**Input AST:**

```json
{
  "tag": "function",
  "children": {
    "name": { "text": "my_func" },
    "body": {
      "tag": "statements",
      "children": [
        {
          "tag": "assignment",
          "children": { "target": { "text": "a" }, "value": { "value": 1 } }
        },
        { "tag": "return", "children": { "value": { "text": "a" } } }
      ]
    }
  }
}
```

**`transpiler.yaml`**

```yaml
rules:
  function:
    # The body will be correctly placed on a new line and indented.
    template: "def {name}():\n{body}"

  statements:
    indent: true # Indent the children of this node
    join_children_with: "\n" # Put each child on a new line
    template: "{children}"

  assignment:
    template: "{target} = {value}"

  return:
    template: "return {value}"

  # ...other rules
```

**Resulting Output:**

```python
def my_func():
    a = 1
    return a
```

**How it Works:**

1.  The transpiler starts at the `function` node. Its template is `def {name}():\n{body}`. It resolves `{name}` to `"my_func"`.
2.  To resolve `{body}`, it must transpile the child `statements` node.
3.  The `statements` rule has `indent: true`. This tells the engine to **increase** the global indentation level for any output generated by its children.
4.  The rule also has `join_children_with: "\n"`. It recursively transpiles its children:
    - The `assignment` node becomes `"a = 1"`.
    - The `return` node becomes `"return a"`.
5.  These results are joined with a newline, producing a multi-line string: `a = 1\nreturn a`.
6.  The `template: "{children}"` in the `statements` rule uses this joined string. Because `indent: true` was active, the engine automatically prepends the correct indentation string (e.g., `"    "`) to each line of the result.
7.  The final, indented string for the `statements` node is `    a = 1\n    return a`.
8.  This string is substituted back into the `{body}` placeholder of the `function` rule. When the `statements` rule is finished, its `indent: true` directive also tells the engine to **decrease** the indentation level back to what it was before.

---

## Full Directive Reference

The transpiler grammar has two main parts: the optional top-level `transpiler` block for global settings, and the `rules` block for node-specific transformations.

#### Top-Level `transpiler` Block

| Key      | Description                                     | Default             |
| :------- | :---------------------------------------------- | :------------------ |
| `indent` | The string to use for one level of indentation. | `"    "` (4 spaces) |

#### `rules` Block Directives

Each key under `rules` corresponds to an AST node `tag`.

| Key                  | Description                                                                                                                                                                     |
| :------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `template`           | Uses a Python f-string-like template for output. Placeholders like `{repo}` are filled in from the AST node's `children`, or special keys like `{left}`, `{right}`, and `{op}`. |
| `use`                | Uses a specific property from the AST node. `"use: "value"` for numbers/bools, `"use: "text"` for identifiers/strings.                                                          |
| `value`              | Provides a hardcoded string as the output for this node. Perfect for converting operators into function names.                                                                  |
| `cases`              | A list of conditional rules to select a template, providing if/else-if/else logic.                                                                                              |
| `state_set`          | A dictionary to set variables in the transpiler's state after the node is processed. E.g., `{ "vars.{name}": True }`.                                                           |
| `join_children_with` | For nodes with list-based children, specifies the separator (e.g., `", "` or `"\n"`).                                                                                           |
| `indent`             | If `true`, the output of this rule's children will be indented one level. Used for generating code for indented languages like Python.                                          |
