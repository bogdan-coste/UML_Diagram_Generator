"""Regression tests for the data-integrity fixes.

Both defects were invisible to the dataset builder's round-trip gate: the gate
compares an exporter against a parser that mirrored it, so a *consistent*
direction error and a dropped parameter type both scored `roundtrip: 1.0`.
They are pinned here instead.
"""
import networkx as nx

from src.dataset import parse_mermaid_class_diagram, parse_plantuml
from src.exporters.mermaid_exporter import to_mermaid_class_diagram
from src.exporters.plantuml_exporter import to_plantuml
from src.ingestion.parser import parse_file


def _graph() -> nx.DiGraph:
    """Child -> Parent, stored the way `graph/relationships.py` stores it."""
    g = nx.DiGraph()
    g.add_node("p.Child", name="Child", type="class", context="p", methods=[])
    g.add_node("p.Parent", name="Parent", type="class", context="p", methods=[])
    g.add_edge("p.Child", "p.Parent", edge_type="inheritance")
    return g


def test_plantuml_arrowhead_sits_on_the_supertype():
    dsl = to_plantuml(_graph())
    assert "Parent <|-- Child" in dsl
    assert "Child <|-- Parent" not in dsl


def test_plantuml_roundtrip_preserves_edge_direction():
    back = parse_plantuml(to_plantuml(_graph()))
    assert back is not None
    assert back.has_edge("Child", "Parent")
    assert back.edges["Child", "Parent"]["edge_type"] == "inheritance"
    assert not back.has_edge("Parent", "Child")


def test_implementation_arrow_is_also_reversed():
    g = nx.DiGraph()
    g.add_node("p.Impl", name="Impl", type="class", context="p", methods=[])
    g.add_node("p.Iface", name="Iface", type="interface", context="p", methods=[])
    g.add_edge("p.Impl", "p.Iface", edge_type="implementation")

    dsl = to_plantuml(g)
    assert "Iface <|.. Impl" in dsl

    back = parse_plantuml(dsl)
    assert back is not None
    assert back.has_edge("Impl", "Iface")
    assert not back.has_edge("Iface", "Impl")


def test_mermaid_roundtrip_preserves_edge_direction():
    back = parse_mermaid_class_diagram(to_mermaid_class_diagram(_graph()))
    assert back is not None
    assert back.has_edge("Child", "Parent")
    assert not back.has_edge("Parent", "Child")


def test_type_argument_is_not_an_interface_and_primitive_types_survive(tmp_path):
    src = tmp_path / "Foo.java"
    src.write_text(
        "package com.example;\n"
        "\n"
        "public class Foo<T> implements Bar<T> {\n"
        "    public void add(int count) { }\n"
        "    public int size() { return 0; }\n"
        "}\n",
        encoding="utf-8",
    )
    cls = parse_file(str(src))["classes"][0]

    assert cls["interfaces"] == ["Bar"], "type argument leaked into interfaces"

    methods = {m["name"]: m for m in cls["methods"]}
    assert methods["add"]["return_type"] == "void"
    assert methods["add"]["params"] == ["int"]
    assert methods["size"]["return_type"] == "int"
