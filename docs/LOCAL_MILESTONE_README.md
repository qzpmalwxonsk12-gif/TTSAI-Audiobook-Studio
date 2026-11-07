# TTSAIIdea — local audiobook studio

A working first milestone for a novel-to-audiobook application, built for Windows and English text.
It uses Kokoro ONNX speech synthesis, persistent voice blends, and a local Ollama speaker-analysis adapter.

## Start
Double-click **Start.cmd**, then open http://127.0.0.1:8767.
Keep its terminal open while generating. Closing the browser does not stop the worker.
Closing the terminal stops the app; interrupted jobs become paused on the next launch.
The computer must remain awake for overnight production. The app does not change Windows power settings.

The isolated environment and models were installed in this folder.
Measured first sample: roughly 6 minutes of local speaker analysis for about one minute of audio.
This prototype is useful for testing the workflow; local live-analysis speed needs improvement. For another computer:
install Python 3.11+ and Ollama, then run Setup.cmd. Models require roughly 3 GB of downloads.
No paid API key is required. No novel text is sent to external services.

## Use
1. Import pasted text or a UTF-8 TXT file. Numbered "Chapter 1" headings split chapters.
2. Click **Map the story**. The AI reads passage context, lookahead, and the saved cast.
3. Review uncertain passages under **Script & review**. Edit character aliases and preview voices.
4. Choose full narration or dialogue-only, optionally include thoughts, then **Generate audiobook**.
5. Play/download separate chapters or the combined FLAC from **Audio library**.

**Listen as chapters finish** maps and generates sequentially. It begins playback after the first complete
chapter is ready. This is chapter buffering, not instant sentence-by-sentence streaming. Ambiguity pauses
production unless you explicitly enable narrator fallback. The whole-book route maps first and gives you
a review step before synthesis.

## Persistence and recovery
- data/library.sqlite3: books, source spans, cast, manual corrections, job states and raw analysis responses.
- data/audio/cache: exact text + voice recipe + actual model hash -> reusable PCM audio.
- data/audio/exports: chapter WAV, combined FLAC, and production manifests.
- models: Kokoro weights, model hashes, isolated Ollama model store and log.
- The dedicated Ollama instance uses 127.0.0.1:11435; it does not change your usual Ollama model folder.
- Manual corrections are locked against later analysis. Merging characters retains the chosen target voice.
- Pause interrupts active analysis (checked every 0.25 seconds). Completed batches remain saved; resume retries the interrupted batch. Speech pauses after the current speech segment.
- Keep this folder on one computer while running; do not run multiple app instances on the same database.
  Because the requested folder is under OneDrive, local files may also be synced by your OneDrive settings.

## Voice design
Kokoro blends actual voice vectors, not just pitch shifts. The exact two-voice blend and speed are saved.
New named characters receive a saved blend, influenced only by an explicitly supported voice profile.
The prototype does not promise unlimited perceptually distinct voices, voice cloning, or emotional acting.
Change a main character's voice after listening to a preview if the automatic choice is unsuitable.

## Current boundaries
- AI confidence is a model estimate, not a calibrated probability. Review even high-confidence results.
- Full-book mapping is sequential with persistent cast/context. There is no automatic global second pass
  that retroactively resolves every ambiguous earlier identity.
- Unusual quote conventions, nested quotes, and multi-paragraph dialogue need careful manual review.
  Segments can be reclassified and assigned; arbitrary split/join editing is a future feature.
- First release supports English, TXT/paste, and WAV chapters / FLAC books. EPUB/PDF, MP3/M4B, video, subtitles and packaging
  are future milestones. Combined FLAC streams to disk without the WAV RIFF size limit.
- Very large casts stop with a clear context-budget error; a retrieval index is a future milestone.
- Existing exports are retained; edits conservatively mark earlier revisions as stale.
- Local analysis currently has one implemented provider (Ollama); its protocol is replaceable.
  Cloud providers, credentials and remote URLs are intentionally not implemented.
- No arbitrary prose rewriting or context-summary mode.
- Verify novel and voice rights before publishing an audiobook.

## Development
Open this exact folder in VS Code. Read **HANDOFF.md** for measured validation and the next steps.
Run tests: .venv\Scripts\python.exe -m pytest -q
Run server manually: .venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8767
Frontend: plain HTML/CSS/JS in static/. No Node build step.
Use one server worker. Do not expose this prototype to a network.

Source documentation:
- https://github.com/thewh1teagle/kokoro-onnx
- https://huggingface.co/hexgrad/Kokoro-82M
- https://docs.ollama.com/api/chat
