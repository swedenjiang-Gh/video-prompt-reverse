# Windows runtime setup

This checker only inspects local paths. It does not download models, launch
processes, or establish credentials. Runtime installation is completed by Task 7;
this document does not claim that any component is installed.

Use `D:\CodexVideoLearning\vision\skycaptioner` as the SkyCaptioner root. Its
structural model belongs in `models\SkyCaptioner-V1`. Place the five official
Qwen Q4_K_M GGUF shards in `models\Qwen2.5-32B-Instruct-GGUF`, including
`qwen2.5-32b-instruct-q4_k_m-00001-of-00005.gguf` through `00005-of-00005.gguf`.

Install a CUDA-capable Windows build of llama.cpp separately and provide its
executable plus safe CUDA evidence to `check_runtime` through configuration. Keep
Python available locally. Do not put tokens, cookies, model credentials, or model
weights in this repository.

Official model pages:

- SkyCaptioner: https://huggingface.co/Skywork/SkyCaptioner-V1
- Qwen2.5-32B-Instruct-GGUF: https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF
- llama.cpp releases: https://github.com/ggml-org/llama.cpp/releases
