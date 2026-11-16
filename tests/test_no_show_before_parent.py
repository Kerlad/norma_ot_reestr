"""Guard: no widget is made visible before it has a parent (it would flash as a separate window).

3.11.0 showed every page subtitle and dialog header as a top-level window for a moment at startup.
Static check over the app sources; a hit means: add the widget to its layout first, or create it
with a parent, and only then call setVisible(True) / show().
"""
import ast
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
APP_DIRS = ("utils", "tabs", "journal", "protocol", "exporters", "importers", "api", "db", "network")

PARENTING = {"addWidget", "insertWidget", "setWidget", "setParent", "addTab", "insertTab", "setCentralWidget",
             "setCornerWidget", "addPermanentWidget", "setCellWidget", "setIndexWidget", "addRow", "insertRow",
             "setMenuWidget", "addWidgetToLayout", "setViewport"}
SHOWING = {"setVisible", "show", "setHidden"}
SKIP_DIRS = {".venv", "INFO", "build", "dist", ".git", "tests", "tools", "__pycache__", "web"}


def target_key(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self":
        return "self." + node.attr
    return None


def looks_like_widget_ctor(call):
    f = call.func
    name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", "")
    if not name or not name[0].isupper():
        return False
    # parent given positionally or as parent=...
    if any(k.arg == "parent" for k in call.keywords):
        return False
    return True


def scan_func(fn, path):
    created = {}  # key -> (line, nargs)
    first_parent = {}
    shown = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call) and looks_like_widget_ctor(node.value):
            for t in node.targets:
                k = target_key(t)
                if k:
                    created.setdefault(k, (node.lineno, len(node.value.args), ast.unparse(node.value.func)))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            meth = node.func.attr
            if meth in PARENTING:
                for a in node.args:
                    k = target_key(a)
                    if k:
                        first_parent[k] = min(first_parent.get(k, 10**9), node.lineno)
            if meth in SHOWING:
                k = target_key(node.func.value)
                if k:
                    arg = node.args[0] if node.args else None
                    # setVisible(False) / setHidden(True) cannot flash
                    if meth == "setVisible" and isinstance(arg, ast.Constant) and arg.value is False:
                        continue
                    if meth == "setHidden" and (arg is None or (isinstance(arg, ast.Constant) and arg.value is True)):
                        continue
                    shown.append((k, node.lineno, meth))
    out = []
    for k, line, meth in shown:
        if k in created:
            cline, nargs, ctor = created[k]
            # Widgets whose first positional ctor arg is usually the parent: assume parented if nargs >= 1
            # only for classes whose first arg is a parent; text-first ctors (QLabel("x")) are NOT parented.
            text_first = ctor.split(".")[-1] in {"QLabel", "QPushButton", "QCheckBox", "QRadioButton", "QGroupBox",
                                                  "QToolButton", "QLineEdit", "QAction"}
            parented_by_ctor = nargs >= (2 if text_first else 1)
            if parented_by_ctor:
                continue
            p = first_parent.get(k)
            if cline <= line and (p is None or line < p):
                out.append("%s:%d  %s.%s() before parenting (created line %d by %s, parented at %s)" % (
                    path, line, k, meth, cline, ctor, p))
    return out




def _app_files():
    yield os.path.join(ROOT, "main.py")
    for top in APP_DIRS:
        for d, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [x for x in dirs if x not in SKIP_DIRS]
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(d, f)


def test_no_widget_shown_before_parent():
    hits = []
    for p in _app_files():
        if not os.path.exists(p):
            continue
        tree = ast.parse(open(p, encoding="utf-8-sig").read())
        for fn in ast.walk(tree):
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                hits += scan_func(fn, os.path.relpath(p, ROOT))
    assert not hits, "; ".join(hits)


def test_scanner_catches_the_3_11_0_bug():
    lines = [
        "def f(self):",
        "    self.subtitle_label = QLabel(subtitle)",
        "    self.subtitle_label.setVisible(bool(subtitle))",
        "    texts.addWidget(self.subtitle_label)",
    ]
    fn = ast.parse(chr(10).join(lines)).body[0]
    assert scan_func(fn, "x.py")
