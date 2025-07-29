import pytest
import yaml
from koine import Parser

def test_promote_behavior_comprehensive():
    """
    Comprehensive test to understand when promote: true does and doesn't return lists.
    This will help us understand the exact behavior with sequences, zero_or_more, and nesting.
    """

    # Test 1: Basic sequence with promote: true
    grammar1 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'a'},
                    {'literal': 'b'}
                ]
            }
        }
    }
    parser1 = Parser(grammar1)
    result1 = parser1.parse('ab')
    print(f"Test 1 - Basic sequence with promote: {type(result1)} = {result1}")

    # Test 2: Sequence with one item and promote: true
    grammar2 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'a'}
                ]
            }
        }
    }
    parser2 = Parser(grammar2)
    result2 = parser2.parse('a')
    print(f"Test 2 - Single item sequence with promote: {type(result2)} = {result2}")

    # Test 3: zero_or_more with promote: true (should always be list)
    grammar3 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'zero_or_more': {'literal': 'a'}
            }
        }
    }
    parser3 = Parser(grammar3)
    result3a = parser3.parse('')  # zero matches
    result3b = parser3.parse('a')  # one match
    result3c = parser3.parse('aaa')  # multiple matches
    print(f"Test 3a - zero_or_more (0 items) with promote: {type(result3a)} = {result3a}")
    print(f"Test 3b - zero_or_more (1 item) with promote: {type(result3b)} = {result3b}")
    print(f"Test 3c - zero_or_more (3 items) with promote: {type(result3c)} = {result3c}")

    # Test 4: Nested - sequence containing zero_or_more with promote
    grammar4 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'start'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {'literal': 'a'}
                    }
                ]
            }
        }
    }
    parser4 = Parser(grammar4)
    result4a = parser4.parse('start')  # zero 'a's
    result4b = parser4.parse('starta')  # one 'a'
    result4c = parser4.parse('startaaa')  # multiple 'a's
    print(f"Test 4a - Nested sequence+zero_or_more (0 items): {type(result4a)} = {result4a}")
    print(f"Test 4b - Nested sequence+zero_or_more (1 item): {type(result4b)} = {result4b}")
    print(f"Test 4c - Nested sequence+zero_or_more (3 items): {type(result4c)} = {result4c}")

    # Test 5: The SLIP-like case - sequence with first item + zero_or_more
    grammar5 = {
        'start_rule': 'path_content',
        'rules': {
            'path_content': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            }
        }
    }
    parser5 = Parser(grammar5)
    result5a = parser5.parse('a')  # single segment
    result5b = parser5.parse('a.b')  # two segments
    result5c = parser5.parse('a.b.c')  # three segments
    print(f"Test 5a - SLIP-like (1 segment): {type(result5a)} = {result5a}")
    print(f"Test 5b - SLIP-like (2 segments): {type(result5b)} = {result5b}")
    print(f"Test 5c - SLIP-like (3 segments): {type(result5c)} = {result5c}")

    # Test 6: Same as Test 5 but WITHOUT promote on the outer sequence
    grammar6 = {
        'start_rule': 'path_content',
        'rules': {
            'path_content': {
                # No promote here!
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            }
        }
    }
    parser6 = Parser(grammar6)
    result6a = parser6.parse('a')  # single segment
    result6b = parser6.parse('a.b')  # two segments
    result6c = parser6.parse('a.b.c')  # three segments
    print(f"Test 6a - SLIP-like WITHOUT outer promote (1 segment): {type(result6a)} = {result6a}")
    print(f"Test 6b - SLIP-like WITHOUT outer promote (2 segments): {type(result6b)} = {result6b}")
    print(f"Test 6c - SLIP-like WITHOUT outer promote (3 segments): {type(result6c)} = {result6c}")

    # Test 7: Choice with promote
    grammar7 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'choice': [
                    {'literal': 'a'},
                    {'literal': 'b'}
                ]
            }
        }
    }
    parser7 = Parser(grammar7)
    result7a = parser7.parse('a')
    result7b = parser7.parse('b')
    print(f"Test 7a - Choice with promote (option a): {type(result7a)} = {result7a}")
    print(f"Test 7b - Choice with promote (option b): {type(result7b)} = {result7b}")

