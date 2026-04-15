import { http } from './http';
import type { CanonSnapshot, ChapterBlueprint, ChapterDraft, ChapterGoal, ChapterWorkbenchState, ChangeSet, CharacterCard, CreativeObject, FactionCard, Genre, LocationCard, Project, SceneCard, StoryDirectory, StoryDirectoryUpsertPayload, StoryPlanning, StoryPlanningCardCandidate, StoryPlanningCardCandidateActionResult, StoryPlanningCardCandidateGenerateReport, StoryPlanningCardCandidateType, StoryPlanningUpsertPayload, TerminologyCard } from '../types/domain';
import type { Dict } from '../types/api';


export type StructuredCardType = 'characters' | 'terminologies' | 'factions' | 'locations';
export interface StructuredCardImportError { row: number; field: string; message: string; }
export interface StructuredCardImportSkipped { row: number; reason: string; }
export interface StructuredCardImportReport {
  card_type: 'all' | StructuredCardType;
  total_rows: number;
  created_count: number;
  skipped_count: number;
  error_count: number;
  errors: StructuredCardImportError[];
  skipped: StructuredCardImportSkipped[];
}

async function downloadBlob(path: string): Promise<Blob> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'}${path}`);
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.blob();
}

async function postFormData<T>(path: string, formData: FormData): Promise<T> {
  const response = await fetch(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000/api/v1'}${path}`, {
    method: 'POST',
    body: formData,
  });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const payload = await response.json();
  return payload.data as T;
}

