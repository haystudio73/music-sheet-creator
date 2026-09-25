import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { X, ChevronLeft, ChevronRight, Upload, AudioLines, Music2, MessageSquareText, CheckCircle2, Download } from 'lucide-react';
import { languages, setLanguage, t, type Language } from './i18n';
import './fonts.css';

export const lyricFonts = ['Noto Sans', 'Noto Serif', 'Roboto', 'Open Sans', 'Lora', 'Merriweather', 'Nunito', 'Source Sans 3', 'Source Serif 4', 'Birthstone'] as const;
export const lyricFontSizes = [12, 14, 16, 18, 20, 24, 28, 32, 38, 42] as const;
export const noteColors = ['#0066ff', '#e4002b', '#00874b', '#8b35d1'] as const;
export interface Settings {
  language: Language; autoAnalyze: boolean; autoScroll: boolean; activeColor: string; computeDevice: 'auto' | 'gpu' | 'cpu';
  lyricsFont: string; lyricsFontSize: number; instrumentVolume: number; metronome: boolean; metronomeVolume: number; guideSeen: boolean;
}
const defaults: Settings = { language: 'vi', computeDevice: 'auto', autoAnalyze: true, autoScroll: true, activeColor: '#0066ff', lyricsFont: 'Noto Sans', lyricsFontSize: 16, instrumentVolume: 100, metronome: false, metronomeVolume: 30, guideSeen: false };
const storageKey = 'studio_settings_v2';
function readSettings(): Settings {
  try {
    const s = JSON.parse(localStorage.getItem(storageKey) || '{}');
    const volume = (v: unknown, fallback: number, max: number) => typeof v === 'number' && Number.isFinite(v) ? Math.max(0, Math.min(max, v)) : fallback;
    const size = typeof s.lyricsFontSize === 'number' && (lyricFontSizes as readonly number[]).includes(s.lyricsFontSize) ? s.lyricsFontSize : defaults.lyricsFontSize;
    return {
      language: languages.some(l => l.id === s.language) ? s.language : defaults.language,
      computeDevice: ['auto', 'gpu', 'cpu'].includes(s.computeDevice) ? s.computeDevice : 'auto',
      autoAnalyze: typeof s.autoAnalyze === 'boolean' ? s.autoAnalyze : defaults.autoAnalyze,
      autoScroll: typeof s.autoScroll === 'boolean' ? s.autoScroll : defaults.autoScroll,
      activeColor: noteColors.includes(s.activeColor) ? s.activeColor : defaults.activeColor,
      lyricsFont: lyricFonts.includes(s.lyricsFont) ? s.lyricsFont : defaults.lyricsFont,
      lyricsFontSize: size,
      instrumentVolume: volume(s.instrumentVolume, 100, 100), metronomeVolume: volume(s.metronomeVolume, 30, 100),
      metronome: s.metronome === true, guideSeen: s.guideSeen === true
    };
  } catch { return defaults; }
}
const Context = createContext<{ settings: Settings; update: (patch: Partial<Settings>) => void }>({ settings: defaults, update: () => { } });
export const useSettings = () => useContext(Context);
export function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState(readSettings);
  setLanguage(settings.language);
  useEffect(() => {
    try { localStorage.setItem(storageKey, JSON.stringify(settings)); } catch { /* Session settings still work. */ }
    document.documentElement.style.setProperty('--active-note-color', settings.activeColor);
    document.documentElement.style.setProperty('--lyrics-font', `"${settings.lyricsFont}"`);
    document.documentElement.style.setProperty('--lyrics-font-size', `${settings.lyricsFontSize}px`);
    document.title = t('Bản nhạc — Local studio');
  }, [settings]);
  return <Context.Provider value={{ settings, update: patch => setSettings(previous => ({ ...previous, ...patch })) }}>{children}</Context.Provider>;
}

export function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const [dialog, setDialog] = useState<HTMLDialogElement | null>(null);
  useEffect(() => { dialog?.showModal(); return () => dialog?.close(); }, [dialog]);
  return <dialog ref={setDialog} className="studio-dialog" aria-label={title} onCancel={close} onClick={event => { if (event.target === event.currentTarget) close(); }}>
    <header><h2>{title}</h2><button className="icon-button" aria-label={t('Đóng')} onClick={close}><X size={20} /></button></header>{children}
  </dialog>;
}

