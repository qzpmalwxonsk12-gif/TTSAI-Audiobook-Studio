# TTSAIIdea: new laptop and assistant handover

## Latest handover — 8 September 2026

Start with [docs/CLOUD_PROTOTYPE.md](docs/CLOUD_PROTOTYPE.md) and README.md. This checkout now includes cloud mapping/speech, chapter management, interactive review and playback following text. The full guide records APIs, private Render deployment preparation, verification and remaining work. The source package excludes data/models/secrets. This checkout does not contain unshared changes from the friend's laptop; compare before merging. The GPU-focused instructions and local-only policy below are historical. Cloud operations are now authorized when the user supplies/configures keys. Hosting is not live and real provider quality is unverified.

Prepared 2026-09-05. This is context for an assistant without the original conversation. Verify the destination hardware and runtime; historical measurements below were made on the original laptop.

## Give the new assistant this instruction

Read AGENTS.md, TRANSFER_HANDOVER.md, README.md and HANDOFF.md. Continue this existing application, without rebuilding it. Set it up on this Windows laptop and verify the RTX 5050 is used for story mapping. Preserve books, source text, saved voices, manual reviews and historical audio. Keep changes focused. Run a short end-to-end check and report measured results. Speech currently uses CPU; GPU speech needs a separate implementation and verification if requested. Do not upload novel text or use paid APIs.

## What the user wants

Create audiobooks from pasted novels, with persistent character identities and voices across hundreds of chapters. Sam in chapter 1 must retain his voice in chapter 72. Support whole-story mapping then review/render, and listening as completed chapters become available. Options include narration plus dialogue, dialogue-only, thoughts, and narrator fallback for uncertain speakers. Review must show the surrounding novel text. The user prefers a simple interface, real working features, small changes, and economical usage. Avoid unnecessary long inference runs or broad refactors.

## Moving the folder

1. Pause jobs and stop the source app before copying to keep SQLite and audio consistent. Preserve the source installation.
2. Copy TTSAIIdea to a local folder such as C:/TTSAIIdea on the friend's laptop. Exclude .venv; virtual environments must be recreated. Python cache folders can also be omitted.
3. Include all of data/ (books, reviews, cast, source and audio, including any SQLite companion files) and models/ (weights and dedicated Ollama storage). Preserve the pre-existing .qodo folder. Prefer a destination outside OneDrive.
4. Install Python 3.11 with PATH enabled, current Ollama for Windows and a current NVIDIA driver. Open a new terminal and check python --version and ollama --version. Setup.cmd uses the command python, so verify it selects the intended interpreter.
5. Run Setup.cmd. It creates .venv, installs requirements.txt, checks/downloads speech files and pulls/verifies qwen3:4b in the dedicated model store. Existing models are reused; missing dependencies require internet.
6. Run Start.cmd and open http://127.0.0.1:8767/. Keep the launcher running, plug in the laptop and keep it awake during production.
7. Open this destination folder in VS Code if desired. .vscode/settings.json already uses a workspace-relative interpreter.

The original path was C:/Users/Arjun/OneDrive/Desktop/TTSAIIdea. Old absolute paths and statements in HANDOFF.md that the app is running refer to the original machine. Runtime paths generally derive from the folder location. Never copy or reuse the original Python environment.

## Verify GPU mapping

The analyzer calls local Ollama with qwen3:4b and does not force CPU use. Ollama chooses GPU offload automatically. The friend's RTX 5050 laptop has not been inspected or benchmarked. Verify GPU identity, driver, VRAM and RAM. Keep the existing model for the initial comparison; no speed multiplier is established.

While a short chapter is actively mapping, run in PowerShell:

```powershell
$env:OLLAMA_HOST = "127.0.0.1:11435"
ollama ps
```

PROCESSOR should show 100% GPU for full placement; a CPU/GPU split indicates partial offload. An empty list between batches is possible because requests use keep_alive=0. Use the dedicated port 11435, not the friend's ordinary Ollama instance. Do not modify their unrelated model storage or service.

Use nvidia-smi and models/ollama.log to investigate GPU discovery and memory. If CPU-only, check Ollama/driver versions, free VRAM and inherited environment variables disabling GPU. The Windows Task Manager 3D graph alone is not reliable inference evidence. A full CUDA development toolkit is not required just to run Ollama.

Recheck current official documentation when troubleshooting:
- https://docs.ollama.com/gpu
- https://docs.ollama.com/faq
- https://ollama.com/download/windows

## Speech remains CPU-only

app/voices.py explicitly uses ONNX Runtime CPUExecutionProvider, four intra-op threads and one inter-op thread. Copying the project will not move Kokoro speech onto the GPU. Mapping was the main observed bottleneck; CPU speech already worked.

