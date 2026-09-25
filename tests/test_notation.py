"""Deterministic notation fixtures; these are not audio-transcription benchmarks."""

from copy import deepcopy
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
import os
import subprocess
import xml.etree.ElementTree as ET

import pytest

from backend.notation import export_abc, export_midi, export_musicxml, export_pdf, transpose_score, validate_score


@pytest.fixture
def score():
    return {
        "schema_version": 1, "revision": 3, "title": "Khúc thử nghiệm – mùa thu", "tempo": 96,
        "meter": [4, 4], "key": "F", "source_engine": "notation-test-fixture",
        "review_status": "reviewed", "melody_role": "instrumental", "diagnostics": [],
        "notes": [
            {"id": "n1", "pitch": 65, "start": "1/2", "duration": "5", "velocity": 85,
             "source_start": 0.3125, "source_end": 3.4375},
            {"id": "n2", "pitch": 70, "start": "6", "duration": "1/3", "velocity": 70,
             "source_start": None, "source_end": None},
            {"id": "n3", "pitch": 72, "start": "19/3", "duration": "2/3", "velocity": 75,
             "source_start": None, "source_end": None},
        ],
        "harmonies": [
            {"id": "h1", "root": "F", "quality": "major", "bass": "A", "start": "0", "duration": "4", "kind": "chord"},
            {"id": "h2", "root": "Bb", "quality": "major-seventh", "bass": None, "start": "4", "duration": "2", "kind": "chord"},
            {"id": "h3", "root": "", "quality": "", "bass": None, "start": "6", "duration": "1", "kind": "unknown"},
            {"id": "h4", "root": "", "quality": "", "bass": None, "start": "7", "duration": "1", "kind": "no_chord"},
        ],
    }


def test_musicxml_roundtrip_preserves_notes_ties_rests_and_vietnamese(score, tmp_path):
    from music21 import converter, note as music21_note

    output = tmp_path / "bản nhạc.musicxml"
    export_musicxml(score, output)
    xml = ET.parse(output).getroot()
    assert xml.findtext("work/work-title") == score["title"]
    assert xml.findtext("part/measure/attributes/key/fifths") == "-1"
    assert xml.findtext("part/measure/attributes/time/beats") == "4"
    measures = xml.findall("part/measure")
    assert len(measures) == 2
    divisions = int(measures[0].findtext("attributes/divisions"))
    assert all(sum(int(note.findtext("duration")) for note in measure.findall("note")) == divisions * 4 for measure in measures)
    assert measures[0].find("note/rest") is not None
    assert any(note.find("tie[@type='start']") is not None for note in measures[0].findall("note"))
    assert measures[1].find("note/tie[@type='stop']") is not None
    assert xml.find(".//time-modification/actual-notes").text == "3"
    parsed = converter.parse(output).parts[0].stripTies().flatten()
    melody = list(parsed.getElementsByClass(music21_note.Note))
    actual = [(int(note.pitch.midi), Fraction(note.offset), Fraction(note.duration.quarterLength)) for note in melody]
    expected = [(note["pitch"], Fraction(note["start"]), Fraction(note["duration"])) for note in score["notes"]]
    assert actual == expected
    assert melody[1].pitch.name == "B-"


def test_chord_types_slash_bass_unknown_and_no_chord_are_distinct(score, tmp_path):
    output = tmp_path / "chords.musicxml"
    export_musicxml(score, output)
    xml = ET.parse(output).getroot()
    chords = xml.findall(".//harmony")
    assert [chord.findtext("kind") for chord in chords] == ["major", "major-seventh", "none"]
    assert chords[0].findtext("bass/bass-step") == "A"
    assert chords[1].findtext("root/root-alter") == "-1"
    assert chords[2].find("kind").get("text") == "N.C."
    assert [item.text for item in xml.findall(".//direction-type/words")] == ["?"]
    assert any("chưa xác định" in warning for warning in validate_score(score))


def test_harmony_gap_stops_chord_at_declared_end(score, tmp_path):
    score["harmonies"] = [score["harmonies"][0]]
    score["harmonies"][0]["duration"] = "1/2"
    output = tmp_path / "gap.musicxml"
    export_musicxml(score, output)
    xml = ET.parse(output).getroot()
    chords = xml.findall(".//harmony")
    divisions = int(xml.findtext(".//divisions"))
    assert [chord.findtext("kind") for chord in chords] == ["major", "none"]
    assert int(chords[1].findtext("offset")) == divisions // 2


