"""Run local SkyCaptioner structural captioning without downloading model weights.

This Windows Transformers adapter is not a replacement for the official Linux/vLLM
SkyCaptioner release. It keeps visual structural analysis separate from other
video evidence and preserves the model's response for review.
"""

import argparse
import json
from collections.abc import Callable, Iterable
from pathlib import Path


STRUCTURAL_FIELDS = (
    "shot_id",
    "shot_type",
    "shot_size",
    "angle",
    "camera_position",
    "camera_motion",
    "expression",
    "environment",
    "lighting",
)


def _ordered_shots(manifest: dict) -> list[dict]:
    shots = manifest.get("shots")
    if not isinstance(shots, list):
        raise ValueError("evidence manifest requires a shots list")
    try:
        return sorted(shots, key=lambda shot: shot["timestamps"]["start"])
    except (KeyError, TypeError):
        raise ValueError("each shot requires timestamps.start") from None


def _validate_request_config(batch_size: int, frame_budget: int) -> None:
    if batch_size < 1:
        raise ValueError("batch_size must be positive")
    if frame_budget < 1:
        raise ValueError("frame_budget must be positive")


def build_structural_prompt(shot: dict) -> str:
    """Build a visual-only, schema-bound request for one source shot."""
    try:
        shot_id = shot["id"]
        evidence = shot["evidence"]
    except KeyError:
        raise ValueError("each shot requires id and evidence") from None
    if not isinstance(shot_id, str) or not shot_id:
        raise ValueError("shot id must be a non-empty string")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("each shot requires evidence")

    references = []
    for item in evidence:
        try:
            role = item["role"]
            timestamp = item["timestamp"]
            path = item["path"]
        except KeyError:
            raise ValueError("each evidence reference requires role, timestamp, and path") from None
        references.append(f"- {role} @ {timestamp}s: {path}")

    fields = ", ".join(f'"{field}"' for field in STRUCTURAL_FIELDS)
    return "\n".join(
        (
            "Analyze only the supplied visual evidence for this one shot.",
            f"Source shot id: {shot_id}",
            "Return one JSON object with exactly these required string fields: " + fields + ".",
            "You may add a string confidence_note. If any detail is not observable, use "
            '"uncertain" for that field and explain why in confidence_note.',
            "Do not infer dialogue, OCR text, audio, or human context.",
            "Evidence references:",
            *references,
        )
    )


def parse_model_response(raw_response: str, source_shot_id: str) -> dict:
    """Validate one model response without filling in absent structural values."""
    try:
        parsed = json.loads(raw_response)
    except (TypeError, json.JSONDecodeError):
        raise ValueError("model response must be a valid JSON object") from None
    if not isinstance(parsed, dict):
        raise ValueError("model response must be a valid JSON object")
    for field in STRUCTURAL_FIELDS:
        if field not in parsed:
            raise ValueError(f"model response missing required field: {field}")
        if not isinstance(parsed[field], str) or not parsed[field].strip():
            raise ValueError(f"model response field must be a non-empty string: {field}")
    if parsed["shot_id"] != source_shot_id:
        raise ValueError("model response shot_id must match the source shot id")
    if "confidence_note" in parsed and (
        not isinstance(parsed["confidence_note"], str) or not parsed["confidence_note"].strip()
    ):
        raise ValueError("model response confidence_note must be a non-empty string")

    result = {field: parsed[field] for field in STRUCTURAL_FIELDS}
    if "confidence_note" in parsed:
        result["confidence_note"] = parsed["confidence_note"]
    return result


def prepare_dry_run(
    manifest: dict,
    *,
    model_path: str,
    batch_size: int,
    frame_budget: int,
    device: str,
) -> dict:
    """Return deterministic requests without importing or loading a model backend."""
    _validate_request_config(batch_size, frame_budget)
    requests = []
    for shot in _ordered_shots(manifest):
        evidence = shot["evidence"][:frame_budget]
        request_shot = {**shot, "evidence": evidence}
        requests.append(
            {
                "shot_id": shot["id"],
                "prompt": build_structural_prompt(request_shot),
                "evidence": evidence,
            }
        )
    return {
        "mode": "dry-run",
        "model_path": model_path,
        "batch_size": batch_size,
        "frame_budget": frame_budget,
        "device": device,
        "requests": requests,
    }


