# TTSAIIdea project instructions
Read README.md, docs/CLOUD_PROTOTYPE.md and HANDOFF.md before changing this application.
For a new machine or fresh assistant session, also read TRANSFER_HANDOVER.md.
The user now wants a cloud API audiobook workflow, retaining local compatibility, persistent character voices, and two modes:
whole-book mapping/production and buffered listen-as-you-go. Preserve source text and manual corrections.
Keep model inference and runtime measurements explicit; do not equate a passing frontend check with working audio.
Never overwrite user books, model files, historical audio, or the pre-existing .qodo folder.
Use this folder's .venv; do not install into the system Python or change existing Ollama model storage.
Use the dedicated loopback Ollama port 11435 and application port 8767.
Generated data and models are ignored by git. Do not add them to commits.
Cloud API adapters and deployment preparation are authorized. No external text uploads or paid provider usage without explicit user configuration. Do not claim hosting is live or real providers are verified without evidence.
Document unfinished functionality candidly in HANDOFF.md. Run meaningful tests for persistence,
speaker identity, source integrity, job interruption, and cache invalidation when those areas change.
