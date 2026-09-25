import { AudioLines, LoaderCircle } from 'lucide-react';
import { t } from './i18n';

export interface AudioAnalysis {
  tempo: number | null; key: string | null; meter: [number, number] | null;
  tempo_confidence: number; key_confidence: number; meter_confidence: number; analyzed_seconds: number;
  alternatives: {key:string; score:number}[];
}
export default function AudioAnalysisPanel({ result, busy, disabled, analyze }: { result: AudioAnalysis | null; busy: boolean; disabled: boolean; analyze: () => void }) {
  return <section id="audio-analysis" className="audio-analysis" aria-label={t('Dò thông số audio')}>
    <div><h2>{t('Dò thông số audio')}</h2><p>{t('Ước lượng tempo, giọng và nhịp trước khi phân tích bản nhạc.')}</p></div>
    <button className="button secondary compact" disabled={disabled} onClick={analyze}>{busy?<LoaderCircle size={16} className="spin"/>:<AudioLines size={16}/>} {busy?t('Đang dò audio…'):'Analyze Audio'}</button>
    {busy && <p role="status" className="field-help">{t('Đang xử lý trên máy, tối đa 120 giây đầu của bản thu…')}</p>}
    {result && <div className="audio-analysis-result"><dl><div><dt>Tempo</dt><dd>{result.tempo ? `${result.tempo} BPM` : t('Chưa xác định')}</dd></div><div><dt>{t('Giọng')}</dt><dd>{result.key || t('Chưa xác định')}</dd></div><div><dt>{t('Nhịp gợi ý')}</dt><dd>{result.meter?.join('/') || t('Chưa xác định')}</dd></div></dl><p>{t('Đây là ước lượng. Tempo có thể lệch nửa/gấp đôi; giọng trưởng/thứ tương đối và số chỉ nhịp cần nghe lại để xác nhận.')}</p><p>{t('Đã nghe {seconds} giây đầu.', {seconds:result.analyzed_seconds})} {t('Có thể chỉnh thông số ở phần Thiết lập âm nhạc.')}</p></div>}
  </section>;
}
