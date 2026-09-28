"""
Streamlit UI: minimal interface for the Architecture Diagram Generator.
"""

import os
import tempfile

import streamlit as st

from src.config import DEFAULT_OUTPUT_FILENAME
from src.ingestion.file_traverser import collect_source_files
from src.ingestion.parser import parse_all_files
from src.graph.builder import build_graph
from src.graph.relationships import extract_edges
from src.ai.semantic_grouper import enrich_graph_with_contexts
from src.ai.summarizer import enrich_graph_with_summaries
from src.gaphor_gen.model_builder import build_gaphor_model, save_model


def run_pipeline(root_dir: str, output_path: str) -> str:
    """
    Execute the full pipeline: ingest → graph → AI enrich → Gaphor → save.
    Returns the path to the generated .gaphor file.
    """
    # Phase 1: Ingestion
    st.info("Phase 1/4: Scanning and parsing source files ...")
    files = collect_source_files(root_dir)
    if not files:
        st.warning("No supported source files found in the given directory.")
        return ""
    st.write(f"Found {len(files)} source file(s).")
    metadata = parse_all_files(files)
    st.write(
        f"Parsed {len(metadata.get('classes', []))} classes and "
        f"{len(metadata.get('interfaces', []))} interfaces."
    )

    # Phase 2: Graph construction
    st.info("Phase 2/4: Building dependency graph ...")
    graph = build_graph(metadata)
    extract_edges(metadata, graph)
    st.write(f"Graph has {graph.number_of_nodes()} nodes and {graph.number_of_edges()} edges.")

    # Phase 3: AI enrichment
    st.info("Phase 3/4: Enriching with AI (Ollama) ...")
    enrich_graph_with_contexts(graph)
    enrich_graph_with_summaries(graph)
    contexts = {graph.nodes[n].get("context", "N/A") for n in graph.nodes()}
    st.write(f"Detected contexts: {', '.join(sorted(contexts))}")

    # Phase 4: Gaphor generation
    st.info("Phase 4/4: Generating .gaphor model ...")
    model = build_gaphor_model(graph)
    save_model(model, output_path)

    return output_path


def main():
    st.set_page_config(page_title="Architecture Diagram Generator", layout="centered")
    st.title("🏗️ Architecture Diagram Generator")
    st.markdown(
        "Point this tool at a Java or Python codebase to generate a "
        "native **.gaphor** architecture diagram with AI-enriched context labels."
    )

    # --- Input ---
    root_dir = st.text_input(
        "Codebase Directory (absolute path)",
        placeholder="e.g. C:\\Users\\kreje\\projects\\spring-boot-app",
    )

    # --- Output location ---
    output_path = st.text_input(
        "Output .gaphor file path",
        value=os.path.join(tempfile.gettempdir(), DEFAULT_OUTPUT_FILENAME),
    )

    # --- Generate button ---
    if st.button("Generate Architecture", type="primary"):
        if not root_dir or not os.path.isdir(root_dir):
            st.error("Please provide a valid directory path.")
            return

        with st.spinner("Running pipeline ..."):
            result_path = run_pipeline(root_dir, output_path)

        if result_path and os.path.isfile(result_path):
            st.success(f"✅ Architecture diagram saved to: `{result_path}`")
            with open(result_path, "rb") as f:
                st.download_button(
                    label="⬇️ Download .gaphor file",
                    data=f,
                    file_name=DEFAULT_OUTPUT_FILENAME,
                    mime="application/xml",
                )
        else:
            st.error("Failed to generate the diagram.")


if __name__ == "__main__":
    main()
