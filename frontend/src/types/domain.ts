import { Dict } from './api';

export interface Project { id: string; project_name: string; premise: string; genre_id?: string | null; current_chapter_no: number; }
export interface Genre { genre_id: string; genre_name: string; file_name?: string; tags?: string[]; }
export interface CanonSnapshot extends Dict { id: string; title: string; project_id: string; version_no: number; }
export interface CreativeObject extends Dict { id: string; logical_object_id?: string; object_type?: string; }
export interface ChapterGoal extends Dict { id: string; }
export interface ChapterBlueprint extends Dict { id: string; selected?: boolean; }
export interface SceneCard extends Dict { id: string; }
export interface ChapterDraft extends Dict { id: string; status?: string; }
export interface ChangeSet extends Dict { id: string; status?: string; patch_operations?: Dict[]; }
export interface ChapterWorkbenchState extends Dict {
  project_id: string;
  chapter_no: number;
  goal_id?: string | null;
  blueprint_candidates?: ChapterBlueprint[];
  selected_blueprint_id?: string | null;
  scene_ids?: string[];
  latest_draft?: ChapterDraft | null;
  recovery_stage?: string;
  recovery_hint?: string;
}
