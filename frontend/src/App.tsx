import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowLeft, ArrowRight, AudioLines, Check, CheckCircle2, ChevronDown, ChevronRight, CircleHelp, FileMusic, FolderOpen, HardDrive, LoaderCircle, Languages, MessageSquareText, Menu, Moon, Music2, Pencil, Plus, Printer, RefreshCw, Save, Settings2, ShieldCheck, SlidersHorizontal, Sun, Trash, Trash2, Undo2, Upload, Wrench, X } from 'lucide-react';
import { api, ApiError, errorMessage, getApiUrl, getClientSession, isActiveJob } from './api';
import type { AnalyzeOptions, Artifact, PdfExportSource, ExportOptions, Health, Job, Project, ScoreDocument } from './types';
import CollapsibleSection from './CollapsibleSection';
import AudioPlayer, { timeLabel } from './AudioPlayer';
import ScorePreview from './ScorePreview';
import ScoreEditor from './ScoreEditor';
import ScorePlayer from './ScorePlayer';
import LyricsEditor from './LyricsEditor';
import { Guide, SettingsPanel, useSettings, workflow } from './Settings';
import { languages, t, type Language } from './i18n';
import AudioAnalysisPanel, { type AudioAnalysis } from './AudioAnalysisPanel';
import { addActivityHistory, readActivityHistory, type ActivityHistoryEntry } from './activityHistory';
const statusNames: Record<Project['status'], string> = { ready: t("Chờ phân tích"), analyzing: t("Đang phân tích"), draft: t("Cần kiểm tra"), reviewed: t("Đã duyệt"), failed: t("Phân tích lỗi") };
const keys = ['C', 'C#', 'G', 'D', 'A', 'E', 'B', 'F#', 'F', 'Bb', 'Eb', 'Ab', 'Db', 'Am', 'Em', 'Bm', 'F#m', 'C#m', 'D#m', 'G#m', 'Dm', 'Gm', 'Cm', 'Fm', 'Bbm'];
const meters = [[4, 4], [3, 4], [2, 4], [6, 8], [9, 8], [12, 8]];
const initialOptions: AnalyzeOptions = { engine: 'sheetsage2', tempo: 120, meter: [4, 4], key: 'C', melody_role: 'instrumental' };
const copy = <T,>(value: T): T => structuredClone(value);
const fraction = (value: string) => { const [a, b = '1'] = value.split('/'); const result = Number(a) / Number(b); return Number.isFinite(result) ? result : 0; };
export default function App() {
    const { settings, update: updateSettings } = useSettings();
    const [showSettings, setShowSettings] = useState(false);
    const [showGuide, setShowGuide] = useState(!settings.guideSeen);
    const [audioAnalysis, setAudioAnalysis] = useState<AudioAnalysis | null>(null);
    const [health, setHealth] = useState<Health | null>(null);
    const [projects, setProjects] = useState<Project[]>([]);
    const [selected, setSelected] = useState<Project | null>(null);
    const [score, setScore] = useState<ScoreDocument | null>(null);
    const [savedScore, setSavedScore] = useState<ScoreDocument | null>(null);
    const [pendingScore, setPendingScore] = useState<ScoreDocument | null>(null);
    const [undoHistory, setUndoHistory] = useState<ScoreDocument[]>([]);
    const [activityHistory, setActivityHistory] = useState<ActivityHistoryEntry[]>(readActivityHistory);
    const [job, setJob] = useState<Job | null>(null);
    const [options, setOptions] = useState<AnalyzeOptions>(initialOptions);
    const [playbackBeat, setPlaybackBeat] = useState<number | null>(null);
    const [tab, setTab] = useState<'sheet' | 'notes' | 'harmonies' | 'lyrics'>('sheet');
    const [busy, setBusy] = useState('');
    const [loadingProject, setLoadingProject] = useState(false);
    const [initialLoading, setInitialLoading] = useState(true);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [dragging, setDragging] = useState(false);
    const [sidebarOpen, setSidebarOpen] = useState(false);
    const [showSystem, setShowSystem] = useState(false);
    const [semitones, setSemitones] = useState(0);
    const [accompaniment, setAccompaniment] = useState(false);
    const [exportScope, setExportScope] = useState<'full' | 'range'>('full');
    const [exportBarStart, setExportBarStart] = useState('1');
    const [exportBarEnd, setExportBarEnd] = useState('');
    const [includeChords, setIncludeChords] = useState(true);
    const [includeLyrics, setIncludeLyrics] = useState(true);
    const [theme, setTheme] = useState<'light' | 'dark'>(() => {
        const saved = localStorage.getItem('studio_theme');
        if (saved === 'dark' || saved === 'light')
            return saved;
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    });
    useEffect(() => {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('studio_theme', theme);
    }, [theme]);
    const toggleTheme = () => setTheme(prev => (prev === 'dark' ? 'light' : 'dark'));
    const autoAnalyze = settings.autoAnalyze;
    const toggleAutoAnalyze = (enabled: boolean) => updateSettings({ autoAnalyze: enabled });
    const input = useRef<HTMLInputElement>(null);
    const selectedId = useRef<string | null>(null);
    const loadVersion = useRef(0);
    const uploadLock = useRef(false);
    const lyricsUploadLock = useRef(false);
    const [analysisMode, setAnalysisMode] = useState(false);
    const [trashOpen, setTrashOpen] = useState(false);
    const [deletedProjects, setDeletedProjects] = useState<Project[]>([]);
    const [isEditingTitle, setIsEditingTitle] = useState(false);
    const [titleDraft, setTitleDraft] = useState('');
    const titleInputRef = useRef<HTMLInputElement>(null);
    useEffect(() => {
        if (isEditingTitle && titleInputRef.current) {
            titleInputRef.current.focus();
            titleInputRef.current.select();
        }
    }, [isEditingTitle]);

    const editingScore = analysisMode ? null : score;
    const dirty = Boolean(score && savedScore && JSON.stringify(score) !== JSON.stringify(savedScore));
    const activeJob = isActiveJob(job);
    const disabled = Boolean(busy || initialLoading || loadingProject || activeJob || pendingScore);
    const engine = health?.models.find(item => item.id === options.engine);
    const displayedScore = pendingScore || score;
    const workflowStep = !selected ? 1 : activeJob ? 3 : !score || analysisMode ? (audioAnalysis ? 3 : 2) : tab === 'lyrics' ? 4 : savedScore?.review_status === 'reviewed' && !dirty ? 6 : 5;
    const measureCount = displayedScore ? Math.ceil(Math.max(0, ...displayedScore.notes.map(note => fraction(note.start) + fraction(note.duration)), ...displayedScore.harmonies.map(chord => fraction(chord.start) + fraction(chord.duration))) / (displayedScore.meter[0] * 4 / displayedScore.meter[1])) : 0;
    const refreshProjects = useCallback(async () => { const list = await api<Project[]>('/projects'); setProjects(list); return list; }, []);
    const loadProject = useCallback(async (id: string) => {
        const version = ++loadVersion.current;
        selectedId.current = id;
        setLoadingProject(true);
        setAudioAnalysis(null);
        setAnalysisMode(false);
        setError('');
        setNotice('');
        setPendingScore(null);
        setSidebarOpen(false);
        setIsEditingTitle(false);
        setTitleDraft('');

        try {
            const project = await api<Project>(`/projects/${id}`);
            const [document, detected] = await Promise.all([project.score_revision === null ? Promise.resolve(null) : api<ScoreDocument>(`/projects/${id}/score`), api<AudioAnalysis | null>(`/projects/${id}/audio-analysis`)]);
            if (version !== loadVersion.current)
                return;
            setAudioAnalysis(detected);
            if (!document)
                setOptions(previous => ({ ...previous, tempo: detected?.tempo ?? initialOptions.tempo, key: detected?.key ?? initialOptions.key, meter: detected?.meter ?? initialOptions.meter }));
            setSelected(project);
            setScore(document);
            setSavedScore(document ? copy(document) : null);
            setUndoHistory([]);
            setJob(project.latest_job);
            setTab('sheet');
            if (document)
                setOptions(previous => ({ ...previous, tempo: document.tempo, meter: document.meter, key: document.key, melody_role: document.melody_role }));
        }
        catch (err) {
            if (version === loadVersion.current) {
                setError(errorMessage(err));
                setSelected(null);
                setScore(null);
                setSavedScore(null);
                setJob(null);
            }
        }
        finally {
            if (version === loadVersion.current)
                setLoadingProject(false);
        }
    }, []);
    const initialize = useCallback(async () => {
        setInitialLoading(true);
        setError('');
        try {
            const state = await api<Health>('/health');
            setHealth(state);
            const preferred = state.models.find(model => model.id === 'sheetsage2' && model.available) || state.models.find(model => model.available);
            if (preferred)
                setOptions(previous => ({ ...previous, engine: preferred.id }));
            const list = await refreshProjects();
            if (list.length && !selectedId.current)
                await loadProject(new URLSearchParams(window.location.search).get('project') || list[0].id);
        }
        catch (err) {
            setHealth(null);
            setError(errorMessage(err));
        }
        finally {
            setInitialLoading(false);
        }
    }, [loadProject, refreshProjects]);
    useEffect(() => { void initialize(); }, [initialize]);
    useEffect(() => {
        const onClose = (event: BeforeUnloadEvent) => { if (dirty) {
            event.preventDefault();
            event.returnValue = '';
        } };
        window.addEventListener('beforeunload', onClose);
        return () => window.removeEventListener('beforeunload', onClose);
    }, [dirty]);
    useEffect(() => { if (!notice)
        return; const timer = window.setTimeout(() => setNotice(''), 6000); return () => window.clearTimeout(timer); }, [notice]);
    useEffect(() => {
        if (!job || !isActiveJob(job))
            return;
        let stopped = false;
        let timer: ReturnType<typeof setTimeout>;
        const poll = async () => {
            try {
                const current = await api<Job>(`/jobs/${job.id}`);
                if (stopped)
                    return;
                setJob(current);
                if (isActiveJob(current))
                    timer = setTimeout(poll, 1000);
                else {
                    await refreshProjects();
                    if (stopped || selectedId.current !== current.project_id)
                        return;
                    const project = await api<Project>(`/projects/${current.project_id}`);
                    if (stopped)
                        return;
                    setSelected(project);
                    if (current.status === 'completed') {
                        setAnalysisMode(false);
                        if (project.score_revision !== null && !score) {
                            const document = await api<ScoreDocument>(`/projects/${project.id}/score`);
                            if (stopped)
                                return;
                            setScore(document);
                            setSavedScore(copy(document));
                            setUndoHistory([]);
                            setTab('lyrics');
                        }
                        setNotice(project.pending_score_revision ? t("Đã có bản phân tích mới. Mở xem để chọn sử dụng.") : t("Đã tạo bản nháp. Hãy nghe và kiểm tra trước khi xuất."));
                    }
                    else if (current.status === 'failed')
                        setError(current.error || current.message || t("Phân tích thất bại."));
                }
            }
            catch (err) {
                if (!stopped) {
                    setError(errorMessage(err));
                    timer = setTimeout(poll, 3000);
                }
            }
        };
        timer = setTimeout(poll, 1000);
        return () => { stopped = true; clearTimeout(timer); };
        // Keep the loop alive through its terminal fetch. Depending on status would tear
        // it down immediately after setJob(completed), before the new score is loaded.
    }, [job?.id, refreshProjects]);
    const upload = async (file?: File) => {
        if (!file || uploadLock.current)
            return;
        if (!/\.(wav|mp3|flac)$/i.test(file.name)) {
            setError(t("Chọn tệp WAV, MP3 hoặc FLAC."));
            return;
        }
        if (file.size > 200 * 1024 * 1024) {
            setError(t("Tệp vượt quá 200 MB. Vui lòng cắt ngắn hoặc nén audio trước khi nhập."));
            return;
        }
        if (dirty && !window.confirm(t("Bản nhạc có thay đổi chưa lưu. Bỏ thay đổi và nhập tệp mới?")))
            return;
        uploadLock.current = true;
        setBusy('upload');
        setError('');
        const body = new FormData();
        body.append('file', file);
        try {
            const project = await api<Project>('/projects', { method: 'POST', body });
            await refreshProjects();
            await loadProject(project.id);
            if (autoAnalyze)
                await detectAudio(project);
            else
                setNotice(t("Đã tải lên audio. Bấm Analyze Audio để dò thông số."));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            uploadLock.current = false;
            setBusy('');
            if (input.current)
                input.current.value = '';
        }
    };
    const detectAudio = async (project = selected) => {
        if (!project || activeJob || dirty)
            return;
        const id = project.id;
        setBusy('detect-audio');
        setError('');
        try {
            const result = await api<AudioAnalysis>(`/projects/${id}/analyze-audio`, { method: 'POST' });
            if (selectedId.current !== id)
                return;
            setAudioAnalysis(result);
            setOptions(previous => ({ ...previous, tempo: result.tempo ?? previous.tempo, key: result.key ?? previous.key, meter: result.meter ?? previous.meter }));
            setAnalysisMode(project.score_revision !== null);
            setNotice(t("Đã dò thông số. Kiểm tra tempo, giọng và nhịp rồi bắt đầu phân tích bản nhạc."));
        }
        catch (err) {
            if (selectedId.current === id)
                setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const analyze = async () => {
        if (!selected || !engine?.available || disabled)
            return;
        if (dirty) {
            setError(t("Lưu các thay đổi trước khi phân tích lại."));
            return;
        }
        setBusy('analyze');
        setError('');
        setPendingScore(null);
        const analysisOptions = score && !analysisMode ? { ...options, tempo: score.tempo, meter: score.meter, key: score.key, melody_role: score.melody_role } : options;
        try {
            const next = await api<Job>(`/projects/${selected.id}/analyze`, { method: 'POST', body: JSON.stringify({ ...analysisOptions, device: settings.computeDevice }) });
            setJob(next);
            setSelected({ ...selected, status: 'analyzing', latest_job: next });
            await refreshProjects();
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const enterAnalysis = () => {
        if (!score || busy || activeJob || loadingProject)
            return;
        if (dirty) {
            setError(t("Lưu thay đổi bản nhạc trước khi quay lại bước 2."));
            return;
        }
        setOptions(previous => ({ ...previous, tempo: score.tempo, meter: score.meter, key: score.key, melody_role: score.melody_role }));
        setPendingScore(null);
        setAnalysisMode(true);
        setError('');
        setNotice('');
    };
    const openTrash = async () => {
        if (trashOpen) {
            setTrashOpen(false);
            return;
        }
        setBusy('trash');
        setError('');
        try {
            setDeletedProjects(await api<Project[]>('/projects?deleted=true'));
            setTrashOpen(true);
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const deleteProject = async () => {
        if (!selected || busy || activeJob || loadingProject)
            return;
        if (dirty) {
            setError(t("Lưu thay đổi bản nhạc trước khi xóa dự án."));
            return;
        }
        if (!window.confirm(t("Xóa dự án “{0}” khỏi danh sách? Có thể khôi phục từ Thùng rác; audio và các phiên bản vẫn được giữ trên máy.", { "0": selected.title })))
            return;
        setBusy('delete');
        setError('');
        try {
            await api(`/projects/${selected.id}`, { method: 'DELETE' });
            ++loadVersion.current;
            selectedId.current = null;
            setSelected(null);
            setScore(null);
            setSavedScore(null);
            setPendingScore(null);
            setUndoHistory([]);
            setJob(null);
            setAnalysisMode(false);
            const list = await refreshProjects();
            if (trashOpen)
                setDeletedProjects(await api<Project[]>('/projects?deleted=true'));
            if (list.length)
                await loadProject(list[0].id);
            setNotice(t("Đã xóa dự án khỏi danh sách. Có thể khôi phục trong Thùng rác."));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const restoreProject = async (project: Project) => {
        setBusy('restore');
        setError('');
        try {
            await api(`/projects/${project.id}/restore`, { method: 'POST' });
            await refreshProjects();
            setDeletedProjects(await api<Project[]>('/projects?deleted=true'));
            setNotice(t("Đã khôi phục “{0}”.", { "0": project.title }));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const emptyTrash = async () => {
        if (!deletedProjects.length || busy)
            return;
        if (!window.confirm(t("Bạn có chắc chắn muốn xóa vĩnh viễn {0} dự án trong thùng rác không?\n\nHành động này sẽ xóa toàn bộ audio và phiên bản trên máy, không thể khôi phục.", { "0": deletedProjects.length })))
            return;
        setBusy('empty-trash');
        setError('');
        try {
            const res = await api<{
                emptied: boolean;
                count: number;
            }>('/projects/empty-trash', { method: 'POST' });
            setDeletedProjects([]);
            setNotice(t("Đã dọn dẹp {0} dự án khỏi thùng rác.", { "0": res.count }));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const changeScore = (next: ScoreDocument) => {
        if (!score || disabled)
            return;
        setUndoHistory(previous => [...previous.slice(-98), copy(score)]);
        setScore({ ...next, review_status: 'needs_review' });
    };
    const startEditingTitle = () => {
        if (disabled || !selected)
            return;
        setTitleDraft(displayedScore?.title || selected.title || '');
        setIsEditingTitle(true);
    };
    const cancelEditingTitle = () => {
        setIsEditingTitle(false);
        setTitleDraft('');
    };
    const saveTitle = async (newTitle: string) => {
        const trimmed = newTitle.trim();
        if (!selected) {
            cancelEditingTitle();
            return;
        }
        if (!trimmed) {
            setError(t("Tên bài hát cần từ 1 đến 200 ký tự."));
            return;
        }
        if (trimmed.length > 200) {
            setError(t("Tên bài hát cần từ 1 đến 200 ký tự."));
            return;
        }
        const currentTitle = displayedScore?.title || selected.title;
        if (trimmed === currentTitle) {
            setIsEditingTitle(false);
            return;
        }
        if (editingScore) {
            if (dirty) {
                changeScore({ ...editingScore, title: trimmed });
                setIsEditingTitle(false);
                setNotice(t("Đã đổi tên bài hát. Hãy bấm Lưu để lưu cùng các thay đổi khác."));
                return;
            }
            setBusy('save');
            setError('');
            try {
                const next = await api<ScoreDocument>(`/projects/${selected.id}/score`, {
                    method: 'PUT',
                    body: JSON.stringify({ expected_revision: savedScore?.revision ?? editingScore.revision, score: { ...editingScore, title: trimmed } }),
                });
                setScore(next);
                setSavedScore(copy(next));
                setSelected(previous => previous ? { ...previous, title: next.title, score_revision: next.revision, status: next.review_status === 'reviewed' ? 'reviewed' : 'draft' } : previous);
                await refreshProjects();
                setIsEditingTitle(false);
                setNotice(t("Đã đổi tên bài hát thành “{0}”.", { "0": next.title }));
            }
            catch (err) {
                setError(errorMessage(err));
            }
            finally {
                setBusy('');
            }
        }
        else {
            setBusy('title');
            setError('');
            try {
                const updated = await api<Project>(`/projects/${selected.id}`, {
                    method: 'PATCH',
                    body: JSON.stringify({ title: trimmed }),
                });
                setSelected(previous => previous ? { ...previous, title: updated.title } : previous);
                await refreshProjects();
                setIsEditingTitle(false);
                setNotice(t("Đã đổi tên bài hát thành “{0}”.", { "0": updated.title }));
            }
            catch (err) {
                setError(errorMessage(err));
            }
            finally {
                setBusy('');
            }
        }
    };

    const undoScore = useCallback(() => {
        if (disabled)
            return;
        setUndoHistory(previous => {
            const snapshot = previous[previous.length - 1];
            if (!snapshot)
                return previous;
            setScore({ ...copy(snapshot), revision: savedScore?.revision ?? snapshot.revision });
            return previous.slice(0, -1);
        });
    }, [disabled, savedScore?.revision]);
    useEffect(() => {
        const onUndo = (event: KeyboardEvent) => {
            if (!(event.ctrlKey || event.metaKey) || event.altKey || event.shiftKey || event.key.toLowerCase() !== 'z')
                return;
            const target = event.target instanceof HTMLElement ? event.target : null;
            if (target?.isContentEditable || ['INPUT', 'TEXTAREA'].includes(target?.tagName || ''))
                return;
            event.preventDefault();
            undoScore();
        };
        window.addEventListener('keydown', onUndo);
        return () => window.removeEventListener('keydown', onUndo);
    }, [undoScore]);
    const autoFixOverlaps = async () => {
        if (!selected || !savedScore || disabled)
            return;
        if (dirty) {
            setError(t("Lưu thay đổi trước khi tự động sửa nốt chồng lấn."));
            return;
        }
        setBusy('fix-overlaps');
        setError('');
        try {
            const next = await api<ScoreDocument>(`/projects/${selected.id}/fix-overlaps`, {
                method: 'POST',
                body: JSON.stringify({ expected_revision: savedScore.revision })
            });
            setScore(next);
            setSavedScore(copy(next));
            setUndoHistory([]);
            setSelected(previous => previous ? { ...previous, score_revision: next.revision, status: next.review_status === 'reviewed' ? 'reviewed' : 'draft' } : previous);
            await refreshProjects();
            setNotice(t("Đã tự động sửa các nốt chồng lấn (phiên bản {0}).", { "0": next.revision }));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const recordActivity = (entry: Omit<ActivityHistoryEntry, 'id' | 'projectId' | 'projectTitle' | 'audioName' | 'audioDuration' | 'createdAt'>) => {
        if (!selected)
            return;
        const next = addActivityHistory({
            ...entry,
            id: crypto.randomUUID(),
            projectId: selected.id,
            projectTitle: score?.title || selected.title,
            audioName: selected.audio_name,
            audioDuration: selected.duration,
            createdAt: new Date().toISOString(),
        });
        setActivityHistory(next);
    };
    const saveScore = async (review = false): Promise<boolean> => {
        if (!selected || !score || !savedScore)
            return false;
        if (review && dirty) {
            setError(t("Lưu thay đổi rồi nghe và xác nhận kiểm tra phiên bản đã lưu."));
            return false;
        }
        setBusy('save');
        setError('');
        try {
            const targetRevision = savedScore.revision;
            const next = review
                ? await api<ScoreDocument>(`/projects/${selected.id}/review`, { method: 'POST', body: JSON.stringify({ expected_revision: targetRevision }) })
                : await api<ScoreDocument>(`/projects/${selected.id}/score`, { method: 'PUT', body: JSON.stringify({ expected_revision: savedScore.revision, score }) });
            setScore(next);
            setSavedScore(copy(next));
            setSelected(previous => previous ? { ...previous, score_revision: next.revision, status: next.review_status === 'reviewed' ? 'reviewed' : 'draft' } : previous);
            await refreshProjects();
            if (review)
                recordActivity({ kind: 'review', revision: next.revision });
            setNotice(review ? t("Đã đánh dấu bản nhạc được kiểm tra và lưu.") : t("Đã lưu phiên bản {0}.", { "0": next.revision }));
            return true;
        }
        catch (err) {
            setError(err instanceof ApiError && err.status === 409 ? t("Dự án đã có phiên bản mới ở phiên làm việc khác. Thay đổi của bạn vẫn còn trên màn hình; tải lại dự án khi đã ghi lại nội dung cần giữ.") : errorMessage(err));
            return false;
        }
        finally {
            setBusy('');
        }
    };
    const selectProject = async (project: Project) => {
        if (project.id === selectedId.current) {
            setSidebarOpen(false);
            return;
        }
        if (dirty) {
            const shouldSave = window.confirm(t("Bản nhạc có thay đổi chưa lưu. Lưu thay đổi trước khi mở dự án khác?"));
            if (!shouldSave || !await saveScore())
                return;
        }
        await loadProject(project.id);
    };
    const uploadLyrics = async (file: File, offset: number) => {
        if (!selected || !savedScore || disabled || lyricsUploadLock.current)
            return;
        if (dirty) {
            setError(t("Lưu thay đổi trước khi nhập tệp lời hát."));
            return;
        }
        if (!/\.(srt|lrc)$/i.test(file.name)) {
            setError(t("Chọn tệp lời hát SRT hoặc LRC."));
            return;
        }
        if (!file.size || file.size > 1024 * 1024) {
            setError(t("Tệp lời hát phải có nội dung và không vượt quá 1 MB."));
            return;
        }
        if (!Number.isFinite(offset) || Math.abs(offset) > 600) {
            setError(t("Dịch mốc thời gian phải nằm trong khoảng −600 đến 600 giây."));
            return;
        }
        const projectId = selected.id;
        const version = loadVersion.current;
        const isCurrent = () => selectedId.current === projectId && loadVersion.current === version;
        lyricsUploadLock.current = true;
        setBusy('lyrics');
        setError('');
        const body = new FormData();
        body.append('file', file);
        body.append('expected_revision', String(savedScore.revision));
        body.append('offset_seconds', String(offset));
        try {
            const next = await api<ScoreDocument>(`/projects/${projectId}/lyrics`, { method: 'POST', body });
            if (isCurrent()) {
                setScore(next);
                setSavedScore(copy(next));
                setUndoHistory([]);
                setSelected(previous => previous?.id === projectId ? { ...previous, score_revision: next.revision, status: 'draft' } : previous);
                const unmatched = (next.lyrics || []).filter(token => !token.note_id).length;
                setNotice(t("Đã nhập {0} từ / âm tiết vào phiên bản {1}.{2}", { "0": (next.lyrics || []).length, "1": next.revision, "2": unmatched ? t(" {0} lời chưa gắn nốt; mở bộ lọc để chỉnh.", { "0": unmatched }) : t(" Kiểm tra vị trí lời trên khuông nhạc.") }));
            }
            await refreshProjects();
        }
        catch (err) {
            if (isCurrent())
                setError(err instanceof ApiError && err.status === 409 ? t("Dự án đã có phiên bản mới. Tải lại dự án trước khi nhập lời hát.") : errorMessage(err));
        }
        finally {
            lyricsUploadLock.current = false;
            setBusy('');
        }
    };
    const clearLyrics = async () => {
        if (!selected || !savedScore || disabled || dirty)
            return;
        setBusy('clear-lyrics');
        setError('');
        try {
            const next = await api<ScoreDocument>(`/projects/${selected.id}/lyrics`, { method: 'DELETE', body: JSON.stringify({ expected_revision: savedScore.revision }) });
            setScore(next);
            setSavedScore(copy(next));
            setUndoHistory([]);
            setSelected(previous => previous ? { ...previous, lyric_attachment: null, score_revision: next.revision, status: 'draft' } : previous);
            await refreshProjects();
            setNotice(t("Đã xóa lời hát. Bạn có thể nhập tệp mới."));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const transpose = async () => {
        if (!selected || !savedScore || !semitones)
            return;
        setBusy('transpose');
        setError('');
        try {
            const next = await api<ScoreDocument>(`/projects/${selected.id}/transpose`, { method: 'POST', body: JSON.stringify({ expected_revision: savedScore.revision, semitones }) });
            setScore(next);
            setSavedScore(copy(next));
            setUndoHistory([]);
            setSemitones(0);
            setSelected(previous => previous ? { ...previous, score_revision: next.revision, status: 'draft' } : previous);
            await refreshProjects();
            setNotice(t("Đã chuyển giọng và lưu thành phiên bản mới."));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const download = async (format: 'musicxml' | 'midi' | 'pdf' | 'abc') => {
        if (!selected || !savedScore || disabled || activeJob || dirty || savedScore.review_status !== 'reviewed')
            return;
        if (exportScope === 'range') {
            const start = Number(exportBarStart);
            const end = Number(exportBarEnd || measureCount);
            if (!Number.isInteger(start) || start < 1) {
                setError(t("Ô nhịp bắt đầu phải là số nguyên ≥ 1."));
                return;
            }
            if (!Number.isInteger(end) || end < start) {
                setError(t("Ô nhịp kết thúc phải là số nguyên lớn hơn hoặc bằng ô nhịp bắt đầu."));
                return;
            }
        }
        setBusy(format);
        setError('');
        try {
            const currentScore = savedScore;
            const payload: ExportOptions = {
                format,
                revision: currentScore.revision,
                accompaniment,
                include_chords: includeChords,
                include_lyrics: includeLyrics,
                scope: exportScope,
                bar_start: exportScope === 'range' ? Number(exportBarStart) : undefined,
                bar_end: exportScope === 'range' ? Number(exportBarEnd || measureCount) : undefined,
            };
            const artifact = await api<Artifact | PdfExportSource>(`/projects/${selected.id}/exports`, { method: 'POST', body: JSON.stringify(payload) });
            const source = 'source' in artifact ? artifact.source : artifact;
            const session = getClientSession();
            const res = await fetch(getApiUrl(source.url), {
                credentials: 'same-origin',
                headers: session ? { 'X-Client-Session': session } : {},
            });
            if (!res.ok)
                throw new Error(t("Không tải được tệp từ máy chủ ({0}).", { "0": res.status }));
            const blob = format === 'pdf'
                ? await (await import('./exportPdf')).createScorePdf(await res.text())
                : await res.blob();
            const blobUrl = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = blobUrl;
            link.download = artifact.filename;
            document.body.append(link);
            link.click();
            link.remove();
            setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
            recordActivity({
                kind: 'export',
                revision: currentScore.revision,
                format,
                outputFilename: artifact.filename,
            });
            setNotice(t("Đã tạo và tải xuống {0}.", { "0": artifact.filename }));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const viewPending = async () => {
        if (!selected?.pending_score_revision)
            return;
        setBusy('pending');
        setError('');
        try {
            setPendingScore(await api<ScoreDocument>(`/projects/${selected.id}/score?revision=${selected.pending_score_revision}`));
            setTab('sheet');
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const activatePending = async () => {
        if (!selected || !pendingScore)
            return;
        if (dirty && !window.confirm(t("Bỏ các thay đổi chưa lưu và dùng bản phân tích mới?")))
            return;
        setBusy('activate');
        setError('');
        try {
            await api<ScoreDocument>(`/projects/${selected.id}/activate-score`, { method: 'POST', body: JSON.stringify({ expected_revision: savedScore?.revision ?? null, revision: pendingScore.revision }) });
            await refreshProjects();
            await loadProject(selected.id);
            setNotice(t("Đã chọn bản phân tích mới làm bản đang chỉnh sửa."));
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    const cancel = async () => {
        if (!job)
            return;
        setBusy('cancel');
        try {
            setJob(await api<Job>(`/jobs/${job.id}/cancel`, { method: 'POST' }));
            await refreshProjects();
        }
        catch (err) {
            setError(errorMessage(err));
        }
        finally {
            setBusy('');
        }
    };
    return <div className="app-shell">
    <input ref={input} type="file" accept=".wav,.mp3,.flac,audio/wav,audio/mpeg,audio/flac" className="sr-only" aria-label={t("Chọn tệp âm thanh")} onChange={e => void upload(e.target.files?.[0])}/>
    <header className="topbar"><div className="brand"><button className="icon-button mobile-menu" aria-label={t("Mở danh sách dự án")} onClick={() => setSidebarOpen(!sidebarOpen)}><Menu size={20}/></button><div className="brand-mark"><Music2 size={22} strokeWidth={1.8}/></div><span>{t("Bản nhạc")}<span className="brand-dot">.</span></span></div><div className="workspace-label">{t("Không gian làm việc")}</div><div className="topbar-right"><label className="language-switch" title={t('Ngôn ngữ')}><Languages size={17}/><select aria-label={t('Ngôn ngữ')} value={settings.language} onChange={e => updateSettings({ language: e.target.value as Language })}>{languages.map(language => <option key={language.id} value={language.id}>{language.id.toUpperCase()}</option>)}</select></label><button className="icon-button" aria-label={t('Cài đặt')} title={t('Cài đặt')} onClick={() => setShowSettings(true)}><Settings2 size={18}/></button><button className="icon-button" aria-label={t('Giúp đỡ')} title={t('Giúp đỡ')} onClick={() => setShowGuide(true)}><CircleHelp size={18}/></button><button className="icon-button theme-toggle" aria-label={theme === 'dark' ? t("Chuyển sang giao diện sáng") : t("Chuyển sang giao diện tối")} title={theme === 'dark' ? t("Giao diện sáng") : t("Giao diện tối")} onClick={toggleTheme}>{theme === 'dark' ? <Sun size={16}/> : <Moon size={16}/>}</button><span className="local-label"><HardDrive size={14}/>{t("Chạy trên máy của bạn")}</span><button className={`system-button ${health ? 'connected' : ''}`} onClick={() => setShowSystem(!showSystem)} aria-expanded={showSystem}><span className="status-dot"/>{health ? 'Local' : initialLoading ? t("Kết nối…") : t("Mất kết nối")}<ChevronDown size={13}/></button></div></header>

    {showSettings && <SettingsPanel close={() => setShowSettings(false)}/>}
    {showGuide && <Guide close={() => setShowGuide(false)}/>}
    {showSystem && <section className="system-panel" aria-label={t("Thông tin hệ thống")}><div className="section-title"><h2>{t("Hệ thống local")}</h2><button className="icon-button" aria-label={t("Đóng thông tin hệ thống")} onClick={() => setShowSystem(false)}><X size={17}/></button></div><dl><div><dt>{t("API")}</dt><dd>{health ? t("Đang chạy · v{0}", { "0": health.version }) : t("Chưa kết nối")}</dd></div><div><dt>{t("GPU")}</dt><dd>{health?.gpu || t("Chưa phát hiện / CPU")}</dd></div><div><dt>{t("FFmpeg")}</dt><dd>{health?.ffmpeg ? t("Sẵn sàng") : t("Chưa cài")}</dd></div><div><dt>{t("Xuất PDF")}</dt><dd>{t("Trực tiếp trong trình duyệt")}</dd></div></dl><button className="button secondary compact" onClick={() => void initialize()} disabled={initialLoading}><RefreshCw size={14}/>{t("Kiểm tra lại")}</button></section>}

    <div className="workspace-grid">
      {sidebarOpen && <button className="sidebar-backdrop" aria-label={t("Đóng danh sách dự án")} onClick={() => setSidebarOpen(false)}/>}
      <aside className={`sidebar ${sidebarOpen ? 'is-open' : ''}`}><div className="sidebar-head"><div className="section-title"><h2>{t("Dự án")}</h2><span className="count">{projects.length.toString().padStart(2, '0')}</span></div><button className="button primary new-project" onClick={() => input.current?.click()} disabled={Boolean(busy) || !health}><Plus size={17}/>{t("Nhập audio mới")}</button></div><nav className="project-list" aria-label={t("Danh sách dự án")}>{projects.length ? projects.map(project => <button key={project.id} className={`project-item ${selected?.id === project.id ? 'selected' : ''}`} onClick={() => void selectProject(project)} disabled={Boolean(busy)} aria-current={selected?.id === project.id ? 'page' : undefined}><FileMusic size={18}/><span><strong>{project.title}</strong><small>{timeLabel(project.duration)}<span className="separator-dot">·</span>{t(statusNames[project.status])}</small></span><ChevronRight size={14}/></button>) : <div className="projects-empty"><FolderOpen size={23} strokeWidth={1.4}/><p>{t("Dự án của bạn sẽ xuất hiện ở đây.")}</p><small>{t("Nhập bản thu đầu tiên để bắt đầu.")}</small></div>}</nav><section className="project-trash"><button className="button secondary compact full-width" onClick={() => void openTrash()} disabled={Boolean(busy)} aria-expanded={trashOpen}><Trash2 size={15}/>{t("Thùng rác ")}{deletedProjects.length > 0 ? `(${deletedProjects.length})` : ''}</button>{trashOpen && <div className="trash-list"><div className="trash-header"><strong>{t("Đã xóa (")}{deletedProjects.length})</strong>{deletedProjects.length > 0 && <button className="button secondary compact danger-btn" disabled={Boolean(busy)} onClick={() => void emptyTrash()} title={t("Dọn sạch toàn bộ thùng rác")}><Trash size={13}/>{t("Dọn dẹp")}</button>}</div>{deletedProjects.length ? deletedProjects.map(project => <div className="trash-item" key={project.id}><strong>{project.title}</strong><button className="button secondary compact" disabled={Boolean(busy)} aria-label={t("Khôi phục {0}", { "0": project.title })} onClick={() => void restoreProject(project)}><Undo2 size={13}/>{t("Khôi phục")}</button></div>) : <p>{t("Thùng rác trống.")}</p>}</div>}</section><div className="sidebar-bottom"><ShieldCheck size={18}/><div><strong>{t("Audio ở lại trên máy")}</strong><p>{t("Phân tích và lưu dự án local.")}</p></div></div></aside>

      <main className="main-workspace" id="main-content">
        <div className="breadcrumb"><span>{t("Thư viện")}</span><ChevronRight size={13}/><strong>{selected ? selected.title : t("Dự án mới")}</strong>{selected && <span className="project-date">{new Date(selected.created_at).toLocaleDateString(settings.language === 'vi' ? 'vi-VN' : 'en-US')}</span>}</div>
        {selected && <div className="project-actions">{score && !analysisMode && <button className="button secondary compact" disabled={Boolean(busy) || activeJob || loadingProject} onClick={enterAnalysis}><ArrowLeft size={14}/>{t("Quay lại bước 2 · Dò audio")}</button>}{score && analysisMode && <button className="button secondary compact" disabled={Boolean(busy) || activeJob} onClick={() => setAnalysisMode(false)}><ArrowLeft size={14}/>{t("Quay lại bản nhạc")}</button>}<button className="button secondary compact delete-project" disabled={Boolean(busy) || activeJob || loadingProject} onClick={() => void deleteProject()}><Trash2 size={14}/>{t("Xóa dự án")}</button></div>}
        <ol className="workflow-stepper" aria-label={t("Quy trình tạo bản nhạc")}>{workflow.map(({ title, icon: Icon }, index) => <li key={title} className={workflowStep === index + 1 ? 'current' : workflowStep > index + 1 ? 'complete' : ''} aria-current={workflowStep === index + 1 ? 'step' : undefined}><span>{index + 1}</span><button className="step-link" title={t(title)} aria-label={t(title)} disabled={Boolean(busy) || activeJob || (index > 0 && !selected) || (index > 2 && !score)} onClick={() => {
                if (index === 0)
                    input.current?.click();
                else if (index === 1 || index === 2) {
                    if (score)
                        enterAnalysis();
                    document.getElementById(index === 1 ? 'audio-analysis' : 'engine')?.scrollIntoView({ block: 'center' });
                }
                else {
                    setAnalysisMode(false);
                    setTab(index === 3 ? 'lyrics' : 'sheet');
                    if (index === 5)
                        document.getElementById('download-panel')?.scrollIntoView({ block: 'center' });
                }
            }}><Icon size={17}/><span>{t(title)}</span></button></li>)}</ol>
        {error && <div className="message error-message" role="alert"><CircleHelp size={17}/><span>{t(error)}</span><button className="icon-button" onClick={() => setError('')} aria-label={t("Đóng thông báo lỗi")}><X size={16}/></button></div>}
        {notice && <div className="message success-message" role="status"><CheckCircle2 size={17}/><span>{t(notice)}</span><button className="icon-button" onClick={() => setNotice('')} aria-label={t("Đóng thông báo")}><X size={16}/></button></div>}
        {initialLoading || loadingProject ? <div className="workspace-loading" role="status"><LoaderCircle className="spin" size={25}/><p>{initialLoading ? t("Đang kết nối không gian làm việc…") : t("Đang mở dự án…")}</p></div> : !selected ? <>
          <div className="empty-heading"><span className="eyebrow">{t("Audio → Lead sheet")}</span><h1>{t("Từ âm thanh,")}<br />{t("thành bản nhạc")}<span>.</span></h1><p>{t("Đưa bản thu vào. Kiểm tra giai điệu và hợp âm.")}<br className="desktop-break"/>{t(" Xuất bản nhạc để tập, chỉnh sửa hoặc chia sẻ.")}</p></div>
          <div className={`upload-zone ${dragging ? 'dragging' : ''} ${busy === 'upload' ? 'uploading' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); if (health)
            void upload(e.dataTransfer.files[0]); }}><div className="upload-symbol">{busy === 'upload' ? <LoaderCircle className="spin" size={30} strokeWidth={1.4}/> : <Upload size={30} strokeWidth={1.4}/>}</div><h2>{busy === 'upload' ? t("Đang nhập audio…") : t("Kéo bản thu của bạn vào đây")}</h2><p>{t("WAV, MP3 hoặc FLAC · Tối đa 200 MB / 10 phút")}</p><button className="button primary" onClick={() => input.current?.click()} disabled={Boolean(busy) || !health}>{t("Chọn tệp từ máy")}<ArrowRight size={17}/></button></div>
          <div className="workflow-steps"><div><span>01</span><h3>{t("Nhập bản thu")}</h3><p>{t("Chọn audio có giai điệu chính nghe rõ.")}</p></div><div><span>02</span><h3>{t("Nghe & chỉnh sửa")}</h3><p>{t("Kiểm tra cao độ, trường độ và hợp âm.")}</p></div><div><span>03</span><h3>{t("Xuất bản nhạc")}</h3><p>{t("MusicXML để sửa tiếp, MIDI để nghe, PDF để in.")}</p></div></div>
        </> : <>
          <div className="project-heading"><div className="project-heading-main"><div className="eyebrow">{t("Lead sheet ")}<span className="thin-divider"/> {displayedScore ? t("Phiên bản {0}", { "0": displayedScore.revision }) : t("Bản thu mới")}</div>{isEditingTitle ? <form className="title-edit-form" onSubmit={e => { e.preventDefault(); void saveTitle(titleDraft); }}><input ref={titleInputRef} type="text" className="title-edit-input" value={titleDraft} maxLength={200} aria-label={t("Tên bài hát")} disabled={Boolean(busy)} onChange={e => setTitleDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Escape') cancelEditingTitle(); }}/><div className="title-edit-actions"><button type="submit" className="button primary compact" disabled={!titleDraft.trim() || Boolean(busy)}>{busy === 'save' || busy === 'title' ? <LoaderCircle className="spin" size={13}/> : <Check size={13}/>}<span>{t("Lưu")}</span></button><button type="button" className="button secondary compact" disabled={Boolean(busy)} onClick={cancelEditingTitle}><X size={13}/><span>{t("Hủy")}</span></button></div></form> : <div className="title-display-row"><h1 className="editable-title" onClick={startEditingTitle} title={t("Bấm để đổi tên bài hát")} tabIndex={0} role="button" onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEditingTitle(); } }}>{displayedScore?.title || selected.title}</h1><button type="button" className="icon-button edit-title-btn" aria-label={t("Đổi tên bài hát")} title={t("Đổi tên bài hát")} disabled={disabled} onClick={startEditingTitle}><Pencil size={18}/></button></div>}<div className="project-meta"><span className={`review-badge ${displayedScore?.review_status === 'reviewed' ? 'reviewed' : ''}`}>{displayedScore?.review_status === 'reviewed' ? <Check size={12}/> : <span className="status-dot"/>}{displayedScore ? (displayedScore.review_status === 'reviewed' ? t("Đã kiểm tra") : t("Cần kiểm tra")) : t(statusNames[selected.status])}</span><span>{timeLabel(selected.duration)}{t(" audio")}</span>{displayedScore && <span>{displayedScore.notes.length}{t(" nốt · ")}{displayedScore.harmonies.length}{t(" hợp âm")}</span>}</div></div>{displayedScore && <div className="measure-folio"><span>{String(measureCount).padStart(2, '0')}</span><small>{t("ô nhịp")}</small></div>}</div>
          {selected.pending_score_revision && <div className="pending-banner"><div><FileMusic size={19}/><span>{pendingScore ? t("Đang xem bản phân tích mới · phiên bản {0}", { "0": pendingScore.revision }) : t("Có bản phân tích mới · phiên bản {0}", { "0": selected.pending_score_revision })}<small>{t("Bản đang chỉnh sửa được giữ lại trong lịch sử.")}</small></span></div><div>{pendingScore ? <><button className="button secondary compact" disabled={Boolean(busy)} onClick={() => setPendingScore(null)}><ArrowLeft size={13}/>{t("Quay lại")}</button><button className="button primary compact" disabled={Boolean(busy)} onClick={() => void activatePending()}>{t("Dùng bản này")}</button></> : <button className="button secondary compact" disabled={Boolean(busy)} onClick={() => void viewPending()}>{t("Mở xem")}<ArrowRight size={14}/></button>}</div></div>}
          <CollapsibleSection storageKey="audio-original" title={<h2>{t("Audio gốc")}</h2>} className="workspace-section"><AudioPlayer projectId={selected.id} duration={selected.duration} filename={selected.audio_name}/></CollapsibleSection>
          <CollapsibleSection storageKey="audio-analysis" title={<h2>{t("Dò thông số audio")}</h2>} className="workspace-section"><AudioAnalysisPanel result={audioAnalysis} busy={busy === 'detect-audio'} disabled={disabled || dirty} analyze={() => void detectAudio()}/></CollapsibleSection>

          {activeJob && <div className={`analysis-progress ${job?.status === 'queued' ? 'queued' : ''}`} role="status"><LoaderCircle className="spin" size={21}/><div><div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}><strong>{job?.status === 'queued' ? t("Đang chờ trong hàng đợi") : t("Đang phân tích bản thu")}</strong>{job?.queue_position ? <span className="auto-analyze-badge" style={{ background: '#d97706' }}>{t("Vị trí #{pos}", { pos: job.queue_position })}</span> : null}</div><p>{t(job?.message || job?.stage || 'Đang chờ worker…')}</p></div><button className="button secondary compact" disabled={Boolean(busy)} onClick={() => void cancel()}>{t("Dừng")}</button></div>}
          {displayedScore && !analysisMode ? <>
            <CollapsibleSection storageKey="score-player" title={<h2>{t("Nghe giai điệu dựng lại")}</h2>} className="workspace-section"><ScorePlayer projectId={selected.id} score={displayedScore} onPlaybackBeat={setPlaybackBeat}/></CollapsibleSection>
            <CollapsibleSection storageKey="score-sheet" title={<h2>{t("Bản nhạc")}</h2>} className="workspace-section">
            <div className="score-toolbar"><div className="tabs" role="tablist" aria-label={t("Nội dung bản nhạc")}>{([['sheet', t("Khuông nhạc")], ['notes', t("Giai điệu")], ['harmonies', t("Hợp âm")], ['lyrics', t("Lời hát")]] as const).map(([id, label]) => <button key={id} role="tab" aria-selected={tab === id} className={tab === id ? 'active' : ''} title={t(label)} aria-label={t(label)} onClick={() => setTab(id)}>{id === 'sheet' ? <FileMusic size={16}/> : id === 'notes' ? <Music2 size={16}/> : id === 'harmonies' ? <AudioLines size={16}/> : <MessageSquareText size={16}/>}<span className="tab-label">{t(label)}</span>{id === 'notes' && <small>{displayedScore.notes.length}</small>}{id === 'harmonies' && <small>{displayedScore.harmonies.length}</small>}{id === 'lyrics' && <small>{(displayedScore.lyrics || []).length}</small>}</button>)}</div><div className="edit-actions">{dirty && <span className="unsaved-label">{t("Chưa lưu")}</span>}<button className="icon-button" aria-label={t("Hoàn tác chỉnh sửa (Ctrl+Z)")} disabled={disabled || !undoHistory.length} onClick={undoScore}><Undo2 size={17}/></button><button className="button secondary compact" disabled={disabled || !dirty} onClick={() => void saveScore()}>{busy === 'save' ? <LoaderCircle className="spin" size={14}/> : <Save size={14}/>}{t("Lưu")}</button><button className="icon-button" aria-label={t("In bản nhạc (Ctrl+P)")} title={t("In bản nhạc (Ctrl+P)")} disabled={disabled || !score} onClick={() => window.print()}><Printer size={16}/></button></div></div>
            <div className="score-content">{tab === 'sheet' ? <><div className="sheet-topline"><span>{displayedScore.key}<span className="separator-dot">·</span>{displayedScore.meter.join('/')}<span className="separator-dot">·</span>♩ = {displayedScore.tempo}</span><span>{displayedScore.source_engine === 'monophonic' ? t("Phân tích đơn âm thử nghiệm") : displayedScore.source_engine}</span></div>{displayedScore.diagnostics?.some(d => d.includes('chồng lấn')) && !pendingScore && <div className="preview-overlap-warning"><span>{t("⚠️ Phát hiện nốt hoặc hợp âm bị chồng lấn. Bản xem đang tự dãn cách để hiển thị; bạn có thể tự động sửa để xuất MusicXML/PDF.")}</span><button className="button compact secondary" disabled={disabled || dirty} onClick={() => void autoFixOverlaps()}>{busy === 'fix-overlaps' ? <LoaderCircle className="spin" size={13}/> : <Wrench size={13}/>}{t("Tự động sửa nốt chồng lấn")}</button></div>}{dirty && !pendingScore && <div className="preview-dirty">{t("Khuông nhạc và nốt đang phát theo bản đang sửa. Lưu trước khi xác nhận kiểm tra.")}</div>}<ScorePreview projectId={selected.id} revision={pendingScore?.revision ?? savedScore!.revision} score={displayedScore} playbackBeat={playbackBeat} changeScore={changeScore} disabled={disabled}/><div className="sheet-footer"><span>{t("Concert pitch · Melody & hợp âm")}</span><span>{displayedScore.review_status === 'reviewed' ? t("Đã kiểm tra") : t("Bản nháp — cần đối chiếu audio")}</span></div></> : tab === 'lyrics' ? <LyricsEditor key={selected.id} score={displayedScore} change={changeScore} disabled={disabled} dirty={dirty} importing={busy === 'lyrics'} upload={uploadLyrics} clear={clearLyrics}/> : <ScoreEditor score={displayedScore} tab={tab} change={changeScore} disabled={disabled}/>}</div>
            </CollapsibleSection>
            {displayedScore.diagnostics.length > 0 && <details className="diagnostics" open={(() => { try { return localStorage.getItem('box_open_diagnostics') === 'true'; } catch { return false; } })()} onToggle={e => { try { localStorage.setItem('box_open_diagnostics', String(e.currentTarget.open)); } catch {} }}><summary><CircleHelp size={16}/>{displayedScore.diagnostics.length}{t(" lưu ý cần kiểm tra")}<ChevronDown size={14}/></summary><ul>{displayedScore.diagnostics.map((message, index) => <li key={`${index}-${message}`}>{t(message)}</li>)}</ul></details>}
          </> : !activeJob && <div className="analysis-empty"><div className="empty-staff" aria-hidden="true"><Music2 size={33} strokeWidth={1.4}/></div><span className="eyebrow">{t("Bước 03")}</span><h2>{score ? t("Phân tích lại bản thu.") : t("Bản thu đã sẵn sàng.")}</h2><p>{t("Chọn công cụ và thiết lập âm nhạc ở bên phải,")}<br />{t("sau đó bắt đầu tạo bản nháp lead sheet.")}</p>{score && <p>{t("Bản đã lưu được giữ nguyên. Chọn lại Giai điệu chính để phân tích Nhạc cụ hoặc Giọng hát.")}</p>}<button className="button primary" disabled={!engine?.available || Boolean(busy)} onClick={() => void analyze()}><AudioLines size={16}/>{t("Bắt đầu phân tích")}<ArrowRight size={16}/></button></div>}
        </>}
        <footer className="workspace-footer"><span>{t("Bản nhạc · Local studio")}</span><span>{t("MusicXML / MIDI / PDF / ABC")}</span></footer>
      </main>

      <aside className="inspector" aria-label={t("Thiết lập và xuất bản nhạc")}><div className="inspector-heading"><SlidersHorizontal size={17}/><h2>{editingScore ? t("Bản nhạc & xuất file") : t("Thiết lập phân tích")}</h2></div>
        <CollapsibleSection storageKey="inspector-engine" className="inspector-section" title={<div className="section-title"><h3>{t("Công cụ phân tích")}</h3><Settings2 size={14}/></div>}><label className="field-label" htmlFor="engine">{t("Model / bộ phân tích")}</label><select id="engine" value={options.engine} disabled={Boolean(busy) || activeJob} onChange={e => setOptions({ ...options, engine: e.target.value })}>{(health?.models.length ? health.models : [{ id: 'sheetsage2', name: 'SheetSage2', available: false }]).map(model => <option key={model.id} value={model.id}>{t(model.name)}{model.available ? '' : t(" · Chưa sẵn sàng")}</option>)}</select><div className={`engine-status ${engine?.available ? 'ready' : ''}`}><span className="status-dot"/><span>{engine?.available ? t("Sẵn sàng trên máy") : t("Chưa sẵn sàng")}</span></div><p className="field-help">{engine?.id === 'monophonic' ? t("Thử nghiệm DSP cho một nhạc cụ chơi từng nốt. Không phải AI; không chép đúng bản hòa âm nhiều nhạc cụ.") : (engine?.description ? t(engine.description) : '') || t("Tải và cấu hình model local trước khi phân tích bản hòa âm.")}</p>{engine?.reason && <p className="engine-reason">{t(engine.reason)}</p>}{!health && <button className="button secondary compact" onClick={() => void initialize()} disabled={initialLoading}><RefreshCw size={13}/>{t("Kết nối lại")}</button>}</CollapsibleSection>
        <CollapsibleSection storageKey="inspector-music-setup" className="inspector-section" title={<div className="section-title"><h3>{editingScore ? t("Thiết lập bản nhạc") : t("Thiết lập âm nhạc")}</h3><span className="section-index">01</span></div>}>
          {!editingScore && <label className="auto-analyze-field" title={t("Tự dò thông số audio sau khi upload")}><input type="checkbox" checked={autoAnalyze} onChange={e => toggleAutoAnalyze(e.target.checked)}/><span className="auto-analyze-badge">{t("AUTO")}</span><span>{t("Tự dò thông số audio sau khi upload")}</span></label>}
          {editingScore ? (
            <label className="field">{t("Tên bài hát")}<input value={editingScore.title} maxLength={200} disabled={disabled} onChange={e => changeScore({ ...editingScore, title: e.target.value })}/></label>
          ) : selected ? (
            <label className="field">{t("Tên bài hát")}<div className="title-inspector-row"><input value={titleDraft !== '' ? titleDraft : selected.title} maxLength={200} disabled={disabled || Boolean(busy)} onChange={e => setTitleDraft(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); void saveTitle(titleDraft !== '' ? titleDraft : selected.title); } }}/><button className="button secondary compact" disabled={disabled || Boolean(busy) || !titleDraft.trim() || titleDraft.trim() === selected.title} onClick={() => void saveTitle(titleDraft)}>{busy === 'title' ? <LoaderCircle className="spin" size={12}/> : <Check size={12}/>}{t("Lưu")}</button></div></label>
          ) : null}
          <div className="field-pair"><label className="field">{t("Tempo (BPM)")}<input type="number" min="20" max="300" value={editingScore?.tempo ?? options.tempo} disabled={disabled} onChange={e => editingScore ? changeScore({ ...editingScore, tempo: Number(e.target.value) }) : setOptions({ ...options, tempo: Number(e.target.value) })}/></label><label className="field">{t("Nhịp")}<select value={(editingScore?.meter || options.meter).join('/')} disabled={disabled} onChange={e => { const meter = e.target.value.split('/').map(Number) as [
        number,
        number
    ]; if (editingScore)
        changeScore({ ...editingScore, meter });
    else
        setOptions({ ...options, meter }); }}>{meters.map(meter => <option key={meter.join('/')}>{meter.join('/')}</option>)}</select></label></div>
          <label className="field">{t("Giọng")}<select value={editingScore?.key || options.key} disabled={disabled} onChange={e => editingScore ? changeScore({ ...editingScore, key: e.target.value }) : setOptions({ ...options, key: e.target.value })}>{keys.map(key => <option key={key} value={key}>{key}{key.endsWith('m') ? t(" — thứ") : t(" — trưởng")}</option>)}</select></label><label className="field">{t("Giai điệu chính")}<select value={editingScore?.melody_role || options.melody_role} disabled={disabled} onChange={e => { const melody_role = e.target.value as 'instrumental' | 'vocal'; if (editingScore)
        changeScore({ ...editingScore, melody_role });
    else
        setOptions({ ...options, melody_role }); }}><option value="instrumental">{t("Nhạc cụ")}</option><option value="vocal">{t("Giọng hát")}</option></select></label><p className="field-help">{t("Phiên bản đầu dùng tempo và nhịp cố định. ")}{editingScore ? t("Đổi tên giọng không đổi cao độ; dùng Chuyển giọng bên dưới.") : t("Chưa tự động xử lý rubato hoặc thay đổi nhịp.")}</p>
          <button className="button primary full-width" disabled={!selected || !engine?.available || Boolean(busy) || activeJob || dirty || Boolean(pendingScore)} onClick={() => score && !analysisMode ? enterAnalysis() : void analyze()}>{busy === 'analyze' ? <LoaderCircle className="spin" size={16}/> : <AudioLines size={16}/>}{score && !analysisMode ? t("Quay lại bước 2") : score ? t("Phân tích lại audio") : t("Bắt đầu phân tích")}<ArrowRight size={16}/></button>{editingScore && <p className="field-help">{t("Phân tích lại tạo bản nháp mới để bạn lựa chọn.")}</p>}
        </CollapsibleSection>
        {score && !analysisMode && <><CollapsibleSection storageKey="inspector-transpose" className="inspector-section" title={<div className="section-title"><h3>{t("Chuyển giọng")}</h3><span className="section-index">02</span></div>}><div className="transpose-row"><select aria-label={t("Số bán âm cần chuyển")} value={semitones} disabled={disabled || dirty} onChange={e => setSemitones(Number(e.target.value))}>{Array.from({ length: 25 }, (_, i) => i - 12).map(value => <option key={value} value={value}>{value > 0 ? '+' : ''}{value}{t(" bán âm")}{value === 0 ? t(" — giữ nguyên") : ''}</option>)}</select><button className="button secondary compact" disabled={disabled || dirty || semitones === 0} onClick={() => void transpose()}>{t("Áp dụng")}</button></div><p className="field-help">{t("Đổi đồng thời nốt, giọng và hợp âm. Tạo phiên bản mới.")}</p></CollapsibleSection><CollapsibleSection storageKey="inspector-export" className="inspector-section" title={<div className="section-title"><h3 id="download-panel">{t("Kiểm tra → Xuất file")}</h3><span className="section-index">03</span></div>}><p className="field-help export-intro">{t("Nghe đối chiếu với bản thu, kiểm tra ô nhịp và hợp âm trước khi dùng.")}</p><button className={`button ${score.review_status === 'reviewed' ? 'secondary' : 'primary'} full-width review-button`} disabled={disabled || dirty || score.review_status === 'reviewed'} onClick={() => void saveScore(true)}><CheckCircle2 size={16}/>{score.review_status === 'reviewed' ? t("Đã kiểm tra bản nhạc") : t("Xác nhận đã kiểm tra")}</button>{dirty && <p className="field-help">{t("Lưu thay đổi trước khi xuất hoặc chuyển giọng.")}</p>}{savedScore?.review_status !== 'reviewed' && <p className="export-locked">{t("Xác nhận đã kiểm tra để mở tải xuống.")}</p>}{activeJob && <p className="export-locked" role="status">{t("Đang phân tích — chưa thể tải file.")}</p>}<div className="export-options"><label className="field">{t("Phạm vi xuất")}<select value={exportScope} onChange={e => setExportScope(e.target.value as 'full' | 'range')}><option value="full">{t("Toàn bộ bài hát (")}{measureCount}{t(" ô nhịp)")}</option><option value="range">{t("Trích đoạn theo ô nhịp")}</option></select></label>{exportScope === 'range' && <div className="field-pair"><label className="field">{t("Từ ô nhịp")}<input type="number" min="1" max={measureCount || 1} value={exportBarStart} onChange={e => setExportBarStart(e.target.value)}/></label><label className="field">{t("Đến ô nhịp")}<input type="number" min="1" max={measureCount || 1} placeholder={String(measureCount || 1)} value={exportBarEnd} onChange={e => setExportBarEnd(e.target.value)}/></label></div>}<div className="export-checkbox-group"><label className="checkbox-field"><input type="checkbox" checked={includeChords} onChange={e => setIncludeChords(e.target.checked)}/>{t("Kèm ký hiệu hợp âm")}</label><label className="checkbox-field"><input type="checkbox" checked={includeLyrics} onChange={e => setIncludeLyrics(e.target.checked)}/>{t("Kèm lời bài hát (nếu có)")}</label><label className="checkbox-field"><input type="checkbox" checked={accompaniment} onChange={e => setAccompaniment(e.target.checked)}/>{t("Thêm hợp âm đệm vào MIDI")}</label></div></div><div className="export-list">{([['musicxml', 'MusicXML', t("Sửa tiếp trong phần mềm ký âm")], ['midi', 'MIDI', t("Nghe lại hoặc mở trong DAW")], ['pdf', 'PDF', t("Bản in A4 trực tiếp từ trình duyệt")], ['abc', 'score.abc', t("File ABC notation 2.1, tiêu chuẩn text")]] as const).map(([format, label, description]) => <button key={format} title={savedScore?.review_status !== 'reviewed' ? t("Cần xác nhận kiểm tra ở trên để mở tải xuống") : dirty ? t("Cần lưu thay đổi trước khi tải file") : ''} disabled={disabled || dirty || savedScore?.review_status !== 'reviewed'} onClick={() => void download(format)}><div><strong>{label}</strong><small>{t(description)}</small></div>{busy === format ? <LoaderCircle className="spin" size={17}/> : <ArrowDownToLine size={17}/>}</button>)}</div></CollapsibleSection></>}
        {score && !analysisMode && <CollapsibleSection storageKey="inspector-history" className="inspector-section activity-history" title={<div className="section-title"><h3>{t("Lịch sử kiểm tra & xuất file")}</h3><span className="count">{activityHistory.length}/10</span></div>}>{activityHistory.length ? <ol>{activityHistory.map(item => <li key={item.id}><strong>{item.kind === 'review' ? t("Đã kiểm tra bản nhạc") : t("Đã xuất {0}", { "0": item.outputFilename || item.format || '' })}</strong><span>{item.projectTitle} · {item.audioName} · r{item.revision}</span><small>{new Date(item.createdAt).toLocaleString(settings.language === 'en' ? 'en-US' : 'vi-VN')}</small></li>)}</ol> : <p className="field-help">{t("Chưa có kết quả kiểm tra hoặc tệp đã xuất trên trình duyệt này.")}</p>}</CollapsibleSection>}
        <div className="inspector-note"><FileMusic size={18}/><p><strong>{t("Lead sheet")}</strong>{t(" gồm một dòng giai điệu và ký hiệu hợp âm. Chép bè riêng cho từng nhạc cụ sẽ được mở rộng sau.")}</p></div>
      </aside>
    </div>
  </div>;
}
