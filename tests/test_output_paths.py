import os
from pathlib import Path
from unittest.mock import patch

from scripts.output_paths import resolve_task_output


def test_standalone_reverse_task_uses_dedicated_root():
    with patch.dict(os.environ, {}, clear=True):
        assert resolve_task_output("demo-job") == Path(
            r"D:\MediaStudio\VideoPromptReverse\demo-job"
        )


def test_project_output_overrides_standalone_root():
    assert resolve_task_output(
        "demo-job", project_output=Path(r"E:\AI视频\project\reverse")
    ) == Path(r"E:\AI视频\project\reverse")


def test_environment_root_is_respected():
    with patch.dict(
        os.environ,
        {"VIDEO_PROMPT_REVERSE_ROOT": r"E:\MediaStudio\Reverse"},
        clear=False,
    ):
        assert resolve_task_output("demo-job") == Path(
            r"E:\MediaStudio\Reverse\demo-job"
        )
