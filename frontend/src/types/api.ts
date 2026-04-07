export interface ApiResponse<T> {
  success: boolean;
  message: string;
  data: T;
}

export type Dict = Record<string, unknown>;
