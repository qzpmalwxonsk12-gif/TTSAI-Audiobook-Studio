# TTSAIIdea — VS Code continuation

## Current cloud milestone — 8 September 2026

Latest fix: Gemini returned HTTP 400 for schema-constrained requests despite working authentication and basic generation. Mapping/casting now use JSON response mode with the schema in the instruction, retaining all Pydantic and exact-passage-ID validation before saving. Real Gemini 3.5 mapping and casting probes passed; 3.8 returned intermittent 503 busy responses during testing. Failed attempts (including provider quota failures) are terminal and hidden from the job list with one transient error notification; they cannot resume, but a fresh attempt reuses saved mapping/cache. Deliberate pause and review states remain resumable. Historical records are retained for accounting and export references. 41 Python tests passed.

Follow-up: read-only provider authentication succeeded for Gemini, ElevenLabs and Hume; ElevenLabs confirmed Free, 0/10,000 credits used. Session keys are configured but not persisted. Added actual ElevenLabs account usage, honest local counters for all three providers, and per-job allowance percentages. Gemini/Hume billing tiers remain unverified. No generation or key rotation was performed. Validation is now 39 passing Python tests plus read-only Chrome usage-panel acceptance. See the follow-up at the top of docs/CLOUD_PROTOTYPE.md.

Read [docs/CLOUD_PROTOTYPE.md](docs/CLOUD_PROTOTYPE.md) first. It supersedes local-only claims below. Implemented: empty books, numbered chapter upload/paste, Gemini mapping and persistent cloud casting, Gemini/ElevenLabs/Hume speech adapters, contextual clickable review, audio timelines and following text, session keys and usage guards. Docker/Render persistent-disk deployment is prepared, not deployed. No provider keys were available for real cloud generation. Validation: 36 Python tests passed and isolated Chrome fixture acceptance passed. The original data and models were preserved; a pre-migration SQLite backup is under data/backups. Start.cmd now avoids launching Ollama; Start-local.cmd enables legacy startup. The remainder of this document records the earlier local milestone.

For a new laptop or assistant session, read TRANSFER_HANDOVER.md first.

Open this exact folder: C:\Users\Arjun\OneDrive\Desktop\TTSAIIdea
Read README.md and docs/ARCHITECTURE.md. User brief: docs/PROJECT_BRIEF.md.
Start.cmd launches the app at http://127.0.0.1:8767. It is currently running locally.

## Goal and present milestone
Create novel audiobooks with a persistent cast and reproducible voices: map-first production plus
buffered listen-as-you-go. Full narration, dialogue-only and internal thoughts are selectable.
This is a working first milestone, not a finished production audiobook publisher.

## Implemented
- FastAPI API and browser studio, TXT/paste imports, numbered chapter splitting.
- Exact imported text in data/sources; source spans and annotations stored separately in SQLite.
- Book-specific character IDs, names, aliases, notes, exact Kokoro voice blends/speed.
- Voice previews/editor, explicit character merges, passage correction with manual locks.
- Local Ollama structured analysis with persistent cast, source context and forward lookahead.
- Required cast/speaker/profile fields; compact request IDs; reject omitted/duplicate/foreign IDs.
- Direct source speech/thought tags and narrowly matched appositional aliases override AI guesses.
- One production worker, review gate, checkpoints, interruption recovery, pause/resume.
- Cache keyed by source text, exact voice recipe and actual model weights.
- Streamed chapter WAV and combined lossless FLAC; full and dialogue-only exports.
- Chapter-buffered playback. This is not low-latency sentence streaming.
- Loopback-only endpoints, Host/Origin checks, escaped text and no cloud text uploads.
- VS Code Python interpreter setting, dependency lock snapshot and meaningful tests.

## Verified on the actual laptop
Ryzen 7 5700U, integrated Radeon, approximately 14 GB usable RAM.
Speech uses four CPU threads. Models release memory between text and speech stages.
Dedicated Ollama port 11435, models/ollama; the usual Ollama instance/store is unchanged.

