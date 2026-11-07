# TTSAI — audiobook studio

## Repository guide and source setup

TTSAI is a local audiobook-production studio that imports chapter text, lets the user review speaker/script decisions, keeps character voice assignments and produces/plays speech through configurable provider paths. It is distinct from the Folio Android PDF-listening application.

On Windows, install Python 3.11 or a compatible runtime for the listed dependencies, then run the included setup/launchers:

```powershell
.\Setup-cloud.cmd
.\Start.cmd
```

The setup script creates `.venv` and installs `requirements-cloud.txt`; `Start.cmd` launches `start.py`. Open the local interface at `http://127.0.0.1:8767`. This starts a local application, not a publicly hosted site.

Cloud provider keys and usage are user-configured. The setup script's historical “free API keys” wording is not a guarantee of free generation, an available allowance or a current billing tier. Review provider availability/costs and the app's usage controls before production requests. Legacy local-model operation has separate dependencies and is documented below; models and personal books/audio are not bundled in this source snapshot.

Application/backend code is under `app/`, the interface under `static/`, supporting scripts under `scripts/` and authored checks under `tests/`. Begin with a small chapter, review the preserved source and speaker mapping, then test a short audio segment before a long book. A passing interface or provider-authentication check does not prove successful full-book audio generation.

See [the cloud prototype guide](docs/CLOUD_PROTOTYPE.md), [handoff](HANDOFF.md) and [transfer guide](TRANSFER_HANDOVER.md) for the current implementation and its historical evidence.

Create a book, add numbered TXT/pasted chapters, map characters with Gemini, review the script, and produce audio with Gemini TTS, ElevenLabs or Hume. Character identities and provider-specific voices are saved across chapters. Playback follows the source passage, and every passage is editable for speaker/classification review.

**Read [the complete cloud prototype guide](docs/CLOUD_PROTOTYPE.md)** for features, setup, API behavior, hosting, tests, limitations and the next assistant's handover.

## Start

On this installed laptop, double-click `Start.cmd` and open http://127.0.0.1:8767. On another Windows machine, install Python 3.11+, run `Setup-cloud.cmd`, then `Start.cmd`.

Add provider keys in **Cloud connections**. Session-entered keys disappear on server restart; hosting environment secrets can provide persistent configuration. Gemini is required for mapping/casting; choose any of the three speech providers for production. No keys are included.

1. Create a book, then add numbered chapters using paste or TXT upload.
2. Choose Gemini's mapping model and the speech provider. Run **Step 1: Start mapping**.
3. Read the complete script, inspect red-underlined uncertainties, and click passages to correct their speaker. Review includes neighboring paragraphs. Preview and adjust the saved cast.
4. Choose narration/dialogue, thoughts and unresolved-speaker fallback settings. Run **Step 2: Produce audiobook**.
5. Play chapter WAV or combined FLAC exports with passage highlighting. Corrections mark previous audio stale and require regeneration.

The server must remain running. Closing the laptop does not keep a locally started job alive. The prepared hosted version can run independently once deployed.

## Hosting and cost status

Docker and Render deployment files are prepared for a private single-user service with a persistent disk. **Hosting has not been deployed, and no real provider generation was tested because credentials were unavailable.** Render Starter plus its disk is paid; nothing was purchased. Eligible free API quotas can be used, but the app cannot grant quota or guarantee zero charges on a paid-enabled key. See the guide before activating hosting or a provider.

## Existing local mode

Original books, audio, Kokoro models and local voice recipes were preserved. `Start-local.cmd` enables the dedicated Ollama startup; local choices remain in the UI. Cloud-only setup does not install local models. Older measurements and GPU migration notes remain in `HANDOFF.md`, `TRANSFER_HANDOVER.md`, and `docs/LOCAL_MILESTONE_README.md`; their original local-only restrictions describe that earlier milestone.

## Development and verification

Python/FastAPI/SQLite backend, plain HTML/CSS/JavaScript frontend. Run one server worker. Tests: `.venv\Scripts\python.exe -m pytest -q`.

Current validation: **36 tests passed**, plus Chrome browser acceptance against isolated synthetic provider fixtures. This verifies application behavior, not real-provider speech quality or live hosting. The full guide records exactly what remains unverified.

Keep secrets, `data`, models and virtual environments out of source control. Back up the entire data directory with the server stopped. Read `AGENTS.md` before editing.

### Latest update: usage counters

The API usage panel shows ElevenLabs' actual balance and percentage, per-provider app-tracked requests/speech characters, and the latest job's allowance percentages. Gemini/Hume account balances remain explicitly unavailable with dashboard links. Provider keys were accepted in read-only checks; ElevenLabs confirmed its Free plan. No real speech was generated. Keys are in server-session memory only. Current checks: 39 Python tests and a read-only browser usage-panel check passed. See the guide's follow-up section for permissions and quota details.


## Source snapshot and validation

See [BACKUP_NOTES.md](BACKUP_NOTES.md) for the omitted build outputs, local settings, credentials and runtime data. Build generated binaries locally using the instructions above; a source checkout is not an installed application. Earlier validation figures in this guide describe their original development runs. This documentation update checks source references and instructions; it does not claim a fresh application, device or gameplay test.
