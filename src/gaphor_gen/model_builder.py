"""
Build a Gaphor UML model from an enriched NetworkX graph and serialize it
as a native .gaphor XML file.

Gaphor 4.x uses gzip-compressed XML with:
  - Namespace:      https://gaphor.org/model
  - Text values:    <name><val>text</val></name>
  - Single ref:     <package><ref refid="..."/></package>
  - Collection:     <ownedOperation><reflist><ref refid="..."/></reflist></ownedOperation>

Because the Gaphor library requires PyGObject (GTK system libraries) which
may not be available, this module generates the .gaphor XML format directly.
"""

import gzip
import uuid
from typing import Dict, List
from xml.dom import minidom
from xml.etree.ElementTree import Element, ElementTree, SubElement, tostring

import networkx as nx

# ---------------------------------------------------------------------------
# Gaphor 4.x XML namespace
# ---------------------------------------------------------------------------
NS_GAPHOR = "https://gaphor.org/model"

# Map graph edge types → Gaphor 4.x model element types (the UML metamodel)
MODEL_EDGE_MAP: Dict[str, str] = {
    "inheritance": "Generalization",
    "implementation": "Realization",
    "composition": "Association",
    "dependency": "Dependency",
}

# Map model element types → diagram presentation item types
PRESENTATION_MAP: Dict[str, str] = {
    "Generalization": "GeneralizationItem",
    "Realization": "RealizationItem",
    "Association": "AssociationItem",
    "Dependency": "DependencyItem",
}


def _make_id() -> str:
    return str(uuid.uuid4())


# --- XML helpers matching Gaphor 4.x save format ---

def _val(parent: Element, tag: str, text: str) -> Element:
    """Create ``<tag><val>text</val></tag>`` inside *parent*."""
    el = SubElement(parent, tag)
    if text:
        SubElement(el, "val").text = text
    return el


def _ref(parent: Element, tag: str, refid: str) -> Element:
    """Create ``<tag><ref refid="..."/></tag>`` inside *parent*."""
    el = SubElement(parent, tag)
    SubElement(el, "ref", attrib={"refid": refid})
    return el


def _reflist(parent: Element, tag: str, refids: List[str]) -> Element:
    """Create ``<tag><reflist><ref refid="..."/>...</reflist></tag>``.

    When *tag* is ``"reflist"`` the wrapper is omitted and the ``<reflist>``
    element is added directly to *parent*.
    """
    if tag == "reflist":
        rl = SubElement(parent, "reflist")
        for rid in refids:
            SubElement(rl, "ref", attrib={"refid": rid})
        return rl
    el = SubElement(parent, tag)
    if refids:
        rl = SubElement(el, "reflist")
        for rid in refids:
            SubElement(rl, "ref", attrib={"refid": rid})
    return el


