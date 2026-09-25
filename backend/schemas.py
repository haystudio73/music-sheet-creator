"""Versioned, deliberately small contracts for the first local release."""
from fractions import Fraction
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


def quarter_fraction(value: str, *, positive: bool = False) -> str:
    if len(value) > 32:
        raise ValueError("Trường độ quá dài")
    try:
        number = Fraction(value)
    except (ValueError, ZeroDivisionError):
        raise ValueError("Trường độ phải là phân số, ví dụ 1 hoặc 3/2") from None
    if number < 0 or (positive and not number) or number > 100000:
        raise ValueError("Vị trí hoặc trường độ ngoài giới hạn")
    if number.denominator > 4096:
        raise ValueError("Độ chia nhịp quá nhỏ")
    return str(number)


class Note(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    pitch: int = Field(ge=0, le=127)
    start: str
    duration: str
    velocity: int = Field(default=80, ge=1, le=127)
    source_start: float | None = Field(default=None, ge=0)
    source_end: float | None = Field(default=None, ge=0)

    @field_validator("start")
    @classmethod
    def start_fraction(cls, value):
        return quarter_fraction(value)

    @field_validator("duration")
    @classmethod
    def duration_fraction(cls, value):
        return quarter_fraction(value, positive=True)


class Harmony(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    root: str = Field(default="C", max_length=4)
    quality: Literal["major", "minor", "dominant-seventh", "major-seventh", "minor-seventh", "diminished", "augmented", "suspended-second", "suspended-fourth"] = "major"
    bass: str | None = Field(default=None, max_length=4)
    start: str
    duration: str
    kind: Literal["chord", "no_chord", "unknown"] = "chord"

    @field_validator("start")
    @classmethod
    def start_fraction(cls, value):
        return quarter_fraction(value)

    @field_validator("duration")
    @classmethod
    def duration_fraction(cls, value):
        return quarter_fraction(value, positive=True)


def valid_meter(value: list[int]) -> list[int]:
    if len(value) != 2 or not 1 <= value[0] <= 12 or value[1] not in (2, 4, 8, 16):
        raise ValueError("Số chỉ nhịp không hợp lệ")
    return value


class LyricToken(StrictModel):
    id: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=200)
    note_id: str | None = Field(default=None, min_length=1, max_length=100)
    verse: int = Field(default=1, ge=1, le=20)
    syllabic: Literal["single", "begin", "middle", "end"] = "single"
    source_start: float | None = Field(default=None, ge=0)
    source_end: float | None = Field(default=None, ge=0)

    @field_validator("text")
    @classmethod
    def printable_text(cls, value):
        value = value.strip()
        if not value or any(not (ord(char) in (9, 10, 13) or 0x20 <= ord(char) <= 0xD7FF
                                or 0xE000 <= ord(char) <= 0xFFFD or 0x10000 <= ord(char) <= 0x10FFFF)
                            for char in value):
            raise ValueError("Lời hát không được rỗng hoặc chứa ký tự điều khiển không hợp lệ")
        return value

    @model_validator(mode="after")
    def ordered_times(self):
        if self.source_start is not None and self.source_end is not None and self.source_end < self.source_start:
            raise ValueError("Mốc kết thúc lời hát không được trước mốc bắt đầu")
        return self


class LyricSource(StrictModel):
    filename: str = Field(min_length=1, max_length=255)
    format: Literal["srt", "lrc"]
    offset_seconds: float = Field(default=0, ge=-600, le=600)
    cue_count: int = Field(ge=1, le=20000)


class ScoreDocument(StrictModel):
    schema_version: Literal[1] = 1
    revision: int = Field(default=0, ge=0)
    title: str = Field(min_length=1, max_length=200)
    tempo: float = Field(default=100, ge=20, le=300)
    meter: list[int] = Field(default_factory=lambda: [4, 4])
    key: str = Field(default="C", max_length=8)
    notes: list[Note] = Field(default_factory=list, max_length=20000)
    harmonies: list[Harmony] = Field(default_factory=list, max_length=5000)
    lyrics: list[LyricToken] = Field(default_factory=list, max_length=20000)
    lyric_source: LyricSource | None = None
    diagnostics: list[str] = Field(default_factory=list, max_length=200)
    source_engine: str = Field(default="manual", max_length=100)
    review_status: Literal["needs_review", "reviewed"] = "needs_review"
    melody_role: Literal["instrumental", "vocal"] = "instrumental"

    _meter = field_validator("meter")(valid_meter)


class AnalyzeRequest(StrictModel):
    engine: Literal["sheetsage2", "monophonic"] = "monophonic"
    device: Literal["auto", "gpu", "cpu"] = "auto"
    tempo: float = Field(default=100, ge=20, le=300)
    meter: list[int] = Field(default_factory=lambda: [4, 4])
    key: str = Field(default="C", max_length=8)
    melody_role: Literal["instrumental", "vocal"] = "instrumental"

    _meter = field_validator("meter")(valid_meter)


class SaveScoreRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    score: ScoreDocument


class SaveEditorRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    expected_version: int = Field(ge=0)
    musicxml: str = Field(min_length=1, max_length=10_000_000)


class TransposeRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    semitones: int = Field(ge=-24, le=24)


class ReviewRequest(StrictModel):
    expected_revision: int = Field(ge=1)


class ActivateScoreRequest(StrictModel):
    expected_revision: int = Field(ge=1)
    revision: int = Field(ge=1)


class ExportRequest(StrictModel):
    format: Literal["musicxml", "midi", "pdf", "abc"]
    revision: int = Field(ge=1)
    accompaniment: bool = False
    include_chords: bool = True
    include_lyrics: bool = True
    scope: Literal["full", "range"] = "full"
    bar_start: int | None = Field(default=None, ge=1)
    bar_end: int | None = Field(default=None, ge=1)
    custom_title: str | None = Field(default=None, max_length=200)
