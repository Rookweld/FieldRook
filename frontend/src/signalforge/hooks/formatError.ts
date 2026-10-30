import { ApiError } from "../../api";

/**
 * One honest error sentence for a failed backend call, matching the
 * phrasing the M025 workstations already show.
 */
export function formatApiError(e: unknown, what: string): string {
  if (e instanceof ApiError) {
    return `${what} failed (HTTP ${e.status}): ${e.message}`;
  }
  return e instanceof Error ? `${what} failed: ${e.message}` : `${what} failed: ${String(e)}`;
}
