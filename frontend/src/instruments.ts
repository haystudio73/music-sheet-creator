export const instruments = [
  ['acoustic_grand_piano', 'Piano'], ['acoustic_guitar_nylon', 'Guitar nylon'],
  ['violin', 'Violin'], ['flute', 'Flute'], ['clarinet', 'Clarinet'], ['acoustic_bass', 'Contrabass'],
] as const;
export type InstrumentName = typeof instruments[number][0];
export type Sample = { buffer: AudioBuffer; rate: number };
const banks = new Map<string, Record<string, string>>();
const decoded = new Map<string, AudioBuffer>();
const natural: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
function midi(name: string) {
  const match = /^([A-G])([#b]?)(-?\d+)$/.exec(name);
  if (!match) throw new Error('Tên nốt trong mẫu âm không hợp lệ.');
  return (Number(match[3]) + 1) * 12 + natural[match[1]] + (match[2] === '#' ? 1 : match[2] === 'b' ? -1 : 0);
}

export async function loadInstrument(context: AudioContext, name: InstrumentName, pitches: number[]): Promise<Map<number, Sample>> {
  if (!instruments.some(item => item[0] === name)) throw new Error('Nhạc cụ không được hỗ trợ.');
  let bank = banks.get(name);
  if (!bank) {
    const response = await fetch(`/instruments/${name}.json`);
    if (!response.ok) throw new Error('Thiếu mẫu nhạc cụ local. Chạy scripts/prepare_instruments.py rồi build lại giao diện.');
    bank = await response.json() as Record<string, string>;
    banks.set(name, bank);
  }
  const available = Object.keys(bank).map(key => ({ key, pitch: midi(key) }));
  if (!available.length) throw new Error('Mẫu nhạc cụ trống.');
  const result = new Map<number, Sample>();
  // Decode only pitches needed for this score, reusing decoded local samples.
  for (const pitch of new Set(pitches)) {
    const closest = available.reduce((best, entry) => Math.abs(entry.pitch - pitch) < Math.abs(best.pitch - pitch) ? entry : best);
    const cacheKey = `${name}:${closest.key}`;
    let buffer = decoded.get(cacheKey);
    if (!buffer) {
      const sample = bank[closest.key];
      if (!sample.startsWith('data:audio/mp3;base64,')) throw new Error('Mẫu âm không hợp lệ.');
      const bytes = Uint8Array.from(atob(sample.split(',')[1]), char => char.charCodeAt(0));
      buffer = await context.decodeAudioData(bytes.buffer);
      decoded.set(cacheKey, buffer);
    }
    result.set(pitch, { buffer, rate: 2 ** ((pitch - closest.pitch) / 12) });
  }
  return result;
}
