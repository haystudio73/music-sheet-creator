export type ActivityKind = 'review' | 'export';

export interface ActivityHistoryEntry {
  id: string;
  kind: ActivityKind;
  projectId: string;
  projectTitle: string;
  audioName: string;
  audioDuration: number;
  revision: number;
  createdAt: string;
  format?: 'musicxml' | 'midi' | 'pdf' | 'abc';
  outputFilename?: string;
}

export const ACTIVITY_HISTORY_KEY = 'studio_check_export_history_v1';
export const ACTIVITY_HISTORY_LIMIT = 10;

const normalizeEntry = (value: unknown): ActivityHistoryEntry | null => {
  if (!value || typeof value !== 'object') return null;
  const item = value as Partial<ActivityHistoryEntry>;
  const valid = (item.kind === 'review' || item.kind === 'export')
    && typeof item.id === 'string'
    && typeof item.projectId === 'string'
    && typeof item.projectTitle === 'string'
    && typeof item.audioName === 'string'
    && typeof item.audioDuration === 'number'
    && Number.isFinite(item.audioDuration)
    && typeof item.revision === 'number'
    && Number.isInteger(item.revision)
    && typeof item.createdAt === 'string'
    && (item.kind !== 'export' || (
      ['musicxml', 'midi', 'pdf', 'abc'].includes(item.format || '')
      && typeof item.outputFilename === 'string'
    ));
  if (!valid)
    return null;
  const normalized: ActivityHistoryEntry = {
    id: item.id!,
    kind: item.kind!,
    projectId: item.projectId!,
    projectTitle: item.projectTitle!,
    audioName: item.audioName!,
    audioDuration: item.audioDuration!,
    revision: item.revision!,
    createdAt: item.createdAt!,
  };
  if (item.kind === 'export') {
    normalized.format = item.format;
    normalized.outputFilename = item.outputFilename;
  }
  return normalized;
};

export const readActivityHistory = (): ActivityHistoryEntry[] => {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(ACTIVITY_HISTORY_KEY) || '[]');
    return Array.isArray(parsed)
      ? parsed.map(normalizeEntry).filter((item): item is ActivityHistoryEntry => item !== null).slice(0, ACTIVITY_HISTORY_LIMIT)
      : [];
  } catch {
    return [];
  }
};

export const addActivityHistory = (entry: ActivityHistoryEntry): ActivityHistoryEntry[] => {
  const next = [entry, ...readActivityHistory().filter(item => item.id !== entry.id)].slice(0, ACTIVITY_HISTORY_LIMIT);
  try {
    localStorage.setItem(ACTIVITY_HISTORY_KEY, JSON.stringify(next));
  } catch {}
  return next;
};