export function SettingsPanel({ close }: { close: () => void }) {
  const { settings, update } = useSettings();
  return <Modal title={t('Cài đặt')} close={close}><div className="settings-fields">
    <label className="field">{t('Ngôn ngữ')}<select value={settings.language} onChange={e => update({ language: e.target.value as Language })}>{languages.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
    <label className="field">{t('Thiết bị xử lý')}<select value={settings.computeDevice} onChange={e => update({ computeDevice: e.target.value as Settings['computeDevice'] })}><option value="auto">{t('Tự động · GPU nếu có')}</option><option value="gpu">GPU · CUDA</option><option value="cpu">CPU only</option></select></label>
    <p className="field-help">{t('Áp dụng cho lần phân tích SheetSage2 tiếp theo. Dò audio và DSP luôn dùng CPU. GPU yêu cầu CUDA; CPU only không dùng GPU.')}</p>
    <label className="checkbox-field"><input type="checkbox" checked={settings.autoAnalyze} onChange={e => update({ autoAnalyze: e.target.checked })} />{t('Tự dò thông số audio sau khi upload')}</label>
    <p className="field-help">{t('Dò tempo, giọng và gợi ý nhịp. Bạn kiểm tra thông số rồi bấm Phân tích bản nhạc.')}</p>
    <label className="checkbox-field"><input type="checkbox" checked={settings.autoScroll} onChange={e => update({ autoScroll: e.target.checked })} />{t('Tự cuộn theo nốt khi nghe thử')}</label>
    <fieldset className="note-colors"><legend>{t('Màu nốt đang phát')}</legend>{noteColors.map((color, i) => <label key={color} style={{ color }}><input type="radio" name="note-color" value={color} checked={settings.activeColor === color} onChange={() => update({ activeColor: color })} /><i style={{ background: color }} />{[t('Xanh dương'), t('Đỏ'), t('Xanh lá'), t('Tím')][i]}</label>)}</fieldset>
    <div className="field-pair">
      <label className="field">{t('Font lời hát')}<select value={settings.lyricsFont} onChange={e => update({ lyricsFont: e.target.value })}>{lyricFonts.map(font => <option key={font}>{font}</option>)}</select></label>
      <label className="field">{t('Cỡ chữ lời hát')}<select value={settings.lyricsFontSize} onChange={e => update({ lyricsFontSize: Number(e.target.value) })}>{lyricFontSizes.map(size => <option key={size} value={size}>{size}px{size === 16 ? ` (${t('Mặc định')})` : ''}</option>)}</select></label>
    </div>
    <p className="lyric-font-sample" style={{ fontFamily: settings.lyricsFont, fontSize: `${settings.lyricsFontSize}px` }}>{t('Lời hát: Nắng lên bên đồi — Sing along')}</p>
    <p className="field-help">{t('Chỉ đổi font và cỡ chữ lời hát trên khuông nhạc và bảng lời. Các ký hiệu và chữ khác giữ nguyên.')}</p>
  </div></Modal>;
}

export const workflow = [
  { title: 'Upload audio', icon: Upload, description: 'Chọn WAV, MP3 hoặc FLAC từ máy, tối đa 200 MB / 10 phút.' },
  { title: 'Dò thông số audio', icon: AudioLines, description: 'Bấm Analyze Audio để ước lượng tempo, giọng và nhịp. Kiểm tra và chỉnh thông số trước bước tiếp theo.' },
  { title: 'Phân tích bản nhạc', icon: Music2, description: 'Chọn bộ phân tích và giai điệu nhạc cụ hoặc giọng hát, rồi tạo bản nháp nốt và hợp âm.' },
  { title: 'Thêm lời (tùy chọn)', icon: MessageSquareText, description: 'Nhập SRT / LRC, kiểm tra vị trí lời. Có thể xóa lời, nhập lại hoặc bỏ qua bước này.' },
  { title: 'Kiểm tra', icon: CheckCircle2, description: 'Nghe thử, tua, chỉnh âm lượng từ 0–100%, bật bộ đếm nhịp. Sửa nốt và lời, lưu rồi bấm Xác nhận đã kiểm tra.' },
  { title: 'Tải xuống', icon: Download, description: 'Sau khi xác nhận, tải MusicXML, MIDI, PDF hoặc ABC. Chỉnh sửa tiếp sẽ yêu cầu kiểm tra lại.' },
];
export function Guide({ close }: { close: () => void }) {
  const [step, setStep] = useState(0);
  const { update } = useSettings();
  const finish = () => { update({ guideSeen: true }); close(); };
  const Icon = workflow[step].icon;
  return <Modal title={t('Hướng dẫn sử dụng')} close={finish}><div className="guide-body">
    <span className="guide-index">{step + 1} / {workflow.length}</span><Icon size={36} />
    <h3>{t(workflow[step].title)}</h3><p>{t(workflow[step].description)}</p>
    <nav aria-label={t('Các bước hướng dẫn')}>{workflow.map((item, i) => <button key={item.title} className={i === step ? 'active' : ''} aria-label={t(item.title)} aria-current={i === step ? 'step' : undefined} onClick={() => setStep(i)}>{i + 1}</button>)}</nav>
    <footer><button className="button secondary" onClick={finish}>{t('Bỏ qua')}</button><div><button className="icon-button" disabled={!step} aria-label={t('Bước trước')} onClick={() => setStep(step - 1)}><ChevronLeft /></button><button className="button primary" onClick={() => step === workflow.length - 1 ? finish() : setStep(step + 1)}>{t(step === workflow.length - 1 ? 'Bắt đầu' : 'Tiếp theo')}<ChevronRight size={16} /></button></div></footer>
  </div></Modal>;
}
