"""
Git integration for the Architecture Diagram Generator.

Provides:
  1. Pre-commit hook: validates architectural consistency before allowing a commit.
     - Detects changed modules
     - Regenerates diagrams for affected components
     - Checks that the new diagram is consistent with the last committed version
     - Blocks the commit if structural violations are detected

  2. Merge request integration: posts architecture diagram updates as comments
     on GitHub/GitLab merge requests when code changes affect the architecture.

  3. CLI tooling for manual diagram regeneration and consistency checks.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
