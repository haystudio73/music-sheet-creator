"""Exact, local notation exports for the editable monophonic lead-sheet model.

Score time is measured in *quarter notes*, represented by rational strings.  The
MusicXML writer never quantizes or removes a source note. Overlapping melody
events must be reviewed before engraving. MIDI retains the original timing.
"""

from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
from math import isfinite, lcm
from pathlib import Path
import re
import xml.etree.ElementTree as ET


NATURAL_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
MAJOR_FIFTHS = {"C": 0, "D": 2, "E": 4, "F": -1, "G": 1, "A": 3, "B": 5}
QUALITY_XML = {
    "major": "major", "minor": "minor", "dominant-seventh": "dominant",
    "major-seventh": "major-seventh", "minor-seventh": "minor-seventh",
    "diminished": "diminished", "augmented": "augmented",
    "suspended-second": "suspended-second", "suspended-fourth": "suspended-fourth",
}
QUALITY_INTERVALS = {
    "major": (0, 4, 7), "minor": (0, 3, 7), "dominant-seventh": (0, 4, 7, 10),
    "major-seventh": (0, 4, 7, 11), "minor-seventh": (0, 3, 7, 10),
    "diminished": (0, 3, 6), "augmented": (0, 4, 8),
    "suspended-second": (0, 2, 7), "suspended-fourth": (0, 5, 7),
}
NOTE_TYPES = (
    (Fraction(16), "long"), (Fraction(8), "breve"), (Fraction(4), "whole"),
    (Fraction(2), "half"), (Fraction(1), "quarter"), (Fraction(1, 2), "eighth"),
    (Fraction(1, 4), "16th"), (Fraction(1, 8), "32nd"),
    (Fraction(1, 16), "64th"), (Fraction(1, 32), "128th"),
    (Fraction(1, 64), "256th"), (Fraction(1, 128), "512th"),
    (Fraction(1, 256), "1024th"),
)


def _fraction(value: object, field: str, *, positive: bool = False) -> Fraction:
    if not isinstance(value, str) or len(value) > 40:
        raise ValueError(f"{field} phải là chuỗi phân số, ví dụ '1/2'.")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError(f"{field}: phân số không hợp lệ.") from exc
    if result < 0 or (positive and result == 0):
        raise ValueError(f"{field} phải {'lớn hơn' if positive else 'không nhỏ hơn'} 0.")
    if result.denominator > 65536 or result > 200000:
        raise ValueError(f"{field}: giá trị vượt giới hạn ký âm của phiên bản này.")
    return result


def _pitch_name(name: object) -> tuple[str, int]:
    if not isinstance(name, str) or not re.fullmatch(r"[A-G](?:#{1,2}|b{1,2}|-{1,2})?", name):
        raise ValueError(f"Tên cao độ không hợp lệ: {name!r}.")
    alteration = name.count("#") - name.count("b") - name.count("-")
    return name[0], alteration


def _pitch_class(name: str) -> int:
    step, alteration = _pitch_name(name)
    return (NATURAL_PC[step] + alteration) % 12


def _key_details(name: object) -> tuple[str, str, int]:
    if not isinstance(name, str):
        raise ValueError("Giọng phải là chuỗi, ví dụ C, Bb hoặc Am.")
    mode = "minor" if name.endswith("m") else "major"
    tonic = name[:-1] if mode == "minor" else name
    step, alteration = _pitch_name(tonic)
    fifths = MAJOR_FIFTHS[step] + alteration * 7 - (3 if mode == "minor" else 0)
    if abs(fifths) > 7:
        raise ValueError("Chọn giọng tương đương có tối đa 7 dấu hóa (ví dụ E thay cho Fb).")
    return tonic, mode, fifths


def _timed_events(score: dict, name: str) -> list[tuple[Fraction, Fraction, dict]]:
    return sorted(
        [(Fraction(event["start"]), Fraction(event["start"]) + Fraction(event["duration"]), event)
         for event in score[name]],
        key=lambda item: (item[0], item[1], item[2]["id"]),
    )


def _overlaps(events: list[tuple[Fraction, Fraction, dict]]) -> list[tuple[str, str]]:
    overlaps = []
    previous_end = Fraction(0)
    previous_id = ""
    for start, end, event in events:
        if start < previous_end:
            overlaps.append((previous_id, event["id"]))
        if end > previous_end:
            previous_end, previous_id = end, event["id"]
    return overlaps


