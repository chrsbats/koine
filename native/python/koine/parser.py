"""Ordinary Python values over Koine's C interface."""

import ctypes as ct
import atexit
from contextlib import ExitStack
from importlib.resources import as_file, files
import json
import os
import sys
import weakref


class _Buffer(ct.Structure):
    _fields_ = [("data", ct.c_void_p), ("size", ct.c_size_t)]


_name = "koine.dll" if sys.platform == "win32" else "libkoine.dylib" if sys.platform == "darwin" else "libkoine.so"
_resources = ExitStack()
atexit.register(_resources.close)
_lib = ct.CDLL(str(_resources.enter_context(as_file(files("koine") / _name))))
_lib.koine_parser_create.argtypes = [ct.c_char_p, ct.c_size_t, ct.POINTER(ct.c_void_p), ct.POINTER(_Buffer)]
_lib.koine_parser_create.restype = ct.c_int
_lib.koine_parser_from_file.argtypes = _lib.koine_parser_create.argtypes
_lib.koine_parser_from_file.restype = ct.c_int
_lib.koine_parser_prepare.argtypes = [ct.c_char_p, ct.c_size_t, ct.c_char_p, ct.c_size_t, ct.c_int,
                                     ct.POINTER(ct.c_void_p), ct.POINTER(_Buffer)]
_lib.koine_parser_prepare.restype = ct.c_int
_lib.koine_parser_prepare_file.argtypes = [ct.c_char_p, ct.c_size_t, ct.c_int,
                                          ct.POINTER(ct.c_void_p), ct.POINTER(_Buffer)]
_lib.koine_parser_prepare_file.restype = ct.c_int
_lib.koine_parser_parse.argtypes = [ct.c_void_p, ct.c_char_p, ct.c_size_t, ct.c_char_p, ct.c_size_t,
                                   ct.POINTER(_Buffer), ct.POINTER(_Buffer)]
_lib.koine_parser_parse.restype = ct.c_int
_lib.koine_parser_parse_transpile.argtypes = [ct.c_void_p, ct.c_void_p, ct.c_char_p, ct.c_size_t,
                                              ct.c_char_p, ct.c_size_t,
                                              ct.POINTER(_Buffer), ct.POINTER(_Buffer)]
_lib.koine_parser_parse_transpile.restype = ct.c_int
_lib.koine_parser_destroy.argtypes = [ct.c_void_p]
_lib.koine_parser_destroy.restype = None
_lib.koine_transpiler_create.argtypes = _lib.koine_parser_create.argtypes
_lib.koine_transpiler_create.restype = ct.c_int
_lib.koine_transpiler_from_file.argtypes = _lib.koine_transpiler_create.argtypes
_lib.koine_transpiler_from_file.restype = ct.c_int
_lib.koine_transpiler_transpile.argtypes = [ct.c_void_p, ct.c_char_p, ct.c_size_t,
                                          ct.POINTER(_Buffer), ct.POINTER(_Buffer)]
_lib.koine_transpiler_transpile.restype = ct.c_int
_lib.koine_transpiler_state.argtypes = [ct.c_void_p, ct.POINTER(_Buffer), ct.POINTER(_Buffer)]
_lib.koine_transpiler_state.restype = ct.c_int
_lib.koine_transpiler_destroy.argtypes = [ct.c_void_p]
_lib.koine_transpiler_destroy.restype = None
_lib.koine_buffer_free.argtypes = [ct.POINTER(_Buffer)]
_lib.koine_buffer_free.restype = None


def _take(value):
    try:
        return ct.string_at(value.data, value.size).decode("utf-8") if value.data else ""
    finally:
        _lib.koine_buffer_free(ct.byref(value))


