# Windows runtime setup

## Verified workstation runtime

The local runtime root is `D:\CodexVideoLearning\vision\skycaptioner`:

- Python virtual environment: `venv` (Python 3.11.15).
- PyTorch 2.7.1+cu128 and TorchVision 0.22.1+cu128.
- Transformers 4.51.3, Accelerate 1.7.0, Safetensors 0.5.3, and bitsandbytes 0.46.1.
- Structural model: `models\SkyCaptioner-V1` (seven indexed safetensors shards; 31,827,208,372 bytes across the verified payload).
- Fusion model: `models\Qwen2.5-32B-Instruct-GGUF` (all five Q4_K_M shards; 19,851,336,384 bytes).
- CUDA llama.cpp server executable: `D:\CodexVideoLearning\vision\runtime\llama-server.exe`.

The verified GPU is an NVIDIA GeForce RTX 4090. PyTorch CUDA tensor execution passed. SkyCaptioner loaded with the official `Qwen2_5_VLForConditionalGeneration` class using 4-bit NF4 weights and FP16 compute on `cuda:0`, with an observed model footprint of about 5.39 GiB. Do not attempt to keep the 31.83 GB official payload fully resident as FP16 on a 24 GiB card.

## Runtime safety

Run SkyCaptioner and 32B llama.cpp inference as independent hidden background processes when Codex Desktop is the controller. Start `llama-server` on a loopback-only port with one slot, redirect its logs to the task directory, and poll `/health` with short commands. Launch the fusion CLI itself as an independent background job when the controller is Codex Desktop. Do not hold a long-lived Codex tool call open around model loading or inference.

Video evidence extraction and prompt fusion do not require ComfyUI. Do not keep ComfyUI models loaded or run H3/Wan generation concurrently with the 32B fusion job. Stop only the task-owned `llama-server` after the four stages finish. The 2026-08-09 run used about 23.87/24.56 GiB total GPU memory while the 32B server was active and returned to about 1.42 GiB after it stopped; the earlier attribution of this peak to ComfyUI was incorrect. The i7-13700K reached 100 degrees Celsius during the run, which is a thermal-limit condition rather than a normal target. For later runs, cap llama.cpp CPU and batch threads in the task-owned server launcher, avoid concurrent heavy jobs, and monitor temperature; do not claim that CPU offload was proven by this run.

Pass the fusion inputs to `scripts/fuse_prompt_package.py --server-url http://127.0.0.1:<port>`. The adapter makes exactly four sequential `/v1/chat/completions` requests—base, I2V, enhanced, and variant replacement sections—and reads only `choices[0].message.content`. It performs no automatic model retry. The controller, not the model, copies manifest and engine fields, expands the complete variants, formats the eight prompt lines, and creates attribution rows. `fusion-response.raw.json` preserves the four raw assistant bodies by stage even when a later stage fails. Server banners and runtime logs never enter the strict parser. Bind only to `127.0.0.1`, disable the Web UI, and stop the task-owned server after completion. Do not weaken the strict one-object parser, restore one-shot full-package generation, or fall back to `llama-cli` stdout extraction.

The runtime checker is read-only. It inspects local paths and never downloads models, launches inference, or establishes credentials. It defaults to the paths above but accepts explicit configuration for another workstation. Keep tokens, cookies, model credentials, model weights, logs, and local outputs out of the repository.

Official sources:

- [SkyCaptioner-V1](https://huggingface.co/Skywork/SkyCaptioner-V1)
- [Qwen2.5-32B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF)
- [llama.cpp releases](https://github.com/ggml-org/llama.cpp/releases)
