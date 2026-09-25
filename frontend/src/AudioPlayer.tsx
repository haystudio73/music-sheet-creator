import { t } from './i18n';
import { useEffect, useRef, useState } from 'react';
import { Pause, Play, RotateCcw, Volume2 } from 'lucide-react';
import { getApiUrl } from './api';
export const timeLabel = (seconds: number) => `${Math.floor((seconds || 0) / 60)}:${String(Math.floor((seconds || 0) % 60)).padStart(2, '0')}`;
export default function AudioPlayer({ projectId, duration, filename }: {
    projectId: string;
    duration: number;
    filename: string;
}) {
    const audio = useRef<HTMLAudioElement>(null);
    const [playing, setPlaying] = useState(false);
    const [time, setTime] = useState(0);
    const [length, setLength] = useState(duration);
    const [rate, setRate] = useState(1);
    const [error, setError] = useState('');
    useEffect(() => {
        if (audio.current) {
            audio.current.pause();
            audio.current.playbackRate = 1;
        }
        setPlaying(false);
        setTime(0);
        setLength(duration);
        setRate(1);
        setError('');
    }, [projectId, duration]);
    const toggle = async () => {
        if (!audio.current)
            return;
        if (playing)
            audio.current.pause();
        else {
            try {
                await audio.current.play();
                setError('');
            }
            catch {
                setError(t("Trình duyệt chưa phát được tệp này. Thử chuyển nguồn sang WAV."));
            }
        }
    };
    return <section className="audio-strip" aria-label={t("Nghe bản thu gốc")}>
    <audio ref={audio} src={getApiUrl(`/projects/${projectId}/audio`)} preload="metadata" onTimeUpdate={e => setTime(e.currentTarget.currentTime)} onLoadedMetadata={e => setLength(Number.isFinite(e.currentTarget.duration) ? e.currentTarget.duration : duration)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={() => setError(t("Không đọc được audio trong trình duyệt."))}/>
    <div className="audio-meta"><Volume2 size={15}/><span title={filename}>{filename}</span><small>{t("Audio gốc")}</small></div>
    <div className="transport">
      <button className="play-button" onClick={() => void toggle()} aria-label={playing ? t("Tạm dừng") : t("Phát audio")}>{playing ? <Pause size={19} fill="currentColor"/> : <Play size={19} fill="currentColor"/>}</button>
      <button className="icon-button restart" aria-label={t("Nghe lại từ đầu")} onClick={() => { if (audio.current) {
        audio.current.currentTime = 0;
        setTime(0);
    } }}><RotateCcw size={17}/></button>
      <span className="audio-time">{timeLabel(time)}</span>
      <input className="audio-range" type="range" min="0" max={length || 1} step="0.05" value={Math.min(time, length || 1)} aria-label={t("Vị trí phát audio")} onChange={e => { const next = Number(e.target.value); if (audio.current)
        audio.current.currentTime = next; setTime(next); }}/>
      <span className="audio-time muted">{timeLabel(length)}</span>
      <select className="playback-rate" aria-label={t("Tốc độ phát audio")} value={rate} onChange={e => { const next = Number(e.target.value); setRate(next); if (audio.current)
        audio.current.playbackRate = next; }}><option value="0.5">{t("0.5×")}</option><option value="0.75">{t("0.75×")}</option><option value="1">{t("1×")}</option><option value="1.25">{t("1.25×")}</option></select>
    </div>
    {error && <p className="inline-error" role="alert">{error}</p>}
  </section>;
}