def test_slip_path_issue_reproduction():
    """
    Reproduce the exact issue from the SLIP grammar where path segments
    are not being returned as lists when there's only one segment.
    """

    # This mimics the current SLIP grammar structure
    slip_grammar = {
        'start_rule': 'set_path_target',
        'rules': {
            'set_path_target': {
                'ast': {'promote': True},
                'choice': [
                    {'rule': 'path_content_no_pipe'},
                    {'rule': 'group'}
                ]
            },
            'path_content_no_pipe': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'path_content'}
                ]
            },
            'path_content': {
                'ast': {'promote': True},  # This is the problematic line
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            },
            'group': {
                'ast': {'tag': 'group'},
                'sequence': [
                    {'literal': '(', 'ast': {'discard': True}},
                    {'literal': 'x'},
                    {'literal': ')', 'ast': {'discard': True}}
                ]
            }
        }
    }

    parser = Parser(slip_grammar)

    # Test single segment (this should be a list but might not be)
    result_single = parser.parse('a')
    print(f"SLIP single segment result: {result_single}")

    # Test multiple segments (this should definitely be a list)
    result_multiple = parser.parse('a.b')
    print(f"SLIP multiple segments result: {result_multiple}")

    # Let's also test what happens without the promote on path_content
    slip_grammar_fixed = slip_grammar.copy()
    slip_grammar_fixed['rules'] = slip_grammar['rules'].copy()
    slip_grammar_fixed['rules']['path_content'] = {
        # Remove promote: True
        'sequence': [
            {'rule': 'path_segment'},
            {
                'ast': {'promote': True},
                'zero_or_more': {
                    'sequence': [
                        {'literal': '.', 'ast': {'discard': True}},
                        {'rule': 'path_segment'}
                    ]
                }
            }
        ]
    }

    parser_fixed = Parser(slip_grammar_fixed)
    result_single_fixed = parser_fixed.parse('a')
    result_multiple_fixed = parser_fixed.parse('a.b')
    print(f"SLIP FIXED single segment result: {result_single_fixed}")
    print(f"SLIP FIXED multiple segments result: {result_multiple_fixed}")

import pytest
import yaml
from koine import Parser

def test_promote_behavior_comprehensive():
    """
    Comprehensive test to understand when promote: true does and doesn't return lists.
    This will help us understand the exact behavior with sequences, zero_or_more, and nesting.
    """

    # Test 1: Basic sequence with promote: true
    grammar1 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'a'},
                    {'literal': 'b'}
                ]
            }
        }
    }
    parser1 = Parser(grammar1)
    result1 = parser1.parse('ab')
    print(f"Test 1 - Basic sequence with promote: {type(result1)} = {result1}")

    # Test 2: Sequence with one item and promote: true
    grammar2 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'a'}
                ]
            }
        }
    }
    parser2 = Parser(grammar2)
    result2 = parser2.parse('a')
    print(f"Test 2 - Single item sequence with promote: {type(result2)} = {result2}")

    # Test 3: zero_or_more with promote: true (should always be list)
    grammar3 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'zero_or_more': {'literal': 'a'}
            }
        }
    }
    parser3 = Parser(grammar3)
    result3a = parser3.parse('')  # zero matches
    result3b = parser3.parse('a')  # one match
    result3c = parser3.parse('aaa')  # multiple matches
    print(f"Test 3a - zero_or_more (0 items) with promote: {type(result3a)} = {result3a}")
    print(f"Test 3b - zero_or_more (1 item) with promote: {type(result3b)} = {result3b}")
    print(f"Test 3c - zero_or_more (3 items) with promote: {type(result3c)} = {result3c}")

    # Test 4: Nested - sequence containing zero_or_more with promote
    grammar4 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'literal': 'start'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {'literal': 'a'}
                    }
                ]
            }
        }
    }
    parser4 = Parser(grammar4)
    result4a = parser4.parse('start')  # zero 'a's
    result4b = parser4.parse('starta')  # one 'a'
    result4c = parser4.parse('startaaa')  # multiple 'a's
    print(f"Test 4a - Nested sequence+zero_or_more (0 items): {type(result4a)} = {result4a}")
    print(f"Test 4b - Nested sequence+zero_or_more (1 item): {type(result4b)} = {result4b}")
    print(f"Test 4c - Nested sequence+zero_or_more (3 items): {type(result4c)} = {result4c}")

    # Test 5: The SLIP-like case - sequence with first item + zero_or_more
    grammar5 = {
        'start_rule': 'path_content',
        'rules': {
            'path_content': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            }
        }
    }
    parser5 = Parser(grammar5)
    result5a = parser5.parse('a')  # single segment
    result5b = parser5.parse('a.b')  # two segments
    result5c = parser5.parse('a.b.c')  # three segments
    print(f"Test 5a - SLIP-like (1 segment): {type(result5a)} = {result5a}")
    print(f"Test 5b - SLIP-like (2 segments): {type(result5b)} = {result5b}")
    print(f"Test 5c - SLIP-like (3 segments): {type(result5c)} = {result5c}")

    # Test 6: Same as Test 5 but WITHOUT promote on the outer sequence
    grammar6 = {
        'start_rule': 'path_content',
        'rules': {
            'path_content': {
                # No promote here!
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            }
        }
    }
    parser6 = Parser(grammar6)
    result6a = parser6.parse('a')  # single segment
    result6b = parser6.parse('a.b')  # two segments
    result6c = parser6.parse('a.b.c')  # three segments
    print(f"Test 6a - SLIP-like WITHOUT outer promote (1 segment): {type(result6a)} = {result6a}")
    print(f"Test 6b - SLIP-like WITHOUT outer promote (2 segments): {type(result6b)} = {result6b}")
    print(f"Test 6c - SLIP-like WITHOUT outer promote (3 segments): {type(result6c)} = {result6c}")

    # Test 7: Choice with promote
    grammar7 = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'choice': [
                    {'literal': 'a'},
                    {'literal': 'b'}
                ]
            }
        }
    }
    parser7 = Parser(grammar7)
    result7a = parser7.parse('a')
    result7b = parser7.parse('b')
    print(f"Test 7a - Choice with promote (option a): {type(result7a)} = {result7a}")
    print(f"Test 7b - Choice with promote (option b): {type(result7b)} = {result7b}")

