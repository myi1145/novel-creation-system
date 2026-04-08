export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export type Dict = Record<string, unknown>;

export const DEFAULT_GATE_NAMES = ['schema_gate', 'canon_gate', 'narrative_gate', 'style_gate'] as const;