def test_overlap_is_reported_without_losing_raw_notes_and_engraving_rejects(score, tmp_path):
    score["notes"][1]["start"] = "2"
    original = deepcopy(score)
    assert any("chồng lấn" in warning for warning in validate_score(score))
    assert score == original
    with pytest.raises(ValueError, match="chồng lấn"):
        export_musicxml(score, tmp_path / "overlap.musicxml")
    assert not (tmp_path / "overlap.musicxml").exists()


@pytest.mark.parametrize("field,value", [("pitch", 128), ("pitch", True), ("duration", "0"), ("start", "-1"), ("duration", "1/0"), ("velocity", 0)])
def test_invalid_events_are_rejected(score, field, value):
    score["notes"][0][field] = value
    with pytest.raises(ValueError):
        validate_score(score)


def test_transposition_updates_melody_key_chord_and_bass_without_changing_timing(score):
    original = deepcopy(score)
    shifted = transpose_score(score, 2)
    assert score == original
    assert shifted["key"] == "G"
    assert [note["pitch"] for note in shifted["notes"]] == [67, 72, 74]
    assert shifted["harmonies"][0]["root"] == "G"
    assert shifted["harmonies"][0]["bass"] == "B"
    assert shifted["harmonies"][1]["root"] == "C"
    assert shifted["harmonies"][2:] == original["harmonies"][2:]
    assert shifted["revision"] == original["revision"]
    assert shifted["review_status"] == "needs_review"
    for actual, expected in zip(shifted["notes"], original["notes"]):
        assert {k: v for k, v in actual.items() if k != "pitch"} == {k: v for k, v in expected.items() if k != "pitch"}
    assert [note["pitch"] for note in transpose_score(shifted, -2)["notes"]] == [note["pitch"] for note in original["notes"]]


def test_minor_and_flat_keys_preserve_mode_and_transposition_does_not_wrap(score):
    score["key"] = "Am"
    assert transpose_score(score, 3)["key"] == "Cm"
    score["key"] = "Bb"
    assert transpose_score(score, 3)["key"] == "Db"
    assert transpose_score(score, 12)["key"] == "Bb"
    score["notes"][0]["pitch"] = 127
    with pytest.raises(ValueError, match="0–127"):
        transpose_score(score, 1)


def _midi_events(track):
    now = 0
    result = []
    for message in track:
        now += message.time
        if message.type in ("note_on", "note_off"):
            result.append((now, message.type, message.note, message.velocity, message.channel))
    return result


def test_midi_exact_timing_metadata_and_optional_accompaniment(score, tmp_path):
    import mido

    without = tmp_path / "melody.mid"
    with_chords = tmp_path / "accompaniment.mid"
    export_midi(score, without)
    export_midi(score, with_chords, accompaniment=True)
    melody = mido.MidiFile(without, charset="utf-8")
    chords = mido.MidiFile(with_chords, charset="utf-8")
    assert len(melody.tracks) == 2
    assert len(chords.tracks) == 3
    assert melody.tracks[0][0].name == score["title"]
    assert next(message for message in melody.tracks[0] if message.type == "set_tempo").tempo == 625000
    assert next(message for message in melody.tracks[0] if message.type == "key_signature").key == "F"
    events = _midi_events(melody.tracks[1])
    for source in score["notes"]:
        start = Fraction(source["start"]) * melody.ticks_per_beat
        end = (Fraction(source["start"]) + Fraction(source["duration"])) * melody.ticks_per_beat
        assert (start, "note_on", source["pitch"], source["velocity"], 0) in events
        assert (end, "note_off", source["pitch"], 0, 0) in events
    accompaniment = _midi_events(chords.tracks[2])
    assert {pitch for tick, kind, pitch, _, _ in accompaniment if tick == 0 and kind == "note_on"} == {53, 57, 60, 45}
    assert all(tick <= 6 * chords.ticks_per_beat for tick, *_ in accompaniment)
    assert all(channel == 1 for *_, channel in accompaniment)