def test_slip_path_issue_reproduction():
    """
    Reproduce the exact issue from the SLIP grammar where path segments
    are not being returned as lists when there's only one segment.
    """

    # This mimics the current SLIP grammar structure
    slip_grammar = {
        'start_rule': 'set_path_target',
        'rules': {
            'set_path_target': {
                'ast': {'promote': True},
                'choice': [
                    {'rule': 'path_content_no_pipe'},
                    {'rule': 'group'}
                ]
            },
            'path_content_no_pipe': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'path_content'}
                ]
            },
            'path_content': {
                'ast': {'promote': True},  # This is the problematic line
                'sequence': [
                    {'rule': 'path_segment'},
                    {
                        'ast': {'promote': True},
                        'zero_or_more': {
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'path_segment'}
                            ]
                        }
                    }
                ]
            },
            'path_segment': {
                'ast': {'tag': 'name', 'leaf': True},
                'regex': '[a-zA-Z]+'
            },
            'group': {
                'ast': {'tag': 'group'},
                'sequence': [
                    {'literal': '(', 'ast': {'discard': True}},
                    {'literal': 'x'},
                    {'literal': ')', 'ast': {'discard': True}}
                ]
            }
        }
    }

    parser = Parser(slip_grammar)

    # Test single segment (this should be a list but might not be)
    result_single = parser.parse('a')
    print(f"SLIP single segment result: {result_single}")

    # Test multiple segments (this should definitely be a list)
    result_multiple = parser.parse('a.b')
    print(f"SLIP multiple segments result: {result_multiple}")

    # Let's also test what happens without the promote on path_content
    slip_grammar_fixed = slip_grammar.copy()
    slip_grammar_fixed['rules'] = slip_grammar['rules'].copy()
    slip_grammar_fixed['rules']['path_content'] = {
        # Remove promote: True
        'sequence': [
            {'rule': 'path_segment'},
            {
                'ast': {'promote': True},
                'zero_or_more': {
                    'sequence': [
                        {'literal': '.', 'ast': {'discard': True}},
                        {'rule': 'path_segment'}
                    ]
                }
            }
        ]
    }

    parser_fixed = Parser(slip_grammar_fixed)
    result_single_fixed = parser_fixed.parse('a')
    result_multiple_fixed = parser_fixed.parse('a.b')
    print(f"SLIP FIXED single segment result: {result_single_fixed}")
    print(f"SLIP FIXED multiple segments result: {result_multiple_fixed}")

