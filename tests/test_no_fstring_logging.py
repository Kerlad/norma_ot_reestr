"""Guard tests: logs and audit must not carry f-strings, user paths or proxy addresses.

AGENTS.md rule 3 (no f-string logging with user data) and ROADMAP B5/R6.
"""
import ast
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN_DIRS = ["api", "db", "exporters", "importers", "tabs", "utils", "journal", "network"]
SCAN_FILES = ["main.py"]

FSTRING_LOG_RE = re.compile(
    r"(logger|logging|log|_logger|audit_logger)\.(debug|info|warning|error|exception|critical)\(\s*f[\"']"
)
LOG_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}
# Names that hold a user file path or a proxy address: must not reach logs as is.
FORBIDDEN_ARGS = {"file_path", "xml_file", "proxy_url", "zip_path", "backup_path"}


def _py_files():
    for d in SCAN_DIRS:
        for base, _dirs, files in os.walk(os.path.join(ROOT, d)):
            for name in files:
                if name.endswith(".py"):
                    yield os.path.join(base, name)
    for f in SCAN_FILES:
        yield os.path.join(ROOT, f)


def _read(path):
    with open(path, encoding="utf-8-sig") as fh:
        return fh.read()


def _is_log_call(node):
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "log_audit"
    if isinstance(func, ast.Attribute):
        if func.attr in LOG_METHODS:
            base = func.value
            name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
            return "log" in name.lower()
    return False


def _bare_names(node):
    """Names used directly (not hidden inside another call such as os.path.basename)."""
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, ast.JoinedStr):
        for part in node.values:
            if isinstance(part, ast.FormattedValue):
                yield from _bare_names(part.value)
    elif isinstance(node, ast.BinOp):
        yield from _bare_names(node.left)
        yield from _bare_names(node.right)
    elif isinstance(node, ast.Tuple):
        for elt in node.elts:
            yield from _bare_names(elt)


def test_no_fstring_in_log_calls():
    found = []
    for path in _py_files():
        text = _read(path)
        for m in FSTRING_LOG_RE.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            found.append("%s:%d" % (os.path.relpath(path, ROOT), line))
    assert found == []


def test_no_user_paths_or_proxy_in_log_calls():
    found = []
    for path in _py_files():
        tree = ast.parse(_read(path), filename=path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_log_call(node):
                args = list(node.args) + [kw.value for kw in node.keywords]
                bad = FORBIDDEN_ARGS.intersection(n for a in args for n in _bare_names(a))
                if bad:
                    found.append("%s:%d %s" % (os.path.relpath(path, ROOT), node.lineno, sorted(bad)))
    assert found == []
