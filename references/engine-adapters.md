# Engine adapters

Adapt only after the shared prompt package passes strict validation. Keep prompt prose, input assets, and structured engine parameters as separate payload parts. Use parameter names and values only when confirmed by the selected installed workflow or official submission API.

## Route the shared package

| Target | Map from the shared package | Verification boundary |
|---|---|---|
| MiniMax H3 | Select the complete T2V or I2V reconstruction prompt; attach the required image input for I2V; carry anchors and the two negative categories without merging them. | Treat availability, accepted fields, parameter names, and visual behavior as unverified until the chosen H3 endpoint or local workflow is inspected and smoke-tested. |
| Wan 2.2 T2V | Use the T2V prompt, anchors, timeline intent, and validated negatives. | Confirm the installed workflow and exposed inputs before assigning parameters. |
| Wan 2.2 I2V | Use the I2V prompt plus the authorized initial image and identity/composition anchors. | Verify image constraints and workflow wiring locally. |
| Wan 2.2 Reference | Supply only authorized reference assets in declared order and use the compatible complete prompt. | Confirm that the installed workflow actually exposes reference conditioning. |
| Wan 2.2 Continuation | Supply the authorized source clip, extension intent, boundary continuity anchors, and the compatible prompt. | Confirm accepted duration/context limits and continuation controls. |
| Wan 2.2 FirstLastFrame | Supply authorized first/last keyframes plus the intended action and camera path between them. | Confirm that both frame inputs and their ordering are exposed. |
| Wan 2.2 Camera | Map camera position, lens/depth intent, motion path, timing, and stabilization character. | Use only camera controls exposed by the inspected workflow; otherwise retain them in prose. |
| Wan 2.2 ContextWindows | Map ordered neighboring-shot context, continuity anchors, and the current shot prompt. | Confirm window count, ordering, and overlap semantics before setting parameters. |
| Wan 2.2 TESpeed | Map requested temporal emphasis or speed intent from action/timing analysis. | Do not invent a `TESpeed` value or flag; verify the installed node/API contract first. |
| Seedance or another cloud engine | Before submission, create or update the project `视频生成任务上下文提交包.md` from the validated package, preserving story, character, style, shot order, actions, model requirement, prohibitions, and input-asset order. | Confirm that the submission entry point explicitly selects or strongly constrains the requested model. If it cannot, disclose that boundary and do not submit. |
| Generic engine | Use the closest complete prompt, authorized assets, anchors, timeline, separated negatives, and explicit uncertainties. | Label unsupported or unknown capabilities; keep unverified settings out of parameters. |

## Selection rules

- Ask the user to choose local or cloud execution and H3, Wan, Seedance, or another engine. Provide a recommendation with its evidence, but do not turn it into a hard rule.
- Run the local runtime health check before offering local execution as ready. Label a discovered component `installed-but-unverified` when only files or static executable structure are proven.
- Record the chosen engine name and confirmed scalar settings in the structured engine object. Keep CLI flags, node wiring, credentials, and model paths out of prompt prose.
- Preserve reconstruction prompts as source-faithful deliverables even when adapting the enhanced prompt for a specific engine.
- Return to `media-studio-orchestrator` before any generation. Use `comfyui-video-workflow-author` only for an approved local workflow; use the selected cloud submission route only after its model-selection and context-package gates pass.
