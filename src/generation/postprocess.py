"""Deterministic repairs for model-emitted PlantUML.

The adapter is a strong transcriber and a poor grammarian. It copies clause order
out of the prose it is given, producing declarations that neither PlantUML nor our
own parser reads; it duplicates inherited members down into subclasses; and it
usually omits the relationship lines those members imply.

Every rule here is mechanical: it moves information that is already somewhere in
the diagram and never invents content. Applied rules are returned so the caller can
report them rather than quietly rewriting output.
"""
from __future__ import annotations

import re

# `class "Name" as Alias extends Base {` -- PlantUML does not accept a quoted
# alias and an extends/implements clause in the same declaration, and silently
# ignores the clause. Split it into a declaration plus a relationship line.
_INLINE_CLAUSE = re.compile(
    r'^(\s*)((?:abstract\s+)?class|interface)\s+"([^"]+)"\s+as\s+(\w+)'
    r"\s+(extends|implements)\s+(\w+)\s*\{\s*$"
)

# A relationship line, with the arrow captured so direction can be normalised.
_RELATION = re.compile(r"^(\w+)\s*(<\|--|<\|\.\.|\*--|\.\.>|-->)\s*(\w+)\s*(?::.*)?$")

# Labels that are not UML relationship types. The arrow already carries the
# meaning, so only the label needs correcting.
_NON_UML_LABELS = {"field": "composition"}

# keyword -> (arrow, edge type). `A extends B` means A is the subtype.
_ARROWS = {
    "extends": ("<|--", "inheritance"),
    "implements": ("<|..", "implementation"),
}


def _edge(line: str) -> tuple[str, str] | None:
    """The ``(source, target)`` edge a relationship line expresses, or ``None``.

    Normalising direction matters: `<|--` and `<|..` are written with the
    *supertype* on the left, so the edge runs the other way. Comparing written
    operand order instead is how a redundant composition gets admitted alongside an
    existing implementation edge for the same pair.
    """
    match = _RELATION.match(line.strip())
    if not match:
        return None
    src, arrow, dst = match.group(1), match.group(2), match.group(3)
    if arrow in ("<|--", "<|.."):
        return dst, src
    return src, dst


def _base_type(field_type: str) -> str:
    """The declared type a field refers to: `LineItem[]` -> LineItem, `List<P>` -> P."""
    if "<" in field_type and ">" in field_type:
        inner = field_type[field_type.index("<") + 1 : field_type.rindex(">")]
        return _base_type(inner.split(",")[0].strip())
    return field_type.replace("[]", "").strip()


def normalize_plantuml(dsl: str) -> tuple[str, list[str]]:
    """Repair mechanical defects in *dsl*.

    Returns ``(dsl, applied_fixes)``; *applied_fixes* is empty when the input was
    already well formed.
    """
    fixes: list[str] = []
    derived: list[str] = []
    out: list[str] = []

    for line in dsl.splitlines():
        match = _INLINE_CLAUSE.match(line)
        if match:
            indent, kind, name, alias, keyword, target = match.groups()
            arrow, edge_type = _ARROWS[keyword]
            out.append(f'{indent}{kind} "{name}" as {alias} {{')
            derived.append(f"{target} {arrow} {alias} : {edge_type}")
            fixes.append(f"split inline `{keyword} {target}` off `{name}`")
            continue

        rewritten = line
        stripped = rewritten.rstrip()
        for bad, good in _NON_UML_LABELS.items():
            if stripped.endswith(f": {bad}"):
                rewritten = stripped[: -len(bad)] + good
                fixes.append(f"relabelled `{bad}` as `{good}`")
                break
        out.append(rewritten)

    # Relationship lines the model wrote itself, indexed by the edge they express
    # so a clause can find and correct the right one.
    positions: dict[tuple[str, str], int] = {}
    for index, line in enumerate(out):
        edge = _edge(line)
        if edge is not None:
            positions.setdefault(edge, index)
    seen = set(positions)

    # A clause is the model's explicit statement about the relation, so it wins any
    # conflict with an arrow the model guessed -- and PlantUML threw the clause
    # away, making the relationship line the only place it can survive.
    appended: list[str] = []
    for line in derived:
        edge = _edge(line)
        if edge is None:
            appended.append(line)
        elif edge in positions:
            if out[positions[edge]].strip() != line.strip():
                out[positions[edge]] = line
                fixes.append(f"corrected an arrow the clause contradicted: `{line}`")
        elif edge not in seen:
            appended.append(line)
            seen.add(edge)
    derived = appended

    # A member whose type is another *declared* type implies a composition edge --
    # the convention `graph/relationships.py` applies to fields. The parser already
    # tracks which class a member belongs to, so reuse it rather than re-scanning.
    # Guarded on `declared`, so `+String name` cannot conjure a class box.
    from src.dataset import parse_plantuml

    parsed = parse_plantuml("\n".join(out))
    if parsed is not None:
        declared = set(parsed.nodes())
        for owner, data in parsed.nodes(data=True):
            for raw in data.get("fields", []):
                target = _base_type(raw)
                edge = (owner, target)
                if target in declared and target != owner and edge not in seen:
                    derived.append(f"{owner} *-- {target} : composition")
                    seen.add(edge)
                    fixes.append(f"derived composition from the `{raw}` field on `{owner}`")

    # Relationship lines belong after the package block, before @enduml.
    if derived:
        if out and out[-1].strip() == "@enduml":
            out[-1:-1] = derived + [""]
        else:
            out.extend(derived)

    if not out or out[-1].strip() != "@enduml":
        out.append("@enduml")
        fixes.append("added the missing @enduml")

    return "\n".join(out), list(dict.fromkeys(fixes))