def test_promote_bug_with_nested_list_child():
    """
    This test aims to reproduce a suspected bug in Koine's `promote: true`
    on a sequence. The hypothesis is that if a sequence has multiple children,
    and one of the children is itself a list, the promotion might incorrectly
    return only the first child instead of a list of all children.

    This behavior would explain why `user.name` was being parsed as `user`
    in the SLIP grammar, as the `path_content` rule's sequence would have
    children `[<name 'user'>, [<name 'name'>]]`, and the bug would cause
    only the first element to be returned.
    """
    grammar = {
        'start_rule': 'test',
        'rules': {
            'test': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'item_a'},
                    {'rule': 'list_of_b'}
                ]
            },
            'item_a': {
                'ast': {'tag': 'item_a', 'leaf': True},
                'literal': 'a'
            },
            'list_of_b': {
                # This rule produces a list of nodes, which should be promoted
                # to flatten into the parent.
                'ast': {'promote': True},
                'one_or_more': {
                    'ast': {'tag': 'item_b', 'leaf': True},
                    'literal': 'b'
                }
            }
        }
    }
    parser = Parser(grammar)
    # The AST is in the 'ast' key of the result dictionary.
    result = parser.parse('abb')['ast']

    # The `promote: true` directive on a sequence is designed to flatten nested
    # lists of children into a single list. This test now verifies that behavior.
    assert isinstance(result, list), f"Result of promoted sequence should be a list, but was {type(result)}"
    assert len(result) == 3, f"Result should have three flattened children, but had {len(result)}"

    # Check the children's types and content
    assert isinstance(result[0], dict)
    assert result[0]['tag'] == 'item_a'
    assert isinstance(result[1], dict)
    assert result[1]['tag'] == 'item_b'
    assert isinstance(result[2], dict)
    assert result[2]['tag'] == 'item_b'

def test_promote_on_sequence_with_quantifier_child():
    """
    Tests the exact structure causing the SLIP parser to fail.
    The structure is a promoted sequence with two children:
    1. A single rule.
    2. A `zero_or_more` quantifier that produces a list of other nodes.

    The hypothesis is that `promote: true` on the parent sequence is
    behaving unexpectedly when one of its direct children is a quantifier
    that returns a list. It seems to be dropping the result of the quantifier.
    """
    grammar = {
        'start_rule': 'path',
        'rules': {
            'path': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'segment'}, # First child
                    { # Second child is the quantifier itself
                        'ast': {'promote': True},
                        'zero_or_more': {
                             # The content of the quantifier
                            'sequence': [
                                {'literal': '.', 'ast': {'discard': True}},
                                {'rule': 'segment'}
                            ]
                        }
                    }
                ]
            },
            'segment': {
                'ast': {'tag': 'seg', 'leaf': True},
                'regex': '[a-z]+'
            }
        }
    }
    parser = Parser(grammar)

    # Test case 1: single segment. The zero_or_more matches zero times.
    result_single = parser.parse('a')['ast']
    assert isinstance(result_single, list), "A promoted sequence should always return a list (single item case)"
    assert len(result_single) == 1, "Should have one segment"
    assert result_single[0]['tag'] == 'seg'
    assert result_single[0]['text'] == 'a'

    # Test case 2: multiple segments. This is the one that fails in slip_parser.
    result_multi = parser.parse('a.b')['ast']
    assert isinstance(result_multi, list), "A promoted sequence should always return a list (multi-item case)"
    assert len(result_multi) == 2, f"Should have two segments, but got {len(result_multi)}"
    assert result_multi[0]['tag'] == 'seg' and result_multi[0]['text'] == 'a'
    assert result_multi[1]['tag'] == 'seg' and result_multi[1]['text'] == 'b'


def test_deeply_nested_promote_flattens_all_levels():
    """
    Tests that `promote: true` correctly flattens children when promotion
    is nested several levels deep. For example, if rule A promotes rule B,
    and rule B promotes rule C, the children of C should appear flattened
    directly in A's result.
    """
    grammar = {
        'start_rule': 'rule_a',
        'rules': {
            'rule_a': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'item_a'},
                    {'rule': 'rule_b'}
                ]
            },
            'rule_b': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'item_b'},
                    {'rule': 'rule_c'}
                ]
            },
            'rule_c': {
                'ast': {'promote': True},
                'one_or_more': {'rule': 'item_c'}
            },
            'item_a': {'ast': {'tag': 'item_a', 'leaf': True}, 'literal': 'a'},
            'item_b': {'ast': {'tag': 'item_b', 'leaf': True}, 'literal': 'b'},
            'item_c': {'ast': {'tag': 'item_c', 'leaf': True}, 'literal': 'c'}
        }
    }
    parser = Parser(grammar)
    result = parser.parse('abcc')['ast']

    assert isinstance(result, list)
    assert len(result) == 4, f"Expected 4 flattened items, but got {len(result)}"
    assert result[0]['tag'] == 'item_a'
    assert result[1]['tag'] == 'item_b'
    assert result[2]['tag'] == 'item_c'
    assert result[3]['tag'] == 'item_c'


