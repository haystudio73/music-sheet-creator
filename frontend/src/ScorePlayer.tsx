import { t } from './i18n';
import { useCallback, useEffect, useId, useMemo, useRef, useState } from 'react';
import { LoaderCircle, Play, Square, Volume2 } from 'lucide-react';
import { useSettings } from './Settings';
import { timeLabel } from './AudioPlayer';
import type { ScoreDocument } from './types';
import { instruments, loadInstrument, type InstrumentName } from './instruments';
interface PlaybackNote {
    pitch: number;
    start: number;
    duration: number;
    velocity: number;
}
interface PlaybackRun {
    context: AudioContext;
    output: GainNode;
    voices: Set<AudioBufferSourceNode>;
    clicks: Set<OscillatorNode>;
    metronomeOutput: GainNode;
    nextPulse: number;
    timer?: number;
    origin: number;
    index: number;
    displayedAt: number;
    tick?: () => void;
}
const MAX_SECONDS = 30 * 60;
// Keep the UI as a familiar 0–100% scale while driving the local instrument
// with five times the previous 0.16 gain at the 100% position.
export const INSTRUMENT_GAIN_AT_100 = 0.8;
export const instrumentGain = (value: number) => INSTRUMENT_GAIN_AT_100 * Math.max(0, Math.min(100, value)) / 100;
const fraction = (value: string) => {
    if (!/^(?:\d+(?:\.\d+)?|\.\d+)(?:\/\d+)?$/.test(value.trim()))
        return NaN;
    const [numerator, denominator = '1'] = value.trim().split('/');
    const result = Number(numerator) / Number(denominator);
    return Number.isFinite(result) ? result : NaN;
};
function playbackScore(score: ScoreDocument): {
    notes: PlaybackNote[];
    duration: number;
    error: string;
} {
    if (!Number.isFinite(score.tempo) || score.tempo < 20 || score.tempo > 300) {
        return { notes: [], duration: 0, error: t("Đặt tempo từ 20 đến 300 BPM để nghe bản nhạc.") };
    }
    const secondsPerQuarter = 60 / score.tempo;
    const notes: PlaybackNote[] = [];
    let duration = 0;
    for (const note of score.notes) {
        const start = fraction(note.start) * secondsPerQuarter;
        const length = fraction(note.duration) * secondsPerQuarter;
        if (!Number.isFinite(start) || !Number.isFinite(length) || start < 0 || length <= 0 ||
            !Number.isInteger(note.pitch) || note.pitch < 0 || note.pitch > 127 ||
            !Number.isFinite(note.velocity) || note.velocity < 1 || note.velocity > 127) {
            return { notes: [], duration: 0, error: t("Sửa cao độ, vị trí hoặc trường độ không hợp lệ trước khi nghe.") };
        }
        duration = Math.max(duration, start + length);
        notes.push({ pitch: note.pitch, start, duration: length, velocity: note.velocity });
    }
    if (duration > MAX_SECONDS || notes.length > 20000) {
        return { notes: [], duration: 0, error: t("Bản nghe thử hỗ trợ tối đa 30 phút và 20.000 nốt. Kiểm tra lại vị trí, trường độ của các nốt.") };
    }
    notes.sort((a, b) => a.start - b.start);
    return { notes, duration, error: '' };
}
export default function ScorePlayer({ projectId, score, onPlaybackBeat }: {
    projectId: string;
    score: ScoreDocument;
    onPlaybackBeat: (beat: number | null) => void;
}) {
    const playback = useMemo(() => playbackScore(score), [score]);
    const run = useRef<PlaybackRun | null>(null);
    const [state, setState] = useState<'stopped' | 'starting' | 'playing'>('stopped');
    const [position, setPosition] = useState(0);
    const [error, setError] = useState('');
    const [instrument, setInstrument] = useState<InstrumentName>('acoustic_grand_piano');
    const { settings, update: updateSettings } = useSettings();
    const volume = settings.instrumentVolume;
    const metronomeRef = useRef(settings.metronome);
    metronomeRef.current = settings.metronome;
    const pulseQuarters = score.meter[1] === 8 && score.meter[0] % 3 === 0 ? 1.5 : 4 / score.meter[1];
    const pulsesPerBar = score.meter[0] * 4 / score.meter[1] / pulseQuarters;
    const pulseSeconds = pulseQuarters * 60 / score.tempo;
    const pulseIndex = Math.floor(position / pulseSeconds + 1e-6);
    const volumeRef = useRef(volume);
    volumeRef.current = volume;
    const clickVolumeRef = useRef(settings.metronomeVolume);
    clickVolumeRef.current = settings.metronomeVolume;
    useEffect(() => {
        const current = run.current;
        if (!current)
            return;
        current.metronomeOutput.gain.setTargetAtTime(settings.metronome ? settings.metronomeVolume / 100 * .25 : 0, current.context.currentTime, .01);
    }, [settings.metronome, settings.metronomeVolume]);
    const positionRef = useRef(0);
    const descriptionId = useId();
    useEffect(() => {
        onPlaybackBeat(state === 'playing' ? position * score.tempo / 60 : null);
    }, [position, state, score.tempo, onPlaybackBeat]);
    const dispose = useCallback(() => {
        const current = run.current;
        run.current = null;
        if (!current)
            return;
        window.clearInterval(current.timer);
        for (const voice of current.voices) {
            try {
                voice.stop();
            }
            catch { /* The voice may already have ended. */ }
            voice.disconnect();
        }
        current.voices.clear();
        for (const click of current.clicks) {
            try {
                click.stop();
            }
            catch { /* Ended. */ }
            click.disconnect();
        }
        current.clicks.clear();
        current.metronomeOutput.disconnect();
        current.output.disconnect();
        void current.context.close().catch(() => { });
    }, []);
    useEffect(() => {
        dispose();
        setState('stopped');
        setPosition(0);
        positionRef.current = 0;
        setError('');
        return () => { dispose(); onPlaybackBeat(null); };
    }, [projectId, score, instrument, dispose, onPlaybackBeat]);
    const stop = () => { dispose(); setState('stopped'); setPosition(0); positionRef.current = 0; };
    const seek = (value: number) => {
        const next = Math.max(0, Math.min(playback.duration, value));
        positionRef.current = next;
        setPosition(next);
        const active = run.current;
        if (!active?.tick)
            return; // Loading uses the latest requested position when ready.
        for (const voice of active.voices) {
            try {
                voice.stop();
            }
            catch { /* Already ended. */ }
            voice.disconnect();
        }
        active.voices.clear();
        for (const click of active.clicks) {
            try {
                click.stop();
            }
            catch { /* Ended. */ }
            click.disconnect();
        }
        active.clicks.clear();
        active.nextPulse = Math.ceil(next / pulseSeconds - 1e-6);
        active.origin = active.context.currentTime - next;
        active.index = 0; // Also replay notes spanning the seek target.
        active.displayedAt = -1;
        active.tick();
    };
    const changeVolume = (value: number) => {
        updateSettings({ instrumentVolume: value });
        volumeRef.current = value;
        const active = run.current;
        if (active)
            active.output.gain.setTargetAtTime(instrumentGain(value), active.context.currentTime, 0.015);
    };
    const play = async () => {
        if (run.current || playback.error || !playback.notes.length)
            return;
        if (positionRef.current >= playback.duration) {
            positionRef.current = 0;
            setPosition(0);
        }
        setError('');
        setState('starting');
        if (typeof AudioContext === 'undefined') {
            setError(t("Trình duyệt chưa hỗ trợ Web Audio. Hãy dùng Chrome hoặc Edge để nghe kiểm tra."));
            setState('stopped');
            return;
        }
        let current: PlaybackRun | null = null;
        try {
            const context = new AudioContext({ latencyHint: 'interactive' });
            const output = context.createGain();
            output.gain.value = instrumentGain(volumeRef.current);
            // A compressor keeps simultaneous draft notes at a comfortable level.
            const compressor = context.createDynamicsCompressor();
            output.connect(compressor);
            compressor.connect(context.destination);
            const metronomeOutput = context.createGain();
            metronomeOutput.gain.value = metronomeRef.current ? clickVolumeRef.current / 100 * .25 : 0;
            metronomeOutput.connect(compressor);
            current = { context, output, voices: new Set(), clicks: new Set(), metronomeOutput, nextPulse: 0, origin: 0, index: 0, displayedAt: -1 };
            run.current = current;
            await context.resume();
            if (run.current !== current)
                return;
            const samples = await loadInstrument(context, instrument, playback.notes.map(note => note.pitch));
            if (run.current !== current)
                return;
            current.origin = context.currentTime + 0.05 - positionRef.current;
            const active = current;
            active.nextPulse = Math.ceil(positionRef.current / pulseSeconds - 1e-6);
            const tick = () => {
                if (run.current !== active)
                    return;
                try {
                    const now = context.currentTime;
                    const elapsed = Math.max(0, now - active.origin);
                    if (elapsed - active.displayedAt >= 0.025) {
                        positionRef.current = Math.min(playback.duration, elapsed);
                        setPosition(positionRef.current);
                        active.displayedAt = elapsed;
                    }
                    if (elapsed >= playback.duration + 0.03) {
                        dispose();
                        setState('stopped');
                        setPosition(playback.duration);
                        positionRef.current = playback.duration;
                        return;
                    }
                    active.nextPulse = Math.max(active.nextPulse, Math.ceil((elapsed - .03) / pulseSeconds));
                    while (active.nextPulse * pulseSeconds < Math.min(playback.duration, elapsed + .12)) {
                        const pulse = active.nextPulse++;
                        const at = Math.max(now + .002, active.origin + pulse * pulseSeconds);
                        const oscillator = context.createOscillator();
                        const envelope = context.createGain();
                        oscillator.frequency.value = pulse % pulsesPerBar === 0 ? 1200 : 800;
                        envelope.gain.setValueAtTime(.001, at);
                        envelope.gain.exponentialRampToValueAtTime(1, at + .003);
                        envelope.gain.exponentialRampToValueAtTime(.001, at + .045);
                        oscillator.connect(envelope);
                        envelope.connect(active.metronomeOutput);
                        active.clicks.add(oscillator);
                        oscillator.onended = () => { active.clicks.delete(oscillator); oscillator.disconnect(); envelope.disconnect(); };
                        oscillator.start(at);
                        oscillator.stop(at + .05);
                    }
                    // Schedule only a short horizon. Even a long score has few live nodes;
                    // timer throttling skips elapsed notes instead of playing them in a burst.
                    while (active.index < playback.notes.length && playback.notes[active.index].start < elapsed + 0.2) {
                        const note = playback.notes[active.index++];
                        const end = active.origin + note.start + note.duration;
                        const start = Math.max(now + 0.005, active.origin + note.start);
                        if (end <= start)
                            continue;
                        if (active.voices.size >= 32)
                            throw new Error(t("Có quá nhiều nốt chồng nhau để nghe thử. Hãy kiểm tra lại giai điệu."));
                        const voice = context.createBufferSource();
                        const envelope = context.createGain();
                        const sample = samples.get(note.pitch)!;
                        voice.buffer = sample.buffer;
                        voice.playbackRate.value = sample.rate;
                        const attack = Math.min(0.008, (end - start) / 4);
                        const release = Math.min(0.035, (end - start) / 4);
                        const volume = note.velocity / 127;
                        envelope.gain.setValueAtTime(0, start);
                        envelope.gain.linearRampToValueAtTime(volume, start + attack);
                        envelope.gain.setValueAtTime(volume, end - release);
                        envelope.gain.linearRampToValueAtTime(0, end);
                        voice.connect(envelope);
                        envelope.connect(output);
                        active.voices.add(voice);
                        voice.onended = () => { active.voices.delete(voice); voice.disconnect(); envelope.disconnect(); };
                        // Resume the sample at its elapsed age when seeking into a held note.
                        voice.start(start, Math.min(sample.buffer.duration, Math.max(0, now - active.origin - note.start) * sample.rate));
                        voice.stop(end);
                    }
                }
                catch (err) {
                    dispose();
                    setState('stopped');
                    setError(err instanceof Error ? err.message : t("Không phát được giai điệu dựng lại."));
                }
            };
            active.tick = tick;
            setState('playing');
            tick();
            if (run.current === active)
                active.timer = window.setInterval(tick, 25);
        }
        catch (err) {
            if (current && run.current !== current)
                return;
            dispose();
            setState('stopped');
            setError(err instanceof Error ? err.message : t("Không khởi động được âm thanh. Thử bấm phát lại."));
        }
    };
    return <section className="score-player" aria-label={t("Nghe giai điệu dựng lại")}>
    <div className="score-player-heading"><Volume2 size={15}/><strong>{t("Nghe giai điệu dựng lại")}</strong></div>
    <p id={descriptionId} className="score-player-description">{t("Mẫu nhạc cụ local · Chỉ giai điệu · Theo các chỉnh sửa hiện tại")}</p>
    <div className="score-player-settings">
      <label className="field instrument-choice">{t("Nhạc cụ nghe thử")}<select value={instrument} onChange={event => setInstrument(event.target.value as InstrumentName)}>{instruments.map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></label>
      <label className="score-volume"><span><Volume2 size={14}/>{t("Âm lượng ")}<output>{volume}%</output></span><input className="audio-range" type="range" min="0" max="100" step="1" value={volume} aria-label={t("Âm lượng giai điệu dựng lại")} aria-valuetext={`${volume}%`} onChange={event => changeVolume(Number(event.target.value))}/></label>
    </div>
    <div className="metronome-controls">
      <label className="checkbox-field"><input type="checkbox" checked={settings.metronome} onChange={event => updateSettings({ metronome: event.target.checked })}/>{t("Bộ đếm nhịp")}</label>
      <div className="beat-counter" aria-label={t("Ô nhịp và phách hiện tại")}><span>{t("Ô nhịp ")}{Math.floor(pulseIndex / pulsesPerBar) + 1}</span><span>{t("Phách ")}{pulseIndex % pulsesPerBar + 1} / {pulsesPerBar}</span><div aria-hidden="true">{Array.from({ length: pulsesPerBar }, (_, i) => <i key={i} className={state === 'playing' && i === pulseIndex % pulsesPerBar ? 'active' : ''}/>)}</div></div>
      <label className="score-volume"><span>{t("Âm lượng nhịp ")}<output>{settings.metronomeVolume}%</output></span><input className="audio-range" type="range" min="0" max="100" value={settings.metronomeVolume} aria-label={t("Âm lượng bộ đếm nhịp")} onChange={e => updateSettings({ metronomeVolume: Number(e.target.value) })}/></label>
    </div>
    {state === 'starting' && <p className="field-help" role="status">{t("Đang nạp mẫu nhạc cụ trên máy…")}</p>}
    <div className="transport">
      <button className="play-button" aria-label={state === 'stopped' ? t("Phát giai điệu dựng lại") : t("Dừng giai điệu dựng lại")} aria-describedby={descriptionId} disabled={Boolean(playback.error) || !playback.notes.length} onClick={() => state === 'stopped' ? void play() : stop()}>
        {state === 'starting' ? <LoaderCircle size={17} className="spin"/> : state === 'playing' ? <Square size={14} fill="currentColor"/> : <Play size={17} fill="currentColor"/>}
      </button>
      <span className="audio-time">{timeLabel(position)}</span>
      <input className="audio-range score-player-seek" type="range" min="0" step="any" aria-label={t("Vị trí phát giai điệu dựng lại")} aria-valuetext={`${timeLabel(position)} / ${timeLabel(playback.duration)}`} max={playback.duration || 1} value={position} disabled={Boolean(playback.error) || !playback.notes.length} onChange={event => seek(Number(event.target.value))}/>
      <span className="audio-time muted">{timeLabel(playback.duration)}</span>
    </div>
    {!playback.notes.length && !playback.error && <p className="inline-error">{t("Chưa có nốt giai điệu để phát.")}</p>}
    {(playback.error || error) && <p className="inline-error" role="alert">{playback.error || error}</p>}
  </section>;
}