def _validate_lyrics(score: dict) -> list[str]:
    """Keep imported words losslessly, but only engrave valid note bindings."""
    lyrics = score.get("lyrics", [])
    if not isinstance(lyrics, list) or len(lyrics) > 20000:
        raise ValueError("Lời hát phải là danh sách có tối đa 20000 từ/âm tiết.")
    note_ids = {note["id"] for note in score["notes"]}
    seen_ids = set()
    bindings = set()
    unmatched = 0
    for token in lyrics:
        if not isinstance(token, dict):
            raise ValueError("Phần tử lời hát không hợp lệ.")
        identity = token.get("id")
        if not isinstance(identity, str) or not 1 <= len(identity) <= 100 or identity in seen_ids:
            raise ValueError("Mỗi từ/âm tiết lời hát phải có ID duy nhất dài 1–100 ký tự.")
        seen_ids.add(identity)
        text = token.get("text")
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise ValueError(f"{identity}: lời hát phải có 1–200 ký tự và không được để trống.")
        # ElementTree escapes markup, but does not reject forbidden XML 1.0
        # code points. Reject them before a saved score becomes unexportable.
        if any(not (character in "\t\n\r" or 0x20 <= ord(character) <= 0xD7FF
                    or 0xE000 <= ord(character) <= 0xFFFD
                    or 0x10000 <= ord(character) <= 0x10FFFF) for character in text):
            raise ValueError(f"{identity}: lời hát chứa ký tự không hợp lệ cho MusicXML.")
        verse = token.get("verse", 1)
        if type(verse) is not int or not 1 <= verse <= 20:
            raise ValueError(f"{identity}: số lời/đoạn phải là số nguyên từ 1 đến 20.")
        if token.get("syllabic", "single") not in ("single", "begin", "middle", "end"):
            raise ValueError(f"{identity}: kiểu âm tiết không hợp lệ.")
        note_id = token.get("note_id")
        if note_id is None:
            unmatched += 1
        else:
            if not isinstance(note_id, str) or note_id not in note_ids:
                raise ValueError(f"{identity}: nốt gắn với lời hát không tồn tại.")
            if (note_id, verse) in bindings:
                raise ValueError(f"{identity}: mỗi nốt chỉ có một từ/âm tiết cho mỗi lời/đoạn.")
            bindings.add((note_id, verse))
        for field in ("source_start", "source_end"):
            value = token.get(field)
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                      or not isfinite(value) or value < 0):
                raise ValueError(f"{identity}.{field}: thời gian lời hát không hợp lệ.")
        if (token.get("source_start") is not None and token.get("source_end") is not None
                and token["source_end"] < token["source_start"]):
            raise ValueError(f"{identity}: thời gian kết thúc lời hát trước thời gian bắt đầu.")
    if unmatched:
        return [f"Lời hát: {unmatched} từ/âm tiết chưa gắn với nốt; chưa xuất hiện trên bản nhạc."]
    return []


def validate_score(score: dict) -> list[str]:
    """Validate losslessly; return review warnings, including any overlaps.

    Overlap warnings deliberately do not make a draft impossible to save. The
    engraving exporter rejects them until a person repairs the melody.
    """
    if not isinstance(score, dict):
        raise ValueError("Bản nhạc phải là một đối tượng JSON.")
    if score.get("schema_version") != 1:
        raise ValueError("Phiên bản cấu trúc bản nhạc không được hỗ trợ.")
    if not isinstance(score.get("title"), str) or not score["title"].strip():
        raise ValueError("Tên bản nhạc không được để trống.")
    tempo = score.get("tempo")
    if isinstance(tempo, bool) or not isinstance(tempo, (int, float)) or not isfinite(tempo) or tempo <= 0:
        raise ValueError("Tempo phải là số dương hữu hạn.")
    meter = score.get("meter")
    if (not isinstance(meter, (list, tuple)) or len(meter) != 2
            or any(type(value) is not int for value in meter)
            or not 1 <= meter[0] <= 32 or meter[1] not in (1, 2, 4, 8, 16, 32)):
        raise ValueError("Số chỉ nhịp không hợp lệ; mẫu số phải là 1, 2, 4, 8, 16 hoặc 32.")
    _key_details(score.get("key"))
    warnings = []
    for collection in ("notes", "harmonies"):
        if not isinstance(score.get(collection), list) or len(score[collection]) > 50000:
            raise ValueError(f"{collection} phải là danh sách có tối đa 50000 phần tử.")
        seen_ids = set()
        for event in score[collection]:
            if not isinstance(event, dict):
                raise ValueError(f"Phần tử {collection} không hợp lệ.")
            identity = event.get("id")
            if not isinstance(identity, str) or not identity or identity in seen_ids:
                raise ValueError(f"Mỗi phần tử {collection} phải có ID duy nhất và không rỗng.")
            seen_ids.add(identity)
            _fraction(event.get("start"), f"{identity}.start")
            _fraction(event.get("duration"), f"{identity}.duration", positive=True)
            if collection == "notes":
                if type(event.get("pitch")) is not int or not 0 <= event["pitch"] <= 127:
                    raise ValueError(f"{identity}: cao độ MIDI phải thuộc 0–127.")
                if type(event.get("velocity")) is not int or not 1 <= event["velocity"] <= 127:
                    raise ValueError(f"{identity}: velocity phải thuộc 1–127.")
                for name in ("source_start", "source_end"):
                    value = event.get(name)
                    if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                              or not isfinite(value) or value < 0):
                        raise ValueError(f"{identity}.{name}: thời gian nguồn không hợp lệ.")
                if (event.get("source_start") is not None and event.get("source_end") is not None
                        and event["source_end"] < event["source_start"]):
                    raise ValueError(f"{identity}: thời gian kết thúc nguồn trước thời gian bắt đầu.")
            else:
                kind = event.get("kind")
                if kind not in ("chord", "no_chord", "unknown"):
                    raise ValueError(f"{identity}: loại hợp âm không hợp lệ.")
                if kind == "chord":
                    _pitch_name(event.get("root"))
                    if event.get("quality") not in QUALITY_XML:
                        raise ValueError(f"{identity}: tính chất hợp âm chưa được hỗ trợ.")
                    if event.get("bass") is not None:
                        _pitch_name(event["bass"])
                elif kind == "unknown":
                    warnings.append(f"Hợp âm {identity} chưa xác định; cần nghe và kiểm tra.")
        events = _timed_events(score, collection)
        for left, right in _overlaps(events):
            warnings.append(f"{'Nốt giai điệu' if collection == 'notes' else 'Hợp âm'} chồng lấn: {left} / {right}.")
    if not score["notes"]:
        warnings.append("Bản nhạc chưa có nốt giai điệu.")
    if not score["harmonies"]:
        warnings.append("Bản nhạc chưa có hợp âm; ứng dụng không tự giả định hợp âm.")
    if any(note["pitch"] < 48 or note["pitch"] > 96 for note in score["notes"]):
        warnings.append("Một số nốt nằm xa khuông khóa Sol; hãy kiểm tra quãng tám.")
    warnings.extend(_validate_lyrics(score))
    return warnings