20 tests pass. Coverage includes source integrity, required response fields, malformed AI outputs,
cross-book identity rejection, merging, locked corrections, alias ambiguity, restart recovery,
job/edit locking, review gate, dialogue filtering, pause, FLAC losslessness, complete artifact publication,
and integration of deterministic source evidence into the mapping pipeline.
Two dependency deprecation warnings are recorded; they do not fail these tests.
Python compilation and JavaScript syntax checks pass.

Real inference/audio evidence is in docs/runtime-report.json and docs/runtime-initial.json.
The original three-chapter sample uses headings Chapter 1, Chapter 2 and Chapter 72;
this is not an evaluation on seventy-two actual chapters.
- Mapping the 34 passages took 351.1 seconds with Qwen3 4B on this CPU/current desktop load.
- Final reviewed cast produces about 62 seconds of full audio and 19 seconds of dialogue-only audio.
- A fresh 3.567-second voice sample synthesized in 1.505 seconds, excluding first engine load.
- Repeat preview returned the identical cache URL with zero synthesis time.
- Distinct character recipes produced different real PCM waveforms.
- Actual app restart retained the exact cast and reused saved audio.
- The initially failed export successfully resumed after its export-record fix.
- Browser import, mapping, voice editing and visible cast state were exercised; desktop layout inspected.

The model-only sample misattributed Sam's returning line and missed an explicit thought.
These errors are retained in runtime-initial.json. Production source-evidence rules were then replayed
against the real annotations and verified to fix both while keeping the genuinely unknown speaker flagged.
The final sample voices were intentionally reviewed through the UI (Mira Sarah/Nicole; Sam Michael/Onyx)
and audio regenerated. This is manual casting, not a claim that the model always chooses a fitting voice.
Fresh inference of the final required profile schema identified Sam correctly, but returned a neutral
voice profile despite an explicit male description. This casting-quality limitation is recorded in
docs/final-profile-smoke.json; automatic voice suitability still requires review.

## Important limitations / next work
1. Local analysis is slow: about six minutes to map one minute of this sample's audio. No real-time or
   overnight completion promise for long novels. Evaluate a faster local model / efficient labeling pipeline.
2. AI confidence is not calibrated. The tiny sample is not broad attribution accuracy evidence.
3. Add scene-aware split/join controls, evidence-backed aliases and a whole-book reconciliation pass.
   Current whole-book mapping is sequential with lookahead; it cannot revisit every earlier ambiguity.
4. Add a cast retrieval index for large novels. Oversized casts currently stop with a context-budget error.
5. Improve sentence buffering and playback recovery. Existing exports are conservatively marked stale by
   a book revision rather than precise dependencies.
6. English TXT/paste only. MP3/M4B, EPUB/PDF, subtitles, video and a packaged installer remain future work.
7. No emotional acting control or voice cloning. Distinct blend recipes may still sound similar.
8. Whole-book jobs must run while the PC is awake. No OS sleep/power settings were changed.
9. OneDrive may sync this folder according to the user's existing settings. Run one instance/computer.

## Files and commands
Application: app/store.py, text.py, analysis.py, voices.py, jobs.py, main.py.
UI: static/index.html, style.css, app.js.
Tests: .venv\Scripts\python.exe -m pytest -q
Server: .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8767
Real acceptance harness: scripts/verify_runtime.py (creates original sample data and may take several minutes).
Evidence replay/export harness: scripts/finalize_verification.py (retains original model errors).
Runtime library: data/library.sqlite3. Raw analysis is stored in analysis_log.
Exports: data/audio/exports; exact recipe manifests live beside chapter WAV files.
Keep user data, model files and pre-existing .qodo assets intact. Use .venv, not system Python.