# ---------------------------------------------------------------------------
# Core model generation
# ---------------------------------------------------------------------------
def build_gaphor_model(graph: nx.DiGraph) -> ElementTree:
    """Generate a Gaphor 4.x compatible ElementTree from the enriched graph."""
    root = Element("gaphor", attrib={
        "version": "4",
        "gaphor-version": "4.0.0",
        "xmlns": NS_GAPHOR,
    })
    tree = ElementTree(root)

    # --- Top-level Package (the model root) ---
    pkg_id = _make_id()
    pkg = SubElement(root, "Package", attrib={"id": pkg_id})
    _val(pkg, "name", "Root")
    owned_diagram_el = SubElement(pkg, "ownedDiagram")
    owned_type_el = SubElement(pkg, "ownedType")

    # --- Main Diagram ---
    diagram_id = _make_id()
    diagram = SubElement(owned_diagram_el, "Diagram", attrib={"id": diagram_id})
    _val(diagram, "name", "Architecture Diagram")
    _val(diagram, "diagramType", "")

    # Registries
    package_registry: Dict[str, str] = {}   # context_name → package element id
    element_registry: Dict[str, str] = {}    # graph_node_id → model element id
    owned_pkg_refs: List[str] = []           # collect for root ownedType

    # === Step 1: Create Package elements for each unique context ===
    for _node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        if ctx not in package_registry:
            cpkg_id = _make_id()
            package_registry[ctx] = cpkg_id
            owned_pkg_refs.append(cpkg_id)

            cpkg = SubElement(root, "Package", attrib={"id": cpkg_id})
            _val(cpkg, "name", ctx)
            _ref(cpkg, "nestingPackage", pkg_id)
            SubElement(cpkg, "ownedType")
            SubElement(cpkg, "ownedDiagram")
            SubElement(cpkg, "presentation")

    # Populate root Package ownedType
    _reflist(owned_type_el, "reflist", owned_pkg_refs)  # type: ignore[arg-type]

    # === Step 2: Create Class / Interface elements ===
    for node_id, data in graph.nodes(data=True):
        ctx = data.get("context", "Default Package")
        node_type = data.get("type", "class")
        model_id = _make_id()
        element_registry[node_id] = model_id

        tag = "Class" if node_type == "class" else "Interface"
        class_el = SubElement(root, tag, attrib={"id": model_id})
        _val(class_el, "name", str(data.get("name", node_id)))
        _ref(class_el, "package", package_registry[ctx])

        if data.get("responsibility"):
            _val(class_el, "note", data["responsibility"])

        # ownedOperation → reflist of Operation refs
        owned_op = SubElement(class_el, "ownedOperation")
        op_refids: List[str] = []
        for method in data.get("methods", []):
            op_id = _make_id()
            op = SubElement(root, "Operation", attrib={"id": op_id})
            _val(op, "name", method.get("name", ""))
            _ref(op, "class_", model_id)
            op_refids.append(op_id)
        if op_refids:
            rl = SubElement(owned_op, "reflist")
            for oid in op_refids:
                SubElement(rl, "ref", attrib={"refid": oid})

        # presentation → reflist with one ClassItem / InterfaceItem
        presentation = SubElement(class_el, "presentation")
        item_id = _make_id()
        item_tag = "ClassItem" if node_type == "class" else "InterfaceItem"
        item = SubElement(root, item_tag, attrib={"id": item_id})
        _ref(item, "subject", model_id)
        _ref(item, "diagram", diagram_id)
        _val(item, "matrix", "(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)")
        _val(item, "top-left", "(0, 0)")
        _val(item, "width", "150")
        _val(item, "height", "100")
        rl = SubElement(presentation, "reflist")
        SubElement(rl, "ref", attrib={"refid": item_id})

    # === Step 3: Create relationship (edge) elements ===
    for src, dst, edge_data in graph.edges(data=True):
        edge_type = edge_data.get("edge_type", "dependency")
        model_tag = MODEL_EDGE_MAP.get(edge_type, "Dependency")
        pres_tag = PRESENTATION_MAP.get(model_tag, "DependencyItem")

        src_id = element_registry.get(src)
        dst_id = element_registry.get(dst)
        if not src_id or not dst_id:
            continue

        rel_id = _make_id()
        rel_el = SubElement(root, model_tag, attrib={"id": rel_id})

        if model_tag == "Generalization":
            _ref(rel_el, "general", src_id)
            _ref(rel_el, "specific", dst_id)
        elif model_tag == "Realization":
            _ref(rel_el, "implementingClassifier", src_id)
            _ref(rel_el, "contract", dst_id)
        elif model_tag == "Association":
            member_end = SubElement(rel_el, "memberEnd")
            src_end_id = _make_id()
            dst_end_id = _make_id()

            src_end = SubElement(root, "Property", attrib={"id": src_end_id})
            _val(src_end, "name", "")
            _ref(src_end, "type", src_id)
            _ref(src_end, "association", rel_id)
            if edge_type == "composition":
                _val(src_end, "aggregation", "composite")

            dst_end = SubElement(root, "Property", attrib={"id": dst_end_id})
            _val(dst_end, "name", "")
            _ref(dst_end, "type", dst_id)
            _ref(dst_end, "association", rel_id)

            rl = SubElement(member_end, "reflist")
            SubElement(rl, "ref", attrib={"refid": src_end_id})
            SubElement(rl, "ref", attrib={"refid": dst_end_id})
        else:  # Dependency
            _ref(rel_el, "client", src_id)
            _ref(rel_el, "supplier", dst_id)

        # Presentation for the relationship
        pres = SubElement(rel_el, "presentation")
        pres_item_id = _make_id()
        pres_item = SubElement(root, pres_tag, attrib={"id": pres_item_id})
        _val(pres_item, "matrix", "(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)")
        _ref(pres_item, "diagram", diagram_id)
        _ref(pres_item, "subject", rel_id)
        rl = SubElement(pres, "reflist")
        SubElement(rl, "ref", attrib={"refid": pres_item_id})

    return tree


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------
def save_model(tree: ElementTree, output_path: str) -> str:
    """Write the Gaphor XML model to *output_path* as a GZip-compressed file."""
    raw_xml = minidom.parseString(
        tostring(tree.getroot(), encoding="unicode")
    ).toprettyxml(indent="  ", encoding="utf-8")

    with gzip.open(output_path, "wb") as f:
        f.write(raw_xml)

    return output_path


# ---------------------------------------------------------------------------
# Graceful import for the Gaphor Python API (used as a preference)
# ---------------------------------------------------------------------------
def try_gaphor_api():
    """Attempt to import Gaphor's native API. Returns (ElementFactory, storage)
    or (None, None) if Gaphor is not installed."""
    try:
        from gaphor.core.modeling import ElementFactory  # type: ignore
        from gaphor.storage import storage  # type: ignore
        return ElementFactory, storage
    except ImportError:
        return None, None