def test_midi_same_pitch_boundary_sends_off_before_on(score, tmp_path):
    import mido

    score["notes"] = [deepcopy(score["notes"][0]), deepcopy(score["notes"][0])]
    for index, note in enumerate(score["notes"]):
        note.update(id=f"repeat-{index}", start=str(index), duration="1")
    path = tmp_path / "repeat.mid"
    export_midi(score, path)
    result = mido.MidiFile(path, charset="utf-8")
    boundary = [item for item in _midi_events(result.tracks[1]) if item[0] == result.ticks_per_beat]
    assert [item[1] for item in boundary] == ["note_off", "note_on"]


def test_compound_meter_bars_and_empty_melody_are_valid(score, tmp_path):
    score.update(meter=[6, 8], notes=[], harmonies=[])
    path = tmp_path / "empty.musicxml"
    export_musicxml(score, path)
    xml = ET.parse(path).getroot()
    divisions = int(xml.findtext(".//divisions"))
    assert sum(int(note.findtext("duration")) for note in xml.findall(".//note")) == 3 * divisions
    assert all(note.find("rest") is not None for note in xml.findall(".//note"))


def test_pdf_subprocess_failure_preserves_error_and_existing_destination(score, tmp_path, monkeypatch):
    executable = tmp_path / "MuseScore4.exe"
    executable.touch()
    destination = tmp_path / "existing.pdf"
    destination.write_bytes(b"existing-file")
    calls = []

    def fail(command, **options):
        calls.append((command, options))
        return SimpleNamespace(returncode=2, stdout="", stderr="engraving failed: deliberate test")

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(RuntimeError, match="engraving failed: deliberate test"):
        export_pdf(score, destination, str(executable))
    assert destination.read_bytes() == b"existing-file"
    assert calls[0][0][1] == "-o"
    assert calls[0][1]["timeout"] == 120
    assert "shell" not in calls[0][1]
    if os.name == "nt":
        assert calls[0][1]["creationflags"] & subprocess.CREATE_NO_WINDOW


def test_pdf_timeout_is_explicit(score, tmp_path, monkeypatch):
    executable = tmp_path / "MuseScore4.exe"
    executable.touch()

    def timeout(command, **options):
        raise subprocess.TimeoutExpired(command, options["timeout"], stderr=b"waiting for renderer")

    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(RuntimeError, match="120.*waiting for renderer"):
        export_pdf(score, tmp_path / "timeout.pdf", str(executable))


def test_pdf_success_copies_verified_pdf(score, tmp_path, monkeypatch):
    executable = tmp_path / "MuseScore4.exe"
    executable.touch()
    monkeypatch.delenv("QT_QPA_PLATFORM", raising=False)

    def succeed(command, **options):
        assert options["env"]["QT_QPA_PLATFORM"] == ("windows" if os.name == "nt" else "offscreen")
        Path(command[2]).write_bytes(b"%PDF-1.4\nfixture")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", succeed)
    destination = tmp_path / "result.pdf"
    export_pdf(score, destination, str(executable))
    assert destination.read_bytes().startswith(b"%PDF-")


def _lyric(identity, note_id, text, **values):
    return {"id": identity, "note_id": note_id, "text": text, "verse": 1,
            "syllabic": "single", "source_start": None, "source_end": None, **values}


def test_lyrics_unicode_verses_and_syllables_survive_musicxml_roundtrip(score, tmp_path):
    from music21 import converter, note as music21_note

    score["lyrics"] = [
        _lyric("l2", "n1", "Gió & mây <êm>", verse=2),
        _lyric("l1", "n1", "Mây", syllabic="begin", source_start=0.3, source_end=1.0),
        _lyric("l3", "n2", "bay", syllabic="middle"),
        _lyric("l4", "n3", "qua", syllabic="end"),
    ]
    output = tmp_path / "lyrics.musicxml"
    export_musicxml(score, output)
    xml = ET.parse(output).getroot()
    lyrics = xml.findall(".//note/lyric")
    assert [(token.get("number"), token.findtext("text"), token.findtext("syllabic")) for token in lyrics] == [
        ("1", "Mây", "begin"), ("2", "Gió & mây <êm>", "single"),
        ("1", "bay", "middle"), ("1", "qua", "end"),
    ]
    assert all(token.get("placement") == "below" for token in lyrics)
    assert "Gió &amp; mây &lt;êm&gt;" in output.read_text(encoding="utf-8")
    parsed = converter.parse(output).parts[0].flatten()
    melody = list(parsed.getElementsByClass(music21_note.Note))
    assert [(token.number, token.text, token.syllabic) for token in melody[0].lyrics] == [
        (1, "Mây", "begin"), (2, "Gió & mây <êm>", "single"),
    ]


