import { t } from './i18n';
import { useEffect, useMemo, useRef, useState } from 'react';
import {
    CheckCircle2, ChevronLeft, ChevronRight, FileMusic, LoaderCircle,
    MessageSquareText, Minus, Pencil, Plus, Trash2, TriangleAlert, X
} from 'lucide-react';
import { useSettings } from './Settings';
import type { LyricToken, ScoreDocument } from './types';
import { errorMessage, getApiUrl, getClientSession } from './api';
import type { VexFlowGraphicalNote } from 'opensheetmusicdisplay';
import { pitchLabel } from './ScoreEditor';
import { validateQuickNote, type NoteEditValidation } from './noteEditValidation';

interface TimedNote {
    start: number;
    end: number;
    element: SVGGElement;
    noteId?: string;
}

interface QuickEditorPosition {
    top: number;
    left: number;
    width: number;
    placement: 'below' | 'above';
}

const parseFraction = (value: string) => {
    const [a, b = '1'] = value.split('/');
    const res = Number(a) / Number(b);
    return Number.isFinite(res) ? res : 0;
};

const PITCH_CHOICES = Array.from({ length: 49 }, (_, i) => i + 36);

export default function ScorePreview({
    projectId,
    revision,
    score,
    playbackBeat = null,
    changeScore,
    disabled = false,
}: {
    projectId: string;
    revision: number;
    score: ScoreDocument;
    playbackBeat?: number | null;
    changeScore?: (next: ScoreDocument) => void;
    disabled?: boolean;
}) {
    const target = useRef<HTMLDivElement>(null);
    const notes = useRef<TimedNote[]>([]);
    const highlighted = useRef<Set<SVGGElement>>(new Set());
    const beat = useRef(playbackBeat);
    beat.current = playbackBeat;
    const { settings, update: updateSettings } = useSettings();
    const following = settings.autoScroll;
    const follow = useRef(following);
    follow.current = following;

    const [selectedNoteId, setSelectedNoteId] = useState<string | null>(null);
    const selectedNoteIdRef = useRef<string | null>(null);
    selectedNoteIdRef.current = selectedNoteId;
    const [lyricText, setLyricText] = useState('');
    const lyricInputRef = useRef<HTMLInputElement>(null);
    const editorRef = useRef<HTMLDivElement>(null);
    const [editorPosition, setEditorPosition] = useState<QuickEditorPosition | null>(null);
    const noteElementsMap = useRef<Map<string, SVGGElement>>(new Map());
    const disabledRef = useRef(disabled);
    const changeScoreRef = useRef(changeScore);
    disabledRef.current = disabled;
    changeScoreRef.current = changeScore;

    const selectedNote = useMemo(() => score.notes.find(n => n.id === selectedNoteId), [score.notes, selectedNoteId]);
    const selectedNoteIndex = useMemo(() => score.notes.findIndex(n => n.id === selectedNoteId), [score.notes, selectedNoteId]);
    const selectedValidation = useMemo(
        () => selectedNote ? validateQuickNote(score, selectedNote) : null,
        [score, selectedNote]
    );
    const [editValidation, setEditValidation] = useState<NoteEditValidation | null>(null);

    const positionQuickEditor = () => {
        const noteId = selectedNoteIdRef.current;
        const anchor = noteId ? noteElementsMap.current.get(noteId) : null;
        const editor = editorRef.current;
        if (!anchor?.isConnected || !editor)
            return;

        const edge = 12;
        const gap = 10;
        const anchorRect = anchor.getBoundingClientRect();
        const scoreRect = target.current?.getBoundingClientRect();
        const availableLeft = Math.max(edge, scoreRect?.left ?? edge);
        const availableRight = Math.min(window.innerWidth - edge, scoreRect?.right ?? window.innerWidth - edge);
        const width = Math.min(960, Math.max(0, availableRight - availableLeft));
        const height = editor.offsetHeight;
        const below = anchorRect.bottom + gap;
        const above = anchorRect.top - height - gap;
        const canFitBelow = below + height <= window.innerHeight - edge;
        const canFitAbove = above >= edge;
        const placement: QuickEditorPosition['placement'] = canFitBelow || !canFitAbove ? 'below' : 'above';
        const preferredTop = placement === 'below' ? below : above;
        const top = Math.max(edge, Math.min(preferredTop, window.innerHeight - height - edge));
        const centeredLeft = anchorRect.left + anchorRect.width / 2 - width / 2;
        const left = Math.max(availableLeft, Math.min(centeredLeft, availableRight - width));
        const next = { top, left, width, placement };
        setEditorPosition(current => current
            && Math.abs(current.top - next.top) < 0.5
            && Math.abs(current.left - next.left) < 0.5
            && Math.abs(current.width - next.width) < 0.5
            && current.placement === next.placement
            ? current : next);
    };
    const positionQuickEditorRef = useRef(positionQuickEditor);
    positionQuickEditorRef.current = positionQuickEditor;

    const updateHighlight = () => {
        const next = new Set(notes.current.filter(note => beat.current !== null && note.start <= beat.current && beat.current < note.end).map(note => note.element));
        for (const element of highlighted.current)
            if (!next.has(element))
                element.classList.remove('playback-active-note');
        for (const element of next) {
            if (highlighted.current.has(element))
                continue;
            element.classList.add('playback-active-note');
            if (follow.current && !document.querySelector('.score-player-seek:active')) {
                const rect = element.getBoundingClientRect();
                if (rect.top < 24 || rect.bottom > window.innerHeight - 32 || rect.left < 0 || rect.right > window.innerWidth) {
                    element.scrollIntoView({ block: 'center', inline: 'nearest', behavior: 'instant' });
                }
            }
        }
        highlighted.current = next;
    };
    const update = useRef(updateHighlight);
    update.current = updateHighlight;
    useEffect(() => { update.current(); }, [playbackBeat, following]);

    const [busy, setBusy] = useState(true);
    const [error, setError] = useState('');

    const updatePitch = (delta: number) => {
        if (!changeScore || !selectedNote) return;
        const newPitch = Math.max(21, Math.min(108, selectedNote.pitch + delta));
        const candidate = { ...selectedNote, pitch: newPitch };
        const validation = validateQuickNote(score, candidate);
        setEditValidation(validation);
        if (!validation.valid) return;
        changeScore({
            ...score,
            notes: score.notes.map(n => n.id === selectedNote.id ? candidate : n)
        });
    };

    const updatePitchExact = (newPitch: number) => {
        if (!changeScore || !selectedNote) return;
        const candidate = { ...selectedNote, pitch: newPitch };
        const validation = validateQuickNote(score, candidate);
        setEditValidation(validation);
        if (!validation.valid) return;
        changeScore({
            ...score,
            notes: score.notes.map(n => n.id === selectedNote.id ? candidate : n)
        });
    };

    const setPitchClass = (letter: string) => {
        if (!changeScore || !selectedNote) return;
        const currentOctave = Math.floor(selectedNote.pitch / 12) - 1;
        const stepOffsets: Record<string, number> = { C: 0, D: 2, E: 4, F: 5, G: 7, A: 9, B: 11 };
        const offset = stepOffsets[letter.toUpperCase()];
        if (offset !== undefined) {
            const newPitch = (currentOctave + 1) * 12 + offset;
            updatePitchExact(newPitch);
        }
    };

    const updateDuration = (dur: string) => {
        if (!changeScore || !selectedNote) return;
        const candidate = { ...selectedNote, duration: dur };
        const validation = validateQuickNote(score, candidate);
        setEditValidation(validation);
        if (!validation.valid) return;
        changeScore({
            ...score,
            notes: score.notes.map(n => n.id === selectedNote.id ? candidate : n)
        });
    };

    const toggleDottedDuration = () => {
        if (!changeScore || !selectedNote) return;
        const map: Record<string, string> = {
            '4': '6', '6': '4',
            '2': '3', '3': '2',
            '1': '3/2', '3/2': '1',
            '1/2': '3/4', '3/4': '1/2',
            '1/4': '3/8', '3/8': '1/4',
        };
        const nextDur = map[selectedNote.duration] || selectedNote.duration;
        updateDuration(nextDur);
    };

    const saveLyric = (noteId: string, text: string) => {
        if (!changeScore) return;
        const trimmed = text.trim();
        const currentLyrics = score.lyrics || [];
        const existingIndex = currentLyrics.findIndex(l => l.note_id === noteId);

        let nextLyrics: LyricToken[];
        if (!trimmed) {
            if (existingIndex >= 0) {
                nextLyrics = currentLyrics.filter((_, i) => i !== existingIndex);
            } else {
                return;
            }
        } else if (existingIndex >= 0) {
            nextLyrics = currentLyrics.map((l, i) => i === existingIndex ? { ...l, text: trimmed } : l);
        } else {
            const targetNote = score.notes.find(n => n.id === noteId);
            const newToken: LyricToken = {
                id: crypto.randomUUID(),
                text: trimmed,
                note_id: noteId,
                verse: 1,
                syllabic: 'single',
                source_start: targetNote?.source_start ?? null,
                source_end: targetNote?.source_end ?? null,
            };
            nextLyrics = [...currentLyrics, newToken];
        }
        changeScore({ ...score, lyrics: nextLyrics });
    };

    const deleteNote = (noteId: string) => {
        if (!changeScore) return;
        const nextNotes = score.notes.filter(n => n.id !== noteId);
        const nextLyrics = (score.lyrics || []).map(l => l.note_id === noteId ? { ...l, note_id: null } : l);
        setSelectedNoteId(null);
        changeScore({ ...score, notes: nextNotes, lyrics: nextLyrics });
    };

    const selectPrevNote = () => {
        if (!selectedNoteId) return;
        const idx = score.notes.findIndex(n => n.id === selectedNoteId);
        if (idx > 0) {
            const prevId = score.notes[idx - 1].id;
            setSelectedNoteId(prevId);
            const el = noteElementsMap.current.get(prevId);
            el?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
        }
    };

    const selectNextNote = () => {
        if (!selectedNoteId) return;
        const idx = score.notes.findIndex(n => n.id === selectedNoteId);
        if (idx >= 0 && idx < score.notes.length - 1) {
            const nextId = score.notes[idx + 1].id;
            setSelectedNoteId(nextId);
            const el = noteElementsMap.current.get(nextId);
            el?.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' });
        }
    };

    useEffect(() => {
        if (selectedNoteId) {
            const cur = (score.lyrics || []).find(l => l.note_id === selectedNoteId);
            setLyricText(cur?.text || '');
        }
    }, [selectedNoteId, score.lyrics]);

    useEffect(() => {
        setEditValidation(selectedValidation);
    }, [selectedNoteId, selectedValidation]);

    useEffect(() => {
        selectedNoteIdRef.current = selectedNoteId;
        for (const [id, el] of noteElementsMap.current.entries()) {
            if (id === selectedNoteId) {
                el.classList.add('selected-edit-note');
            } else {
                el.classList.remove('selected-edit-note');
            }
        }
    }, [selectedNoteId]);

    useEffect(() => {
        if (!selectedNoteId) {
            setEditorPosition(null);
            return;
        }
        setEditorPosition(null);
        let frame = 0;
        const schedulePosition = () => {
            window.cancelAnimationFrame(frame);
            frame = window.requestAnimationFrame(() => positionQuickEditorRef.current());
        };
        schedulePosition();
        window.addEventListener('resize', schedulePosition);
        document.addEventListener('scroll', schedulePosition, true);
        const observer = new ResizeObserver(schedulePosition);
        if (editorRef.current)
            observer.observe(editorRef.current);
        const anchor = noteElementsMap.current.get(selectedNoteId);
        if (anchor)
            observer.observe(anchor);
        return () => {
            window.cancelAnimationFrame(frame);
            window.removeEventListener('resize', schedulePosition);
            document.removeEventListener('scroll', schedulePosition, true);
            observer.disconnect();
        };
    }, [selectedNoteId]);

    useEffect(() => {
        if (!selectedNoteId) return;
        const closeOnOutsidePointer = (event: PointerEvent) => {
            const element = event.target instanceof Element ? event.target : null;
            if (!element || element.closest('.in-place-note-editor, .studio-interactive-note, .studio-interactive-lyric'))
                return;
            setSelectedNoteId(null);
        };
        // Capture pointerdown before an input blur can re-render the score. This makes
        // one outside click reliably close the editor, including after editing lyrics.
        document.addEventListener('pointerdown', closeOnOutsidePointer, true);
        return () => document.removeEventListener('pointerdown', closeOnOutsidePointer, true);
    }, [selectedNoteId]);

    useEffect(() => {
        const container = target.current;
        if (!container) return;
        const openEditor = (event: MouseEvent) => {
            const element = event.target instanceof Element ? event.target : null;
            const interactive = element?.closest('[data-note-id]') as HTMLElement | null;
            const noteId = interactive?.dataset.noteId;
            if (!noteId || disabledRef.current || !changeScoreRef.current)
                return;
            event.stopPropagation();
            setSelectedNoteId(noteId);
            if (interactive.classList.contains('studio-interactive-lyric'))
                setTimeout(() => lyricInputRef.current?.focus(), 60);
        };
        // Delegate from the stable container so every pitched note remains editable
        // even when OSMD replaces its SVG and when the score has no lyric nodes.
        container.addEventListener('click', openEditor);
        return () => container.removeEventListener('click', openEditor);
    }, []);

    useEffect(() => {
        if (!selectedNoteId || disabled || !changeScore) return;
        const onKeyDown = (e: KeyboardEvent) => {
            const tag = (e.target as HTMLElement).tagName;
            if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') {
                return;
            }
            if (e.key === 'ArrowUp') {
                e.preventDefault();
                updatePitch(e.shiftKey ? 12 : 1);
            } else if (e.key === 'ArrowDown') {
                e.preventDefault();
                updatePitch(e.shiftKey ? -12 : -1);
            } else if (e.key === 'ArrowLeft') {
                e.preventDefault();
                selectPrevNote();
            } else if (e.key === 'ArrowRight') {
                e.preventDefault();
                selectNextNote();
            } else if (e.key === 'Delete' || e.key === 'Backspace') {
                e.preventDefault();
                deleteNote(selectedNoteId);
            } else if (e.key === 'Escape') {
                e.preventDefault();
                setSelectedNoteId(null);
            } else if (['c', 'd', 'e', 'f', 'g', 'a', 'b'].includes(e.key.toLowerCase())) {
                e.preventDefault();
                setPitchClass(e.key.toUpperCase());
            } else if (e.key === '1') {
                e.preventDefault();
                updateDuration('4');
            } else if (e.key === '2') {
                e.preventDefault();
                updateDuration('2');
            } else if (e.key === '4') {
                e.preventDefault();
                updateDuration('1');
            } else if (e.key === '8') {
                e.preventDefault();
                updateDuration('1/2');
            } else if (e.key === '6') {
                e.preventDefault();
                updateDuration('1/4');
            } else if (e.key === 'Enter') {
                e.preventDefault();
                lyricInputRef.current?.focus();
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [selectedNoteId, disabled, changeScore, score]);

    useEffect(() => {
        let cancelled = false;
        const controller = new AbortController();
        let clear: (() => void) | undefined;
        setBusy(true);
        setError('');
        notes.current = [];
        highlighted.current.clear();
        noteElementsMap.current.clear();

        const render = async () => {
            try {
                const [{ OpenSheetMusicDisplay }, response] = await Promise.all([
                    import('opensheetmusicdisplay'),
                    fetch(getApiUrl(`/projects/${projectId}/preview-draft`), {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: {
                            'Content-Type': 'application/json',
                            ...(getClientSession() ? { 'X-Client-Session': getClientSession() } : {})
                        },
                        body: JSON.stringify(score),
                        signal: controller.signal
                    }),
                    document.fonts.load(`${settings.lyricsFontSize || 16}px "${settings.lyricsFont}"`).catch(() => null),
                ]);
                if (!response.ok) {
                    const problem = await response.json().catch(() => null);
                    throw new Error(problem?.detail || t("Không tải được khuông nhạc để kiểm tra."));
                }
                const xml = await response.text();
                if (cancelled || !target.current)
                    return;
                const mount = document.createElement('div');
                target.current.replaceChildren(mount);
                const osmd = new OpenSheetMusicDisplay(mount, {
                    autoResize: false,
                    backend: 'svg',
                    drawTitle: false,
                    drawSubtitle: false,
                    drawComposer: false,
                    drawingParameters: 'default'
                });
                clear = () => { osmd.clear(); mount.remove(); };
                await osmd.load(xml);
                if (cancelled) {
                    osmd.clear();
                    return;
                }
                osmd.Zoom = 0.95;
                const renderNotes = () => {
                    osmd.render();
                    notes.current = [];
                    highlighted.current.clear();
                    noteElementsMap.current.clear();
                    const orderedScoreNotes = [...score.notes].sort((left, right) => parseFraction(left.start) - parseFraction(right.start));

                    for (const measures of osmd.GraphicSheet?.MeasureList || []) {
                        if (!measures) continue;
                        for (const measure of measures) {
                            if (!measure || !measure.staffEntries) continue;
                            for (const entry of measure.staffEntries || []) {
                                const start = entry.getAbsoluteTimestamp().RealValue * 4;
                                const exact = orderedScoreNotes.find(n => {
                                    const nStart = parseFraction(n.start);
                                    return Math.abs(nStart - start) < 0.06;
                                });
                                const containing = orderedScoreNotes.find(n => {
                                    const nStart = parseFraction(n.start);
                                    const nDur = parseFraction(n.duration);
                                    return start >= nStart - 0.04 && start < nStart + nDur - 0.04;
                                });
                                // Exact attacks win over a previous tied segment. The containing
                                // fallback keeps every split/tied glyph mapped to its source note.
                                const matched = exact || containing;

                                for (const voice of entry?.graphicalVoiceEntries || []) {
                                    for (const note of voice?.notes || []) {
                                        if (note.sourceNote?.isRest?.())
                                            continue;
                                        const element = (note as VexFlowGraphicalNote).getSVGGElement();
                                        if (!element)
                                            continue;
                                        const durationVal = note.graphicalNoteLength.RealValue * 4;
                                        const end = start + durationVal;
                                        element.dataset.playbackStart = String(start);
                                        element.dataset.playbackEnd = String(end);

                                        if (matched) {
                                            element.dataset.noteId = matched.id;
                                            element.classList.add('studio-interactive-note');
                                            noteElementsMap.current.set(matched.id, element);
                                            if (matched.id === selectedNoteIdRef.current) {
                                                element.classList.add('selected-edit-note');
                                            }
                                        }

                                        notes.current.push({ start, end, element, noteId: matched?.id });
                                    }
                                }

                                for (const lyric of entry.LyricsEntries || []) {
                                    const node = lyric.GraphicalLabel.SVGNode;
                                    if (node instanceof SVGElement) {
                                        node.classList.add('studio-lyric');
                                        node.style.fontFamily = `"${settings.lyricsFont}"`;
                                        node.style.fontSize = `${settings.lyricsFontSize || 16}px`;
                                        node.querySelectorAll('text').forEach(text => {
                                            text.style.fontFamily = `"${settings.lyricsFont}"`;
                                            text.style.fontSize = `${settings.lyricsFontSize || 16}px`;
                                        });
                                        if (matched) {
                                            node.dataset.noteId = matched.id;
                                            node.classList.add('studio-interactive-lyric');
                                        }
                                    }
                                }
                            }
                        }
                    }

                    mount.onclick = (e) => {
                        if ((e.target as Element).closest?.('.studio-interactive-note, .studio-interactive-lyric')) return;
                        setSelectedNoteId(null);
                    };

                    update.current();
                    window.requestAnimationFrame(() => positionQuickEditorRef.current());
                };
                renderNotes();
                setBusy(false);
                let lastWidth = target.current.clientWidth;
                const observer = new ResizeObserver(entries => {
                    const width = Math.round(entries[0].contentRect.width);
                    if (!cancelled && width > 0 && Math.abs(width - lastWidth) > 8) {
                        lastWidth = width;
                        renderNotes();
                    }
                });
                observer.observe(target.current);
                clear = () => { observer.disconnect(); osmd.clear(); mount.remove(); };
            }
            catch (err) {
                if (!cancelled) {
                    if (err instanceof DOMException && err.name === 'AbortError') return;
                    setError(errorMessage(err));
                    setBusy(false);
                }
            }
        };
        const debounce = window.setTimeout(() => void render(), 180);
        return () => { cancelled = true; controller.abort(); window.clearTimeout(debounce); notes.current = []; highlighted.current.clear(); clear?.(); };
    }, [projectId, revision, score, settings.lyricsFont, settings.lyricsFontSize]);

    return <div className="score-preview">
        <div className="playback-note-legend">
            <span><i />{t("Nốt đang phát")}</span>
            {changeScore && <span className="in-place-edit-badge"><Pencil size={12} />{t("Nhấn vào nốt hoặc lời để sửa trực tiếp")}</span>}
            <label><input type="checkbox" checked={following} onChange={event => updateSettings({ autoScroll: event.target.checked })} />{t("Tự cuộn theo nốt")}</label>
        </div>
        {busy && <div className="preview-status" role="status"><LoaderCircle className="spin" size={20} />{t(" Đang dàn khuông nhạc…")}</div>}
        {error && <div className="preview-status error-text" role="alert"><FileMusic size={20} /><span>{error}</span></div>}
        <div ref={target} aria-label={t("Khuông nhạc, phiên bản {0}", { "0": revision })} className={busy ? 'notation-container is-loading' : 'notation-container'} />

        {changeScore && selectedNote && (
            <div
                ref={editorRef}
                className="in-place-note-editor"
                data-placement={editorPosition?.placement || 'below'}
                role="region"
                aria-label={t("Chỉnh sửa nốt trực tiếp")}
                style={editorPosition ? {
                    top: `${editorPosition.top}px`,
                    left: `${editorPosition.left}px`,
                    width: `${editorPosition.width}px`,
                    visibility: 'visible',
                } : { visibility: 'hidden' }}
            >
                <div className="in-place-editor-row">
                    <div className="in-place-note-badge">
                        <span>#{String((selectedNoteIndex >= 0 ? selectedNoteIndex : 0) + 1).padStart(2, '0')}</span>
                        <strong>{pitchLabel(selectedNote.pitch)}</strong>
                    </div>

                    <div className="in-place-pitch-group" title={t("Chỉnh cao độ")}>
                        <button
                            type="button"
                            className="button secondary compact"
                            disabled={disabled}
                            title={t("Giảm nửa cung (↓)")}
                            onClick={() => updatePitch(-1)}
                        >
                            <Minus size={13} />
                        </button>
                        <button
                            type="button"
                            className="button secondary compact"
                            disabled={disabled}
                            title={t("Tăng nửa cung (↑)")}
                            onClick={() => updatePitch(1)}
                        >
                            <Plus size={13} />
                        </button>
                        <select
                            className="in-place-pitch-select"
                            disabled={disabled}
                            value={selectedNote.pitch}
                            onChange={e => updatePitchExact(Number(e.target.value))}
                        >
                            {PITCH_CHOICES.map(p => (
                                <option key={p} value={p}>
                                    {pitchLabel(p)} ({p})
                                </option>
                            ))}
                        </select>
                    </div>

                    <div className="in-place-duration-group" title={t("Trường độ")}>
                        {[
                            { dur: '4', label: '𝅝', title: t("Tròn (4)") },
                            { dur: '2', label: '𝅗𝅥', title: t("Trắng (2)") },
                            { dur: '1', label: '𝅘𝅥', title: t("Đen (1)") },
                            { dur: '1/2', label: '𝅘𝅥𝅮', title: t("Móc đơn (1/2)") },
                            { dur: '1/4', label: '𝅘𝅥𝅯', title: t("Móc kép (1/4)") },
                        ].map(item => (
                            <button
                                key={item.dur}
                                type="button"
                                className={`button secondary compact in-place-dur-btn ${selectedNote.duration === item.dur ? 'active' : ''}`}
                                disabled={disabled}
                                title={item.title}
                                onClick={() => updateDuration(item.dur)}
                            >
                                {item.label}
                            </button>
                        ))}
                        <button
                            type="button"
                            className={`button secondary compact in-place-dur-btn ${['6', '3', '3/2', '3/4', '3/8'].includes(selectedNote.duration) ? 'active' : ''}`}
                            disabled={disabled}
                            title={t("Chấm dôi (.)")}
                            onClick={toggleDottedDuration}
                        >
                            •
                        </button>
                    </div>

                    <div className="in-place-lyric-box" title={t("Sửa lời bài hát")}>
                        <MessageSquareText size={15} className="muted" />
                        <input
                            ref={lyricInputRef}
                            type="text"
                            className="in-place-lyric-input"
                            placeholder={t("Gõ lời bài hát (Enter: nốt kế)…")}
                            value={lyricText}
                            disabled={disabled}
                            onChange={e => setLyricText(e.target.value)}
                            onBlur={() => saveLyric(selectedNote.id, lyricText)}
                            onKeyDown={e => {
                                if (e.key === 'Enter' || e.key === 'Tab') {
                                    e.preventDefault();
                                    saveLyric(selectedNote.id, lyricText);
                                    selectNextNote();
                                    setTimeout(() => lyricInputRef.current?.focus(), 60);
                                }
                            }}
                        />
                    </div>

                    <div className="in-place-actions">
                        <button
                            type="button"
                            className="icon-button"
                            disabled={disabled || selectedNoteIndex <= 0}
                            title={t("Nốt trước (←)")}
                            onClick={selectPrevNote}
                        >
                            <ChevronLeft size={16} />
                        </button>
                        <button
                            type="button"
                            className="icon-button"
                            disabled={disabled || selectedNoteIndex >= score.notes.length - 1}
                            title={t("Nốt sau (→)")}
                            onClick={selectNextNote}
                        >
                            <ChevronRight size={16} />
                        </button>
                        <button
                            type="button"
                            className="icon-button"
                            disabled={disabled}
                            title={t("Xóa nốt (Del)")}
                            onClick={() => deleteNote(selectedNote.id)}
                        >
                            <Trash2 size={15} />
                        </button>
                        <button
                            type="button"
                            className="icon-button"
                            title={t("Đóng (Esc)")}
                            onClick={() => setSelectedNoteId(null)}
                        >
                            <X size={16} />
                        </button>
                    </div>
                </div>

                {editValidation && <div className={`in-place-validation ${editValidation.tone}`} role={editValidation.tone === 'error' ? 'alert' : 'status'}>
                    {editValidation.tone === 'valid' ? <CheckCircle2 size={13} /> : <TriangleAlert size={13} />}
                    <span>{t(editValidation.message)}</span>
                </div>}

                <div className="in-place-hint">
                    <Pencil size={12} />
                    <span>{t("Phím tắt: A–G đặt nốt · ↑/↓ nửa cung (Shift: quãng 8) · 1, 2, 4, 8, 6 trường độ · Enter gõ lời · Del xóa · Esc đóng")}</span>
                </div>
            </div>
        )}
    </div>;
}

