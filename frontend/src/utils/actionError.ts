import { ApiError } from '../api/http';

export function toActionErrorMessage(actionLabel: string, error: unknown, suggestion?: string): string {
  const fallback = `${actionLabel}失败。${suggestion || '请稍后重试。'}`;
  if (error instanceof ApiError) {
    const parts = [`${actionLabel}失败`];
    if (suggestion) {
      parts.push(suggestion);
    }
    if (error.code) {
      parts.push(`错误码：${error.code}`);
    } else if (error.status) {
      parts.push(`状态码：HTTP ${error.status}`);
    }
    return `${parts.join(' ')}。`;
  }
  if (error instanceof Error && error.message) {
    return `${fallback} 原始错误：${error.message}`;
  }
  return fallback;
}
