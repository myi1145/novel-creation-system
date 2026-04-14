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




export interface StoryPlanning {
  id: string;
  project_id: string;
  worldview: string;
  main_outline: string;
  volume_plan: string;
  core_seed_summary: string;
  planning_status: 'draft' | 'confirmed';
  last_update_source: string;
  created_at: string;
  updated_at: string;
}

export interface StoryPlanningUpsertPayload {
  worldview: string;
  main_outline: string;
  volume_plan: string;
  core_seed_summary: string;
  planning_status: 'draft' | 'confirmed';
}
export interface CharacterCard {
  id: number;
  project_id: string;
  name: string;
  aliases: string[];
  role_position: string;
  profile: string;
  personality_keywords: string[];
  relationship_notes: string;
  current_status: string;
  first_appearance_chapter?: number | null;
  last_update_source: string;
  is_canon: boolean;
  created_at: string;
  updated_at: string;
}

export interface TerminologyCard {
  id: number;
  project_id: string;
  term: string;
  term_type: string;
  definition: string;
  usage_rules: string;
  examples: string[];
  first_appearance_chapter?: number | null;
  last_update_source: string;
  is_canon: boolean;
  created_at: string;
  updated_at: string;
}


export interface FactionCard {
  id: number;
  project_id: string;
  name: string;
  aliases: string[];
  faction_type: string;
  description: string;
  core_members: string[];
  territory: string;
  stance: string;
  goals: string;
  relationship_notes: string;
  current_status: string;
  first_appearance_chapter?: number | null;
  last_update_source: string;
  is_canon: boolean;
  created_at: string;
  updated_at: string;
}

export interface LocationCard {
  id: number;
  project_id: string;
  name: string;
  aliases: string[];
  location_type: string;
  description: string;
  region: string;
  key_features: string[];
  related_factions: string[];
  narrative_role: string;
  current_status: string;
  first_appearance_chapter?: number | null;
  last_update_source: string;
  is_canon: boolean;
  created_at: string;
  updated_at: string;
}
