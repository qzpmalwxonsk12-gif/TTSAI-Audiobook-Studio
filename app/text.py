"""Deterministic source spans; the language model labels IDs, never rewrites prose."""
import re


def chapter_parts(text):
    matches = list(re.finditer(r'(?im)^\s*(?:chapter|chap\.)\s+\d+[^\n]*', text))
    if not matches:
        return [('Chapter 1', text)]
    parts = []
    if text[:matches[0].start()].strip():
        parts.append(('Prologue', text[:matches[0].start()]))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        parts.append((m.group().strip(), text[m.end():end]))
    return parts


def spans(source):
    # Double quotes and curly single quotes; straight apostrophes stay inside words.
    # Unbalanced/multiline quote blocks are deliberately flagged for review.
    pattern = r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’'
    boundaries = []
    pos = 0
    for m in re.finditer(pattern, source):
        if m.start() > pos:
            boundaries.append((pos, m.start(), 'narration'))
        boundaries.append((m.start(), m.end(), 'dialogue'))
        pos = m.end()
    if pos < len(source):
        boundaries.append((pos, len(source), 'narration'))
    result = []
    for a, b, kind in boundaries:
        chunk_start = a
        # Small sentence/paragraph chunks bound TTS memory and model requests.
        for cut in re.finditer(r'\n+|(?<=[.!?])\s+(?=[A-Z“"])', source[a:b]):
            stop = a + cut.end()
            _append(result, source, chunk_start, stop, kind)
            chunk_start = stop
        _append(result, source, chunk_start, b, kind)
    return result


def _append(out, text, a, b, kind):
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    while b - a > 650:
        cut = text.rfind(' ', a + 200, a + 650)
        if cut < a:
            cut = a + 650
        out.append({'start': a, 'end': cut, 'text': text[a:cut], 'kind': kind})
        a = cut
        while a < b and text[a].isspace():
            a += 1
    if a < b:
        out.append({'start': a, 'end': b, 'text': text[a:b], 'kind': kind})


def batches(segments, limit=3500):
    batch, size = [], 0
    for s in segments:
        if batch and (size + len(s['text']) > limit or len(batch) >= 24):
            yield batch
            batch, size = [], 0
        batch.append(s)
        size += len(s['text'])
    if batch:
        yield batch