def _load_transformers_backend(model_path: str, device: str) -> Callable[[list[dict]], list[str]]:
    """Load only a configured local Transformers model after dry-run is bypassed."""
    local_model = Path(model_path)
    if not local_model.is_dir():
        raise ValueError("model_path must be an existing local model directory")

    import torch
    from PIL import Image
    from transformers import AutoModelForVision2Seq, AutoProcessor

    torch_dtype = torch.float16 if device.startswith("cuda") else torch.float32
    processor = AutoProcessor.from_pretrained(local_model, local_files_only=True, trust_remote_code=True)
    model = AutoModelForVision2Seq.from_pretrained(
        local_model,
        local_files_only=True,
        torch_dtype=torch_dtype,
        trust_remote_code=True,
    ).to(device)
    model.eval()

    def caption(requests: list[dict]) -> list[str]:
        messages = []
        images = []
        for request in requests:
            content = []
            for evidence in request["evidence"]:
                with Image.open(evidence["path"]) as image:
                    images.append(image.convert("RGB"))
                content.append({"type": "image", "image": evidence["path"]})
            content.append({"type": "text", "text": request["prompt"]})
            messages.append([{"role": "user", "content": content}])
        prompts = [
            processor.apply_chat_template(message, tokenize=False, add_generation_prompt=True)
            for message in messages
        ]
        inputs = processor(images=images, text=prompts, return_tensors="pt", padding=True)
        inputs = {name: value.to(device) for name, value in inputs.items()}
        generated = model.generate(**inputs, max_new_tokens=512)
        input_lengths = [len(input_ids) for input_ids in inputs["input_ids"]]
        generated_tokens = [
            output[input_length:] for output, input_length in zip(generated, input_lengths, strict=True)
        ]
        return processor.batch_decode(generated_tokens, skip_special_tokens=True)

    return caption


def _batches(items: list[dict], size: int) -> Iterable[list[dict]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def run_structural_captioning(
    manifest: dict,
    *,
    model_path: str,
    batch_size: int,
    frame_budget: int,
    device: str,
    backend: Callable[[list[dict]], list[str]] | None = None,
) -> list[dict]:
    """Run structural-only requests and retain model output with evidence references."""
    dry_run = prepare_dry_run(
        manifest,
        model_path=model_path,
        batch_size=batch_size,
        frame_budget=frame_budget,
        device=device,
    )
    caption = backend or _load_transformers_backend(model_path, device)
    records = []
    for batch in _batches(dry_run["requests"], batch_size):
        raw_responses = caption(batch)
        if not isinstance(raw_responses, list) or len(raw_responses) != len(batch):
            raise ValueError("backend must return one ordered response per request")
        for request, raw_response in zip(batch, raw_responses, strict=True):
            record = parse_model_response(raw_response, request["shot_id"])
            records.append(
                {
                    **record,
                    "raw_model_response": raw_response,
                    "evidence": request["evidence"],
                }
            )
    return records


def _write_jsonl(records: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run local SkyCaptioner structural video captioning.")
    parser.add_argument("evidence_manifest", type=Path)
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--batch-size", type=int, default=1)
    parser.add_argument("--frame-budget", type=int, default=3)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = json.loads(args.evidence_manifest.read_text(encoding="utf-8"))
    output_root = Path("D:/VideoLearning/work") / args.task / "video-prompt-reverse"
    if args.dry_run:
        result = prepare_dry_run(
            manifest,
            model_path=args.model_path,
            batch_size=args.batch_size,
            frame_budget=args.frame_budget,
            device=args.device,
        )
        output_path = args.output or output_root / "skycaptioner-dry-run.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        result = run_structural_captioning(
            manifest,
            model_path=args.model_path,
            batch_size=args.batch_size,
            frame_budget=args.frame_budget,
            device=args.device,
        )
        output_path = args.output or output_root / "skycaptioner-structural.jsonl"
        _write_jsonl(result, output_path)
    print(output_path)


if __name__ == "__main__":
    main()
