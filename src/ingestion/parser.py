import os
from typing import Any

from tree_sitter import Language, Node, Parser

_java_parser: Parser | None = None
_python_parser: Parser | None = None

def _get_parser(file_path: str) -> Parser | None:
    """
        Return a cached tree-sitter Parser for the given file's language.
    """

    global _java_parser, _python_parser
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".java":
        if _java_parser is None:
            import tree_sitter_java
            lang = Language(tree_sitter_java.language())
            _java_parser = Parser(lang)
        return _java_parser
    elif ext == ".py":
        if _python_parser is None:
            import tree_sitter_python
            lang = Language(tree_sitter_python.language())
            _python_parser = Parser(lang)
        return _python_parser
    return None


def _is_java(file_path: str) -> bool:
    return file_path.lower().endswith(".java")


# ---------------------------------------------------------------------------
# Standard library filter lists
# ---------------------------------------------------------------------------
JAVA_STD_PREFIXES = frozenset({
    "java.", "javax.", "jakarta.", "org.springframework.",
    "org.hibernate.", "org.apache.", "org.junit.", "org.mockito.",
    "org.slf4j.", "com.fasterxml.", "lombok.", "kotlin.",
})

PYTHON_STD_MODULES = frozenset({
    "os", "sys", "re", "json", "datetime", "collections", "itertools",
    "functools", "typing", "abc", "dataclasses", "enum", "io", "pathlib",
    "logging", "unittest", "math", "random", "hashlib", "base64", "copy",
    "textwrap", "argparse", "ast", "asyncio", "builtins", "contextlib",
    "csv", "decimal", "fractions", "gettext", "glob", "gzip", "html",
    "http", "importlib", "inspect", "locale", "multiprocessing", "operator",
    "pickle", "pkgutil", "platform", "pprint", "queue", "shutil",
    "signal", "socket", "sqlite3", "ssl", "statistics", "string",
    "struct", "subprocess", "tempfile", "threading", "time", "traceback",
    "types", "uuid", "warnings", "weakref", "xml", "zipfile"
})

def _is_java_stdlib(import_name: str) -> bool:
    """
        return True if the toplevel is a standard java library
    """
    for prefix in JAVA_STD_PREFIXES:
        if import_name.startswith(prefix):
            return True
    return False

def _is_python_stdlib(module_name: str) -> bool:
    """
        return True if the toplevel is a standard python library
    """
    top = module_name.split(".")[0]
    return top in PYTHON_STD_MODULES


def _text_of(node: Node, source: bytes) -> str:
    """
        Return the source text spanned by *node*, decoded to str.
    """

    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

def _first_child_text(node: Node, child_type: str, source: bytes) -> str | None:
    """
        Return the text of the first child of *node* matching *child_type*.
    """
    for child in node.children:
        if child.type == child_type:
            return _text_of(child, source)
    return None

def _find_all(node: Node, *types: str) -> list[Node]:
    """
        Recursively collect all descendants of *node* whose type is in *types*.
    """

    results: list[Node] = []
    if node.type in types:
        results.append(node)
    for child in node.children:
        results.extend(_find_all(child, *types))
    return results


def _find_direct(node: Node, *types: str) -> list[Node]:
    """Return direct children of *node* whose type is in *types*."""
    return [child for child in node.children if child.type in types]


# ---------------------------------------------------------------------------
# Java Abstract Syntax Tree extraction
# ---------------------------------------------------------------------------
def _extract_java_package(root: Node, source: bytes) -> str:
    for child in root.children:
        if child.type == "package_declaration":
            for sc in child.children:
                if sc.type == "scoped_identifier":
                    return _text_of(sc, source)
    return ""

def _extract_java_imports(root: Node, source: bytes) -> list[str]:
    imports: list[str] = []
    for child in root.children:
        if child.type == "import_declaration":
            for sc in child.children:
                if sc.type == "scoped_identifier":
                    imp = _text_of(sc, source)
                    if not _is_java_stdlib(imp):
                        imports.append(imp)
    return imports

