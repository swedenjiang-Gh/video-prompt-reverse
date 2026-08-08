"""Read-only health checks for the local video-prompt-reverse runtime."""

import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path


DEFAULT_SKYCAPTIONER_ROOT = Path("D:/CodexVideoLearning/vision/skycaptioner")
DEFAULT_QWEN_ROOT = DEFAULT_SKYCAPTIONER_ROOT / "models" / "Qwen2.5-32B-Instruct-GGUF"
DEFAULT_LLAMA_EXECUTABLE = Path("D:/CodexVideoLearning/llama.cpp/llama-cli.exe")
QWEN_SHARDS = tuple(
    f"qwen2.5-32b-instruct-q4_k_m-{index:05d}-of-00005.gguf"
    for index in range(1, 6)
)


def _path(
    config: Mapping[str, object], key: str, default: Path | None, *, allow_none: bool = False
) -> Path | None:
    value = config.get(key, default)
    if value is None:
        if allow_none:
            return None
        raise ValueError(key)
    if not isinstance(value, (str, Path)):
        raise ValueError(key)
    return Path(value)


def _files(path: Path) -> list[Path]:
    if not path.is_dir():
        return []
    return [item for item in path.rglob("*") if item.is_file()]


def _component(state: str, label: str, **details: int | str) -> dict:
    return {"state": state, "label": label, **details}


def _is_pe_file(path: Path | None) -> tuple[bool, int]:
    if path is None or not path.is_file():
        return False, 0
    try:
        size = path.stat().st_size
        with path.open("rb") as executable:
            dos_header = executable.read(0x40)
            if len(dos_header) < 0x40 or dos_header[:2] != b"MZ":
                return False, size
            pe_offset = int.from_bytes(dos_header[0x3C:0x40], "little")
            if pe_offset < 0x40 or pe_offset + 4 > size:
                return False, size
            executable.seek(pe_offset)
            return executable.read(4) == b"PE\0\0", size
    except OSError:
        return False, 0


def _is_llama_executable(path: Path | None) -> tuple[bool, int]:
    if path is None or path.suffix.lower() != ".exe":
        return False, 0
    return _is_pe_file(path)


def _is_cuda_marker(path: Path) -> bool:
    name = path.name.casefold()
    if name not in {"nvcuda.dll", "nvcc.exe"} and not re.fullmatch(
        r"(?:cudart|cublas)64(?:_\d+)?\.dll", name
    ):
        return False
    return _is_pe_file(path)[0]


def _is_cuda_evidence(path: Path | None) -> bool:
    if path is None:
        return False
    if path.is_file():
        return _is_cuda_marker(path)
    if not path.is_dir():
        return False
    bin_directory = path / "bin"
    if not bin_directory.is_dir():
        return False
    candidates = [bin_directory / "nvcuda.dll", bin_directory / "nvcc.exe"]
    candidates.extend(bin_directory.glob("cudart64_*.dll"))
    candidates.extend(bin_directory.glob("cublas64_*.dll"))
    return any(_is_cuda_marker(candidate) for candidate in candidates)


def check_runtime(config: Mapping[str, object]) -> dict:
    """Return a safe, read-only local runtime health report."""
    if not isinstance(config, Mapping):
        return {"state": "blocked", "components": {}, "blockers": ["Invalid runtime configuration."]}

    try:
        sky_root = _path(config, "skycaptioner_root", DEFAULT_SKYCAPTIONER_ROOT)
        qwen_root = _path(config, "qwen_root", DEFAULT_QWEN_ROOT)
        llama_path = _path(config, "llama_cpp_executable", DEFAULT_LLAMA_EXECUTABLE)
        cuda_default = os.environ.get("CUDA_PATH")
        cuda_path = _path(
            config,
            "cuda_evidence_path",
            Path(cuda_default) if cuda_default else None,
            allow_none=True,
        )
        python_path = _path(config, "python_executable", Path(sys.executable))
    except (TypeError, ValueError):
        return {"state": "blocked", "components": {}, "blockers": ["Invalid runtime configuration."]}

    structural_root = sky_root / "models" / "SkyCaptioner-V1"
    structural_files = _files(structural_root)
    structural_bytes = sum(item.stat().st_size for item in structural_files)
    components = {
        "skycaptioner": _component(
            "ready" if structural_files else "missing",
            "models/SkyCaptioner-V1",
            file_count=len(structural_files),
            size_bytes=structural_bytes,
        )
    }
    blockers = []
    if not structural_files:
        blockers.append("SkyCaptioner-V1 structural model files are missing.")

    present_shards = []
    if qwen_root and qwen_root.is_dir():
        names = {item.name.casefold() for item in qwen_root.iterdir() if item.is_file()}
        present_shards = [name for name in QWEN_SHARDS if name.casefold() in names]
    missing_shards = [name for name in QWEN_SHARDS if name not in present_shards]
    qwen_state = "ready" if not missing_shards else ("partial" if present_shards else "missing")
    components["qwen"] = _component(
        qwen_state,
        "models/Qwen2.5-32B-Instruct-GGUF",
        shard_count=len(present_shards),
        required_shards=len(QWEN_SHARDS),
    )
    if missing_shards:
        blockers.extend(f"Missing Qwen GGUF shard: {name}." for name in missing_shards)

    llama_ready, llama_size = _is_llama_executable(llama_path)
    components["llama_cpp"] = _component(
        "ready" if llama_ready else "missing",
        "configured llama.cpp executable",
        size_bytes=llama_size,
    )
    if not llama_ready:
        blockers.append("A usable llama.cpp executable is missing.")

    cuda_ready = _is_cuda_evidence(cuda_path)
    components["cuda"] = _component("ready" if cuda_ready else "missing", "CUDA availability evidence")
    if not cuda_ready:
        blockers.append("CUDA availability evidence is missing.")

    python_ready = python_path is not None and python_path.is_file()
    components["python"] = _component("ready" if python_ready else "missing", "Python runtime")
    if not python_ready:
        blockers.append("Python runtime is missing.")

    component_states = [component["state"] for component in components.values()]
    if all(state == "ready" for state in component_states):
        state = "ready"
    elif any(state == "ready" or state == "partial" for state in component_states):
        state = "partial"
    else:
        state = "missing"
    return {"state": state, "components": components, "blockers": blockers}