class Parser:
    """Prepare a runtime grammar once and reuse it for parsing and validation.

    Subgrammar paths are relative to base_path (the current directory by default).
    from_file() supplies the grammar file's directory automatically.
    """

    _mode = 0

    def __init__(self, grammar_dict, base_path=None):
        data = json.dumps(grammar_dict, ensure_ascii=False).encode("utf-8")
        base = None if base_path is None else os.fsencode(base_path)
        self._create(_lib.koine_parser_prepare, data, len(data), base, len(base) if base is not None else 0, self._mode)

    def _create(self, constructor, *args):
        handle = ct.c_void_p()
        error = _Buffer()
        status = constructor(*args, ct.byref(handle), ct.byref(error))
        message = _take(error)
        if status:
            raise ValueError(message or "Native Koine construction failed")
        self._handle = handle
        self._release = weakref.finalize(self, _lib.koine_parser_destroy, handle)

    @classmethod
    def from_file(cls, filepath):
        parser = cls.__new__(cls)
        data = os.fsencode(filepath)
        parser._create(_lib.koine_parser_prepare_file, data, len(data), cls._mode)
        return parser

    def parse(self, text, start_rule=None):
        source = text.encode("utf-8")
        rule = None if start_rule is None else start_rule.encode("utf-8")
        result, error = _Buffer(), _Buffer()
        status = _lib.koine_parser_parse(self._handle, source, len(source), rule, len(rule) if rule is not None else 0,
                                         ct.byref(result), ct.byref(error))
        message = _take(error)
        if status:
            _take(result)
            raise ValueError(message or "Native Koine parsing failed")
        return json.loads(_take(result))

    def parse_transpile(self, text, transpiler, start_rule=None):
        """Parse and generate output in one native call.

        Avoids serializing the intermediate AST through Python. Returns a dict:
        {"status": "success", "text": ...} or the ordinary parse error object.
        """
        if not isinstance(transpiler, Transpiler):
            raise TypeError("transpiler must be a Transpiler")
        source = text.encode("utf-8")
        rule = None if start_rule is None else start_rule.encode("utf-8")
        result, error = _Buffer(), _Buffer()
        status = _lib.koine_parser_parse_transpile(self._handle, transpiler._handle,
            source, len(source), rule, len(rule) if rule is not None else 0,
            ct.byref(result), ct.byref(error))
        message = _take(error)
        if status:
            _take(result)
            raise ValueError(message or "Native Koine parse/transpile failed")
        return json.loads(_take(result))

    def validate(self, text):
        result = self.parse(text)
        return (True, "success") if result["status"] == "success" else (False, result["message"])


class PlaceholderParser(Parser):
    """Prepare one grammar using its local subgrammar placeholders."""

    _mode = 1

    def __init__(self, grammar_dict):
        super().__init__(grammar_dict)


class Transpiler:
    """Prepare output rules once and transpile ordinary AST data to text."""

    def __init__(self, transpile_grammar=None):
        data = json.dumps({} if transpile_grammar is None else transpile_grammar,
                          ensure_ascii=False).encode("utf-8")
        self._create(_lib.koine_transpiler_create, data)

    def _create(self, constructor, data):
        handle, error = ct.c_void_p(), _Buffer()
        status = constructor(data, len(data), ct.byref(handle), ct.byref(error))
        message = _take(error)
        if status:
            raise ValueError(message or "Native Koine construction failed")
        self._handle = handle
        self._release = weakref.finalize(self, _lib.koine_transpiler_destroy, handle)

    @classmethod
    def from_file(cls, filepath):
        """Load YAML/JSON output rules using the native loader."""
        transpiler = cls.__new__(cls)
        transpiler._create(_lib.koine_transpiler_from_file, os.fsencode(filepath))
        return transpiler

    def transpile(self, node):
        data = json.dumps(node, ensure_ascii=False).encode("utf-8")
        result, error = _Buffer(), _Buffer()
        status = _lib.koine_transpiler_transpile(self._handle, data, len(data),
                                               ct.byref(result), ct.byref(error))
        message = _take(error)
        if status:
            _take(result)
            raise ValueError(message or "Native Koine transpilation failed")
        return _take(result)

    @property
    def state(self):
        """A detached snapshot of the most recent call's state."""
        result, error = _Buffer(), _Buffer()
        status = _lib.koine_transpiler_state(self._handle, ct.byref(result), ct.byref(error))
        message = _take(error)
        if status:
            _take(result)
            raise ValueError(message or "Native Koine state inspection failed")
        return json.loads(_take(result))