def _extract_java_class(node: Node, source: bytes, pkg: str, imports: list[str]) -> dict[str, Any] | None:
    """
        Extract metadata from a class_declaration node.
    """
    name = _first_child_text(node, "identifier", source)
    if not name:
        return None

    # Superclass
    superclass = ""
    superclass_child = _find_direct(node, "superclass")
    if superclass_child:
        superclass = _first_child_text(superclass_child[0], "type_identifier", source) or ""

    # Interfaces
    interfaces: list[str] = []
    si = _find_direct(node, "super_interfaces")
    if si:
        for ti in _find_all(si[0], "type_identifier"):
            txt = _text_of(ti, source)
            if txt not in interfaces:
                interfaces.append(txt)

    # Methods
    methods: list[dict[str, Any]] = []
    body = _find_direct(node, "class_body")
    if body:
        for method_node in _find_direct(body[0], "method_declaration", "constructor_declaration"):
            method_name = _first_child_text(method_node, "identifier", source) or ""
            return_type = ""
            if method_node.type == "method_declaration":
                ret = _find_direct(method_node, "type_identifier")
                if not ret:
                    ret = _find_direct(method_node, "generic_type")
                if ret:
                    return_type = _text_of(ret[0], source)  # includes generics

            # Parameters
            params: list[str] = []
            fp_list = _find_direct(method_node, "formal_parameters")
            if fp_list:
                for fp in _find_all(fp_list[0], "formal_parameter"):
                    ti = _find_direct(fp, "type_identifier")
                    if ti:
                        params.append(_text_of(ti[0], source))

            methods.append({
                "name": method_name,
                "return_type": return_type,
                "params": params,
            })

    fields: list[str] = []
    if body:
        for fd in _find_direct(body[0], "field_declaration"):
            ti = _find_direct(fd, "type_identifier")
            if ti:
                ftype = _text_of(ti[0], source)
                if ftype not in fields:
                    fields.append(ftype)

    constructor_params: list[str] = []
    if body:
        for constr in _find_direct(body[0], "constructor_declaration"):
            fp_list = _find_direct(constr, "formal_parameters")
            if fp_list:
                for fp in _find_all(fp_list[0], "formal_parameter"):
                    ti = _find_direct(fp, "type_identifier")
                    if ti:
                        ptype = _text_of(ti[0], source)
                        if ptype not in constructor_params:
                            constructor_params.append(ptype)

    return {
        "name": name,
        "file_path": "",  # filled by caller
        "superclass": superclass,
        "interfaces": interfaces,
        "methods": methods,
        "fields": fields,
        "constructor_params": constructor_params,
        "imports": imports,
        "package": pkg,
    }


def _extract_java_interface(node: Node, source: bytes, pkg: str, imports: list[str]) -> dict[str, Any] | None:
    """Extract metadata from an interface_declaration node."""
    name = _first_child_text(node, "identifier", source)
    if not name:
        return None

    methods: list[dict[str, Any]] = []
    body = _find_direct(node, "interface_body")
    if body:
        for md in _find_direct(body[0], "method_declaration"):
            mname = _first_child_text(md, "identifier", source) or ""
            ret_type = ""
            ret = _find_direct(md, "type_identifier")
            if not ret:
                ret = _find_direct(md, "generic_type")
            if ret:
                ret_type = _text_of(ret[0], source)
            params: list[str] = []
            fp_list = _find_direct(md, "formal_parameters")
            if fp_list:
                for fp in _find_all(fp_list[0], "formal_parameter"):
                    ti = _find_direct(fp, "type_identifier")
                    if ti:
                        params.append(_text_of(ti[0], source))
            methods.append({"name": mname, "return_type": ret_type, "params": params})

    return {
        "name": name,
        "file_path": "",
        "methods": methods,
        "imports": imports,
        "package": pkg,
    }


def _parse_java(file_path: str) -> dict[str, Any]:
    parser = _get_parser(file_path)
    if parser is None:
        return {"classes": [], "interfaces": []}

    with open(file_path, "rb") as f:
        source = f.read()

    tree = parser.parse(source)
    root = tree.root_node
    pkg = _extract_java_package(root, source)
    imports = _extract_java_imports(root, source)

    classes: list[dict[str, Any]] = []
    interfaces: list[dict[str, Any]] = []

    for node in root.children:
        if node.type == "class_declaration":
            cls = _extract_java_class(node, source, pkg, imports)
            if cls:
                cls["file_path"] = file_path
                classes.append(cls)
        elif node.type == "interface_declaration":
            iface = _extract_java_interface(node, source, pkg, imports)
            if iface:
                iface["file_path"] = file_path
                interfaces.append(iface)

    return {"classes": classes, "interfaces": interfaces}

# ---------------------------------------------------------------------------
# Python Abstract Syntax Tree extraction
# ---------------------------------------------------------------------------
def _extract_python_imports(root: Node, source: bytes) -> list[str]:
    imports: list[str] = []
    for child in root.children:
        if child.type == "import_statement":
            for dn in _find_direct(child, "dotted_name"):
                mod = _text_of(dn, source)
                if not _is_python_stdlib(mod):
                    imports.append(mod)
        elif child.type == "import_from_statement":
            # from X import Y, Z
            dns = _find_direct(child, "dotted_name")
            for dn in dns:
                mod = _text_of(dn, source)
                if not _is_python_stdlib(mod):
                    imports.append(mod)
    return imports


