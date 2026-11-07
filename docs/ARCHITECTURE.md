# Architecture and decisions
Python/FastAPI serves a static local studio and typed API. SQLite stores book-scoped identities and immutable
source spans. A single background worker owns production jobs; UI corrections are blocked while its book
has an active job to prevent output mixing across revisions.

Import -> deterministic source spans -> local language-model labels -> validated identity resolution ->
persistent cast -> review gate -> Kokoro per-span audio -> atomic chunk cache -> streamed chapter assembly.

The AI receives identifiers plus source text. It returns identifiers/classifications, never replacement prose.
Missing/duplicate output identifiers fail a batch transaction. Manual locks prevent overwrites.
Explicit speech/thought tags and narrowly matched appositional aliases override model guesses.
Identity resolution uses normalized exact canonical names/aliases. Ambiguous aliases remain unresolved.
Character merge is explicit and preserves the target's stored voice.

Full-book production is two jobs: map all supplied chapters, then render. It is not an omniscient global
entity solver. Listen mode interleaves mapping/rendering per chapter and makes finished chapters playable.
Mapping includes prior text, forward context, neighboring chapter text, and the current persistent cast.

Audio cache keys include actual model weights hash, literal text and the complete voice recipe.
Speech is CPU-only with four threads. Text and speech loading share a lock and release models between
stages to reduce RAM pressure. HTTP requests are bounded and jobs checkpoint around inference.
No nested worker pools; Chapter WAV assembly checks the RIFF size cap; combined FLAC streams frames without that cap.

Security scope: loopback only, restricted Host/Origin, JSON mutations, no remote provider URL, parameterized
SQL, validated file identifiers, text escaping in UI, and no novel text uploads. This is a personal local app,
not a multi-user hosted service.

Continuation roadmap:
1. Evaluate representative novel excerpts with labeled ground truth; improve speaker attribution before UI expansion.
2. Scene-aware segment split/join editing, aliases with evidence, and a whole-book reconciliation pass.
3. Cast retrieval index and rolling summaries for huge casts/context.
4. Sentence-level listening buffer, per-artifact dependency signatures, and more robust playback recovery.
5. MP3/M4B streaming export, subtitles, EPUB import and a packaged Windows launcher.
