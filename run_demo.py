"""Run the full pipeline against demo_project and show results."""
import sys, os
sys.path.insert(0, '.')

from src.ingestion.file_traverser import collect_source_files
from src.ingestion.parser import parse_all_files
from src.graph.builder import build_graph
from src.graph.relationships import extract_edges
from src.ai.semantic_grouper import enrich_graph_with_contexts
from src.ai.summarizer import enrich_graph_with_summaries
from src.gaphor_gen.model_builder import build_gaphor_model, save_model

DEMO_DIR = os.path.join(os.path.dirname(__file__), "demo_project")

print("=" * 60)
print("   ARCHITECTURE DIAGRAM GENERATOR — LIVE DEMO")
print("=" * 60)

# Phase 1
print("\n[1/4] Scanning demo_project ...")
files = collect_source_files(DEMO_DIR)
print(f"      Found {len(files)} source files:")
for f in files:
    print(f"        - {os.path.relpath(f, DEMO_DIR)}")

metadata = parse_all_files(files)
print(f"      Extracted: {len(metadata['classes'])} classes, {len(metadata['interfaces'])} interfaces")
for cls in metadata['classes']:
    print(f"        Class: {cls['name']} (extends {cls['superclass'] or 'nothing'}, methods: {len(cls['methods'])})")
for iface in metadata['interfaces']:
    print(f"        Interface: {iface['name']} (methods: {len(iface['methods'])})")

# Phase 2
print("\n[2/4] Building dependency graph ...")
graph = build_graph(metadata)
extract_edges(metadata, graph)
print(f"      Nodes: {graph.number_of_nodes()} | Edges: {graph.number_of_edges()}")
print("      Relationships:")
for src, dst, edata in graph.edges(data=True):
    print(f"        {src}  ──[{edata['edge_type']}]──>  {dst}")

# Phase 3
print("\n[3/4] AI enrichment (Ollama @ localhost:11434) ...")
enrich_graph_with_contexts(graph)
enrich_graph_with_summaries(graph)
contexts = {graph.nodes[n].get('context', 'N/A') for n in graph.nodes()}
print(f"      Detected contexts: {', '.join(sorted(contexts))}")
summary_count = sum(1 for n in graph.nodes() if graph.nodes[n].get('responsibility'))
print(f"      Classes with AI summaries: {summary_count}")

# Phase 4
print("\n[4/4] Generating .gaphor file ...")
out_path = os.path.join(os.path.dirname(__file__), "demo_output.gaphor")
tree = build_gaphor_model(graph)
save_model(tree, out_path)
size_kb = os.path.getsize(out_path) / 1024
print(f"      Output: {out_path} ({size_kb:.1f} KB)")

# Validate
import gzip
with gzip.open(out_path, 'rb') as f:
    xml = f.read().decode('utf-8')
has_class = 'Class ' in xml or '<Class' in xml
has_iface = 'Interface' in xml
has_pkg = 'Package' in xml
has_inherit = 'GeneralizationItem' in xml
has_impl = 'RealizationItem' in xml
has_composition = 'AssociationItem' in xml
has_dep = 'DependencyItem' in xml
print(f"      Valid .gaphor: YES (gzip XML)")
print(f"      Contains UML Classes: {has_class}")
print(f"      Contains UML Interfaces: {has_iface}")
print(f"      Contains UML Packages: {has_pkg}")
print(f"      Contains Inheritance: {has_inherit}")
print(f"      Contains Implementation: {has_impl}")
print(f"      Contains Composition: {has_composition}")
print(f"      Contains Dependency: {has_dep}")

print("\n" + "=" * 60)
print("   DONE! Open demo_output.gaphor in Gaphor desktop app.")
print("=" * 60)
