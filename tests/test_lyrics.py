"""Timed-lyrics import tests: preserve text, respect boundaries, avoid false matches."""
from copy import deepcopy
from fractions import Fraction

import pytest

from backend.lyrics import MAX_BYTES, parse_and_align


def score_at(*times, tempo=60, source=False):
    return {
        "tempo": tempo,
        "notes": [
            {"id": f"note-{index}", "start": str(Fraction(str(time)) * Fraction(tempo) / 60),
             "duration": "1/2", "pitch": 60,
             **({"source_start": time} if source else {})}
            for index, time in enumerate(times)
        ],
    }


def imported(text, notes=(), filename="test.lrc", **kwargs):
    return parse_and_align(text.encode("utf-8"), filename, score_at(*notes), **kwargs)


def words(result):
    return [token["text"] for token in result["lyrics"]]


def assignments(result):
    return [token["note_id"] for token in result["lyrics"]]


def test_srt_unicode_multiline_markup_and_fractional_fallback():
    text = "1\r\n00:00:00,000 --> 00:00:02,400\r\n<i>Mây</i> bay\r\nqua trời\r\n\r\n2\r\n00:00:02,400 --> 00:00:04,800\r\nNắng lên bên đồi"
    score = score_at(0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.6, 4.2, tempo=100)
    original = deepcopy(score)
    result = parse_and_align(text.encode("utf-8-sig"), r"C:\lyrics\bài hát.SRT", score)
    assert words(result) == ["Mây", "bay", "qua", "trời", "Nắng", "lên", "bên", "đồi"]
    assert assignments(result) == [f"note-{i}" for i in range(8)]
    assert result["lyric_source"] == {"filename": "bài hát.SRT", "format": "srt", "offset_seconds": 0, "cue_count": 2}
    assert result["lyrics"][0]["source_start"] == 0
    assert result["lyrics"][0]["source_end"] == 2.4
    assert score == original
    assert all(warning.startswith("Lời hát:") for warning in result["warnings"])
    assert len({token["id"] for token in result["lyrics"]}) == 8
    assert all(token["syllabic"] == "single" and token["verse"] == 1 for token in result["lyrics"])


def test_srt_optional_index_entities_styling_and_positions():
    result = imported(
        "00:00:00.000 --> 00:00:02.000 X1:10 X2:20 Y1:1 Y2:2\n{\\an8}Mây<br/>trời &amp; nắng",
        (0, 0.5, 1, 1.5), "test.srt",
    )
    assert words(result) == ["Mây", "trời", "nắng"]
    assert assignments(result) == ["note-0", "note-1", "note-2"]


@pytest.mark.parametrize("encoding", ["utf-8", "utf-8-sig", "utf-16"])
def test_supported_encodings(encoding):
    result = parse_and_align("[00:00.0]Nắng ấm\n[00:02.0]".encode(encoding), "a.lrc", score_at(0, 1))
    assert words(result) == ["Nắng", "ấm"]
    assert assignments(result) == ["note-0", "note-1"]


def test_utf16_big_endian_bom():
    data = b"\xfe\xff" + "[00:00.00]Lời\n[00:01.00]".encode("utf-16-be")
    assert words(parse_and_align(data, "a.lrc", score_at(0))) == ["Lời"]


def test_lrc_repeated_line_timestamps_metadata_and_empty_boundary():
    result = imported(
        "[ar:Example]\n[ti:Title][al:Album]\n[by:Test]\n[00:00.00][00:04.00]Mây bay\n[00:02.00]\n[00:06.00]",
        (0, 1, 2, 3, 4, 5, 6, 100),
    )
    assert words(result) == ["Mây", "bay", "Mây", "bay"]
    assert assignments(result) == ["note-0", "note-1", "note-4", "note-5"]
    assert result["lyric_source"]["cue_count"] == 2
    assert not any("cuối không" in warning for warning in result["warnings"])


def test_lrc_empty_end_marker_bounds_last_cue():
    result = imported("[00:00.00]Mây bay qua trời\n[00:02.40]Nắng lên bên đồi\n[00:04.80]",
                      (0, 0.6, 1.2, 1.8, 2.4, 3.0, 3.6, 4.2, 4.8, 100))
    assert assignments(result) == [f"note-{i}" for i in range(8)]
    assert result["lyric_source"]["cue_count"] == 2


def test_positive_lrc_embedded_offset_advances_but_positive_ui_offset_delays():
    source = "[offset:+1000]\n[00:02.00]Mây\n[00:02.50]"
    earlier = imported(source, (1, 2, 3))
    assert assignments(earlier) == ["note-0"]
    later = imported(source, (1, 2, 3), offset_seconds=2)
    assert assignments(later) == ["note-2"]
    assert later["lyrics"][0]["source_start"] == 3
    assert later["lyric_source"]["offset_seconds"] == 2


