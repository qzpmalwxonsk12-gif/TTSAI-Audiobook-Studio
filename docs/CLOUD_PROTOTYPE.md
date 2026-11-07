# TTSAI cloud audiobook prototype — complete handover

Prepared 8 September 2026. This is the current guide for this checkout. It supersedes earlier statements that cloud APIs are not implemented. The older local-engine notes remain useful for the original Kokoro/Ollama installation.

### Follow-up: connected keys and usage panel

**Mapping fix after first user run:** Gemini rejected schema-constrained requests with HTTP 400. The adapter now requests JSON mode and includes the schema in its instruction instead of passing `responseJsonSchema`/`responseSchema` to generation configuration. Returned data still passes strict Pydantic validation and exact passage-ID checks before saving. A real Gemini 3.5 passage-mapping probe and a real casting probe both passed. Gemini 3.8 also produced intermittent HTTP 503 high-demand errors. Gemini 2.5 returned a model-unavailable error for this account despite appearing in model listings; use 3.5 for the next run. No audiobook speech synthesis was tested in this fix.

Failed attempts now disappear from the visible job list and produce a one-time transient error notification. Provider failures, including quota errors, terminate an attempt rather than leaving it paused for Resume. Start a new attempt once the cause is resolved; saved mapped passages and audio cache are reused. Manual pauses and review gates remain resumable. Database history and usage records are preserved, so hiding a failed row does not erase its counted usage or orphan audio. Validation is now **41 Python tests passed**, with browser verification that the affected book has no failed rows or failed Resume buttons. Earlier pause-on-quota descriptions below are historical.

After the initial handover, the user supplied provider credentials. Read-only authentication checks succeeded for all three services. ElevenLabs' subscription API confirmed `tier=free`, 0 used of a 10,000-credit allowance, and allowance extension disabled at the time of checking. Gemini's model listing and Hume's voice listing accepted their keys; those responses do not establish the accounts' billing tiers or actual generation quotas. No paid plan was enabled, no text generation or speech synthesis request was made, and no API keys were written into this guide, the source or the delivery ZIP. Keys were loaded into the running app's session memory and will need re-entry after restart.

The API usage panel now shows:

- ElevenLabs' provider-reported credits used, total allowance, credits remaining, percentage used, plan and reset date. This is the account billing cycle, not necessarily a calendar month. Provider-reported values may lag recent generation.
- App-tracked request counts and speech characters for each provider this UTC calendar month, plus requests today. These are durable request reservations, including failed/uncertain attempts, and exclude activity in other applications. Mapping input tokens are not measured by the speech-character counter.
- The selected book's latest cloud job's request and speech-character allowance, each with a percentage bar. This is the app's guardrail, not an account quota.
- Explicitly unavailable account balances for Gemini and Hume, with dashboard links. Unknown quotas are never displayed as zero or as a made-up percentage. A missing/denied ElevenLabs balance likewise remains unavailable.

The browser refreshes the panel every 30 seconds while visible. A Refresh usage button is also available. ElevenLabs account checks, including failures, are cached for 60 seconds to avoid excessive requests; changing the key changes the cache identity. These checks use a read-only subscription endpoint and do not consume speech-generation credits.

