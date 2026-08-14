"""Resolve canonical task-owned output directories."""

import os
from pathlib import Path


DEFAULT_OUTPUT_ROOT = Path(r"D:\MediaStudio\VideoPromptReverse")


def resolve_task_output(
    task: str,
    *,
    output_root: Path | None = None,
    project_output: Path | None = None,
) -> Path:
    """Use a project-owned directory when supplied, otherwise root the standalone job."""
    if not task or task in {".", ".."} or any(mark in task for mark in ("/", "\\")):
        raise ValueError("task must be one local task directory name")
    if project_output is not None:
        return Path(project_output)
    root = Path(
        output_root
        or os.environ.get("VIDEO_PROMPT_REVERSE_ROOT", DEFAULT_OUTPUT_ROOT)
    )
    return root / task
