# Upstream attribution

Use the MIT-licensed prompt-structure method from [luozhilzh/video-prompt-reverse](https://github.com/luozhilzh/video-prompt-reverse) as a reference, not as an unmodified drop-in Skill.

The repository's upstream MIT license was retrieved from https://raw.githubusercontent.com/luozhilzh/video-prompt-reverse/main/LICENSE on 2026-08-08 and is reproduced in this repository's `LICENSE`.

## Model and implementation references

- Use the official [SkyCaptioner-V1 model card](https://huggingface.co/Skywork/SkyCaptioner-V1) for the structural-caption model boundary and upstream usage notes.
- Use the official [Qwen repository](https://github.com/QwenLM/Qwen) and [Qwen2.5-32B-Instruct-GGUF model card](https://huggingface.co/Qwen/Qwen2.5-32B-Instruct-GGUF) for Qwen/llama.cpp compatibility claims.
- Use [ZeroLu/awesome-seedance](https://github.com/ZeroLu/awesome-seedance) only as a curated prompt/reference example source when adapting Seedance-facing context.

The scripts and Skill instructions in this repository are independently implemented. Do not claim that SkyCaptioner, Qwen, or awesome-seedance code was copied into this Skill; cite a source only where its model guidance, prompt example, or method informed the result.
