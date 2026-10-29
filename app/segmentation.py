"""Gruppiert die word-level-Antwort von ElevenLabs zu Sprecher-Turns."""


def default_label(index):
    """0 -> 'Sprecher A', 1 -> 'Sprecher B', ... 26 -> 'Sprecher AA'."""
    letters = ""
    index += 1
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"Sprecher {letters}"


def build_segments(api_response):
    """Liefert (segments, labels).

    segments: Liste von {speaker_id, start, end, text}
    labels:   {speaker_id: Standard-Anzeigename}
    """
    words = api_response.get("words") or []

    order = []
    for word in words:
        speaker = word.get("speaker_id") or "speaker_0"
        if speaker not in order:
            order.append(speaker)
    labels = {speaker: default_label(i) for i, speaker in enumerate(order)}

    segments = []
    current = None
    for word in words:
        speaker = word.get("speaker_id") or "speaker_0"
        start = word.get("start")
        end = word.get("end")
        if current is None or speaker != current["speaker_id"]:
            if current is not None:
                segments.append(current)
            current = {"speaker_id": speaker, "start": start, "end": end, "text": ""}
        current["text"] += word.get("text", "")
        if start is not None and (current["start"] is None or start < current["start"]):
            current["start"] = start
        if end is not None and (current["end"] is None or end > current["end"]):
            current["end"] = end
    if current is not None:
        segments.append(current)

    for segment in segments:
        segment["text"] = segment["text"].strip()
    return [s for s in segments if s["text"]], labels