## Small review update (2026-09-05)
Script & review now opens the complete chapter with clickable red-underlined review spans.
The review list and passage dialog include the containing paragraph plus one paragraph above/below.
Chapter-local narration/dialogue, thoughts, narrator fallback and generate/analyze controls reuse existing jobs.
TXT/paste import was already supported. Earlier export revisions are hidden by default with an opt-in toggle.
Corrected male Mira recipe in the older original-test-story demo to Sarah/Nicole; newer demo was already female.
Historical audio was preserved, not regenerated. Regenerate older audio to apply the corrected casting.
Verified JS syntax, context boundaries, Unicode offsets, HTML escaping, selected-chapter settings wiring,
and live HTTP serving. No new model inference or long audio generation was run for this small update.

## Prompt mapping pause (2026-09-05)
Analysis HTTP requests now run as cancellable async tasks; the worker checks pause/shutdown every 0.25 seconds, including while waiting for response headers. Cancellation closes the connection; only complete validated batches are saved. Resume retries the interrupted batch. Speech remains interruptible between passages.
Stopped the requested Aftermath and Test jobs and restarted the app to disconnect the old blocking request. Both remain resumable; no source or historical audio was removed.
Validation: 21 tests passed, including cancellation of an in-flight stalled request in under two seconds with no partial mappings saved, plus existing persistence/source/identity/recovery tests. No expensive new model generation was run.

## Partial speech recovery — 8 September 2026
The first real ElevenLabs render stopped at the app's 60-request guard, after 4,521 speech characters; provider balance was 4,521/10,000 credits used. Recovered the contiguous first 60/170 passages from existing matching WAV cache files into a 289.76-second incomplete chapter artifact, with manifest timeline and spoken TXT. No new synthesis calls were made. Incomplete artifact IDs use the `incomplete-` prefix and the frontend displays them in an Incomplete audio section. This was a one-time recovery, not automatic partial-export support for future failures. Existing mapping and cache were preserved.


## Deepgram integration - 10 September 2026
Deepgram Aura-2 is now available under Speech AI, Cloud connections, and usage tracking. Sixteen curated English voices include gender, age, accent and timbre descriptions for Gemini casting. Assignments remain book/character/provider specific. On a previously mapped book, Step 1 reuses mapped passages and assigns only missing provider voices; this casting step still uses Gemini. Alternatively assign voices manually in Cast. Step 2 generates WAV audio with existing passage playback timings and review gates.

Each Deepgram character supports saved speed (0.7-1.5, native API) and pitch (-3 to +3 semitones, local FFmpeg RubberBand with preserved formants). Pitch-only changes reuse the original speech cache without further API calls. Speed or voice changes require new synthesis. Direction is casting metadata, not a spoken prompt or acting control. Aura-2 expressiveness is not exposed. Other providers retain their previous behavior and caches.

Authentication uses the fixed api.deepgram.com/v1/speak endpoint and Authorization Token header. Keys remain session-only or DEEPGRAM_API_KEY environment secrets. The usage panel reports app requests/characters, including reserved failed attempts; Deepgram account remaining credits/percentage are unavailable, with a console link. No unlimited-free claim or automatic paid fallback. The imageio-ffmpeg 0.6.0 dependency bundles FFmpeg; Windows pitch processing was verified, Docker/Linux deployment was not tested.

Verification: 43 Python tests passed (including real local pitch processing, cache reuse, authentication format, durable usage and saved settings). Browser checks confirmed 16 voices, visible controls and no JavaScript errors. A real 36-character Deepgram preview with speed 0.95 and pitch +0.6 produced 2.4 seconds of decoded audio through the app. This validates live synthesis, not a full-book quality audition. Original books, mapping and audio remain intact; a SQLite backup precedes the additive migration. The app was restarted and its four connections restored to session memory. Hosting remains prepared only.

Official references: https://developers.deepgram.com/docs/tts-models and https://developers.deepgram.com/docs/tts-voice-controls