def test_lrc_offset_at_end_applies_to_all_lines_and_last_tag_wins():
    result = imported("[offset:500]\n[00:00.00]Mây\n[00:01.00]\n[offset:-1000]", (0, 1))
    assert assignments(result) == ["note-1"]
    assert any("thẻ cuối cùng" in warning for warning in result["warnings"])


def test_all_words_preserved_when_not_enough_notes():
    result = imported("[00:00.00]Mây bay qua trời\n[00:02.00]", (0, 1, 10))
    assert words(result) == ["Mây", "bay", "qua", "trời"]
    assert assignments(result) == ["note-0", "note-1", None, None]
    assert any("2/4" in warning for warning in result["warnings"])


def test_extra_notes_distributed_across_phrase():
    result = imported("[00:00.00]Mây bay\n[00:04.00]", (0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5))
    assert assignments(result) == ["note-0", "note-4"]


def test_cue_is_closed_at_start_and_open_at_end():
    result = imported("[00:01.00]Mây\n[00:02.00]Bay\n[00:03.00]", (0.999, 1, 2, 3))
    assert assignments(result) == ["note-1", "note-2"]


def test_float_rounding_does_not_steal_note_at_next_cue_boundary():
    result = imported("[00:00.00]Mây\n[00:01.80]Bay\n[00:02.00]", (0, 3 * 0.6))
    assert assignments(result) == ["note-0", "note-1"]


def test_unicode_whitespace_and_bracketed_lyric_text():
    result = imported("[00:00.00][Oh] Mây\u00a0bay\u2003xa\n[00:04.00]", (0, 1, 2, 3))
    assert words(result) == ["[Oh]", "Mây", "bay", "xa"]
    assert assignments(result) == ["note-0", "note-1", "note-2", "note-3"]


def test_metadata_and_section_tags_anywhere_do_not_consume_notes():
    result = imported(
        '[ti:Bài hát][ar:Ca sĩ]\n[Verse 1]\n'
        '[00:00.00][Chorus]Mây[by:Editor] bay[al:Album]\n'
        '[Bridge: softly]\n[00:02.00][Điệp khúc]Nắng lên\n[00:04.00][Outro]',
        (0, 1, 2, 3, 4),
    )
    assert words(result) == ['Mây', 'bay', 'Nắng', 'lên']
    assert assignments(result) == ['note-0', 'note-1', 'note-2', 'note-3']
    assert result['lyrics'][-1]['source_end'] == 4
    assert sum('metadata' in warning for warning in result['warnings']) == 1


def test_cleaning_keeps_enhanced_timing_repeats_and_inline_offset():
    result = imported(
        '[00:02.00][00:06.00][Pre-Chorus]<00:02.00>Mây '
        '<00:03.00>bay[offset:1000]<00:04.00>', (1, 2, 5, 6),
    )
    assert words(result) == ['Mây', 'bay', 'Mây', 'bay']
    assert assignments(result) == ['note-0', 'note-1', 'note-2', 'note-3']
    assert [token['source_start'] for token in result['lyrics']] == [1, 2, 5, 6]


def test_srt_metadata_headers_and_sections_removed_before_alignment():
    result = imported(
        '[ti:Bài hát]\n[ar:Ca sĩ]\n\n1\n00:00:00,000 --> 00:00:02,000\n'
        '[Verse 1]\n<i>Mây</i>[by:Editor] bay\n\n'
        '2\n00:00:02,000 --> 00:00:03,000\n[Instrumental]',
        (0, 1, 2), 'test.srt',
    )
    assert words(result) == ['Mây', 'bay']
    assert assignments(result) == ['note-0', 'note-1']


def test_metadata_only_upload_rejected():
    with pytest.raises(ValueError, match='không có lời hát'):
        imported('[ti:Song]\n[Verse 1]\n[00:00.00][Instrumental]')


def test_notes_use_source_time_before_quantized_score_time():
    score = score_at(0, 1, 2)
    score["notes"][0]["source_start"] = 50
    score["notes"][1]["source_start"] = 0.1
    score["notes"][2]["source_start"] = 0.5
    result = parse_and_align(b"[00:00.00]MAY BAY\n[00:01.00]", "test.lrc", score)
    assert assignments(result) == ["note-1", "note-2"]


def test_no_nearest_note_fallback_or_distant_outro_for_final_lrc():
    result = imported("[00:05.00]Mây bay", (0, 4.9, 50, 100))
    assert assignments(result) == [None, None]
    assert result["lyrics"][0]["source_end"] <= 15
    assert any("10 giây" in warning for warning in result["warnings"])