def fix_overlaps(score: dict) -> dict:
    """Resolve note and chord overlaps cleanly by shortening preceding durations."""
    score = deepcopy(score)
    for _ in range(30):
        notes = sorted(score.get("notes", []), key=lambda n: (Fraction(n["start"]), n["id"]))
        changed = False
        for i in range(len(notes) - 1):
            start = Fraction(notes[i]["start"])
            duration = Fraction(notes[i]["duration"])
            next_start = Fraction(notes[i + 1]["start"])
            if start + duration > next_start:
                changed = True
                if next_start > start:
                    notes[i]["duration"] = str(next_start - start)
                else:
                    notes[i]["duration"] = "1/16"
                    notes[i + 1]["start"] = str(start + Fraction(1, 16))
        score["notes"] = notes
        if not changed:
            break

    for _ in range(30):
        harmonies = sorted(score.get("harmonies", []), key=lambda h: (Fraction(h["start"]), h["id"]))
        changed = False
        deduped = []
        seen_starts = set()
        for h in harmonies:
            st = Fraction(h["start"])
            if st in seen_starts:
                changed = True
                continue
            seen_starts.add(st)
            deduped.append(h)
        harmonies = deduped
        for i in range(len(harmonies) - 1):
            start = Fraction(harmonies[i]["start"])
            duration = Fraction(harmonies[i]["duration"])
            next_start = Fraction(harmonies[i + 1]["start"])
            if start + duration > next_start and next_start > start:
                changed = True
                harmonies[i]["duration"] = str(next_start - start)
        score["harmonies"] = harmonies
        if not changed:
            break

    warnings = validate_score(score)
    retained = [m for m in score.get("diagnostics", []) if "chồng lấn" not in m]
    score["diagnostics"] = list(dict.fromkeys(retained + warnings))[:200]
    return score


def _element(parent: ET.Element, name: str, value: object = None, **attributes: str) -> ET.Element:
    child = ET.SubElement(parent, name, attributes)
    if value is not None:
        child.text = str(value)
    return child


def _spelling(pitch_class: int, key: str) -> tuple[str, int]:
    _, _, fifths = _key_details(key)
    alterations = dict.fromkeys(NATURAL_PC, 0)
    for step in ("FCGDAEB"[:fifths] if fifths >= 0 else "BEADGCF"[:-fifths]):
        alterations[step] = 1 if fifths >= 0 else -1
    for step, alteration in alterations.items():
        if (NATURAL_PC[step] + alteration) % 12 == pitch_class % 12:
            return step, alteration
    names = ("C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B") if fifths < 0 else (
        "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")
    return _pitch_name(names[pitch_class % 12])


def _components(duration: Fraction) -> list[tuple[Fraction, str, int, tuple[int, int] | None]]:
    """Spell a rational duration as tied binary/dotted notes or exact tuplets."""
    odd = duration.denominator
    while odd % 2 == 0:
        odd //= 2
    normal = 1 << (odd.bit_length() - 1)
    ratio = Fraction(normal, odd)
    tuplet = (odd, normal) if odd != 1 else None
    candidates = sorted(
        [(base * multiplier * ratio, name, dots, tuplet)
         for base, name in NOTE_TYPES
         for dots, multiplier in ((0, Fraction(1)), (1, Fraction(3, 2)), (2, Fraction(7, 4)))],
        key=lambda item: item[0], reverse=True,
    )
    result = []
    remainder = duration
    while remainder:
        component = next((item for item in candidates if item[0] <= remainder), None)
        if component is None or len(result) > 1000:
            raise ValueError("Trường độ quá nhỏ/phức tạp để ký âm. Hãy lượng tử hóa trước khi xuất sheet.")
        result.append(component)
        remainder -= component[0]
    return result


