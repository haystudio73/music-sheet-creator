import type { Note, ScoreDocument } from './types';

export interface NoteEditValidation {
  valid: boolean;
  tone: 'valid' | 'warning' | 'error';
  message: string;
  measure: number;
  beat: number;
}

const fraction = (value: string): number | null => {
  const [numerator, denominator = '1'] = value.split('/');
  const top = Number(numerator);
  const bottom = Number(denominator);
  if (!Number.isFinite(top) || !Number.isFinite(bottom) || bottom === 0)
    return null;
  const result = top / bottom;
  return Number.isFinite(result) ? result : null;
};

const position = (score: ScoreDocument, start: number) => {
  const barDuration = score.meter[0] * 4 / score.meter[1];
  if (!Number.isFinite(barDuration) || barDuration <= 0)
    return { barDuration: 0, measure: 0, beat: 0 };
  const measure = Math.floor(start / barDuration) + 1;
  const beat = start - (measure - 1) * barDuration + 1;
  return { barDuration, measure, beat };
};

const numberLabel = (value: number) => Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);

export function validateQuickNote(score: ScoreDocument, candidate: Note): NoteEditValidation {
  const start = fraction(candidate.start);
  const duration = fraction(candidate.duration);
  const fallback = { measure: 0, beat: 0 };

  if (!Number.isInteger(candidate.pitch) || candidate.pitch < 0 || candidate.pitch > 127)
    return { valid: false, tone: 'error', message: 'Cao độ MIDI phải là số nguyên từ 0 đến 127.', ...fallback };
  if (start === null || start < 0)
    return { valid: false, tone: 'error', message: 'Vị trí nốt phải là số hoặc phân số không âm.', ...fallback };
  const where = position(score, start);
  if (!where.barDuration)
    return { valid: false, tone: 'error', message: 'Số chỉ nhịp không hợp lệ.', measure: 0, beat: 0 };
  if (duration === null || duration <= 0)
    return { valid: false, tone: 'error', message: 'Trường độ nốt phải là số hoặc phân số dương.', measure: where.measure, beat: where.beat };

  const others = score.notes
    .filter(note => note.id !== candidate.id)
    .map(note => ({ note, start: fraction(note.start), duration: fraction(note.duration) }))
    .filter((item): item is { note: Note; start: number; duration: number } => item.start !== null && item.duration !== null)
    .sort((left, right) => left.start - right.start);
  const epsilon = 1e-7;
  const previous = [...others].reverse().find(item => item.start <= start + epsilon);
  const next = others.find(item => item.start >= start - epsilon);
  if (previous && previous.start + previous.duration > start + epsilon)
    return { valid: false, tone: 'error', message: `Nốt đang chồng lên nốt trước (${previous.note.id}).`, measure: where.measure, beat: where.beat };
  if (next && start + duration > next.start + epsilon)
    return { valid: false, tone: 'error', message: `Trường độ vượt sang nốt kế tiếp (${next.note.id}).`, measure: where.measure, beat: where.beat };

  const endMeasure = Math.floor((start + duration - epsilon) / where.barDuration) + 1;
  if (endMeasure > where.measure)
    return {
      valid: true,
      tone: 'warning',
      message: `Hợp lệ · ô nhịp ${where.measure}, phách ${numberLabel(where.beat)} · nốt kéo sang ô ${endMeasure} và sẽ được nối bằng dấu nối.`,
      measure: where.measure,
      beat: where.beat,
    };
  if (candidate.pitch < 48 || candidate.pitch > 96)
    return {
      valid: true,
      tone: 'warning',
      message: `Hợp lệ · ô nhịp ${where.measure}, phách ${numberLabel(where.beat)} · kiểm tra lại quãng tám vì nốt nằm xa khuông khóa Sol.`,
      measure: where.measure,
      beat: where.beat,
    };
  return {
    valid: true,
    tone: 'valid',
    message: `Nốt hợp lệ · ô nhịp ${where.measure}, phách ${numberLabel(where.beat)}.`,
    measure: where.measure,
    beat: where.beat,
  };
}
