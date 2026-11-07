# Original agreed direction
Build a local-first application that converts novel text into audiobooks with consistent character voices.

Two modes share one persistent book-specific cast:
- Listen as you go: analyze ahead, identify speakers, generate buffered audio.
- Whole-book production: analyze supplied chapters, review the cast, then generate unattended.

Save stable character IDs, names, aliases, descriptions, and exact voice configurations. Resolve uncertain
identities visibly, allow manual corrections and character merging, and keep returning voices unchanged.
Use supported TTS voice blending/design, preview and manual override. Separate identity from delivery.
Support full narration, dialogue-only and an internal-thought toggle. Always analyze narration for context.
Preserve source wording. Start with TXT/paste. Keep source, annotations, cast and audio separately.

Production jobs should resume, checkpoint, limit resources, recover after interruption and reuse unaffected
audio. Prefer local speech. Keep analysis providers replaceable and never upload text without configuration.
Export chapter audio plus a combined audiobook. Verify publication rights to novels and voices.

First milestone: real multi-chapter import, speaker review, persistent cast, voice preview, actual audio
export, returning-character/alias/ambiguity/restart/interruption tests, and measured runtime evidence.
