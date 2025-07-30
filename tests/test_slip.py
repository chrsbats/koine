
from koine.parser import Parser
import yaml
import pytest

from pathlib import Path

def test_parser():
    """Loads the SLIP grammar and returns a Parser instance."""
    grammar_path = Path(__file__).parent / "slip_grammar.yaml"
    
    # Use Parser.from_file to correctly set the base path for subgrammars
    p = Parser.from_file(str(grammar_path))
    assert p
    
