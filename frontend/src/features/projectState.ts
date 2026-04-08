export type ProjectChainState = {
  currentChapterNo: number;
  goalId: string;
  blueprintId: string;
  draftId: string;
  publishedChapterId: string;
  hasPendingChangeset: boolean;
  hasAttentionRun: boolean;
  hasBlockedRun: boolean;
  latestWorkflowRunId: string;
};

const DEFAULT_STATE: ProjectChainState = {
  currentChapterNo: 1,
  goalId: '',
  blueprintId: '',
  draftId: '',
  publishedChapterId: '',
  hasPendingChangeset: false,
  hasAttentionRun: false,
  hasBlockedRun: false,
  latestWorkflowRunId: '',
};

function safeJsonParse(raw: string | null): Record<string, unknown> | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
    return parsed as Record<string, unknown>;
  } catch {
    return null;
  }
}

export function getProjectChainState(projectId: string): ProjectChainState {
  if (!projectId) return DEFAULT_STATE;

  const chapterNo = Number(window.localStorage.getItem(`workbench:${projectId}:lastChapterNo`) || '1');
  const currentChapterNo = Number.isFinite(chapterNo) && chapterNo > 0 ? chapterNo : 1;
  const chapterPayload = safeJsonParse(window.localStorage.getItem(`workbench:${projectId}:${currentChapterNo}`));

  const goalId = typeof chapterPayload?.goalId === 'string' ? chapterPayload.goalId : '';
  const blueprintId = typeof chapterPayload?.blueprintId === 'string' ? chapterPayload.blueprintId : '';
  const draftId =
    (typeof chapterPayload?.draftId === 'string' && chapterPayload.draftId) ||
    window.localStorage.getItem(`workbench:${projectId}:lastDraftId`) ||
    '';

  const publishedChapterId = window.localStorage.getItem(`published:${projectId}:lastPublishedChapterId`) || '';

  return {
    ...DEFAULT_STATE,
    currentChapterNo,
    goalId,
    blueprintId,
    draftId,
    publishedChapterId,
  };
}

export function saveProjectChainState(projectId: string, patch: Partial<ProjectChainState>) {
  const current = getProjectChainState(projectId);
  const next = { ...current, ...patch };
  window.localStorage.setItem(`project:${projectId}:chainState`, JSON.stringify(next));
}

export function mergeProjectChainState(projectId: string, patch: Partial<ProjectChainState>): ProjectChainState {
  const base = getProjectChainState(projectId);
  const persisted = safeJsonParse(window.localStorage.getItem(`project:${projectId}:chainState`));
  const merged: ProjectChainState = {
    ...base,
    ...(persisted || {}),
    ...patch,
  } as ProjectChainState;
  window.localStorage.setItem(`project:${projectId}:chainState`, JSON.stringify(merged));
  return merged;
}

export function readMergedProjectChainState(projectId: string): ProjectChainState {
  const base = getProjectChainState(projectId);
  const persisted = safeJsonParse(window.localStorage.getItem(`project:${projectId}:chainState`));
  return {
    ...base,
    ...(persisted || {}),
  } as ProjectChainState;
}
