"""Input mode → graph → DSL.

Three ways in, deliberately routed differently:

* ``folder`` — the static pipeline (tree-sitter → graph → exporter). No model.
* ``code`` — a pasted snippet, written to a temp file so the *same* static
  pipeline can run on it. The language is inferred from the source.
* ``text`` / ``story`` — prose has no ground truth to extract, so a model
  extracts a graph, which the deterministic exporters then render. Either the
  remote LLM or the local fine-tuned adapter can act as that model.

Keeping `text` routed through a graph (rather than asking the LLM for DSL
directly) is what lets the response report graph statistics, and it means the
rendering step is identical across all three modes.
"""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field

import networkx as nx

from src.ai.text_to_diagram import text_to_graph, user_story_to_graph
from src.exporters.graphviz_exporter import to_graphviz_dot
from src.exporters.mermaid_exporter import to_mermaid
from src.exporters.plantuml_exporter import to_plantuml
from src.exporters.structurizr_exporter import to_structurizr_dsl
from src.graph.builder import build_graph
from src.graph.relationships import extract_edges
from src.ingestion.file_traverser import collect_source_files
from src.ingestion.parser import parse_all_files

from .schemas import DiagramType, GraphSummary, OutputFormat

DEFAULT_TITLE = "Architecture Diagram"

FALLBACK_CONTEXT = "Default Package"

# Files are listed in the response only for `folder` and `code` modes, and are
# capped: a large repository would otherwise return thousands of paths.
MAX_FILES_REPORTED = 50

# Which requested diagram types each exporter can actually render. Anything else
# falls back to that format's default and is reported as a warning, so the API
# never silently returns a different diagram than the one requested.
SUPPORTED_DIAGRAM_TYPES: dict[str, set[str]] = {
    "mermaid": {"class", "flowchart"},
    "plantuml": {"class"},
    "structurizr": {"class", "component"},
    "graphviz": {"class", "flowchart"},
}

_DEFAULT_DIAGRAM_TYPE: dict[str, DiagramType] = {
    "mermaid": "class",
    "plantuml": "class",
    "structurizr": "component",
    "graphviz": "class",
}

RAG_NOT_WIRED_WARNING = (
    "RAG retrieval was requested but is not yet applied to generation; "
    "the diagram was produced without retrieval context."
)

# Markers used to tell a pasted Java snippet from a Python one.
_JAVA_MARKERS = (
    "public class ",
    "public interface ",
    "public enum ",
    "protected ",
    "private ",
    "package ",
    "import java.",
    "@Override",
)


class PipelineError(RuntimeError):
    """A request that cannot be satisfied; the API maps this to a 422."""


@dataclass
class GraphBuild:
    """A graph plus the provenance the response needs."""

    graph: nx.DiGraph
    files: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    # Set only by the prose path. The fine-tuned model's raw DSL, kept so the
    # PlantUML response can return what the model actually wrote instead of the
    # deterministic re-render of its parsed graph -- otherwise a parser miss is
    # indistinguishable from a model miss.
    model_dsl: str | None = None


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def _graph_from_files(files: list[str]) -> nx.DiGraph:
    metadata = parse_all_files(files)
    graph = build_graph(metadata)
    extract_edges(metadata, graph)
    return graph


def _require_nodes(graph: nx.DiGraph, context: str) -> None:
    if graph.number_of_nodes() == 0:
        raise PipelineError(f"No entities were extracted from {context}.")


def build_from_folder(path: str) -> GraphBuild:
    """Run the static pipeline over a directory."""
    candidate = path.strip()
    if not candidate:
        raise PipelineError("`content` must be a directory path when mode is 'folder'.")

    root = os.path.abspath(os.path.expanduser(candidate))
    if not os.path.isdir(root):
        raise PipelineError(f"Not a directory: {root}")

    files = sorted(collect_source_files(root))
    if not files:
        raise PipelineError(f"No supported source files found under {root}.")

    graph = _graph_from_files(files)
    _require_nodes(graph, root)
    graph.graph.setdefault("title", os.path.basename(root) or DEFAULT_TITLE)

    warnings: list[str] = []
    if len(files) > MAX_FILES_REPORTED:
        warnings.append(
            f"{len(files)} source files were parsed; only the first "
            f"{MAX_FILES_REPORTED} are listed below."
        )

    listed = [os.path.relpath(f, root) for f in files[:MAX_FILES_REPORTED]]
    return GraphBuild(graph=graph, files=listed, warnings=warnings)


