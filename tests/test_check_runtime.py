import sys
from pathlib import Path

from scripts.check_runtime import QWEN_SHARDS, check_runtime


def _minimal_pe() -> bytes:
    header = bytearray(0x44)
    header[:2] = b"MZ"
    header[0x3C:0x40] = (0x40).to_bytes(4, "little")
    header[0x40:0x44] = b"PE\0\0"
    return bytes(header)


def _healthy_config(tmp_path: Path) -> dict:
    skycaptioner = tmp_path / "skycaptioner" / "models" / "SkyCaptioner-V1"
    skycaptioner.mkdir(parents=True)
    (skycaptioner / "config.json").write_text("{}", encoding="utf-8")
    (skycaptioner / "model.safetensors").write_bytes(b"weights")

    qwen = tmp_path / "skycaptioner" / "models" / "Qwen2.5-32B-Instruct-GGUF"
    qwen.mkdir()
    for shard in QWEN_SHARDS:
        (qwen / shard).write_bytes(b"gguf")

    llama = tmp_path / "llama-cli.exe"
    llama.write_bytes(_minimal_pe())
    cuda = tmp_path / "cudart64_12.dll"
    cuda.write_bytes(_minimal_pe())
    return {
        "skycaptioner_root": skycaptioner.parent.parent,
        "qwen_root": qwen,
        "llama_cpp_executable": llama,
        "cuda_evidence_path": cuda,
        "python_executable": Path(sys.executable),
    }


def test_check_runtime_reports_partial_when_structural_model_is_missing(tmp_path):
    """Creating only the model directory must not count as structural model files."""
    config = _healthy_config(tmp_path)
    model = config["skycaptioner_root"] / "models" / "SkyCaptioner-V1"
    (model / "config.json").unlink()
    (model / "model.safetensors").unlink()

    report = check_runtime(config)

    assert report["state"] == "partial"
    assert report["components"]["skycaptioner"]["state"] == "missing"
    assert any("SkyCaptioner-V1" in blocker for blocker in report["blockers"])


def test_check_runtime_reports_missing_first_qwen_shard(tmp_path):
    """Dropping shard 00001 must make the Qwen payload incomplete."""
    config = _healthy_config(tmp_path)
    (config["qwen_root"] / QWEN_SHARDS[0]).unlink()

    report = check_runtime(config)

    assert report["state"] == "partial"
    assert report["components"]["qwen"]["state"] == "partial"
    assert any(QWEN_SHARDS[0] in blocker for blocker in report["blockers"])


def test_check_runtime_reports_ready_for_healthy_cuda_llama_chain(tmp_path):
    """Removing any required local component must prevent a ready report."""
    report = check_runtime(_healthy_config(tmp_path))

    assert report["state"] == "ready"
    assert report["components"]["llama_cpp"]["state"] == "ready"
    assert report["components"]["cuda"]["state"] == "ready"
    assert report["components"]["qwen"]["shard_count"] == 5


def test_check_runtime_rejects_a_truncated_mz_only_llama_fixture(tmp_path):
    """Accepting MZ alone would treat arbitrary text as a usable executable."""
    config = _healthy_config(tmp_path)
    config["llama_cpp_executable"].write_bytes(b"MZ not a PE executable")

    report = check_runtime(config)

    assert report["state"] == "partial"
    assert report["components"]["llama_cpp"]["state"] == "missing"


def test_check_runtime_rejects_an_unrelated_cuda_file(tmp_path):
    """CUDA evidence must have a recognized runtime filename, not merely exist."""
    config = _healthy_config(tmp_path)
    unrelated = tmp_path / "runtime-notes.txt"
    unrelated.write_text("not cuda", encoding="utf-8")
    config["cuda_evidence_path"] = unrelated

    report = check_runtime(config)

    assert report["state"] == "partial"
    assert report["components"]["cuda"]["state"] == "missing"


def test_check_runtime_rejects_a_same_name_cuda_text_file(tmp_path):
    """A recognized CUDA basename without a PE image is not usable evidence."""
    config = _healthy_config(tmp_path)
    config["cuda_evidence_path"].write_text("not a PE image", encoding="utf-8")

    report = check_runtime(config)

    assert report["state"] == "partial"
    assert report["components"]["cuda"]["state"] == "missing"


def test_check_runtime_accepts_a_cuda_path_style_directory_without_reporting_it(tmp_path, monkeypatch):
    """CUDA_PATH roots need a bounded bin marker check without leaking their value."""
    config = _healthy_config(tmp_path)
    cuda_root = tmp_path / "cuda-root-not-for-reporting"
    cuda_marker = cuda_root / "bin" / "cudart64_12.dll"
    cuda_marker.parent.mkdir(parents=True)
    cuda_marker.write_bytes(_minimal_pe())
    config.pop("cuda_evidence_path")
    monkeypatch.setenv("CUDA_PATH", str(cuda_root))

    report = check_runtime(config)

    assert report["state"] == "ready"
    assert report["components"]["cuda"]["state"] == "ready"
    assert str(cuda_root) not in repr(report)


def test_check_runtime_never_reports_secret_config_values(tmp_path):
    """Serializing config or environment values would expose this deliberate secret."""
    config = _healthy_config(tmp_path)
    config["token"] = "do-not-report-this-token"

    report = check_runtime(config)

    assert "do-not-report-this-token" not in repr(report)


def test_check_runtime_reports_missing_when_no_local_component_exists(tmp_path):
    """Treating absent payloads as partial would hide a clean-machine setup need."""
    missing = tmp_path / "missing"

    report = check_runtime(
        {
            "skycaptioner_root": missing,
            "qwen_root": missing,
            "llama_cpp_executable": missing,
            "cuda_evidence_path": missing,
            "python_executable": missing,
        }
    )

    assert report["state"] == "missing"


def test_check_runtime_blocks_an_invalid_configuration():
    """Accepting a non-mapping config would make safe inspection ambiguous."""
    report = check_runtime("not a configuration")

    assert report == {
        "state": "blocked",
        "components": {},
        "blockers": ["Invalid runtime configuration."],
    }


def test_check_runtime_blocks_a_required_path_set_to_none():
    """Treating a required root as the current directory risks unsafe discovery."""
    report = check_runtime({"skycaptioner_root": None})

    assert report["state"] == "blocked"