def test_promote_flattens_mixed_child_types_in_sequence():
    """
    Tests that `promote: true` on a sequence correctly flattens children
    when the children are a mix of a single AST node and a list of AST nodes.

    This scenario is critical for list-like structures, e.g., `item (',' item)*`
    where the sequence children might be `[<item_node>, [<item_node>, ...]]`.
    The promotion should "deeply flatten" this into a single list.
    """
    grammar = {
        'start_rule': 'list',
        'rules': {
            'list': {
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'item'},       # This child is a single node
                    {'rule': 'sub_list'}    # This child is a list of nodes
                ]
            },
            'sub_list': {
                'ast': {'promote': True},
                'one_or_more': {
                    'rule': 'item'
                }
            },
            'item': {
                'ast': {'tag': 'item', 'leaf': True},
                'regex': '[a-z]'
            }
        }
    }
    parser = Parser(grammar)
    # 'a' is matched by the first 'item'
    # 'bc' is matched by 'sub_list', which produces a list of two items
    # The children of 'list' before promotion will be: [<item 'a'>, [<item 'b'>, <item 'c'>]]
    result = parser.parse('abc')['ast']

    assert isinstance(result, list), f"Promoted sequence should always return a list, but got {type(result)}"
    assert len(result) == 3, f"Expected 3 flattened children, but got {len(result)}"
    assert result[0]['tag'] == 'item' and result[0]['text'] == 'a'
    assert result[1]['tag'] == 'item' and result[1]['text'] == 'b'
    assert result[2]['tag'] == 'item' and result[2]['text'] == 'c'


def test_promote_of_buggy_sequence_as_named_child():
    """
    This test aims to reproduce the SLIP parser bug by combining all the
    suspected elements into a minimal grammar. The hypothesis is that the bug
    in Koine's `promote: true` is triggered by a specific combination of factors:

    1. A parent rule (`parent`) uses a named child (`ast: {name: 'the_list'}`).
    2. The rule for that child (`buggy_list`) is a sequence with `promote: true`.
    3. That sequence has children that result in a `[<node>, <list>]` structure,
       which is the pattern that seems to trigger the bug.
    4. The bug manifests as the promotion incorrectly returning only the first
       `<node>` instead of a flattened list of all children.

    This exact structure exists in the SLIP grammar, where the `set_path` rule
    has a named child `path` that resolves to the `path_content` rule, which
    exhibits the `[<node>, <list>]` behavior.
    """
    grammar = {
        'start_rule': 'parent',
        'rules': {
            'parent': {
                'ast': {'tag': 'parent'},
                'sequence': [
                    {'rule': 'buggy_list', 'ast': {'name': 'the_list'}}
                ]
            },
            'buggy_list': {
                # This rule should produce a flat list of 3 children.
                'ast': {'promote': True},
                'sequence': [
                    {'rule': 'item_a'},
                    {'rule': 'list_of_b'}
                ]
            },
            'item_a': {
                'ast': {'tag': 'item_a', 'leaf': True},
                'literal': 'a'
            },
            'list_of_b': {
                # This rule produces a list of 'b' nodes.
                'ast': {'promote': True},
                'one_or_more': {
                    'ast': {'tag': 'item_b', 'leaf': True},
                    'literal': 'b'
                }
            }
        }
    }
    parser = Parser(grammar)
    result = parser.parse('abb')['ast']

    # The result should be a parent node with a dictionary of children.
    assert 'the_list' in result['children'], "Parent node should have a 'the_list' child."

    # The 'the_list' child should be a list containing all the flattened items.
    the_list = result['children']['the_list']

    # This is the key assertion that should fail if the bug is present.
    # The bug causes `the_list` to be a single dict node instead of a list.
    assert isinstance(the_list, list), \
        f"Named child from promoted list should be a list, but was {type(the_list)}"

    assert len(the_list) == 3, \
        f"Named child list should have 3 items, but has {len(the_list)}. Got: {the_list}"

    # Check the children's types and content
    assert the_list[0]['tag'] == 'item_a'
    assert the_list[1]['tag'] == 'item_b'
    assert the_list[2]['tag'] == 'item_b'


if __name__ == "__main__":
    print("=== Comprehensive Promote Behavior Tests ===")
    test_promote_behavior_comprehensive()
    print("\n=== SLIP Path Issue Reproduction ===")
    test_slip_path_issue_reproduction()