def _infer_language(source: str) -> str:
    """Best-effort language guess for a pasted snippet.

    Java is detected by explicit markers; anything else is treated as Python,
    which is the losing side of a two-way guess. The result is always reported
    in the response warnings, so the guess is never silent.
    """
    return "java" if any(marker in source for marker in _JAVA_MARKERS) else "python"


def build_from_code(source: str) -> GraphBuild:
    """Run the static pipeline over a pasted snippet.

    The traverser and parser both operate on paths, so the snippet is written to
    a temporary directory and the normal folder pipeline runs on it. Node
    ``file_path`` values are rewritten to the synthetic filename so no temporary
    path leaks into the response.
    """
    language = _infer_language(source)
    filename = "Snippet.java" if language == "java" else "snippet.py"

    with tempfile.TemporaryDirectory(prefix="archigen-") as tmp:
        with open(os.path.join(tmp, filename), "w", encoding="utf-8") as handle:
            handle.write(source)
        graph = _graph_from_files(collect_source_files(tmp))

    _require_nodes(graph, "the pasted snippet")
    graph.graph.setdefault("title", filename)
    for _, data in graph.nodes(data=True):
        if data.get("file_path"):
            data["file_path"] = filename

    return GraphBuild(
        graph=graph,
        files=[filename],
        warnings=[f"Pasted snippet was parsed as {language}."],
    )


def build_from_text(content: str, *, is_story: bool) -> GraphBuild:
    """Extract a graph from prose using the configured LLM."""
    graph = user_story_to_graph(content) if is_story else text_to_graph(content)
    if graph is None:
        raise PipelineError(
            "LLM extraction failed. Configure LLM_API_KEY / LLM_BASE_URL for the "
            "generative path, or use mode 'folder'/'code' for static analysis."
        )

    _require_nodes(graph, "the description")
    return GraphBuild(graph=graph, files=[])


def build_from_text_with_adapter(content: str, *, is_story: bool) -> GraphBuild:
    """Extract a graph from prose using the local fine-tuned adapter.

    Prose is still routed through a graph, exactly like the LLM path: the model
    emits PlantUML and the existing parser turns it back into a graph, so the
    response can report statistics and every exporter can re-render it. The
    model therefore contributes *content*; layout stays deterministic.
    """
    from src.dataset import parse_plantuml
    from src.generation.local_adapter import generate_dsl, strip_code_fences
    from src.generation.postprocess import normalize_plantuml
    from src.prompts.prompt_templates import PromptTemplates

    description = content.strip()
    if is_story:
        description = f"USER STORY:\n{description}"

    dsl = generate_dsl(
        PromptTemplates.build_prompt(description, output_format="plantuml")
    )
    if not dsl:
        raise PipelineError(
            "The fine-tuned model was unavailable (no GPU, or the adapter is "
            "missing). Configure LLM_API_KEY / LLM_BASE_URL for the remote path, "
            "or use mode 'folder'/'code' for static analysis."
        )

    # Repair mechanical defects before parsing, so the graph and the returned DSL
    # agree -- and so PlantUML renders what we think it renders.
    dsl, fixes = normalize_plantuml(strip_code_fences(dsl))

    graph = parse_plantuml(dsl)
    if graph is None:
        raise PipelineError(
            "The fine-tuned model produced output that could not be read as a "
            "PlantUML class diagram."
        )

    _require_nodes(graph, "the model output")
    graph.graph.setdefault("title", DEFAULT_TITLE)
    warnings = [
        "Diagram content was extracted by the fine-tuned model and is not validated."
    ]
    warnings += [f"Normalised model output: {fix}." for fix in fixes]
    return GraphBuild(graph=graph, files=[], warnings=warnings, model_dsl=dsl)


# ---------------------------------------------------------------------------
# Enrichment, rendering, summarising
# ---------------------------------------------------------------------------
def contexts(graph: nx.DiGraph) -> list[str]:
    """Distinct node contexts, sorted."""
    return sorted(
        {str(data["context"]) for _, data in graph.nodes(data=True) if data.get("context")}
    )


