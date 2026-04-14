import { http } from './http';
import type { CanonSnapshot, ChapterBlueprint, ChapterDraft, ChapterGoal, ChapterWorkbenchState, ChangeSet, CreativeObject, Genre, Project, SceneCard } from '../types/domain';
import type { Dict } from '../types/api';

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