def _add_note(measure: ET.Element, duration: Fraction, divisions: int, key: str,
              source: dict | None, tie_stop: bool = False, tie_start: bool = False,
              note_type: str = "quarter", dots: int = 0,
              tuplet: tuple[int, int] | None = None,
              lyrics: list[dict] | None = None) -> None:
    note = _element(measure, "note")
    if source is None:
        _element(note, "rest")
    else:
        step, alteration = _spelling(source["pitch"] % 12, key)
        pitch = _element(note, "pitch")
        _element(pitch, "step", step)
        if alteration:
            _element(pitch, "alter", alteration)
        _element(pitch, "octave", (source["pitch"] - NATURAL_PC[step] - alteration) // 12 - 1)
    _element(note, "duration", int(duration * divisions))
    if source is not None:
        for active, tie_type in ((tie_stop, "stop"), (tie_start, "start")):
            if active:
                _element(note, "tie", type=tie_type)
    _element(note, "voice", 1)
    _element(note, "type", note_type)
    for _ in range(dots):
        _element(note, "dot")
    if tuplet:
        modification = _element(note, "time-modification")
        _element(modification, "actual-notes", tuplet[0])
        _element(modification, "normal-notes", tuplet[1])
    if source is not None and (tie_stop or tie_start):
        notations = _element(note, "notations")
        for active, tie_type in ((tie_stop, "stop"), (tie_start, "start")):
            if active:
                _element(notations, "tied", type=tie_type)
    # A source note can become multiple written notes when a duration is split
    # or crosses a barline. Its lyric belongs only to its initial attack.
    if source is not None and not tie_stop:
        for token in lyrics or []:
            lyric = _element(note, "lyric", number=str(token.get("verse", 1)), placement="below")
            _element(lyric, "syllabic", token.get("syllabic", "single"))
            _element(lyric, "text", token["text"])


def _add_harmony(measure: ET.Element, event: dict, offset: Fraction, divisions: int) -> None:
    if event["kind"] == "unknown":
        direction = _element(measure, "direction", placement="above")
        direction_type = _element(direction, "direction-type")
        _element(direction_type, "words", "?", **{"font-style": "italic"})
        _element(direction, "offset", int(offset * divisions))
        return
    harmony = _element(measure, "harmony", placement="above")
    root = _element(harmony, "root")
    if event["kind"] == "no_chord":
        _element(root, "root-step", "C", **{"text": ""})
        _element(harmony, "kind", "none", **{"text": "N.C."})
    else:
        step, alteration = _pitch_name(event["root"])
        _element(root, "root-step", step)
        if alteration:
            _element(root, "root-alter", alteration)
        _element(harmony, "kind", QUALITY_XML[event["quality"]], **{"use-symbols": "no"})
        if event.get("bass") is not None:
            bass_step, bass_alter = _pitch_name(event["bass"])
            bass = _element(harmony, "bass")
            _element(bass, "bass-step", bass_step)
            if bass_alter:
                _element(bass, "bass-alter", bass_alter)
    _element(harmony, "offset", int(offset * divisions))


def export_musicxml(score: dict, path: Path, options: dict | None = None) -> None:
    """Export complete bars, rests, ties, chords and note-bound UTF-8 lyrics."""
    validate_score(score)
    opts = options or {}
    title = opts.get("custom_title") or score["title"]
    include_chords = opts.get("include_chords", True)
    include_lyrics = opts.get("include_lyrics", True)
    scope = opts.get("scope", "full")

    notes = _timed_events(score, "notes")
    harmonies = _timed_events(score, "harmonies") if include_chords else []
    lyrics_by_note: dict[str, list[dict]] = {}
    if include_lyrics:
        for token in score.get("lyrics", []):
            if token.get("note_id") is not None:
                lyrics_by_note.setdefault(token["note_id"], []).append(token)
        for tokens in lyrics_by_note.values():
            tokens.sort(key=lambda token: token.get("verse", 1))
    if _overlaps(notes):
        raise ValueError("Nốt giai điệu đang chồng lấn. Hãy sửa trước khi xuất MusicXML/PDF.")
    if _overlaps(harmonies):
        raise ValueError("Hợp âm đang chồng lấn. Hãy sửa thời điểm/trường độ trước khi xuất MusicXML/PDF.")
    bar_duration = Fraction(score["meter"][0] * 4, score["meter"][1])
    ending = max([bar_duration] + [end for _, end, _ in notes + harmonies])
    total_bars = int(-(-ending // bar_duration))
    if total_bars > 10000:
        raise ValueError("Bản nhạc vượt giới hạn 10000 ô nhịp.")

    bar_start = 1
    bar_end = total_bars
    if scope == "range":
        if opts.get("bar_start"):
            bar_start = max(1, min(int(opts["bar_start"]), total_bars))
        if opts.get("bar_end"):
            bar_end = max(bar_start, min(int(opts["bar_end"]), total_bars))

    divisions = lcm(480, bar_duration.denominator,
                    *(point.denominator for start, end, _ in notes + harmonies for point in (start, end)))
    if divisions > 2_147_483_647:
        raise ValueError("Lưới trường độ quá phức tạp; hãy lượng tử hóa trước khi xuất.")
    root = ET.Element("score-partwise", version="4.0")
    work = _element(root, "work")
    _element(work, "work-title", title)
    _element(root, "movement-title", title)
    identification = _element(root, "identification")
    encoding = _element(identification, "encoding")
    _element(encoding, "software", "Local Lead Sheet")
    _element(encoding, "encoding-description", "Giai điệu và hợp âm; tempo và số chỉ nhịp cố định.")
    defaults = _element(root, "defaults")
    scaling = _element(defaults, "scaling")
    _element(scaling, "millimeters", 7)
    _element(scaling, "tenths", 40)
    part_list = _element(root, "part-list")
    score_part = _element(part_list, "score-part", id="P1")
    _element(score_part, "part-name", "Giai điệu")
    part = _element(root, "part", id="P1")
    _, mode, fifths = _key_details(score["key"])
    # Explicit N.C. events stop harmony when a provided chord duration leaves a gap.
    labels = [(start, event) for start, _, event in harmonies]
    for index, (_, end, event) in enumerate(harmonies):
        next_start = harmonies[index + 1][0] if index + 1 < len(harmonies) else ending
        if event["kind"] == "chord" and end < next_start:
            labels.append((end, {"kind": "no_chord"}))
    labels.sort(key=lambda item: item[0])
    note_index = 0
    label_index = 0
    for bar_num in range(bar_start, bar_end + 1):
        bar_index = bar_num - 1
        start, end = bar_index * bar_duration, (bar_index + 1) * bar_duration
        measure = _element(part, "measure", number=str(bar_num))
        if bar_num == bar_start:
            attributes = _element(measure, "attributes")
            _element(attributes, "divisions", divisions)
            key = _element(attributes, "key")
            _element(key, "fifths", fifths)
            _element(key, "mode", mode)
            time = _element(attributes, "time")
            _element(time, "beats", score["meter"][0])
            _element(time, "beat-type", score["meter"][1])
            clef = _element(attributes, "clef")
            _element(clef, "sign", "G")
            _element(clef, "line", 2)
            direction = _element(measure, "direction", placement="above")
            direction_type = _element(direction, "direction-type")
            metronome = _element(direction_type, "metronome")
            _element(metronome, "beat-unit", "quarter")
            _element(metronome, "per-minute", f"{score['tempo']:g}")
            _element(direction, "sound", tempo=str(score["tempo"]))
        while label_index < len(labels) and labels[label_index][0] < end:
            offset, event = labels[label_index]
            if offset >= start:
                _add_harmony(measure, event, offset - start, divisions)
            label_index += 1
        cursor = start
        while cursor < end:
            while note_index < len(notes) and notes[note_index][1] <= cursor:
                note_index += 1
            source = None
            source_start, source_end = cursor, end
            if note_index < len(notes):
                event_start, event_end, event = notes[note_index]
                if event_start <= cursor:
                    source, source_start, source_end = event, event_start, event_end
                    segment_end = min(end, event_end)
                else:
                    segment_end = min(end, event_start)
            else:
                segment_end = end
            for length, note_type, dots, tuplet in _components(segment_end - cursor):
                _add_note(measure, length, divisions, score["key"], source,
                          tie_stop=source is not None and cursor > source_start,
                          tie_start=source is not None and cursor + length < source_end,
                          note_type=note_type, dots=dots, tuplet=tuplet,
                          lyrics=lyrics_by_note.get(source["id"]) if source is not None else None)
                cursor += length
        if bar_num == bar_end:
            barline = _element(measure, "barline", location="right")
            _element(barline, "bar-style", "light-heavy")
    ET.indent(root, space="  ")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


CHORD_QUALITY_ABC = {
    "major": "", "minor": "m", "dominant-seventh": "7",
    "major-seventh": "maj7", "minor-seventh": "m7",
    "diminished": "dim", "augmented": "aug",
    "suspended-second": "sus2", "suspended-fourth": "sus4",
}


def _pitch_to_abc(pitch: int, key: str) -> str:
    """Convert MIDI pitch to standard ABC notation note string according to key."""
    pitch_class = pitch % 12
    step, alteration = _spelling(pitch_class, key)
    accidental = ("^" * alteration) if alteration > 0 else ("_" * -alteration)
    octave = pitch // 12 - 1
    if octave >= 5:
        base_letter = step.lower()
        marks = "'" * (octave - 5)
    elif octave == 4:
        base_letter = step.upper()
        marks = ""
    else:
        base_letter = step.upper()
        marks = "," * (4 - octave)
    return f"{accidental}{base_letter}{marks}"


def _is_power_of_two(val: int) -> bool:
    return val > 0 and (val & (val - 1)) == 0


def _is_representable_abc(units: Fraction, allow_dotted: bool = True) -> bool:
    """Check if a duration (in units of 1/16) can be represented by a single ABC glyph.

    A glyph can represent pure powers of 2 (1, 2, 4, 8, 16, 1/2, 1/4...)
    or single-dotted values (3, 6, 12, 24, 3/2, 3/4...).
    """
    if units <= 0:
        return False
    if not _is_power_of_two(units.denominator):
        return False
    n = units.numerator
    while n % 2 == 0:
        n //= 2
    if n == 1:
        return True
    if allow_dotted and n == 3:
        return True
    return False


def _format_abc_duration(units: Fraction) -> str:
    """Format duration in units of 1/16 (since default L is 1/16)."""
    if units == 1:
        return ""
    if units.denominator == 1:
        return str(units.numerator)
    if units.numerator == 1:
        return f"/{units.denominator}"
    return f"{units.numerator}/{units.denominator}"


def _decompose_units_abc(units: Fraction, is_rest: bool = False, is_compound: bool = False) -> list[Fraction]:
    """Decompose duration in units of 1/16 into representable ABC durations.

    In ABC notation, each note or rest glyph can only represent powers of 2
    or single-dotted values. Composite/unrepresentable durations (e.g. 5, 7, 9, 10, 11, 13)
    must be split into representable components.
    """
    if units <= 0:
        return []
    if _is_representable_abc(units, allow_dotted=True):
        return [units]
    if not _is_power_of_two(units.denominator):
        return [units]

    if is_rest:
        allowed = [
            Fraction(16), Fraction(8), Fraction(4), Fraction(2), Fraction(1),
            Fraction(1, 2), Fraction(1, 4), Fraction(1, 8), Fraction(1, 16)
        ]
        if is_compound:
            allowed = sorted(allowed + [Fraction(12), Fraction(6), Fraction(3)], reverse=True)
    else:
        allowed = [
            Fraction(32), Fraction(24), Fraction(16), Fraction(12),
            Fraction(8), Fraction(6), Fraction(4), Fraction(3),
            Fraction(2), Fraction(3, 2), Fraction(1), Fraction(3, 4),
            Fraction(1, 2), Fraction(3, 8), Fraction(1, 4), Fraction(3, 16),
            Fraction(1, 8), Fraction(1, 16)
        ]

    result = []
    rem = units
    while rem > 0:
        val = next((cand for cand in allowed if cand <= rem), None)
        if val is None:
            if rem > 0:
                result.append(rem)
            break
        result.append(val)
        rem -= val

    return result


def _duration_to_abc(duration: Fraction) -> str:
    """Format duration in units of 1/16 (since default L is 1/16)."""
    return _format_abc_duration(duration * 4)


def _harmony_to_abc(event: dict) -> str:
    kind = event.get("kind", "chord")
    if kind == "no_chord":
        return '"N.C."'
    if kind == "unknown":
        return '"?"'
    root = event.get("root", "C")
    quality = CHORD_QUALITY_ABC.get(event.get("quality", "major"), "")
    chord = f"{root}{quality}"
    if event.get("bass"):
        chord += f"/{event['bass']}"
    return f'"{chord}"'


def export_abc(score: dict, path: Path, options: dict | None = None) -> None:
    """Export complete bars, rests, ties, chords and note-bound lyrics in ABC 2.1 notation."""
    validate_score(score)
    opts = options or {}
    title = opts.get("custom_title") or score["title"]
    include_chords = opts.get("include_chords", True)
    include_lyrics = opts.get("include_lyrics", True)
    scope = opts.get("scope", "full")

    notes = _timed_events(score, "notes")
    harmonies = _timed_events(score, "harmonies") if include_chords else []
    if _overlaps(notes):
        raise ValueError("Nốt giai điệu đang chồng lấn. Hãy sửa trước khi xuất ABC.")
    if _overlaps(harmonies):
        raise ValueError("Hợp âm đang chồng lấn. Hãy sửa thời điểm/trường độ trước khi xuất ABC.")

    lyrics_by_note: dict[str, list[dict]] = {}
    if include_lyrics:
        for token in score.get("lyrics", []):
            if token.get("note_id") is not None:
                lyrics_by_note.setdefault(token["note_id"], []).append(token)
        for tokens in lyrics_by_note.values():
            tokens.sort(key=lambda t: t.get("verse", 1))

    bar_duration = Fraction(score["meter"][0] * 4, score["meter"][1])
    is_compound = (score["meter"][1] == 8 and score["meter"][0] % 3 == 0)
    ending = max([bar_duration] + [end for _, end, _ in notes + harmonies])
    total_bars = int(-(-ending // bar_duration))

    bar_start = 1
    bar_end = total_bars
    if scope == "range":
        if opts.get("bar_start"):
            bar_start = max(1, min(int(opts["bar_start"]), total_bars))
        if opts.get("bar_end"):
            bar_end = max(bar_start, min(int(opts["bar_end"]), total_bars))

    labels = [(start, event) for start, _, event in harmonies]
    for index, (_, end, event) in enumerate(harmonies):
        next_start = harmonies[index + 1][0] if index + 1 < len(harmonies) else ending
        if event["kind"] == "chord" and end < next_start:
            labels.append((end, {"kind": "no_chord"}))
    labels.sort(key=lambda item: item[0])

    lines = [
        "X: 1",
        f"T: {title}",
        f"M: {score['meter'][0]}/{score['meter'][1]}",
        "L: 1/16",
        f"Q: 1/4={score['tempo']:g}",
        f"K: {score['key']}",
    ]

    current_music_line = []
    current_lyric_line = []
    note_index = 0
    label_index = 0
    bars_on_line = 0

    for bar_num in range(bar_start, bar_end + 1):
        bar_index = bar_num - 1
        start, end = bar_index * bar_duration, (bar_index + 1) * bar_duration
        bar_music = []
        bar_lyrics = []

        cursor = start
        while cursor < end:
            chord_prefix = ""
            while label_index < len(labels) and labels[label_index][0] <= cursor:
                lbl_time, lbl_event = labels[label_index]
                if include_chords and lbl_time == cursor:
                    chord_prefix = _harmony_to_abc(lbl_event)
                label_index += 1

            while note_index < len(notes) and notes[note_index][1] <= cursor:
                note_index += 1

            source = None
            source_start, source_end = cursor, end
            if note_index < len(notes):
                event_start, event_end, event = notes[note_index]
                if event_start <= cursor:
                    source, source_start, source_end = event, event_start, event_end
                    segment_end = min(end, event_end)
                else:
                    segment_end = min(end, event_start)
            else:
                segment_end = end

            seg_duration = segment_end - cursor
            seg_units = seg_duration * 4
            tie_stop = source is not None and cursor > source_start
            tie_start = source is not None and cursor + seg_duration < source_end

            if source is not None:
                comp_units_list = _decompose_units_abc(seg_units, is_rest=False, is_compound=is_compound)
                pitch_str = _pitch_to_abc(source["pitch"], score["key"])
                for comp_idx, comp_u in enumerate(comp_units_list):
                    is_first_comp = (comp_idx == 0)
                    is_last_comp = (comp_idx == len(comp_units_list) - 1)
                    dur_str = _format_abc_duration(comp_u)
                    pfx = chord_prefix if is_first_comp else ""
                    has_tie_forward = (not is_last_comp) or tie_start
                    tie_suffix = "-" if has_tie_forward else ""
                    bar_music.append(f"{pfx}{pitch_str}{dur_str}{tie_suffix}")
                    if include_lyrics:
                        if is_first_comp:
                            if not tie_stop:
                                toks = lyrics_by_note.get(source["id"])
                                if toks:
                                    tok = toks[0]
                                    w_text = tok["text"]
                                    if tok.get("syllabic") in ("begin", "middle"):
                                        w_text += "-"
                                    bar_lyrics.append(w_text)
                                else:
                                    bar_lyrics.append("*")
                            else:
                                bar_lyrics.append("_")
                        else:
                            toks = lyrics_by_note.get(source["id"])
                            if toks or tie_stop:
                                bar_lyrics.append("_")
                            else:
                                bar_lyrics.append("*")
            else:
                comp_units_list = _decompose_units_abc(seg_units, is_rest=True, is_compound=is_compound)
                for comp_idx, comp_u in enumerate(comp_units_list):
                    pfx = chord_prefix if comp_idx == 0 else ""
                    dur_str = _format_abc_duration(comp_u)
                    bar_music.append(f"{pfx}z{dur_str}")

            cursor = segment_end

        is_last_bar = (bar_num == bar_end)
        bar_close = "|]" if is_last_bar else "|"
        current_music_line.append(" ".join(bar_music) + f" {bar_close}")
        if include_lyrics:
            current_lyric_line.append(" ".join(bar_lyrics) + " |")

        bars_on_line += 1
        if bars_on_line >= 4 or is_last_bar:
            lines.append(" ".join(current_music_line))
            if include_lyrics and any(tok not in ("*", "|", "_") for item in current_lyric_line for tok in item.split()):
                lines.append("w: " + " ".join(current_lyric_line))
            current_music_line = []
            current_lyric_line = []
            bars_on_line = 0

    content = "\n".join(lines) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def export_midi(score: dict, path: Path, accompaniment: bool = False, options: dict | None = None) -> None:
    """Write exact note events; accompaniment is an optional synthetic chord track."""
    import mido

    validate_score(score)
    opts = options or {}
    title = opts.get("custom_title") or score["title"]
    if "accompaniment" in opts:
        accompaniment = opts["accompaniment"]
    scope = opts.get("scope", "full")

    notes = _timed_events(score, "notes")
    harmonies = _timed_events(score, "harmonies")
    if accompaniment and _overlaps(harmonies):
        raise ValueError("Hợp âm đang chồng lấn; hãy sửa trước khi tạo MIDI có bè đệm.")

    bar_duration = Fraction(score["meter"][0] * 4, score["meter"][1])
    ending = max([bar_duration] + [end for _, end, _ in notes + harmonies])
    total_bars = int(-(-ending // bar_duration))

    time_offset = Fraction(0)
    if scope == "range":
        bar_start = max(1, min(int(opts.get("bar_start", 1)), total_bars))
        bar_end = max(bar_start, min(int(opts.get("bar_end", total_bars)), total_bars))
        range_start = (bar_start - 1) * bar_duration
        range_end = bar_end * bar_duration
        time_offset = range_start
        notes = [(max(Fraction(0), s - time_offset), max(Fraction(0), e - time_offset), n)
                 for s, e, n in notes if e > range_start and s < range_end]
        harmonies = [(max(Fraction(0), s - time_offset), max(Fraction(0), e - time_offset), h)
                     for s, e, h in harmonies if e > range_start and s < range_end]

    selected = notes + (harmonies if accompaniment else [])
    ticks = lcm(480, *(point.denominator for start, end, _ in selected for point in (start, end)))
    if ticks > 32767:
        raise ValueError("Lưới trường độ vượt độ phân giải MIDI; hãy lượng tử hóa trước khi xuất.")
    tempo = round(60_000_000 / score["tempo"])
    if not 1 <= tempo <= 0xFFFFFF:
        raise ValueError("Tempo nằm ngoài phạm vi biểu diễn của định dạng MIDI.")
    midi = mido.MidiFile(type=1, ticks_per_beat=ticks, charset="utf-8")
    metadata = mido.MidiTrack()
    midi.tracks.append(metadata)
    metadata.append(mido.MetaMessage("track_name", name=title, time=0))
    metadata.append(mido.MetaMessage("set_tempo", tempo=tempo, time=0))
    metadata.append(mido.MetaMessage("time_signature", numerator=score["meter"][0], denominator=score["meter"][1], time=0))
    metadata.append(mido.MetaMessage("key_signature", key=score["key"].replace("-", "b"), time=0))
    metadata.append(mido.MetaMessage("end_of_track", time=0))

    def add_track(name: str, events: list[tuple[Fraction, Fraction, int, int]], channel: int) -> None:
        track = mido.MidiTrack()
        midi.tracks.append(track)
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", program=0, channel=channel, time=0))
        messages = []
        for start, end, pitch, velocity in events:
            messages.append((int(start * ticks), 1, pitch, velocity))
            messages.append((int(end * ticks), 0, pitch, 0))
        messages.sort(key=lambda item: (item[0], item[1], item[2]))
        previous = 0
        for tick, on, pitch, velocity in messages:
            track.append(mido.Message("note_on" if on else "note_off", note=pitch, velocity=velocity,
                                      channel=channel, time=tick - previous))
            previous = tick
        track.append(mido.MetaMessage("end_of_track", time=0))

    add_track("Giai điệu", [(start, end, note["pitch"], note["velocity"]) for start, end, note in notes], 0)
    if accompaniment:
        chord_events = []
        for start, end, harmony in harmonies:
            if harmony["kind"] != "chord":
                continue
            root_pitch = 48 + _pitch_class(harmony["root"])
            pitches = {root_pitch + interval for interval in QUALITY_INTERVALS[harmony["quality"]]}
            if harmony.get("bass") is not None:
                pitches.add(36 + _pitch_class(harmony["bass"]))
            chord_events.extend((start, end, pitch, 60) for pitch in sorted(pitches))
        add_track("Bè đệm hợp âm tổng hợp (tham khảo)", chord_events, 1)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    midi.save(path)


def transpose_score(score: dict, semitones: int) -> dict:
    """Return a copy transposed by signed semitones; never wrap/clamp MIDI notes.

    Fractions, source timestamps, IDs, quality, no-chord/unknown states and
    revision remain unchanged. The caller owns persistence/revision increments.
    """
    validate_score(score)
    if type(semitones) is not int:
        raise ValueError("Khoảng chuyển giọng phải là số nguyên bán cung.")
    if any(not 0 <= note["pitch"] + semitones <= 127 for note in score["notes"]):
        raise ValueError("Chuyển giọng sẽ đưa nốt ra ngoài cao độ MIDI 0–127.")
    transposed = deepcopy(score)
    tonic, mode, _ = _key_details(score["key"])
    if semitones % 12:
        major_names = ("C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B")
        minor_names = ("C", "C#", "D", "Eb", "E", "F", "F#", "G", "G#", "A", "Bb", "B")
        target = (major_names if mode == "major" else minor_names)[(_pitch_class(tonic) + semitones) % 12]
        transposed["key"] = target + ("m" if mode == "minor" else "")
    for note in transposed["notes"]:
        note["pitch"] += semitones
    for harmony in transposed["harmonies"]:
        if harmony["kind"] != "chord" or semitones % 12 == 0:
            continue
        for name in ("root", "bass"):
            if harmony.get(name) is not None:
                step, alteration = _spelling((_pitch_class(harmony[name]) + semitones) % 12, transposed["key"])
                harmony[name] = step + ("#" * alteration if alteration > 0 else "b" * -alteration)
    if semitones:
        transposed["review_status"] = "needs_review"
    validate_score(transposed)
    return transposed