If GPU speech is requested, check current ONNX Runtime GPU/CUDA/cuDNN compatibility for RTX 5050 before changing dependencies. Avoid conflicting runtime packages. Add explicit provider selection with CPU fallback. Verify actual uncached synthesis, provider use, timings and playable audio, not only a provider listing. Preserve exact cast recipes; consider cache identity if backend changes affect output. No GPU speech integration has been implemented or tested.

## Implementation map

- Python 3.11; FastAPI/Uvicorn; SQLite; plain HTML/CSS/JavaScript, no frontend build step. requirements.txt contains the actual dependency versions.
- start.py starts a dedicated Ollama service on 127.0.0.1:11435 using models/ollama. App port is 8767. Run one app instance/worker.
- app/text.py: chapter splitting and exact source spans. app/analysis.py: structured labels, validation, identities and explicit source-evidence corrections.
- app/store.py: book-scoped persistence, locks, revisions and startup recovery. app/jobs.py: sequential map/render queue and checkpoints.
- app/voices.py: saved two-voice Kokoro blends, mixing weight, speed and language; cache keyed by exact text, recipe and model weights; WAV chapters and combined FLAC.
- app/main.py: API and serving. static/: import, cast editor/preview, chapter review, jobs and audio library.
- docs/PROJECT_BRIEF.md and docs/ARCHITECTURE.md explain scope. HANDOFF.md contains original implementation evidence and limitations.
- Listen mode buffers complete chapters, not individual sentences. Whole-story mapping is sequential, not a global reconciliation pass. There are no external text uploads or paid providers.

## Recent changes that must be preserved

1. Script & review shows the complete original chapter. Uncertain passages are clickable and red-underlined. The review list and edit dialog show the containing paragraph plus one paragraph above/below. static/review.js handles HTML escaping and Python codepoint versus JavaScript UTF-16 offsets.
2. Chapter-local full/dialogue, thoughts and stop-for-review/narrator-fallback settings apply to selected-chapter analysis/generation. Paste import already exists.
3. Earlier audio revisions are hidden by default with an opt-in checkbox. The older original-test-story demo's Mira recipe was corrected from male to Sarah/Nicole; the newer demo was already corrected. Historical audio was retained, not regenerated. Old exports need regeneration to reflect voice edits. Automatic voice-profile selection remains imperfect.
4. Mapping pause now uses asyncio.run with a cancellable httpx.AsyncClient task and a checkpoint every 0.25 seconds, including before response headers arrive. Cancellation closes the request; only complete validated batches are saved. Resume retries the interrupted batch. Speech still pauses between passages.
5. Aftermath and Test were stopped at the user's request and left resumable in paused state. Their job IDs are b81b016b3c474a8598472049434a8342 and b5ba3a2e5f5343e4a5159b931c3ed852. Do not automatically resume these long jobs on transfer. The original app process/session is not portable.

## Evidence and its limits

- Latest run: 21 tests passed with two dependency deprecation warnings. Coverage includes persistence, source integrity, identities, locked corrections, recovery, review gates, exports and interruption.
- New cancellation test simulates a stalled HTTP client, verifies interruption under two seconds and no partial mappings saved. Prompt cancellation on the actual GPU still needs destination verification. Do not call the simulated test a measured GPU stop.
- Review UI checks covered JavaScript syntax, paragraph boundaries, Unicode offsets, escaping and selected-chapter settings. No new long inference accompanied those UI changes.
- Original CPU sample: 34 passages mapped in 351.1 seconds; about 62 seconds full audio and 19 seconds dialogue-only. A fresh 3.567-second voice sample took 1.505 seconds excluding initial load. See docs/runtime-report.json, docs/runtime-initial.json and docs/final-profile-smoke.json.
- The sample has only three chapters labelled 1, 2 and 72. Model attribution/profile mistakes occurred and examples were corrected through source rules/manual review. This is not broad novel accuracy evidence.

## Destination acceptance checklist

1. Confirm copied books, source and cast are intact. Back up data before substantive changes.
2. Run .venv/Scripts/python.exe -m pytest -q. Tests use isolated storage. Do not casually run long acceptance scripts against user data.
3. Start one app instance and verify status, review controls and existing audio playback.
4. Map a short original sample; record model, driver, GPU placement, elapsed time and passage count.
5. Pause during inference. Confirm paused state promptly AND Ollama computation stops. Verify saved batches/manual edits persist and resume completes without partial or duplicate mappings.
6. Generate/play a short uncached sample with saved voices. Report CPU speech unless GPU speech was actually integrated and tested.
7. Update HANDOFF.md with measured destination results and unresolved issues.

## Future work

Improve attribution and voice profiles, scene-aware split/join, whole-book reconciliation, large-cast retrieval, context/model-loading efficiency, finer playback buffering and precise export invalidation. EPUB/PDF import, MP3/M4B, subtitles/video and packaging remain future work. Current target is English TXT/paste. Emotional acting, cloning and unlimited perceptually distinct voices are not implemented. Keep these separate from the immediate transfer/GPU check.
