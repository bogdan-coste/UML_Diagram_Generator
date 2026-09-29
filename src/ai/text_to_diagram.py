from typing import Any, Dict, List, Optional

import networkx as nx

from src.llm.factory import build_llm_client

EXTRACT_ENTITIES_PROMPT = """\
You are an expert software architect. Given the following description of a system,
extract ALL structural elements as a JSON object.

Return ONLY valid JSON, no explanation, no markdown fences.

DESCRIPTION:
{description}

EXPECTED JSON FORMAT:
{{
  "title": "short diagram title",
  "entities": [
    {{
      "name": "EntityName",
      "type": "class|interface|service|database|external_system|user|component",
      "context": "logical grouping name (e.g. Security, Persistence, API)",
      "description": "one sentence of what this entity does",
      "methods": ["methodName(param): returnType", ...]
    }}
  ],
  "relationships": [
    {{
      "from": "EntityName",
      "to": "EntityName",
      "type": "inheritance|implementation|composition|dependency|calls|uses|publishes|subscribes",
      "description": "short explanation"
    }}
  ]
}}
"""

USER_STORY_PROMPT = """\
You are an expert software architect. Given the following user story,
infer the architectural elements affected or required.

Return ONLY valid JSON, no explanation, no markdown fences.

USER STORY:
{story}

EXPECTED JSON FORMAT:
{{
  "title": "short diagram title",
  "entities": [
    {{
      "name": "EntityName",
      "type": "class|interface|service|database|external_system|user|component",
      "context": "logical grouping name",
      "description": "one sentence of what this entity does",
      "methods": ["methodName(param): returnType", ...]
    }}
  ],
  "relationships": [
    {{
      "from": "EntityName",
      "to": "EntityName",
      "type": "inheritance|implementation|composition|dependency|calls|uses",
      "description": "short explanation"
    }}
  ]
}}
"""

import json
import re

def _extract_json(text: str) -> dict[str, Any] | None:
    """Robustly extract a JSON object from SLM output (may have markdown)."""
    if not text:
        return None

    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = cleaned.replace("```", "").strip()

    # Find the outermost JSON object
    start = cleaned.find("{")
    if start == -1:
        return None
    end = cleaned.rfind("}") + 1
    if end <= start:
        return None

    try:
        return json.loads(cleaned[start:end])
    except json.JSONDecodeError:
        return None


def _normalize_relationship_type(rel_type: str) -> str:
    """Map SLM-returned relationship types to canonical edge types."""
    mapping = {
        "inheritance": "inheritance",
        "extends": "inheritance",
        "subclass": "inheritance",
        "implementation": "implementation",
        "implements": "implementation",
        "composition": "composition",
        "has_a": "composition",
        "owns": "composition",
        "aggregation": "composition",
        "dependency": "dependency",
        "uses": "dependency",
        "calls": "dependency",
        "depends_on": "dependency",
        "imports": "dependency",
        "publishes": "dependency",
        "subscribes": "dependency",
        "communicates_with": "dependency",
    }
    return mapping.get(rel_type.lower().strip(), "dependency")

def _json_to_graph(data: Dict[str, Any]) -> nx.DiGraph:
    """Convert the extracted JSON into a NetworkX DiGraph."""
    graph = nx.DiGraph()
    title = data.get("title", "Generated Diagram")

    for ent in data.get("entities", []):
        node_id = ent.get("name", "Unnamed")
        ent_type = ent.get("type", "class")

        # Map to canonical type
        canonical_type = "interface" if ent_type in ("interface",) else "class"

        methods_raw = ent.get("methods", [])
        methods = []
        for m in methods_raw:
            if isinstance(m, dict):
                methods.append(m)
            elif isinstance(m, str):
                # Parse "methodName(param): ReturnType"
                parts = m.split("(", 1)
                mname = parts[0].strip()
                params_str = parts[1].split(")", 1)[0] if len(parts) > 1 else ""
                ret = parts[1].split(":", 1)[-1].strip() if len(parts) > 1 and ":" in parts[1] else ""
                methods.append({
                    "name": mname,
                    "return_type": ret,
                    "params": [p.strip() for p in params_str.split(",") if p.strip()],
                })

        graph.add_node(
            node_id,
            name=ent.get("name", node_id),
            type=canonical_type,
            context=ent.get("context", "Default Package"),
            responsibility=ent.get("description", ""),
            methods=methods,
            fields=[],
            constructor_params=[],
            imports=[],
            file_path="",
            package=ent.get("context", ""),
            superclass="",
            interfaces=[],
        )

    graph.graph["title"] = title

    for rel in data.get("relationships", []):
        src = rel.get("from", "")
        dst = rel.get("to", "")
        if src in graph and dst in graph:
            edge_type = _normalize_relationship_type(rel.get("type", "dependency"))
            desc = rel.get("description", "")
            graph.add_edge(src, dst, edge_type=edge_type, description=desc)

    return graph


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _ask_llm(prompt: str) -> Optional[str]:
    """Send *prompt* through the configured LLM; return None on any failure."""
    try:
        return build_llm_client().ask_llm(prompt)
    except Exception:
        return None


def text_to_graph(description: str) -> Optional[nx.DiGraph]:
    prompt = EXTRACT_ENTITIES_PROMPT.format(description=description)
    response = _ask_llm(prompt)
    if not response:
        return None

    data = _extract_json(response)
    if not data:
        return None

    return _json_to_graph(data)


def user_story_to_graph(story: str) -> Optional[nx.DiGraph]:
    prompt = USER_STORY_PROMPT.format(story=story)
    response = _ask_llm(prompt)
    if not response:
        return None

    data = _extract_json(response)
    if not data:
        return None

    return _json_to_graph(data)


def batch_stories_to_graphs(stories: List[str]) -> List[Dict[str, Any]]:
    results = []
    for story in stories:
        try:
            graph = user_story_to_graph(story)
            results.append({
                "story": story,
                "graph": graph,
                "error": None if graph else "SLM failed to process story",
            })
        except Exception as e:
            results.append({"story": story, "graph": None, "error": str(e)})
    return results


def _generate_diagram(description: str, output_format: str) -> Optional[str]:
    """Ask the LLM directly for diagram source in *output_format*."""
    try:
        from src.generation.diagram_generator import DiagramGeneratorLLM

        generator = DiagramGeneratorLLM(build_llm_client())
        return generator.generate(
            description, diagram_type="class", output_format=output_format
        )
    except Exception:
        return None


def text_to_mermaid(description: str) -> Optional[str]:
    """One-shot: text description → Mermaid class diagram source."""
    return _generate_diagram(description, "mermaid")


def text_to_plantuml(description: str) -> Optional[str]:
    """One-shot: text description → PlantUML source."""
    return _generate_diagram(description, "plantuml")


def text_to_structurizr(description: str) -> Optional[str]:
    """One-shot: text description → Structurizr DSL source."""
    return _generate_diagram(description, "structurizr")