@pytest.mark.parametrize("start,duration", [("1/2", "5"), ("0", "5/4")])
def test_lyric_is_only_on_first_attack_when_note_is_split(score, tmp_path, start, duration):
    score["notes"] = [dict(score["notes"][0], start=start, duration=duration)]
    score["harmonies"] = []
    score["lyrics"] = [_lyric("l1", "n1", "trời")]
    output = tmp_path / "tied-lyric.musicxml"
    export_musicxml(score, output)
    xml = ET.parse(output).getroot()
    written = [note for note in xml.findall(".//note") if note.find("pitch") is not None]
    assert len(written) > 1
    assert written[0].findtext("lyric/text") == "trời"
    assert all(note.find("tie[@type='stop']") is not None for note in written[1:])
    assert all(note.find("lyric") is None for note in written[1:])
    assert all(note.find("lyric") is None for note in xml.findall(".//note") if note.find("rest") is not None)


def test_unmatched_lyrics_are_preserved_warned_and_not_attached_to_arbitrary_notes(score, tmp_path):
    score["lyrics"] = [_lyric("l1", "n1", "Mây"), _lyric("l2", None, "xa")]
    before = deepcopy(score)
    warnings = validate_score(score)
    assert any(warning.startswith("Lời hát: 1") for warning in warnings)
    output = tmp_path / "unmatched.musicxml"
    export_musicxml(score, output)
    assert [token.text for token in ET.parse(output).findall(".//lyric/text")] == ["Mây"]
    assert score == before


@pytest.mark.parametrize("change", [
    {"note_id": "missing-note"}, {"text": "  "}, {"text": "bad\x00xml"},
    {"verse": 0}, {"verse": 21}, {"syllabic": "broken"},
    {"source_start": -1}, {"source_start": float("nan")},
    {"source_start": 2, "source_end": 1},
])
def test_invalid_lyrics_are_rejected_before_export(score, tmp_path, change):
    score["lyrics"] = [dict(_lyric("l1", "n1", "Mây"), **change)]
    output = tmp_path / "invalid.musicxml"
    with pytest.raises(ValueError):
        export_musicxml(score, output)
    assert not output.exists()


@pytest.mark.parametrize("duplicate", [
    _lyric("l2", "n1", "bay"),
    _lyric("l1", "n2", "bay"),
])
def test_duplicate_lyric_binding_or_identity_is_rejected(score, duplicate):
    score["lyrics"] = [_lyric("l1", "n1", "Mây"), duplicate]
    with pytest.raises(ValueError):
        validate_score(score)


def test_transposition_preserves_lyric_bindings_and_source_times(score):
    score["lyrics"] = [_lyric("l1", "n1", "Mây", source_start=0.3, source_end=0.7)]
    original = deepcopy(score)
    transposed = transpose_score(score, 2)
    assert transposed["lyrics"] == original["lyrics"]
    transposed["lyrics"][0]["text"] = "Nắng"
    assert score == original


def test_export_abc_full_song_produces_valid_headers_notes_chords_and_lyrics(score, tmp_path):
    score["lyrics"] = [
        _lyric("l1", "n1", "Mây"),
        _lyric("l2", "n2", "bay"),
        _lyric("l3", "n3", "xa"),
    ]
    output = tmp_path / "score.abc"
    export_abc(score, output)
    content = output.read_text(encoding="utf-8")
    lines = content.splitlines()

    assert "X: 1" in lines
    assert "T: Khúc thử nghiệm – mùa thu" in lines
    assert "M: 4/4" in lines
    assert "L: 1/16" in lines
    assert "Q: 1/4=96" in lines
    assert "K: F" in lines
    assert '"F/A"' in content
    assert '"Bbmaj7"' in content
    assert any(line.startswith("w: ") and "Mây" in line for line in lines)
    assert any(line.startswith("w: ") and "bay" in line for line in lines)


