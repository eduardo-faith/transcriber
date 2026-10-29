"""Erzeugt die Ausgabeformate: strukturiertes JSON, TXT, SRT, VTT."""


def _timestamp(seconds, separator=","):
    if seconds is None:
        seconds = 0
    millis = int(round(seconds * 1000))
    hours, millis = divmod(millis, 3_600_000)
    minutes, millis = divmod(millis, 60_000)
    secs, millis = divmod(millis, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}{separator}{millis:03d}"


def _mmss(seconds):
    if seconds is None:
        seconds = 0
    total = int(seconds)
    return f"{total // 60:02d}:{total % 60:02d}"


def speaker_name(speaker_id, labels, overrides):
    if overrides and overrides.get(speaker_id):
        return overrides[speaker_id]
    return labels.get(speaker_id, speaker_id)


def to_structured(segments, labels, overrides, meta):
    return {
        "metadata": meta,
        "speakers": {
            speaker_id: speaker_name(speaker_id, labels, overrides) for speaker_id in labels
        },
        "segments": [
            {
                "speaker_id": s["speaker_id"],
                "speaker": speaker_name(s["speaker_id"], labels, overrides),
                "start": s["start"],
                "end": s["end"],
                "text": s["text"],
            }
            for s in segments
        ],
    }


def to_txt(segments, labels, overrides):
    lines = [
        f"[{_mmss(s['start'])}] {speaker_name(s['speaker_id'], labels, overrides)}: {s['text']}"
        for s in segments
    ]
    return "\n".join(lines) + "\n"


def to_srt(segments, labels, overrides):
    blocks = []
    for index, s in enumerate(segments, 1):
        blocks.append(str(index))
        blocks.append(f"{_timestamp(s['start'])} --> {_timestamp(s['end'])}")
        blocks.append(f"{speaker_name(s['speaker_id'], labels, overrides)}: {s['text']}")
        blocks.append("")
    return "\n".join(blocks)


def to_vtt(segments, labels, overrides):
    blocks = ["WEBVTT", ""]
    for s in segments:
        blocks.append(f"{_timestamp(s['start'], '.')} --> {_timestamp(s['end'], '.')}")
        blocks.append(f"{speaker_name(s['speaker_id'], labels, overrides)}: {s['text']}")
        blocks.append("")
    return "\n".join(blocks)