def _extract_python_class(node: Node, source: bytes, imports: list[str]) -> dict[str, Any] | None:
    """Extract metadata from a class_definition node."""
    name = _first_child_text(node, "identifier", source)
    if not name:
        return None

    superclass = ""
    interfaces: list[str] = []
    arg_list = _find_direct(node, "argument_list")
    if arg_list:
        idents = _find_all(arg_list[0], "identifier")
        if idents:
            superclass = _text_of(idents[0], source)
            for sc in idents[1:]:
                txt = _text_of(sc, source)
                if txt not in ("metaclass",) and not txt.startswith("_"):
                    interfaces.append(txt)

    methods: list[dict[str, Any]] = []
    block = _find_direct(node, "block")
    if block:
        for fd in _find_direct(block[0], "function_definition"):
            mname = _first_child_text(fd, "identifier", source) or ""
            ret_type = ""
            arrow = _find_direct(fd, "->")
            if arrow:
                arrow_idx = list(fd.children).index(arrow[0])
                if arrow_idx + 1 < len(fd.children):
                    type_node = fd.children[arrow_idx + 1]
                    ret_type = _text_of(type_node, source)

            params: list[str] = []
            param_nodes = _find_direct(fd, "parameters")
            if param_nodes:
                for p in _find_direct(param_nodes[0], "identifier"):
                    txt = _text_of(p, source)
                    if txt not in ("self", "cls"):
                        params.append(txt)
                for tp in _find_direct(param_nodes[0], "typed_parameter"):
                    ident = _find_direct(tp, "identifier")
                    if ident:
                        txt = _text_of(ident[0], source)
                        if txt not in ("self", "cls") and txt not in params:
                            params.append(txt)

            methods.append({
                "name": mname,
                "return_type": ret_type,
                "params": params,
            })

    fields: list[str] = []
    if block:
        for fd in _find_direct(block[0], "function_definition"):
            if _first_child_text(fd, "identifier", source) == "__init__":
                assignments = _find_all(fd, "assignment")
                for ass in assignments:
                    attr_nodes = _find_direct(ass, "attribute")
                    for attr in attr_nodes:
                        parts = list(attr.children)
                        if len(parts) >= 3 and _text_of(parts[0], source) == "self" and parts[1].type == ".":
                                fname = _text_of(parts[2], source)
                                if fname not in fields:
                                    fields.append(fname)

    constructor_params: list[str] = []
    if block:
        for fd in _find_direct(block[0], "function_definition"):
            if _first_child_text(fd, "identifier", source) == "__init__":
                param_blocks = _find_direct(fd, "parameters")
                for pb in param_blocks:
                    for tp in _find_direct(pb, "typed_parameter"):
                        type_nodes = _find_direct(tp, "type")
                        for tn in type_nodes:
                            ptype = _text_of(tn, source)
                            if ptype not in constructor_params:
                                constructor_params.append(ptype)

    return {
        "name": name,
        "file_path": "",
        "superclass": superclass,
        "interfaces": interfaces,
        "methods": methods,
        "fields": fields,
        "constructor_params": constructor_params,
        "imports": imports,
        "package": ""
    }


def _parse_python(file_path: str) -> dict[str, Any]:
    parser = _get_parser(file_path)
    if parser is None:
        return {"classes": [], "interfaces": []}

    with open(file_path, "rb") as f:
        source = f.read()

    tree = parser.parse(source)
    root = tree.root_node
    imports = _extract_python_imports(root, source)

    classes: list[dict[str, Any]] = []
    for node in _find_all(root, "class_definition"):
        cls = _extract_python_class(node, source, imports)
        if cls:
            cls["file_path"] = file_path
            classes.append(cls)

    return {"classes": classes, "interfaces": []}

def parse_file(file_path: str) -> dict[str, Any]:
    """Parse a single source file and return {classes: [...], interfaces: [...]}."""
    if _is_java(file_path):
        return _parse_java(file_path)
    else:
        return _parse_python(file_path)

def parse_all_files(file_paths: list[str]) -> dict[str, Any]:
    """Parse all collected source files and return an aggregated metadata dict."""
    all_classes: list[dict[str, Any]] = []
    all_interfaces: list[dict[str, Any]] = []

    for fp in file_paths:
        result = parse_file(fp)
        all_classes.extend(result.get("classes", []))
        all_interfaces.extend(result.get("interfaces", []))

    return {"classes": all_classes, "interfaces": all_interfaces}