def enrich(graph: nx.DiGraph, warnings: list[str]) -> None:
    """LLM enrichment: context names and one-line responsibilities.

    Best-effort by design. Both helpers fall back to ``Default Package`` on their
    own, and this wrapper guarantees enrichment can never fail a request.
    """
    from src.ai.semantic_grouper import enrich_graph_with_contexts
    from src.ai.summarizer import enrich_graph_with_summaries

    try:
        enrich_graph_with_contexts(graph)
        enrich_graph_with_summaries(graph)
    except Exception:  # noqa: BLE001 - enrichment must never fail a request
        warnings.append("AI enrichment failed; contexts fall back to 'Default Package'.")
        return

    if contexts(graph) == [FALLBACK_CONTEXT]:
        # The helpers swallow their own errors, so a total fallback is the only
        # observable signal that the LLM was unavailable.
        warnings.append(
            "AI enrichment produced no distinct contexts (LLM unavailable); "
            "everything was grouped under 'Default Package'."
        )


def render(
    graph: nx.DiGraph,
    output_format: OutputFormat,
    diagram_type: DiagramType,
    warnings: list[str],
) -> tuple[str, DiagramType]:
    """Render *graph* to DSL.

    Returns ``(dsl, effective_diagram_type)`` — the effective type may differ
    from the requested one if the exporter cannot render it, in which case a
    warning is appended.
    """
    title = graph.graph.get("title") or DEFAULT_TITLE

    effective: DiagramType = diagram_type
    if diagram_type not in SUPPORTED_DIAGRAM_TYPES.get(output_format, set()):
        effective = _DEFAULT_DIAGRAM_TYPE.get(output_format, "class")
        warnings.append(
            f"'{diagram_type}' is not supported for {output_format}; "
            f"rendered a '{effective}' diagram instead."
        )

    if output_format == "mermaid":
        style = "flowchart" if effective == "flowchart" else "class"
        return to_mermaid(graph, style=style), effective
    if output_format == "structurizr":
        return to_structurizr_dsl(graph, workspace_name=title), effective
    if output_format == "graphviz":
        return to_graphviz_dot(graph, title=title), effective
    return to_plantuml(graph, title=title), effective


# The adapter was fine-tuned on exactly one task: canonical-AST description of
# real Java/Python code -> PlantUML class diagram. Anything else is
# out-of-distribution, so it is refused and rendered deterministically instead
# of being guessed at.
ADAPTER_FORMATS = {"plantuml"}
ADAPTER_DIAGRAM_TYPES = {"class"}


def render_with_adapter(
    graph: nx.DiGraph,
    output_format: OutputFormat,
    diagram_type: DiagramType,
    warnings: list[str],
) -> tuple[str, DiagramType]:
    """Render by asking the fine-tuned adapter, falling back deterministically.

    The prompt is rebuilt with ``PromptTemplates.build_prompt`` -- the same
    function the dataset builder calls -- so the model is served the input shape
    it was trained on rather than something hand-rolled here.
    """
    from src.generation.local_adapter import generate_dsl
    from src.generation.postprocess import normalize_plantuml
    from src.prompts.prompt_templates import PromptTemplates

    if output_format not in ADAPTER_FORMATS or diagram_type not in ADAPTER_DIAGRAM_TYPES:
        warnings.append(
            f"The fine-tuned model only covers plantuml/class diagrams; "
            f"{output_format}/{diagram_type} was rendered deterministically."
        )
        return render(graph, output_format, diagram_type, warnings)

    # Imported here so a missing rag stack cannot break module import.
    from src.rag import canonical_ast_to_text, graph_to_canonical_ast

    description = canonical_ast_to_text(graph_to_canonical_ast(graph))
    prompt = PromptTemplates.build_prompt(
        description, diagram_type=diagram_type, output_format=output_format
    )

    dsl = generate_dsl(prompt)
    if not dsl:
        warnings.append(
            "The fine-tuned model was unavailable (no GPU, or the adapter is "
            "missing); rendered deterministically instead."
        )
        return render(graph, output_format, diagram_type, warnings)

    dsl, fixes = normalize_plantuml(dsl)
    warnings += [f"Normalised model output: {fix}." for fix in fixes]
    warnings.append("Rendered by the fine-tuned model; the output was not validated.")
    return dsl, diagram_type


def summarise(graph: nx.DiGraph) -> GraphSummary:
    """Graph statistics reported alongside the generated DSL."""
    classes = sum(1 for _, d in graph.nodes(data=True) if d.get("type") == "class")
    interfaces = sum(1 for _, d in graph.nodes(data=True) if d.get("type") == "interface")

    return GraphSummary(
        title=graph.graph.get("title") or DEFAULT_TITLE,
        nodes=graph.number_of_nodes(),
        edges=graph.number_of_edges(),
        classes=classes,
        interfaces=interfaces,
        contexts=contexts(graph),
    )
