/**
 * Typed client for the Flask API (`../api/app.py`, documented in
 * `docs/api.md`).
 *
 * In dev, requests go to a relative `/api/...` path which the Vite
 * dev-server proxies to `http://127.0.0.1:5000` (see `vite.config.ts`), so
 * the browser stays same-origin and the API's restricted CORS is never in
 * play. For a deployed build, set `VITE_API_BASE_URL` to the API's origin.
 *
 * Rate limits (from `docs/api.md`): the two coverage endpoints are capped
 * at 10/minute and the RMS estimator at 30/minute. Callers must not fire a
 * request per keystroke - the UI debounces or requires explicit submit
 * (see CLAUDE.md). A `429` surfaces here as an `ApiError` with
 * `status === 429`.
 */
import type {
  ContourRequest,
  ContourResponse,
  EstimateRmsResponse,
  ProfileRequest,
  ProfileResponse,
  ApiErrorBody,
} from '@/types/api';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function isApiErrorBody(value: unknown): value is ApiErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as Record<string, unknown>).error === 'string'
  );
}

async function postJson<TResponse>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<TResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === 'AbortError') throw cause;
    throw new ApiError(
      'Could not reach the coverage API. Is it running on port 5000 (python api/app.py)?',
      0,
    );
  }

  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    // Non-JSON body (e.g. a proxy error page) - fall through to status handling.
  }

  if (!response.ok) {
    const message = isApiErrorBody(payload)
      ? payload.error
      : response.status === 429
        ? 'Rate limit reached (10 requests/minute on coverage endpoints). Wait a moment and retry.'
        : `Request failed (HTTP ${response.status}).`;
    throw new ApiError(message, response.status);
  }

  return payload as TResponse;
}

export function estimateRms(powerKw: number, signal?: AbortSignal): Promise<EstimateRmsResponse> {
  return postJson<EstimateRmsResponse>('/api/estimate-rms', { power_kw: powerKw }, signal);
}

export function coverageContour(
  req: ContourRequest,
  signal?: AbortSignal,
): Promise<ContourResponse> {
  return postJson<ContourResponse>('/api/coverage/contour', req, signal);
}

export function coverageProfile(
  req: ProfileRequest,
  signal?: AbortSignal,
): Promise<ProfileResponse> {
  return postJson<ProfileResponse>('/api/coverage/profile', req, signal);
}

export async function health(signal?: AbortSignal): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/api/health`, { signal });
    return res.ok;
  } catch {
    return false;
  }
}
