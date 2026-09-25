"""Import timed lyrics without pretending that line timestamps are syllable timing.

The importer proposes one whitespace-separated token per melody note. Unmatched
tokens remain editable in the score; it never borrows a note outside a cue. LRC's
embedded positive offset advances lyrics, whereas the UI's positive offset delays
them. Enhanced LRC <mm:ss.xx> word timestamps are absolute within the first repeat.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from fractions import Fraction
import html
import math
from pathlib import PureWindowsPath
import re
from uuid import uuid4


MAX_BYTES = 1024 * 1024
MAX_TOKENS = 20000
MAX_TOKEN_LENGTH = 200
_SRT_TIME = r"\d{1,3}:\d{2}:\d{2}[,.]\d{1,3}"
_SRT_RANGE = re.compile(
    rf"^({_SRT_TIME})[ \t]*-->[ \t]*({_SRT_TIME})"
    r"(?:[ \t]+(?:[XY][12]:\d+[ \t]*)+)?$"
)
_LRC_TIME = re.compile(r"^(\d{1,5}):(\d{2})(?:\.(\d{1,3}))?$")
_LEADING_TAG = re.compile(r"^\[([^\[\]]*)\]")
_METADATA = re.compile(r"^([A-Za-z#][A-Za-z0-9_#-]*)\s*:(.*)$")
_WORD_TAG = re.compile(r"<(\d[^<>]*)>")
_BRACKET_TAG = re.compile(r"\[([^\[\]\n]*)\]")
_SECTION_TAG = re.compile(
    r"(?:intro|outro|verse|chorus|pre[- ]?chorus|post[- ]?chorus|bridge|hook|"
    r"refrain|interlude|instrumental|(?:guitar |piano |drum )?solo|breakdown|"
    r"break|ending|điệp khúc|đoạn|dạo đầu|dạo cuối)"
    r"(?:\s+\d+)?(?:\s*[:\-–].*)?", re.IGNORECASE,
)


@dataclass(frozen=True)
class _Segment:
    start: float
    end: float | None
    words: list[str]


@dataclass(frozen=True)
class _Cue:
    start: float
    end: float | None
    segments: list[_Segment]


def _warn(warnings: list[str], message: str) -> None:
    value = f"Lời hát: {message}"
    if value not in warnings:
        warnings.append(value)


def _clean_metadata(text: str, format_name: str, warnings: list[str]) -> str:
    """Remove descriptive tags before alignment, never remove timing markers.

    LRC offsets affect timing even though they are not sung. Collect them in
    source order for the existing validator (including duplicate/invalid tags).
    Preserve unknown bracketed words instead of guessing they are metadata.
    """
    offsets: list[str] = []
    removed = False

    def clean_tag(match: re.Match) -> str:
        nonlocal removed
        tag = match[1].strip()
        metadata = _METADATA.fullmatch(tag)
        if metadata or _SECTION_TAG.fullmatch(tag):
            if metadata and metadata[1].lower() == 'offset' and format_name == 'lrc':
                offsets.append(f'[{tag}]')
            removed = True
            return ' '
        return match[0]

    lines = []
    for line in text.splitlines():
        cleaned = _BRACKET_TAG.sub(clean_tag, line)
        # Remove tag-only lines without introducing a blank within an SRT cue.
        if cleaned.strip() or not line.strip():
            lines.append(cleaned)
    if removed:
        _warn(warnings, 'Đã tự động loại bỏ thẻ metadata và nhãn đoạn khỏi lời hát; giữ nguyên mốc thời gian để căn lời.')
    return '\n'.join(offsets + lines).strip()


def _xml_compatible(text: str) -> bool:
    return all(
        char in "\t\n\r"
        or 0x20 <= ord(char) <= 0xD7FF
        or 0xE000 <= ord(char) <= 0xFFFD
        or 0x10000 <= ord(char) <= 0x10FFFF
        for char in text
    )


def _decode(data: bytes) -> str:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Tệp lời hát phải có dữ liệu và không quá 1 MB.")
    try:
        text = data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeError:
        raise ValueError("Tệp lời hát phải dùng UTF-8 hoặc UTF-16 có BOM.") from None
    if not _xml_compatible(text):
        raise ValueError("Tệp lời hát chứa ký tự điều khiển không hợp lệ cho MusicXML.")
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise ValueError("Tệp lời hát trống.")
    return text


def _words(text: str) -> list[str]:
    # Subtitle styling is not lyric content. Entities are decoded before the
    # tag pass so encoded formatting cannot end up being interpreted as XML.
    text = html.unescape(text)
    text = re.sub(r"<br\s*/?>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]*>", "", text)
    text = re.sub(r"{\s*(?:[\\/]|[yY]:)[^}]*}", "", text)
    # Loại bỏ các ký tự đặc biệt, biểu tượng (như @, #, $, %, ^, &, *, +, =, <, >, /, \, |, ~, biểu tượng nhạc ♪...)
    # Giữ lại các dấu câu và dấu ngoặc: , . ! ? " ' - _ ( ) [ ] { } “” ‘’ — – … : ;
    text = re.sub(r"[^\w\s,.\!?\"'\-_()\[\]{}“”‘’—–…:;]", " ", text)
    if not _xml_compatible(text):
        raise ValueError("Lời hát chứa ký tự không hợp lệ cho MusicXML.")
    words = text.split()
    if any(len(word) > MAX_TOKEN_LENGTH for word in words):
        raise ValueError("Mỗi từ trong lời hát không được dài quá 200 ký tự.")
    return words


def _srt_time(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    if int(minutes) >= 60 or float(seconds) >= 60:
        raise ValueError(f"Mốc thời gian SRT không hợp lệ: {value}.")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _lrc_time(value: str) -> float:
    match = _LRC_TIME.fullmatch(value)
    if not match or int(match[2]) >= 60:
        raise ValueError(f"Mốc thời gian LRC không hợp lệ: {value}.")
    return int(match[1]) * 60 + int(match[2]) + (float(f"0.{match[3]}") if match[3] else 0)


def _srt_cues(text: str, warnings: list[str]) -> list[_Cue]:
    cues = []
    for block_index, block in enumerate(re.split(r"\n[ \t]*\n", text), 1):
        lines = block.strip().splitlines()
        if lines and lines[0].strip().isdigit():
            lines = lines[1:]
        match = _SRT_RANGE.fullmatch(lines[0].strip()) if lines else None
        if not match:
            raise ValueError(f"Đoạn SRT {block_index} thiếu mốc thời gian hợp lệ.")
        if any("-->" in line for line in lines[1:]):
            raise ValueError("Các đoạn SRT phải được ngăn cách bằng một dòng trống.")
        start, end = _srt_time(match[1]), _srt_time(match[2])
        if end <= start:
            raise ValueError(f"Đoạn SRT {block_index} phải kết thúc sau khi bắt đầu.")
        words = _words("\n".join(lines[1:]))
        if not words:
            _warn(warnings, "Đã bỏ qua đoạn thời gian không có nội dung lời.")
            continue
        cues.append(_Cue(start, end, [_Segment(start, end, words)]))
    return cues


def _lrc_segments(body: str, line_start: float) -> tuple[list[_Segment], float | None]:
    markers = list(_WORD_TAG.finditer(body))
    if not markers:
        return [_Segment(line_start, None, _words(body))], None

    parts: list[tuple[float, list[str]]] = []
    prefix = _words(body[:markers[0].start()])
    if prefix:
        parts.append((line_start, prefix))
    previous = None
    for index, marker in enumerate(markers):
        time = _lrc_time(marker[1])
        if time < line_start or (previous is not None and time <= previous):
            raise ValueError("Mốc từng từ LRC phải tăng dần và không sớm hơn mốc đầu dòng.")
        if prefix and index == 0 and time == line_start:
            raise ValueError("Mốc từng từ LRC không được trùng với phần lời ngay trước đó.")
        stop = markers[index + 1].start() if index + 1 < len(markers) else len(body)
        parts.append((time, _words(body[marker.end():stop])))
        previous = time
    segments = [
        _Segment(time, parts[index + 1][0] if index + 1 < len(parts) else None, words)
        for index, (time, words) in enumerate(parts)
        if words
    ]
    # A trailing timestamp without text is an explicit end, not a lyric token.
    explicit_end = parts[-1][0] if not parts[-1][1] else None
    return segments, explicit_end


def _lrc_cues(text: str, warnings: list[str]) -> tuple[list[_Cue], float]:
    cues: list[_Cue] = []
    boundaries: list[float] = []
    embedded_offset = 0.0
    offset_seen = False
    for line_index, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            continue
        timestamps: list[float] = []
        while match := _LEADING_TAG.match(line):
            tag = match[1]
            metadata = _METADATA.fullmatch(tag)
            if metadata:
                if timestamps:
                    break  # A bracketed stage direction after timing is text.
                if metadata[1].lower() == "offset":
                    if not re.fullmatch(r"[+-]?\d{1,9}", metadata[2].strip()):
                        raise ValueError("Giá trị [offset:...] trong LRC phải là số nguyên mili giây.")
                    if offset_seen:
                        _warn(warnings, "Có nhiều thẻ offset trong LRC; dùng thẻ cuối cùng.")
                    embedded_offset = int(metadata[2].strip()) / 1000
                    offset_seen = True
                line = line[match.end():].lstrip()
                continue
            if timestamps and not tag[:1].isdigit():
                break  # Preserve bracketed lyric text such as [Chorus].
            timestamps.append(_lrc_time(tag))
            line = line[match.end():].lstrip()
        if not timestamps:
            if line:
                raise ValueError(f"Dòng LRC {line_index} thiếu mốc [phút:giây].")
            continue
        boundaries.extend(timestamps)
        segments, explicit_end = _lrc_segments(line, timestamps[0])
        if not any(segment.words for segment in segments):
            continue  # Keep an empty line's timestamps as boundary markers.
        for start in timestamps:
            shift = start - timestamps[0]
            repeated = [
                _Segment(segment.start + shift, None if segment.end is None else segment.end + shift, segment.words)
                for segment in segments
            ]
            cues.append(_Cue(start, None if explicit_end is None else explicit_end + shift, repeated))

    boundaries = sorted(set(boundaries))
    bounded = []
    for cue in cues:
        position = bisect_right(boundaries, cue.start)
        next_start = boundaries[position] if position < len(boundaries) else None
        end = cue.end
        if next_start is not None:
            end = min(end, next_start) if end is not None else next_start
        if end is None:
            # LRC has no end time for its last line. Do not let it attach to a
            # distant outro: only a conservative 2–10 second final window.
            tail = cue.segments[-1]
            end = tail.start + max(2.0, min(10.0, len(tail.words) * 0.8))
            _warn(warnings, "Dòng LRC cuối không có mốc kết thúc; cửa sổ ghép cuối được ước lượng tối đa 10 giây. Có thể thêm dòng thời gian trống để đặt mốc kết thúc.")
        bounded.append(_Cue(cue.start, end, cue.segments))
    if embedded_offset:
        _warn(warnings, "Đã áp dụng thẻ offset của LRC: giá trị dương đưa lời sớm hơn; độ lệch nhập trên giao diện dương đưa lời muộn hơn.")
    return bounded, embedded_offset


def parse_and_align(data: bytes, filename: str, score: dict, offset_seconds: float = 0) -> dict:
    """Clean metadata and parse SRT/LRC, preserving every remaining lyric word.

    ``source_start`` / ``source_end`` describe the imported cue (or enhanced LRC
    segment) after offsets, not a claim of estimated phoneme/word timing.
    Filename paths are removed and the provided score is never mutated.
    """
    if not math.isfinite(offset_seconds):
        raise ValueError("Độ lệch thời gian lời hát phải là số hữu hạn.")
    name = PureWindowsPath(filename).name
    format_name = PureWindowsPath(name).suffix.lower().lstrip(".")
    if format_name not in ("srt", "lrc"):
        raise ValueError("Chỉ hỗ trợ tệp lời hát .srt hoặc .lrc.")
    if not name or len(name) > 255 or not _xml_compatible(name):
        raise ValueError("Tên tệp lời hát không hợp lệ hoặc quá dài.")
    text = _decode(data)
    warnings: list[str] = []
    text = _clean_metadata(text, format_name, warnings)
    if format_name == "srt":
        cues, embedded_offset = _srt_cues(text, warnings), 0.0
    else:
        cues, embedded_offset = _lrc_cues(text, warnings)
    count = sum(len(segment.words) for cue in cues for segment in cue.segments)
    if not count:
        raise ValueError("Tệp không có lời hát kèm mốc thời gian hợp lệ.")
    if count > MAX_TOKENS:
        raise ValueError("Tệp lời hát không được vượt quá 20.000 từ.")
    _warn(warnings, "Ghép lời theo mốc thời gian và khoảng trắng là gợi ý; chưa tự chia âm tiết hoặc nhận biết luyến. Hãy nghe và kiểm tra vị trí từng từ.")

    tempo = float(score.get("tempo", 100))
    if not math.isfinite(tempo) or tempo <= 0:
        raise ValueError("Tempo của bản nhạc không hợp lệ.")
    note_times = []
    for index, note in enumerate(score.get("notes", [])):
        time = note.get("source_start")
        time = float(time) if time is not None else float(Fraction(note["start"])) * 60 / tempo
        if not math.isfinite(time) or time < 0:
            raise ValueError("Mốc thời gian của nốt nhạc không hợp lệ.")
        note_times.append((time, index, note["id"]))
    note_times.sort()
    times = [note[0] for note in note_times]
    used_notes: set[str] = set()
    lyrics = []
    shift = offset_seconds - embedded_offset
    for cue in sorted(cues, key=lambda value: value.start):
        for segment in cue.segments:
            start = segment.start + shift
            end = min(segment.end, cue.end) + shift if segment.end is not None else cue.end + shift
            if start < 0:
                _warn(warnings, "Một số mốc lời nằm trước đầu audio sau khi dịch thời gian; mốc hiển thị được chặn tại 0 giây và từ không khớp vẫn được giữ lại.")
            # Audio frame arithmetic and decimal subtitle timestamps can differ
            # by a few floating-point bits at a shared boundary. Snap only this
            # sub-microsecond numerical noise, preserving half-open intervals.
            left = bisect_left(times, start - 1e-7)
            right = bisect_left(times, end - 1e-7)
            candidates = [note[2] for note in note_times[left:right] if note[2] not in used_notes]
            word_count = len(segment.words)
            for index, word in enumerate(segment.words):
                note_id = None
                if len(candidates) >= word_count:
                    # Spread a short phrase over the notes available in its cue.
                    note_id = candidates[index * len(candidates) // word_count]
                elif index < len(candidates):
                    note_id = candidates[index]
                if note_id is not None:
                    used_notes.add(note_id)
                lyrics.append({
                    "id": f"lyric-{uuid4().hex}", "text": word, "note_id": note_id,
                    "verse": 1, "syllabic": "single",
                    "source_start": max(0.0, start), "source_end": max(0.0, start, end),
                })
    unmatched = sum(token["note_id"] is None for token in lyrics)
    if unmatched:
        _warn(warnings, f"Có {unmatched}/{len(lyrics)} từ chưa gắn với nốt; giữ lại toàn bộ để bạn gắn thủ công, không tự ghép sang nốt ngoài khoảng thời gian.")
    return {
        "lyrics": lyrics,
        "lyric_source": {"filename": name, "format": format_name, "offset_seconds": offset_seconds, "cue_count": len(cues)},
        "warnings": warnings,
    }