For the current ElevenLabs integration, grant **Text to Speech: Access** (`text_to_speech`), **Voices: Read** (`voices_read`), and **User: Read** (`user_read`) for the balance panel. The third permission is unnecessary for synthesis itself. There is no need to grant voice deletion/write, workspace management or all permissions. Keys authenticate against a workspace quota; extra keys do not create extra credits. [ElevenLabs key permissions and quotas](https://elevenlabs.io/docs/overview/administration/workspaces/api-keys).

Current public free offerings include eligible Gemini models and Hume's 10,000 monthly TTS characters, but account-specific access must still be checked in the relevant dashboard. Hume and ElevenLabs free output is non-commercial; consult current terms before monetized publishing. [Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing), [Hume pricing](https://www.hume.ai/pricing), [Hume TTS FAQ](https://dev.hume.ai/docs/text-to-speech-tts/faq), [ElevenLabs publishing terms](https://help.elevenlabs.io/hc/en-us/articles/13313564601361-Can-I-publish-the-content-I-generate-on-the-platform).

No multiple-key rotation system was implemented; the user only asked about feasibility. Gemini quotas are per project, ElevenLabs quotas are per workspace, and Hume prohibits creating multiple accounts to obtain extra free-tier benefits. [Gemini quota scope](https://ai.google.dev/gemini-api/docs/rate-limits), [Hume terms](https://www.hume.ai/terms-of-use).

Validation after this addition: **39 Python tests passed**, including account-versus-local accounting, job percentages, month boundaries, missing permission, cached failures, changed keys and zero/unknown allowances. A separate read-only Chrome test of the real running app passed with the actual ElevenLabs account balance and no JavaScript errors. New files: `app/usage.py`, `static/usage-ui.js`, `tests/test_usage.py`, and `tests/browser_usage.cjs`. Earlier statements about credentials being unavailable below describe the initial build; real generation quality and hosting remain unverified.

## 1. Delivery status

The application now supports the requested book → chapters → Gemini mapping → review → selected cloud speech → audio with following text workflow. It remains a single-user prototype. Cloud inference runs at the selected provider; the studio, database, job coordinator, and audio assembly run wherever you start this application.

| Area | Status |
| --- | --- |
| Empty books, numbered chapters, TXT upload and paste | Implemented and tested |
| Gemini mapping adapter and persistent character casting | Implemented; API contract tested with controlled responses |
| Gemini TTS, ElevenLabs, and Hume speech adapters | Implemented; response decoding, cache and failure paths tested with fixtures |
| Full source text, clickable passages, contextual review, red uncertainty marks | Implemented and browser tested |
| Chapter WAV and combined FLAC, passage-following playback | Implemented and browser tested with synthetic audio |
| Saved books, characters, manual corrections, provider-specific voices and job progress | Implemented in SQLite and local files |
| Private cloud deployment configuration | Prepared for Render, including persistent storage and password protection |
| Live hosted URL | **Not deployed**: no hosting account credentials were available |
| Real Gemini / ElevenLabs / Hume synthesis or listening quality comparison | **Not run**: no provider API keys were available |
| Docker image execution on the target host | **Not verified in this session** |

Do not confuse the browser's successful demonstration with a real provider quality benchmark. The automated browser test uses an isolated fixture server and synthetic speech data. No novel text was sent to a speech or mapping provider during these tests.

The current application lives in `C:\Users\Arjun\OneDrive\Desktop\TTSAIIdea`. This work does not include unshared changes on the friend's laptop. Compare that checkout before combining the two versions.

## 2. Starting the application

### This laptop

Run `Start.cmd` and open `http://127.0.0.1:8767`. The default launcher now starts the studio without starting Ollama. Keep the server terminal open. The browser can close while jobs continue, but the laptop and server must stay running until the app is actually hosted elsewhere.

The original local models and data have been preserved. Use `Start-local.cmd` to enable the dedicated local Ollama startup, then select local providers in the studio. Cloud-only installations do not include the local model dependencies or weights.

### Another Windows computer, cloud API mode

1. Copy or extract the source folder.
2. Install Python 3.11 or a compatible newer release.
3. Run `Setup-cloud.cmd` to create the folder's isolated Python environment and install cloud requirements.
4. Run `Start.cmd`.
5. Open Cloud connections and enter the keys for the services you want to use.

The source ZIP contains application source, tests, launchers and documentation. It deliberately excludes your library, novel text, audio, model downloads, Python environment and secrets. To transfer an existing library, stop its server and separately copy its entire `data` directory. Preserve the original copy.

### Key handling

The Cloud connections dialog has separate Gemini, ElevenLabs and Hume fields. Keys entered there remain in the server process's memory; they are not saved in browser storage or the library database. They disappear when the server restarts. The connection status only returns a yes/no indication, never the stored key.

For unattended hosting, supply `GEMINI_API_KEY`, `ELEVENLABS_API_KEY` and/or `HUME_API_KEY` as hosting dashboard secrets. Environment keys survive a restart through the host's configuration. Removing a connection in the UI disables it for that running server session; remove the dashboard secret as well if it should remain removed after restart. Secrets are not included in the deployment files.

Gemini is needed for mapping and automatic cloud casting even when another provider produces the speech. Gemini-only operation requires one key; ElevenLabs or Hume speech additionally requires that provider's key.

## 3. Books and chapter text

Create book can create an empty named book. Initial pasted text or a TXT file remains optional; an initial text import can still split recognized numbered chapter headings.

Inside a book, Add chapter accepts a chapter number, optional title, and either pasted text or a TXT file. Numbers determine ordering, so adding 72 before 1 still displays chapter 1 first. Duplicate chapter numbers are rejected. The chapter-number limit is 1 to 1,000,000; the chapter API limits text to 1,000,000 characters. The upload control uses a conservative 1 MB file limit. Use UTF-8 TXT files.

The app preserves imported source text and stores passage annotations separately. Text can be read in full, including narration and unspoken material. Changing a passage's speaker does not rewrite the novel. The tests include emoji and original line breaks so source offsets remain aligned across Python and JavaScript Unicode representations.

Adding chapters or changing cast/review data requires the book's active job to finish or pause. This protects the job's view of the source and cast. Existing chapter prose does not yet have an arbitrary replacement, splitting, or joining editor; make corrections to classification and speaker through review.

## 4. Step 1: mapping and casting

Select the mapping provider and model, then select the speech provider before pressing **Step 1: Start mapping**. Gemini is the default mapping provider. The legacy Ollama option remains available for installations with local models.

Mapping sends source passages, surrounding context, forward lookahead and the saved cast to Gemini. It asks for structured classifications and speaker assignments. The parser requires every requested passage exactly once and rejects missing, duplicated, or foreign passage IDs. It identifies narration, dialogue and thoughts, with confidence/review information.

Existing characters have persistent book-specific IDs, aliases and descriptions. A character's saved voice remains associated with that character across chapters. Manual speaker corrections are locked against later mapping. These mechanisms support Sam retaining his casting in chapters 1 and 72; they cannot guarantee that the model will always recognize a disguised character or an obscure alias correctly.

After mapping a chapter, automatic casting selects voices for characters that do not yet have a voice for the chosen provider. Gemini receives character descriptions, aliases, voice profiles and the available voice catalog. It returns an existing voice ID, delivery direction and casting reason. Casting is batched; completed batches are saved. Existing assignments are reused rather than randomized on every run.

Mapping and casting use the chosen Gemini model. The selectable cloud models in this version are `gemini-3.8-flash`, `gemini-3.5-flash` and `gemini-2.5-flash`. Availability is provider-controlled and can change. If one is unavailable to an account, select another supported option.

The app saves the job's chosen settings with the book. Production options are snapshotted for a running job, so changing visible controls does not change an already running request.

### Review before production

Open Script & review to read the chapter in full. Every segmented passage is clickable, including narration and confident dialogue. Uncertain passages receive red underlining. Clicking a passage opens its classification, speaker and review controls with the preceding and following paragraphs for context where those paragraphs exist.

You can change the speaker, classify the passage as narration/dialogue/thought, and either resolve it or keep it flagged. A deliberately unknown speaker can remain flagged. Save commits the correction and invalidates audio from earlier book revisions; it does not silently alter audio already produced.

The cast editor lets you adjust names, aliases, descriptions and voices. Metadata and the selected cloud voice are saved together, so an invalid voice cannot leave half an edit committed. Existing character merge behavior remains available; inspect provider assignments after complex cast changes.

## 5. Voice identity and the three speech providers

Each character has separate saved assignments for Gemini, ElevenLabs and Hume. Switching providers uses that provider's assignment, or requires casting if it has none. Provider voice IDs are not interchangeable.

For Gemini, the application offers the documented prebuilt voice catalog. ElevenLabs voices come from the account's `/v1/voices` response. Hume lists the first 100 shared `HUME_AI` catalog entries. The editor also accepts an existing provider voice ID. This version does not browse all pages of Hume voices or automatically enumerate all custom voices.

Automatic casting selects from catalogs. It does **not** create an unlimited number of new voice identities or clone voices. Characters can share a base voice. Descriptive direction can influence performance but is not a guarantee of a completely different vocal identity. Reusing a provider ID is more stable than asking a model to invent a fresh voice on each chapter, but generative delivery may still vary between calls.

| Provider | Model / version used | How character instructions are used |
| --- | --- | --- |
| Gemini TTS | `gemini-3.1-flash-tts-preview` | Saved prebuilt voice ID plus delivery direction in the synthesis request |
| ElevenLabs | `eleven_v3` | Saved account-accessible voice ID; exact passage text is sent. The saved direction is casting metadata in this adapter, not injected acting tags |
| Hume | TTS version `2` | Saved voice ID and description/delivery direction in the utterance request |

Listen to main characters' previews and override unsuitable assignments before rendering a long book. The program can preserve a chosen voice, but the correct gender, age and character interpretation still need listening verification. This session did not establish that one of these providers sounds better than the friend's local Kokoro/Qwen/Cosy/Chatterbox setup.

Preview requests use the selected provider and can consume its quota. The preview limit described below applies separately from production jobs.

## 6. Step 2: production, review policy and playback

After mapping and review, press **Step 2: Produce audiobook**. Choose full narration plus dialogue or dialogue-only, whether to include thoughts, and whether unresolved passages may use the narrator. With fallback disabled, unresolved required speech pauses production for review. With fallback enabled, the manifest records the actual narrator used for those passages.

Production checks that the included text is mapped and the required cast has voices. It renders passages, normalizes audio to 24 kHz mono, inserts short gaps, and assembles chapter WAV files. Whole-book output also produces a combined FLAC. FLAC avoids WAV's conventional large-file size constraint for long books.

Speech cache keys include the provider, model, exact text, voice and direction. Matching passages can reuse audio without a new provider request. Changed casting or delivery changes the cache key. A decoded output is written atomically, so interrupted writes do not become apparently complete cache files.

Exports receive unique filenames, and earlier audio is preserved. A manifest stores passage IDs, chapter IDs, actual speakers and start/end times. Current timings use decoded audio durations, with 0.16 seconds between passages and 0.7 seconds between chapters in combined output. The manifest is written before its artifact is published to the library.

### Following text

Playing a new export loads its timing manifest. The current spoken passage is highlighted, and Follow audio scrolls to it and changes chapters as needed. Seeking through the audio updates the passage highlight. Clicking a passage pauses playback for review; Play this passage seeks to its corresponding interval when one exists in the loaded audio.

These are **passage-level timings**, not word-by-word forced alignment. Silence or unspoken material may have no highlighted passage. The app relies on the provider's audio matching the supplied text; it does not currently transcribe the result to detect omissions, additions or incorrect pronunciation.

Correcting text annotations or casting pauses current playback and tells you to regenerate. Earlier exports are marked stale and hidden by default, with an option to inspect them. An old export may have no timing data; regenerate it to enable following text. Audio is not patched live when you change a speaker.

### Buffered listening and recovery

The existing Listen as chapters finish mode maps and renders sequentially, starting playback after a complete chapter becomes available. This is chapter buffering, not live sentence streaming.

Jobs support pause/resume and keep completed mapping and audio cache work. Cloud requests are checked for interruption approximately every quarter-second, and an interrupted local HTTP task is cancelled. This does not guarantee the provider stops work or reverses a charge after receiving the request. Interrupted requests may need retrying. Process restarts leave interrupted jobs paused for explicit recovery.

SQLite transactions coordinate job creation, pickup and state changes to reduce queued/pause races. Run one server process with one worker on a library; this is not a distributed queue.

## 7. APIs, limits and what “free” means here

This application calls providers directly from the Python server. No GPU, local language model, or local neural speech model is required for cloud mode. This laptop still handles the browser, networking, audio conversion and assembly. A fully hosted instance moves that work to the host as well.

| Purpose | Endpoint | Authentication |
| --- | --- | --- |
| Gemini mapping / casting | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | Google API key header |
| Gemini speech | Same generateContent route with AUDIO response and voice configuration | Google API key header |
| ElevenLabs catalog | `https://api.elevenlabs.io/v1/voices` | `xi-api-key` |
| ElevenLabs speech | `https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128` | `xi-api-key` |
| Hume shared voices | `https://api.hume.ai/v0/tts/voices` | `X-Hume-Api-Key` |
| Hume speech | `https://api.hume.ai/v0/tts` | `X-Hume-Api-Key` |

Gemini mapping requests structured JSON with a schema. Gemini speech receives PCM audio, ElevenLabs receives MP3, and Hume receives base64 WAV. SoundFile decodes the results and SciPy resamples them. Provider URLs are fixed in the adapter; the UI does not accept arbitrary remote endpoints. HTTP redirects are disabled.

API access and consumer subscriptions are separate. A Gemini/Google AI consumer subscription does not substitute for a configured API key or prove that a particular API model has quota. Free offerings, region eligibility, model access and licenses can change. Nothing in this prototype grants credits or bypasses billing setup.

The default production guard is 60 outgoing generation requests and 10,000 speech characters per job. The UI exposes the speech-character allowance. Mapping and casting count against the request limit; mapping input tokens/characters are **not** covered by the speech-character cap. Preview requests have a separate shared daily guard of 15 requests and 5,000 speech characters.

Reservations are recorded in SQLite before a request is sent. Failed or uncertain requests remain counted because the provider may have received them. Cached speech does not need a new request. Resuming the same job keeps its recorded usage; creating another job is a new allowance. These are local guardrails, not account-wide accounting or a monetary budget.

HTTP 429 pauses the job with a quota/rate-limit explanation; there is no automatic loop that burns through retries. Authentication failures are reported without exposing provider keys or raw response payloads. The app does not fall back to another paid provider. **A paid-enabled key can still incur charges at the provider you selected.** Use provider-side billing caps and actual quota information; this prototype cannot promise a zero bill.

For public audiobook publishing, verify the novel's rights and the specific provider account's output license. Free access should not be assumed to include commercial publishing rights. Review each provider's data-use terms before sending unpublished or sensitive manuscripts.

## 8. Hosting decision and prepared deployment

### Selected approach: one Render Docker web service with a persistent disk

The prepared deployment runs the existing Python app as one service with its SQLite database, source text and audio on a persistent disk. This preserves the tested single-worker design and avoids rebuilding the app around several services just for the prototype.

Render's free web service is unsuitable for reliable overnight processing with this storage design: free services sleep after inactivity and do not provide persistent disks. The supplied `render.yaml` therefore selects a **paid Starter service plus a 10 GB persistent disk**. Saving these files does not provision anything or charge an account. No Render service, bill, URL or account was created during this work.

This is the main outstanding distinction: inference can use eligible free API quotas; dependable always-on hosting is a separate cost. The app can stay local while you test free APIs, then move to Render when hosting access and the cost are acceptable.

### Deployment files

| File | Responsibility |
| --- | --- |
| `Dockerfile` | Python 3.11 cloud-only image, app/static/sample code, one hosted entry point |
| `.dockerignore` | Excludes local data, models, environments, secrets and unrelated workspace content |
| `requirements-cloud.txt` | Cloud runtime dependencies without local Kokoro/ONNX model requirements |
| `render.yaml` | Starter service, 10 GB disk at `/var/data`, health route and generated password |
| `scripts/serve_cloud.py` | Requires a password and public host settings, launches one worker |

The container has no local GPU requirement. Local engine choices remain visible for compatibility but are not available in this cloud-only image.

### Activating it when the account is available

1. Put the source in a repository accessible to your Render account. Keep it private if appropriate. Do not commit `data`, `models`, `.env`, keys or the virtual environment.
2. Create a Render Blueprint using `render.yaml`. Inspect Render's actual quoted service and disk prices before activating it.
3. Keep the single instance/worker and persistent disk configuration. `TTSAI_DATA` must point to `/var/data`.
4. Read the generated `TTSAI_PASSWORD` privately in the hosting dashboard. The hosted app uses browser HTTP Basic authentication; the username is ignored and the password is checked. Use HTTPS. This is a private single-user gate, not a full account system.
5. Render supplies its external hostname. The entry script derives the permitted host and HTTPS public URL. For a custom domain, set `TTSAI_HOSTS` and `TTSAI_PUBLIC_URL` to the actual domain/origin.
6. Add provider keys as secret environment variables, or enter session keys after login. Session keys disappear on restart.
7. Deploy, verify `/health`, log in, create a small test book, run mapping, manually inspect casting, and synthesize a few passages. Listen to the result before starting an overnight batch.
8. Test pause/resume and confirm the book and audio survive a service restart. Back up the disk data before importing a large library.

Until those steps run on the actual account, hosting is prepared, not validated or live. This session did not build or execute the Docker image on Render.

### Hosting operations

The server's `/health` route is public for host checks; studio/API content requires the configured password. Trusted-host and same-origin checks are retained. Do not start the normal unauthenticated loopback launcher as a public service; use the hosted entry point.

The password is shared by anyone using this instance. There is no per-user isolation, account registration, password recovery, role system, audit console or public multi-tenant service. Provider keys entered into an instance are shared by its jobs. Do not share access with strangers.

Audio can fill a 10 GB disk during long projects. Monitor actual usage, preserve needed downloads and back up before cleanup or resizing. This version does not implement automatic retention, object storage, backup scheduling or storage alerts. A persistent disk is not a complete backup strategy.

## 9. Storage, migration and preservation

The original `data/library.sqlite3` was backed up before schema migration to `data/backups/before-cloud-20260908.sqlite3`. Existing books, model files, historical exports and the `.qodo` folder were preserved.

The database migration is additive: books gain saved settings; characters gain a voice profile; `cloud_cast` stores provider-specific voice IDs, direction and reasons; `cloud_usage` records local usage reservations. Existing local voice recipes remain in place.

| Location | Contents |
| --- | --- |
| `data/library.sqlite3` | Library, chapter/passages, cast, corrections, jobs, export references, cloud assignments and usage |
| `data/sources` | Original imported source files |
| `data/audio/cache` | Reusable generated passage audio |
| `data/audio/exports` | Chapter WAV, combined FLAC and manifests with playback timelines |
| `models` | Original optional local-engine assets; not needed for cloud mode |

Stop the server before a simple filesystem copy of the library. Copy the whole `data` directory so database references and audio stay together. Do not run two copies against one shared live SQLite library or use OneDrive synchronization as a multi-machine database service. OneDrive may also sync source files according to your existing settings.

Source text is sent externally only when configured cloud operations are explicitly started. Selected speech providers receive the spoken passage and applicable voice direction. Gemini receives mapping/casting context, which can contain more text than the eventual audio. Local disk backups can also contain novel text and should be treated as private.

## 10. Implementation and verification evidence

The server uses Python, FastAPI and Uvicorn. SQLite provides persistence; the background worker runs within the single app process. HTTPX makes cloud requests. Pydantic validates inputs and structured output. NumPy, SoundFile and SciPy handle audio decoding, normalization and resampling. The frontend is plain HTML/CSS/JavaScript, with no Node build required to run it.

The original local path uses Ollama for analysis and Kokoro ONNX for speech. Imports for local speech remain lazy so the cloud-only environment does not have to load those engines.

### Checks completed

**36 Python tests passed**, including original regression checks and new tests for empty-book creation, numbered chapters, exact Unicode source, persistent casting, manual corrections, atomic voice edits, provider response decoding, MP3 input, cache invalidation, missing keys, usage limits, quota errors, cancellation, manifests, stale exports and hosted authentication.

A real headless Chrome browser check passed against an isolated fixture server. It exercised empty-book creation, chapter 72 upload followed by chapter 1 paste, numeric ordering, Gemini-style mapping/casting, a manual cloud voice change verified in the saved cast, full source display, contextual review, audio production, seeking with correct passage highlighting, correction-triggered playback pause, and stale-export visibility. No JavaScript page errors were recorded.

The fixture provider is deliberately synthetic. It validates the application's workflow without consuming credits or sending novel text away. Provider tests validate request/response handling with controlled payloads, including MP3 decoding; they cannot establish current account eligibility, provider uptime, pronunciation, performance, actor-like consistency or actual output quality.

The Python suite emitted two dependency deprecation warnings around the FastAPI/Starlette test client and AnyIO portal alias. They did not fail tests. Review those dependencies during routine upgrades.

### Repeating verification

Run `.venv\Scripts\python.exe -m pytest -q` from the project. For the browser acceptance check, start `tests.ui_fixture_server:app` on port 8768 with `TTSAI_DATA` pointing to a disposable separate directory. Run `tests/browser_cloud.cjs` using Node with Playwright installed and Chrome available. Set `TTSAI_PLAYWRIGHT` to an explicit Playwright package path if necessary and `TTSAI_SCREENSHOT` to a desired screenshot path. Never run the fixture server against the real library.

Do not claim real provider verification until a short authenticated end-to-end generation and listening test has completed. Record model ID, account tier, request size, duration, latency and observed quality when that test becomes possible.

## 11. Remaining limitations and improvement priorities

1. **Real provider acceptance first.** Connect one key, map a short scene, inspect the returned cast, and listen to several voices. Compare the same dialogue across providers. Confirm a free account's actual quota and publication terms.
2. **Identity quality.** Build a benchmark containing pronoun ambiguity, aliases, unnamed speakers, disguises and recurring characters many chapters apart. Add retrieval for very large casts and a later whole-book reconciliation pass that proposes changes without overriding manual locks.
3. **Voice quality.** Add persistent voice design or custom voices only where the provider supports it. Add pronunciation dictionaries and carefully controlled emotion/style options. Longer scene synthesis may improve prosody, but it must retain editable dialogue and reliable timing.
4. **Alignment and correction.** Add optional speech transcription/forced alignment for word highlighting and omission detection. Add targeted passage regeneration and safe recombination so one corrected line does not require rebuilding a whole export workflow.
5. **Editorial tools.** Add segment split/join, multi-paragraph dialogue handling, chapter text versioning, and bulk review. Preserve the original text and explicitly track each new revision.
6. **Operational reliability.** Run the prepared container on the actual host; test restarts, quota exhaustion and long jobs. Add durable external queues and object storage before scaling beyond one private instance. Add automated backups, restore drills and storage monitoring.
7. **Usage clarity.** Add provider quota/usage dashboards where APIs allow them, token estimates for mapping, configurable request limits in the UI and trustworthy account-side spending controls. Present estimates as estimates.
8. **Formats and publishing.** Add EPUB input, deliberate PDF extraction, MP3/M4B export, chapter metadata and optional subtitles/video packaging. None is implemented by this cloud update.

This prototype does not provide guaranteed speaker accuracy, unlimited unique voices, instant streaming, voice cloning, word-level timestamps, a hosted public service, automatic free credits or a guarantee of free commercial audio.

## 12. File map for the next assistant

| File | Role |
| --- | --- |
| `app/cloud.py` | Keys, usage reservations, cloud catalogs, Gemini structured mapping/casting and three speech adapters |
| `app/main.py` | Book/chapter/settings/review/voice APIs, auth and timeline routes |
| `app/store.py` | SQLite schema/migrations and cast persistence |
| `app/analysis.py` | Existing passage analysis pipeline and saved character profiles |
| `app/jobs.py` | Queue, mapping/casting/production, interruption, export manifests and audio assembly |
| `static/index.html` | Studio controls, forms and dialogs |
| `static/app.js` | Library, jobs, cast, review and playback interactions |
| `static/cloud-ui.js` | Connections, providers, chapters, cloud voices and text following |
| `static/review.js` | Exact source markup and contextual review rendering |
| `tests/test_cloud.py` | Cloud adapter, persistence, usage and workflow regressions |
| `tests/ui_fixture_server.py` | Isolated synthetic provider for browser acceptance |
| `tests/browser_cloud.cjs` | Browser acceptance workflow |
| `docs/CLOUD_PROTOTYPE.md` | This current handover |

### Continuation instruction

Read AGENTS.md, README.md and docs/CLOUD_PROTOTYPE.md first. Continue this existing implementation rather than replacing it. Preserve the library, manual corrections, persistent character IDs, provider voices and historical exports. The cloud workflow is implemented and tested with fixtures; real provider generation and Render deployment remain unverified because credentials were unavailable. Compare any newer work on the friend's laptop before merging. Use one server worker. Keep secrets out of files and version control. Start with a short real-provider validation when keys become available, then validate the prepared hosting setup and document measured results.

## 13. Official references checked for this implementation

These are the contract and deployment references used while preparing the prototype. Recheck current availability and terms when activating accounts; this document is a dated snapshot.

- [Gemini generateContent API](https://ai.google.dev/api/generate-content): structured generation and audio request contract.
- [Gemini speech generation](https://ai.google.dev/gemini-api/docs/speech-generation): speech models, voices and controls.
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing): current model tiers, free eligibility and data-use distinctions.
- [ElevenLabs text-to-speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert): voice endpoint, model selection and MP3 output format.
- [Hume synthesis API](https://dev.hume.ai/reference/text-to-speech-tts/synthesize-json): voice ID, description, version and audio response.
- [Hume voice catalog API](https://dev.hume.ai/reference/voices/list): shared catalog, pagination and `voices_page` response.
- [Render free service behavior](https://render.com/docs/free): sleep and storage limitations.
- [Render persistent disks](https://render.com/docs/disks): durable storage behavior and availability.
- [Render Blueprint specification](https://render.com/docs/blueprint-spec): deployment YAML and generated secrets.
- [Render pricing](https://render.com/pricing): check actual service and disk charges before provisioning.


## Deepgram integration - 10 September 2026
Deepgram Aura-2 is now available under Speech AI, Cloud connections, and usage tracking. Sixteen curated English voices include gender, age, accent and timbre descriptions for Gemini casting. Assignments remain book/character/provider specific. On a previously mapped book, Step 1 reuses mapped passages and assigns only missing provider voices; this casting step still uses Gemini. Alternatively assign voices manually in Cast. Step 2 generates WAV audio with existing passage playback timings and review gates.

Each Deepgram character supports saved speed (0.7-1.5, native API) and pitch (-3 to +3 semitones, local FFmpeg RubberBand with preserved formants). Pitch-only changes reuse the original speech cache without further API calls. Speed or voice changes require new synthesis. Direction is casting metadata, not a spoken prompt or acting control. Aura-2 expressiveness is not exposed. Other providers retain their previous behavior and caches.

Authentication uses the fixed api.deepgram.com/v1/speak endpoint and Authorization Token header. Keys remain session-only or DEEPGRAM_API_KEY environment secrets. The usage panel reports app requests/characters, including reserved failed attempts; Deepgram account remaining credits/percentage are unavailable, with a console link. No unlimited-free claim or automatic paid fallback. The imageio-ffmpeg 0.6.0 dependency bundles FFmpeg; Windows pitch processing was verified, Docker/Linux deployment was not tested.

Verification: 43 Python tests passed (including real local pitch processing, cache reuse, authentication format, durable usage and saved settings). Browser checks confirmed 16 voices, visible controls and no JavaScript errors. A real 36-character Deepgram preview with speed 0.95 and pitch +0.6 produced 2.4 seconds of decoded audio through the app. This validates live synthesis, not a full-book quality audition. Original books, mapping and audio remain intact; a SQLite backup precedes the additive migration. The app was restarted and its four connections restored to session memory. Hosting remains prepared only.

Official references: https://developers.deepgram.com/docs/tts-models and https://developers.deepgram.com/docs/tts-voice-controls