def test_overlapping_srt_cues_never_attach_two_words_to_same_note():
    result = imported("1\n00:00:00,000 --> 00:00:02,000\nMây bay\n\n2\n00:00:01,000 --> 00:00:02,000\nTrời",
                      (0, 1), "test.srt")
    assert words(result) == ["Mây", "bay", "Trời"]
    assert assignments(result) == ["note-0", "note-1", None]


def test_enhanced_lrc_honors_word_timestamps_and_end_marker():
    result = imported("[00:05.00]<00:05.00>Mây <00:06.00>bay <00:07.00>qua trời<00:09.00>",
                      (5, 5.5, 6, 6.5, 7, 8, 9))
    assert words(result) == ["Mây", "bay", "qua", "trời"]
    assert assignments(result) == ["note-0", "note-2", "note-4", "note-5"]
    assert [token["source_start"] for token in result["lyrics"]] == [5, 6, 7, 7]
    assert [token["source_end"] for token in result["lyrics"]] == [6, 7, 9, 9]


def test_enhanced_lrc_prefix_and_repeat_are_shifted():
    result = imported("[00:01.00][00:11.00]Mây <00:02.00>bay<00:03.00>", (1, 2, 3, 11, 12, 13))
    assert words(result) == ["Mây", "bay", "Mây", "bay"]
    assert assignments(result) == ["note-0", "note-1", "note-3", "note-4"]
    assert [token["source_start"] for token in result["lyrics"]] == [1, 2, 11, 12]


def test_negative_shift_keeps_unmatched_words_and_nonnegative_source_times():
    result = imported("[00:00.00]Mây\n[00:01.00]", (0,), offset_seconds=-2)
    assert assignments(result) == [None]
    assert result["lyrics"][0]["source_start"] == result["lyrics"][0]["source_end"] == 0
    assert any("trước đầu audio" in warning for warning in result["warnings"])


@pytest.mark.parametrize("text,filename", [
    ("", "a.lrc"),
    ("[ar:Artist]", "a.lrc"),
    ("[00:01.00]", "a.lrc"),
    ("[00:60.00]Hello", "a.lrc"),
    ("[00:xx]Hello", "a.lrc"),
    ("[00:01.1234]Hello", "a.lrc"),
    ("[offset:nan]\n[00:01.00]Hello", "a.lrc"),
    ("Hello", "a.lrc"),
    ("[00:05.00]<00:04.00>Hello", "a.lrc"),
    ("[00:05.00]<00:06.00>Hello<00:05.50>world", "a.lrc"),
    ("[00:05.00]<00:60.00>Hello", "a.lrc"),
    ("1\n00:00:01,000 --> 00:00:01,000\nHello", "a.srt"),
    ("1\n00:60:01,000 --> 01:01:02,000\nHello", "a.srt"),
    ("1\n00:00:01,000 --> 00:00:60,000\nHello", "a.srt"),
    ("1\n00:00:00,000 --> 00:00:01,000\nHello\n2\n00:00:01,000 --> 00:00:02,000\nworld", "a.srt"),
    ("Hello", "a.txt"),
    ("[00:00.00]Hi\x00there", "a.lrc"),
    ("[00:00.00]Hi\uffffthere", "a.lrc"),
    ("[00:00.00]" + "a" * 201, "a.lrc"),
])
def test_invalid_input_is_rejected_without_partial_import(text, filename):
    with pytest.raises(ValueError):
        imported(text, (0, 1, 2), filename)


@pytest.mark.parametrize("data", [b"\xff\x00\xff", b"x" * (MAX_BYTES + 1), "[00:00.00]Hello".encode("utf-16-le")], ids=["bad-utf8", "over-1mb", "utf16-missing-bom"])
def test_invalid_encoding_or_oversized_file(data):
    with pytest.raises(ValueError):
        parse_and_align(data, "a.lrc", score_at(0))


def test_token_count_limit_counts_repeated_lines():
    text = "[00:00.00][00:01.00]" + "x " * 10001
    with pytest.raises(ValueError, match="20.000"):
        imported(text)


@pytest.mark.parametrize("offset", [float("nan"), float("inf"), -float("inf")])
def test_offset_must_be_finite(offset):
    with pytest.raises(ValueError):
        imported("[00:00.00]Hello", offset_seconds=offset)


def test_special_characters_removed_during_upload():
    result = imported("1\n00:00:00,000 --> 00:00:02,000\n♪ Là em, đây anh! (Điệp khúc)... &amp; @123 ♪", (0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0), "a.srt")
    assert words(result) == ["Là", "em,", "đây", "anh!", "(Điệp", "khúc)...", "123"]
