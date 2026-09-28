"""
Text-to-Diagram Pipeline: parse natural language descriptions and user
stories, extract architectural concepts via the SLM, and produce
enriched graphs ready for multi-format export.

Supports:
  - Free-text architecture descriptions
  - User stories ("As a ... I want ... so that ...")
  - Bullet-point system descriptions
"""
from typing import Any, Dict, List, Optional

import networkx as nx

from src.ai.ollama_client import query_ollama


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# JSON extraction / parsing
# ---------------------------------------------------------------------------
import json
import re


def _extract_json(text: str) -> Optional[Dict[str, Any]]:
    """Robustly extract a JSON object from SLM output (may have markdown)."""
    if not text:
        return None

    # Remove markdown code fences if present
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


# ---------------------------------------------------------------------------
# Graph construction from extracted JSON
# ---------------------------------------------------------------------------
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

        graph.add_node(node_id, **{
            "name": ent.get("name", node_id),
            "type": canonical_type,
            "context": ent.get("context", "Default Package"),
            "responsibility": ent.get("description", ""),
            "methods": methods,
            "fields": [],
            "constructor_params": [],
            "imports": [],
            "file_path": "",
            "package": ent.get("context", ""),
            "superclass": "",
            "interfaces": [],
        })

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
def text_to_graph(description: str) -> Optional[nx.DiGraph]:
    """Generate an architecture graph from a free-text description via SLM.

    Args:
        description: Natural language description of the system architecture.

    Returns:
        A NetworkX DiGraph, or None if SLM failed.
    """
    prompt = EXTRACT_ENTITIES_PROMPT.format(description=description)
    response = query_ollama(prompt)
    if not response:
        return None

    data = _extract_json(response)
    if not data:
        return None

    return _json_to_graph(data)


def user_story_to_graph(story: str) -> Optional[nx.DiGraph]:
    """Generate an architecture graph from a user story via SLM.

    Args:
        story: A user story in the format "As a ... I want ... so that ..."

    Returns:
        A NetworkX DiGraph, or None if SLM failed.
    """
    prompt = USER_STORY_PROMPT.format(story=story)
    response = query_ollama(prompt)
    if not response:
        return None

    data = _extract_json(response)
    if not data:
        return None

    return _json_to_graph(data)


def batch_stories_to_graphs(stories: List[str]) -> List[Dict[str, Any]]:
    """Process multiple user stories and return their graphs with metadata.

    Each result dict: { "story": str, "graph": nx.DiGraph | None, "error": str | None }
    """
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


def text_to_mermaid(description: str) -> Optional[str]:
    """One-shot: text description → Mermaid class diagram string."""
    graph = text_to_graph(description)
    if graph is None:
        return None
    from src.exporters.mermaid_exporter import to_mermaid
    return to_mermaid(graph)


def text_to_plantuml(description: str) -> Optional[str]:
    """One-shot: text description → PlantUML string."""
    graph = text_to_graph(description)
    if graph is None:
        return None
    from src.exporters.plantuml_exporter import to_plantuml
    return to_plantuml(graph)


def text_to_structurizr(description: str) -> Optional[str]:
    """One-shot: text description → Structurizr DSL string."""
    graph = text_to_graph(description)
    if graph is None:
        return None
    from src.exporters.structurizr_exporter import to_structurizr_dsl
    return to_structurizr_dsl(graph)