export const api = {
  listProjects: () => http.get<Project[]>('/projects'),
  createProject: (payload: { project_name: string; premise: string; genre_id?: string }) => http.post<Project>('/projects', payload),

  listGenres: () => http.get<Genre[]>('/genres'),
  loadGenre: (payload: { file_name: string }) => http.post<Genre>('/genres/load', payload),

  listCanonSnapshots: (projectId: string) => http.get<CanonSnapshot[]>(`/canon/snapshots?project_id=${projectId}`),
  initCanonSnapshot: (payload: { project_id: string; title: string; initial_rules: Dict[]; initial_characters: Dict[] }) =>
    http.post<CanonSnapshot>('/canon/snapshots/init', payload),

  listObjects: (resource: string, projectId: string) => http.get<CreativeObject[]>(`/objects/${resource}?project_id=${projectId}`),
  createObject: (resource: string, payload: Dict) => http.post<CreativeObject>(`/objects/${resource}`, payload),
  objectHistory: (resource: string, projectId: string, logicalObjectId: string) =>
    http.get<CreativeObject[]>(`/objects/${resource}/history?project_id=${projectId}&logical_object_id=${logicalObjectId}`),
  proposeObjectUpdate: (resource: string, logicalObjectId: string, payload: Dict) =>
    http.post<ChangeSet>(`/objects/${resource}/${logicalObjectId}/changesets/update`, payload),
  proposeObjectRestore: (resource: string, logicalObjectId: string, payload: Dict) =>
    http.post<ChangeSet>(`/objects/${resource}/${logicalObjectId}/changesets/restore`, payload),
  proposeObjectRetire: (resource: string, logicalObjectId: string, payload: Dict) =>
    http.post<ChangeSet>(`/objects/${resource}/${logicalObjectId}/changesets/retire`, payload),

  createGoal: (payload: Dict) => http.post<ChapterGoal>('/chapters/goals', payload),
  getChapterWorkbenchState: (projectId: string, chapterNo: number) =>
    http.get<ChapterWorkbenchState>(`/chapters/workbench-state?project_id=${projectId}&chapter_no=${chapterNo}`),
  generateBlueprints: (payload: Dict) => http.post<ChapterBlueprint[]>('/chapters/blueprints/generate', payload),
  listBlueprints: (projectId: string, chapterGoalId?: string) =>
    http.get<ChapterBlueprint[]>(`/chapters/blueprints?project_id=${projectId}${chapterGoalId ? `&chapter_goal_id=${chapterGoalId}` : ''}`),
  getBlueprint: (projectId: string, blueprintId: string) =>
    http.get<ChapterBlueprint>(`/chapters/blueprints/${blueprintId}?project_id=${projectId}`),
  manualEditBlueprint: (blueprintId: string, payload: Dict) => http.patch<ChapterBlueprint>(`/chapters/blueprints/${blueprintId}`, payload),
  getBlueprintStateHistory: (projectId: string, blueprintId: string) =>
    http.get<Dict[]>(`/chapters/blueprints/${blueprintId}/state-history?project_id=${projectId}`),
  selectBlueprint: (payload: Dict) => http.post<ChapterBlueprint>('/chapters/blueprints/select', payload),
  decomposeScenes: (payload: Dict) => http.post<SceneCard[]>('/chapters/scenes/decompose', payload),
  getScene: (projectId: string, sceneId: string) => http.get<SceneCard>(`/chapters/scenes/${sceneId}?project_id=${projectId}`),
  manualEditScene: (sceneId: string, payload: Dict) => http.patch<SceneCard>(`/chapters/scenes/${sceneId}`, payload),
  getSceneStateHistory: (projectId: string, sceneId: string) =>
    http.get<Dict[]>(`/chapters/scenes/${sceneId}/state-history?project_id=${projectId}`),
  getDependencyStatus: (payload: { project_id: string; chapter_no?: number; blueprint_id?: string; scene_id?: string }) => {
    const query = new URLSearchParams({ project_id: payload.project_id });
    if (typeof payload.chapter_no === 'number') query.set('chapter_no', String(payload.chapter_no));
    if (payload.blueprint_id) query.set('blueprint_id', payload.blueprint_id);
    if (payload.scene_id) query.set('scene_id', payload.scene_id);
    return http.get<Dict>(`/chapters/dependency-status?${query.toString()}`);
  },
  getReleaseReadiness: (projectId: string, chapterNo: number) =>
    http.get<Dict>(`/chapters/projects/${projectId}/chapters/${chapterNo}/release-readiness`),
  getPublishHistory: (projectId: string, chapterNo: number) =>
    http.get<Dict>(`/chapters/projects/${projectId}/chapters/${chapterNo}/publish-history`),
  getVersionDiff: (projectId: string, chapterNo: number) =>
    http.get<Dict>(`/chapters/projects/${projectId}/chapters/${chapterNo}/version-diff`),
  getPublishedReader: (projectId: string, chapterNo: number) =>
    http.get<Dict>(`/chapters/projects/${projectId}/chapters/${chapterNo}/published-reader`),
  getPublishedMarkdownExportUrl: (projectId: string, chapterNo: number) =>
    `/api/v1/chapters/projects/${projectId}/chapters/${chapterNo}/published-reader/export.md`,
  getPublishedTxtExportUrl: (projectId: string, chapterNo: number) =>
    `/api/v1/chapters/projects/${projectId}/chapters/${chapterNo}/published-reader/export.txt`,
  recomputeDependencies: (payload: Dict) => http.post<Dict>('/chapters/dependency-status/recompute', payload),
  generateDraft: (payload: Dict) => http.post<ChapterDraft>('/chapters/drafts/generate', payload),
  reviseDraft: (payload: Dict) => http.post<ChapterDraft>('/chapters/drafts/revise', payload),
  getDraft: (projectId: string, draftId: string) => http.get<ChapterDraft>(`/chapters/drafts/${draftId}?project_id=${projectId}`),
  manualEditDraft: (draftId: string, payload: Dict) => http.post<ChapterDraft>(`/chapters/drafts/${draftId}/manual-edit`, payload),




  listCharacterCards: (projectId: string) => http.get<CharacterCard[]>(`/projects/${projectId}/character-cards`),
  getCharacterCard: (projectId: string, cardId: number) => http.get<CharacterCard>(`/projects/${projectId}/character-cards/${cardId}`),
  createCharacterCard: (projectId: string, payload: Dict) => http.post<CharacterCard>(`/projects/${projectId}/character-cards`, payload),
  updateCharacterCard: (projectId: string, cardId: number, payload: Dict) => http.patch<CharacterCard>(`/projects/${projectId}/character-cards/${cardId}`, payload),

  listTerminologyCards: (projectId: string) => http.get<TerminologyCard[]>(`/projects/${projectId}/terminology-cards`),
  getTerminologyCard: (projectId: string, cardId: number) => http.get<TerminologyCard>(`/projects/${projectId}/terminology-cards/${cardId}`),
  createTerminologyCard: (projectId: string, payload: Dict) => http.post<TerminologyCard>(`/projects/${projectId}/terminology-cards`, payload),
  updateTerminologyCard: (projectId: string, cardId: number, payload: Dict) => http.patch<TerminologyCard>(`/projects/${projectId}/terminology-cards/${cardId}`, payload),

  listFactionCards: (projectId: string) => http.get<FactionCard[]>(`/projects/${projectId}/faction-cards`),
  getFactionCard: (projectId: string, cardId: number) => http.get<FactionCard>(`/projects/${projectId}/faction-cards/${cardId}`),
  createFactionCard: (projectId: string, payload: Dict) => http.post<FactionCard>(`/projects/${projectId}/faction-cards`, payload),
  updateFactionCard: (projectId: string, cardId: number, payload: Dict) => http.patch<FactionCard>(`/projects/${projectId}/faction-cards/${cardId}`, payload),

  listLocationCards: (projectId: string) => http.get<LocationCard[]>(`/projects/${projectId}/location-cards`),
  getStoryPlanning: (projectId: string) => http.get<StoryPlanning | null>(`/projects/${projectId}/story-planning`),

  generateStoryPlanningCardCandidates: (projectId: string) =>
    http.post<StoryPlanningCardCandidateGenerateReport>(`/projects/${projectId}/story-planning/card-candidates/generate`, {}),
  listStoryPlanningCardCandidates: (
    projectId: string,
    filters?: { status?: 'pending' | 'confirmed' | 'skipped'; card_type?: StoryPlanningCardCandidateType },
  ) => {
    const query = new URLSearchParams();
    if (filters?.status) query.set('status', filters.status);
    if (filters?.card_type) query.set('card_type', filters.card_type);
    const suffix = query.toString();
    return http.get<StoryPlanningCardCandidate[]>(`/projects/${projectId}/story-planning/card-candidates${suffix ? `?${suffix}` : ''}`);
  },
  getStoryPlanningCardCandidate: (projectId: string, candidateId: string) =>
    http.get<StoryPlanningCardCandidate>(`/projects/${projectId}/story-planning/card-candidates/${candidateId}`),
  confirmStoryPlanningCardCandidate: (projectId: string, candidateId: string) =>
    http.post<StoryPlanningCardCandidateActionResult>(`/projects/${projectId}/story-planning/card-candidates/${candidateId}/confirm`, {}),
  skipStoryPlanningCardCandidate: (projectId: string, candidateId: string) =>
    http.post<StoryPlanningCardCandidateActionResult>(`/projects/${projectId}/story-planning/card-candidates/${candidateId}/skip`, {}),

  saveStoryPlanning: (projectId: string, payload: StoryPlanningUpsertPayload) => http.put<StoryPlanning>(`/projects/${projectId}/story-planning`, payload),
  getStoryDirectory: (projectId: string) => http.get<StoryDirectory | null>(`/projects/${projectId}/story-directory`),
  saveStoryDirectory: (projectId: string, payload: StoryDirectoryUpsertPayload) => http.put<StoryDirectory>(`/projects/${projectId}/story-directory`, payload),

  getLocationCard: (projectId: string, cardId: number) => http.get<LocationCard>(`/projects/${projectId}/location-cards/${cardId}`),
  createLocationCard: (projectId: string, payload: Dict) => http.post<LocationCard>(`/projects/${projectId}/location-cards`, payload),
  updateLocationCard: (projectId: string, cardId: number, payload: Dict) => http.patch<LocationCard>(`/projects/${projectId}/location-cards/${cardId}`, payload),


  exportStructuredCardsJson: (projectId: string) => downloadBlob(`/projects/${projectId}/structured-cards/export.json`),
  importStructuredCardsJson: async (projectId: string, fileOrPayload: File | Dict) => {
    const form = new FormData();
    if (fileOrPayload instanceof File) {
      form.append('file', fileOrPayload);
    } else {
      form.append('payload', JSON.stringify(fileOrPayload));
    }
    return postFormData<StructuredCardImportReport>(`/projects/${projectId}/structured-cards/import.json`, form);
  },
  exportStructuredCardsCsv: (projectId: string, cardType: StructuredCardType) =>
    downloadBlob(`/projects/${projectId}/structured-cards/${cardType}/export.csv`),
  importStructuredCardsCsv: async (projectId: string, cardType: StructuredCardType, file: File) => {
    const form = new FormData();
    form.append('file', file);
    return postFormData<StructuredCardImportReport>(`/projects/${projectId}/structured-cards/${cardType}/import.csv`, form);
  },
  downloadStructuredCardsCsvTemplate: (projectId: string, cardType: StructuredCardType) =>
    downloadBlob(`/projects/${projectId}/structured-cards/${cardType}/template.csv`),
  listWorkflowRuns: (projectId: string) => http.get<Dict[]>(`/workflows/runs?project_id=${projectId}`),
  getWorkflowRunDetail: (workflowRunId: string) => http.get<Dict>(`/workflows/runs/${workflowRunId}`),
  pauseWorkflowRun: (payload: Dict) => http.post<Dict>('/workflows/runs/pause', payload),
  resumeWorkflowRun: (payload: Dict) => http.post<Dict>('/workflows/runs/resume', payload),
  manualTakeoverWorkflowRun: (payload: Dict) => http.post<Dict>('/workflows/runs/manual-takeover', payload),

  runGateReview: (payload: Dict) => http.post<{ gate_names: string[]; results: Dict[] }>('/gates/reviews', payload),

  generateDraftChangeSetProposal: (draftId: string, payload: Dict) =>
    http.post<Dict>(`/chapters/drafts/${draftId}/changeset-proposals/generate`, payload),
  listChangeSets: () => http.get<ChangeSet[]>('/changesets'),
  approveChangeSet: (id: string, approved_by: string) => http.post<ChangeSet>(`/changesets/${id}/approve`, { approved_by }),
  rejectChangeSet: (id: string, rejected_by: string, reason: string) => http.post<ChangeSet>(`/changesets/${id}/reject`, { rejected_by, reason }),
  applyChangeSet: (id: string) => http.post<ChangeSet>(`/changesets/${id}/apply`, {}),
  rollbackChangeSet: (id: string, payload: Dict) => http.post<ChangeSet>(`/changesets/${id}/rollback`, payload),

  publishDraft: (payload: Dict) => http.post<Dict>('/chapters/drafts/publish', payload),
  listPublished: (projectId: string) => http.get<Dict[]>(`/chapters/published?project_id=${projectId}`),
  listPublishRecords: (projectId: string) => http.get<Dict[]>(`/chapters/publish-records?project_id=${projectId}`),
  getSummary: (projectId: string, publishedId: string) =>
    http.get<Dict>(`/chapters/published/${publishedId}/summary?project_id=${projectId}`),
  getLatestSummary: (projectId: string) => http.get<Dict | null>(`/chapters/projects/${projectId}/latest-summary`),
};