def test_export_abc_options_range_and_filtering(score, tmp_path):
    score["lyrics"] = [_lyric("l1", "n1", "Mây")]
    output = tmp_path / "custom.abc"
    options = {
        "scope": "range",
        "bar_start": 2,
        "bar_end": 2,
        "include_chords": False,
        "include_lyrics": False,
        "custom_title": "Bản Trích Đoạn",
    }
    export_abc(score, output, options=options)
    content = output.read_text(encoding="utf-8")
    assert "T: Bản Trích Đoạn" in content
    assert '"F/A"' not in content
    assert '"Bbmaj7"' not in content
    assert "w: " not in content


def test_export_abc_decomposes_unrepresentable_durations_for_notes_and_rests(score, tmp_path):
    from backend.notation import _decompose_units_abc, _is_representable_abc

    # Mathematical representation checks
    assert _is_representable_abc(Fraction(16)) is True
    assert _is_representable_abc(Fraction(12)) is True
    assert _is_representable_abc(Fraction(8)) is True
    assert _is_representable_abc(Fraction(6)) is True
    assert _is_representable_abc(Fraction(4)) is True
    assert _is_representable_abc(Fraction(3)) is True
    assert _is_representable_abc(Fraction(2)) is True
    assert _is_representable_abc(Fraction(1)) is True
    assert _is_representable_abc(Fraction(11)) is False
    assert _is_representable_abc(Fraction(13)) is False
    assert _is_representable_abc(Fraction(9)) is False
    assert _is_representable_abc(Fraction(10)) is False
    assert _is_representable_abc(Fraction(5)) is False
    assert _is_representable_abc(Fraction(7)) is False

    # Decompositions for rests
    assert _decompose_units_abc(Fraction(11), is_rest=True) == [Fraction(8), Fraction(2), Fraction(1)]
    assert _decompose_units_abc(Fraction(13), is_rest=True) == [Fraction(8), Fraction(4), Fraction(1)]
    assert _decompose_units_abc(Fraction(9), is_rest=True) == [Fraction(8), Fraction(1)]
    assert _decompose_units_abc(Fraction(10), is_rest=True) == [Fraction(8), Fraction(2)]
    assert _decompose_units_abc(Fraction(5), is_rest=True) == [Fraction(4), Fraction(1)]
    assert _decompose_units_abc(Fraction(7), is_rest=True) == [Fraction(4), Fraction(2), Fraction(1)]

    # Notes with unrepresentable duration decompose and tie cleanly with lyrics
    score["notes"] = [
        {"id": "n1", "pitch": 65, "start": "0", "duration": "5/4", "velocity": 85},
        {"id": "n2", "pitch": 67, "start": "11/4", "duration": "5/4", "velocity": 85},
    ]
    score["lyrics"] = [
        {"id": "l1", "note_id": "n1", "text": "Trời", "verse": 1, "syllabic": "single"},
        {"id": "l2", "note_id": "n2", "text": "xanh", "verse": 1, "syllabic": "single"},
    ]
    score["harmonies"] = []
    output = tmp_path / "decomposed.abc"
    export_abc(score, output)
    content = output.read_text(encoding="utf-8")
    assert "F5" not in content
    assert "G5" not in content
    assert "z5" not in content
    assert "F4- F" in content
    assert "G4- G" in content
    lines = content.splitlines()
    lyric_lines = [l for l in lines if l.startswith("w: ")]
    assert any("Trời _" in l and "xanh _" in l for l in lyric_lines)


def test_export_musicxml_options_range_and_custom_title(score, tmp_path):
    output = tmp_path / "range.musicxml"
    options = {
        "scope": "range",
        "bar_start": 1,
        "bar_end": 1,
        "custom_title": "Ô Nhịp 1",
        "include_chords": False,
    }
    export_musicxml(score, output, options=options)
    xml = ET.parse(output).getroot()
    assert xml.findtext("work/work-title") == "Ô Nhịp 1"
    measures = xml.findall("part/measure")
    assert len(measures) == 1
    assert xml.find(".//harmony") is None


def test_export_midi_options_range(score, tmp_path):
    import mido
    output = tmp_path / "range.mid"
    options = {
        "scope": "range",
        "bar_start": 2,
        "bar_end": 2,
        "custom_title": "Đoạn 2",
    }
    export_midi(score, output, options=options)
    mid = mido.MidiFile(output, charset="utf-8")
    assert mid.tracks[0][0].name == "Đoạn 2"
