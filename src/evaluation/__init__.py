"""
Evaluation & Comparison engine: Static Analysis vs LLM-based diagram generation.

Provides a systematic framework for comparing:
  1. Static analysis (tree-sitter) — deterministic structural extraction
  2. LLM interpretation — semantic understanding of architecture

Comparison dimensions:
  - Entity detection accuracy (precision/recall of identified classes/interfaces)
  - Relationship detection accuracy (correct edge type classification)
  - Context/package grouping quality
  - Responsibility summarization quality
"""
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
