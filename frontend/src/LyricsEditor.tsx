import { t } from './i18n';
import { useMemo, useRef, useState } from 'react';
import { ArrowLeft, ArrowRight, LoaderCircle, Plus, Trash2, Upload } from 'lucide-react';
import { pitchLabel } from './ScoreEditor';
import type { LyricToken, ScoreDocument } from './types';
const PAGE_SIZE = 30;
const sourceTime = (seconds: number | null) => seconds === null ? '—' : `${Math.floor(seconds / 60)}:${(seconds % 60).toFixed(2).padStart(5, '0')}`;
export default function LyricsEditor({ score, change, disabled, dirty, importing, upload, clear }: {
  score: ScoreDocument;
  change: (next: ScoreDocument) => void;
  disabled: boolean;
  dirty: boolean;
  importing: boolean;
  upload: (file: File, offset: number) => Promise<void>;
  clear: () => Promise<void>;
}) {
  const fileInput = useRef<HTMLInputElement>(null);
  const [offset, setOffset] = useState('0');
  const [unmatchedOnly, setUnmatchedOnly] = useState(false);
  const [page, setPage] = useState(0);
  const [selectedRow, setSelectedRow] = useState<number | null>(null);
  const lyrics = score.lyrics || [];
  const unmatchedCount = lyrics.filter(token => !token.note_id).length;
  const visible = lyrics.map((token, index) => ({ token, index })).filter(({ token }) => !unmatchedOnly || !token.note_id);
  const pageCount = Math.max(1, Math.ceil(visible.length / PAGE_SIZE));
  const currentPage = Math.min(page, pageCount - 1);
  const rows = visible.slice(currentPage * PAGE_SIZE, (currentPage + 1) * PAGE_SIZE);
  const validOffset = offset.trim() !== '' && Number.isFinite(Number(offset)) && Math.abs(Number(offset)) <= 600;
  const edit = (id: string, patch: Partial<LyricToken>) => change({ ...score, lyrics: lyrics.map(token => token.id === id ? { ...token, ...patch } : token) });
  const noteAssignments = useMemo(() => {
    const assignments = new Map<string, LyricToken>();
    for (const token of lyrics)
      if (token.note_id)
        assignments.set(`${token.verse}:${token.note_id}`, token);
    return assignments;
  }, [lyrics]);

  const addAtEnd = () => {
    const lastVerse = lyrics.length > 0 ? lyrics[lyrics.length - 1].verse : 1;
    const newToken: LyricToken = {
      id: crypto.randomUUID(),
      text: t("Lời"),
      note_id: null,
      verse: lastVerse,
      syllabic: 'single',
      source_start: null,
      source_end: null
    };
    change({ ...score, lyrics: [...lyrics, newToken] });
    const newTotal = (unmatchedOnly ? unmatchedCount : lyrics.length) + 1;
    setPage(Math.floor((newTotal - 1) / PAGE_SIZE));
    setSelectedRow(lyrics.length);
  };

  const insertAt = (index: number) => {
    const clampedIndex = Math.max(0, Math.min(lyrics.length, index));
    const currentToken = lyrics[clampedIndex] || lyrics[clampedIndex - 1];
    const newToken: LyricToken = {
      id: crypto.randomUUID(),
      text: t("Lời"),
      note_id: null,
      verse: currentToken ? currentToken.verse : 1,
      syllabic: 'single',
      source_start: null,
      source_end: null
    };
    const nextLyrics = [
      ...lyrics.slice(0, clampedIndex),
      newToken,
      ...lyrics.slice(clampedIndex)
    ];
    change({ ...score, lyrics: nextLyrics });
    setSelectedRow(clampedIndex);
  };

  const handleAssignNote = (tokenId: string, targetNoteId: string | null) => {
    if (!targetNoteId) {
      edit(tokenId, { note_id: null });
      return;
    }
    const token = lyrics.find(t => t.id === tokenId);
    if (!token) return;

    const noteIndexMap = new Map(score.notes.map((n, i) => [n.id, i]));
    const chosenIndex = noteIndexMap.get(targetNoteId);
    if (chosenIndex === undefined) return;

    const isOccupied = lyrics.some(
      other => other.id !== token.id && other.verse === token.verse && other.note_id === targetNoteId
    );

    if (!isOccupied) {
      edit(tokenId, { note_id: targetNoteId });
    } else {
      const nextLyrics = lyrics.map(other => {
        if (other.id === token.id) {
          return { ...other, note_id: targetNoteId };
        }
        if (other.verse === token.verse && other.note_id) {
          const otherIdx = noteIndexMap.get(other.note_id);
          if (otherIdx !== undefined && otherIdx >= chosenIndex) {
            const nextNote = score.notes[otherIdx + 1];
            return { ...other, note_id: nextNote ? nextNote.id : null };
          }
        }
        return other;
      });
      change({ ...score, lyrics: nextLyrics });
    }
  };

  return <section className="editor-panel lyrics-panel">
    <div className="editor-intro"><div><h2>{t("Lời hát trên khuông nhạc")}</h2><p>{t("Nhập SRT hoặc LRC để ghép lời theo mốc thời gian. Vị trí ghép chỉ là ước lượng; hãy nghe và chỉnh từng từ vào đúng nốt.")}</p></div></div>
    <div className="lyrics-import">
      <div className="lyrics-import-controls"><label className="field">{t("Dịch mốc thời gian (giây)")}<input type="number" step="0.1" min="-600" max="600" value={offset} disabled={disabled || dirty} onChange={event => setOffset(event.target.value)} /></label><button className="button secondary compact" disabled={disabled || dirty || !validOffset} onClick={() => fileInput.current?.click()}>{importing ? <LoaderCircle size={15} className="spin" /> : <Upload size={15} />}{importing ? t("Đang nhập lời…") : score.lyric_source ? t("Thay tệp lời hát") : t("Nhập SRT / LRC")}</button><button className="button secondary compact" disabled={disabled || dirty || (!lyrics.length && !score.lyric_source)} onClick={() => {
        setOffset('0'); setPage(0); setUnmatchedOnly(false); if (fileInput.current)
          fileInput.current.value = ''; void clear();
      }}><Trash2 size={15} />{t("Xóa / reset lời")}</button><button className="button secondary compact" disabled={disabled} onClick={() => setOffset('0')}>{t("Reset độ dịch")}</button></div>
      <input ref={fileInput} type="file" accept=".srt,.lrc" className="sr-only" aria-label={t("Chọn tệp lời hát SRT hoặc LRC")} disabled={disabled || dirty || !validOffset} onChange={event => {
        const file = event.target.files?.[0]; event.target.value = ''; if (file) {
          setPage(0);
          void upload(file, Number(offset));
        }
      }} />
      <p className="field-help">{t("Tối đa 1 MB · UTF-8. Số dương làm lời xuất hiện muộn hơn. Nhập tệp sẽ thay lớp lời hiện tại và lưu một phiên bản mới.")}</p>
      {dirty && <p className="lyrics-warning">{t("Lưu thay đổi trước khi nhập tệp lời hát.")}</p>}
      {score.lyric_source && <p className="lyrics-source"><strong>{score.lyric_source.filename}</strong><span>{score.lyric_source.format.toUpperCase()} · {score.lyric_source.cue_count}{t(" đoạn · Dịch ")}{score.lyric_source.offset_seconds > 0 ? '+' : ''}{score.lyric_source.offset_seconds}{t(" giây")}</span></p>}
    </div>
    <div className="lyrics-summary">
      <div><strong>{lyrics.length}{t(" từ / âm tiết")}</strong><span>{unmatchedCount}{t(" chưa gắn nốt")}</span><span className="lyrics-note-legend"><span className="legend-chip assigned"><i /> {t("Nốt đã gán (xanh da trời)")}</span><span className="legend-chip unassigned"><i /> {t("Nốt chưa gán (đen)")}</span></span></div>
      <div className="lyrics-summary-actions">
        <button
          className="button secondary compact"
          disabled={disabled}
          title={t("Chèn một từ mới vào trước vị trí đang chọn hoặc đầu trang")}
          onClick={() => {
            const targetIndex = selectedRow !== null ? selectedRow : (currentPage * PAGE_SIZE);
            insertAt(targetIndex);
          }}
        >
          <Plus size={15} />{selectedRow !== null ? t("Chèn (vị trí #{0})", { "0": selectedRow + 1 }) : t("Chèn lời")}
        </button>
        <button className="button secondary compact" disabled={disabled} onClick={addAtEnd}>
          <Plus size={15} />{t("Thêm mới (cuối)")}
        </button>
      </div>
    </div>
    {lyrics.length > 0 && <><label className="checkbox-field lyrics-filter"><input type="checkbox" checked={unmatchedOnly} onChange={event => { setUnmatchedOnly(event.target.checked); setPage(0); }} />{t("Chỉ hiện lời chưa gắn nốt")}</label><p className="field-help lyrics-help">{t("Mỗi nốt nhận một từ ở mỗi khổ. Ghép nhiều từ trong một ô nếu cần. “Đầu / Giữa / Cuối” nối các âm tiết của cùng một từ; “Đơn” dùng cho từ riêng.")}</p></>}
    <div className="table-scroll"><table className="score-table lyrics-table"><caption className="sr-only">{t("Lời hát và nốt được gắn")}</caption><thead><tr><th>#</th><th>{t("Lời")}</th><th>{t("Nốt giai điệu")}</th><th>{t("Khổ")}</th><th>{t("Âm tiết")}</th><th>{t("Mốc nguồn")}</th><th><span className="sr-only">{t("Hành động")}</span></th></tr></thead><tbody>{rows.map(({ token, index }) => <tr key={token.id} className={[!token.note_id ? 'lyric-unmatched' : '', selectedRow === index ? 'lyric-selected' : ''].filter(Boolean).join(' ')} onClick={() => setSelectedRow(index)}><td className="row-index">{index + 1}</td><td><input className="lyric-word" aria-label={t("Lời {0}", { "0": index + 1 })} maxLength={200} value={token.text} disabled={disabled} onFocus={() => setSelectedRow(index)} onChange={event => edit(token.id, { text: event.target.value })} /></td><td><select className={`lyric-note-select ${token.note_id ? 'is-assigned' : 'is-unassigned'}`} style={{ color: token.note_id ? 'var(--assigned-note-color, #0284c7)' : 'var(--unassigned-note-color, #000000)', fontWeight: token.note_id ? 600 : 400 }} aria-label={t("Nốt cho lời {0}", { "0": index + 1 })} value={token.note_id || ''} disabled={disabled} onFocus={() => setSelectedRow(index)} onChange={event => handleAssignNote(token.id, event.target.value || null)}><option value="" className="note-option-unassigned" style={{ color: 'var(--unassigned-note-color, #000000)' }}>{t("Chưa gắn nốt")}</option>{score.notes.map((note, noteIndex) => { const assigned = noteAssignments.get(`${token.verse}:${note.id}`); const isAssigned = Boolean(assigned); const isOther = assigned && assigned.id !== token.id; return <option key={note.id} value={note.id} className={isAssigned ? 'note-option-assigned' : 'note-option-unassigned'} style={{ color: isAssigned ? 'var(--assigned-note-color, #0284c7)' : 'var(--unassigned-note-color, #000000)', fontWeight: isAssigned ? 600 : 400 }}>{isAssigned ? '● ' : '○ '}#{noteIndex + 1} · {pitchLabel(note.pitch)}{t(" · phách ")}{note.start}{isOther ? ` (${t("đang gắn")}: "${assigned.text}")` : (assigned ? ` (${t("đang chọn")})` : '')}</option>; })}</select></td><td><input type="number" min="1" max="20" aria-label={t("Khổ lời {0}", { "0": index + 1 })} value={token.verse} disabled={disabled} onFocus={() => setSelectedRow(index)} onChange={event => { const verse = Math.max(1, Math.min(20, Math.trunc(Number(event.target.value)) || 1)); edit(token.id, { verse }); }} /></td><td><select aria-label={t("Âm tiết lời {0}", { "0": index + 1 })} value={token.syllabic} disabled={disabled} onFocus={() => setSelectedRow(index)} onChange={event => edit(token.id, { syllabic: event.target.value as LyricToken['syllabic'] })}><option value="single">{t("Đơn")}</option><option value="begin">{t("Đầu")}</option><option value="middle">{t("Giữa")}</option><option value="end">{t("Cuối")}</option></select></td><td className="lyric-time">{sourceTime(token.source_start)}</td><td><div className="row-actions"><button className="icon-button" title={t("Chèn lời tại vị trí {0}", { "0": index + 1 })} aria-label={t("Chèn lời tại vị trí {0}", { "0": index + 1 })} disabled={disabled} onClick={(e) => { e.stopPropagation(); insertAt(index); }}><Plus size={15} /></button><button className="icon-button" title={t("Xóa")} aria-label={t("Xóa lời {0}", { "0": index + 1 })} disabled={disabled} onClick={(e) => { e.stopPropagation(); change({ ...score, lyrics: lyrics.filter(other => other.id !== token.id) }); }}><Trash2 size={15} /></button></div></td></tr>)}</tbody></table></div>
    {visible.length === 0 && <p className="table-empty">{lyrics.length ? t("Mọi lời hát đã được gắn nốt. Bạn vẫn cần kiểm tra vị trí bằng tai.") : t("Chưa có lời hát. Nhập tệp SRT / LRC hoặc thêm lời thủ công; lời đã gắn nốt sẽ xuất hiện trên khuông nhạc, MusicXML và PDF sau khi lưu.")}</p>}
    {pageCount > 1 && <nav className="lyrics-pagination" aria-label={t("Trang lời hát")}><span>{currentPage * PAGE_SIZE + 1}–{Math.min((currentPage + 1) * PAGE_SIZE, visible.length)} / {visible.length}</span><div><button className="icon-button" disabled={currentPage === 0} aria-label={t("Trang lời trước")} onClick={() => setPage(currentPage - 1)}><ArrowLeft size={15} /></button><span>{currentPage + 1} / {pageCount}</span><button className="icon-button" disabled={currentPage === pageCount - 1} aria-label={t("Trang lời sau")} onClick={() => setPage(currentPage + 1)}><ArrowRight size={15} /></button></div></nav>}
    {unmatchedCount > 0 && <p className="lyrics-warning">{t("Lời chưa gắn nốt vẫn được giữ trong dự án nhưng chưa xuất hiện trên khuông nhạc hoặc file xuất.")}</p>}
  </section>;
}
