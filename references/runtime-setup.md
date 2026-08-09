# Windows runtime setup

## Verified workstation runtime

The local runtime root is `D:\CodexVideoLearning\vision\skycaptioner`:

- Python virtual environment: `venv` (Python 3.11.15).
- PyTorch 2.7.1+cu128 and TorchVision 0.22.1+cu128.
- Transformers 4.51.3, Accelerate 1.7.0, Safetensors 0.5.3, and bitsandbytes 0.46.1.
- Structural model: `models\SkyCaptioner-V1` (seven indexed safetensors shards; 31,827,208,372 bytes across the verified payload).
- Fusion model: `models\Qwen2.5-32B-Instruct-GGUF` (all five Q4_K_M shards; 19,851,336,384 bytes).
- CUDA llama.cpp executable: `D:\CodexVideoLearning\vision\runtime\llama-cli.exe`.

The verified GPU is an NVIDIA GeForce RTX 4090. PyTorch CUDA tensor execution passed. SkyCaptioner loaded with the official `Qwen2_5_VLForConditionalGeneration` class using 4-bit NF4 weights and FP16 compute on `cuda:0`, with an observed model footprint of about 5.39 GiB. Do not attempt to keep the 31.83 GB official payload fully resident as FP16 on a 24 GiB card.

## Runtime safety

Run SkyCaptioner and 32B llama.cpp inference as independent hidden background processes when Codex Desktop is the controller. Write full output to a task-local log and completion state to a small JSON file; let Codex poll only that state with short commands. Do not hold a long-lived Codex tool call open around heavy local inference.

Use `--file <utf8-prompt-path>` to provide the first-turn fusion instruction and `--single-turn` for non-interactive llama.cpp fusion. Do not rely on stdin for the initial chat prompt: the verified Windows chat-template entry can start with an empty prompt instead of consuming the intended instruction. Add `--log-disable`, `--no-show-timings`, `--no-display-prompt`, and `--simple-io`; delete the single temporary prompt file in a `finally` path. Current llama.cpp auto-enables conversation mode for chat-template models; without `--single-turn` the model can produce the requested answer and remain at an interactive prompt indefinitely. This CLI may still mix its startup banner, truncated prompt echo, fenced completion, and exit marker into stdout; keep that as an explicit `partial` boundary rather than weakening the strict one-object parser. A successful job must record an exit code and leave no `llama-cli` process behind.

The runtime checker is read-only. It inspects local paths and never downloads models, launches inference, or establishes credentials. It defaults to the paths above but accepts explicit configuration for another workstation. Keep tokens, cookies, model credentials, model weights, logs, and local outputs out of the repository.

Official sources:

- [SkyCaptioner-V1](https://huggingface.co/Skywork/SkyCaptioner-V1)
- [Qwen2.5-32B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF)
- [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases)
