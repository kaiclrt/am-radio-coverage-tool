/**
 * TypeScript mirrors of the Flask API's request/response shapes.
 *
 * Kept deliberately close to the Python `TypedDict`s in
 * `src/propagation/coverage_map.py` (`ContourResult`, `ProfilePoint`,
 * `ProfileResult`) and the endpoint contracts in `docs/api.md` - the
 * front end continues the type-safety discipline the Python side gets from
 * mypy (see `docs/web_ui_stack.md`).
 */

// --- POST /api/estimate-rms ------------------------------------------------

export interface EstimateRmsRequest {
  power_kw: number;
}

export interface EstimateRmsResponse {
  rms_at_1km_mvm: number;
}

// --- POST /api/coverage/contour -----------------------------------------

export interface ContourRequest {
  tx_lat: number;
  tx_lon: number;
  freq_khz: number;
  rms_at_1km_mvm: number;
  /** One entry (Primary Service / Custom) or two (`day`/`night`), label -> mV/m. */
  targets: Record<string, number>;
  n_radials?: number;
  max_search_km?: number;
  sample_interval_km?: number;
}

/**
 * One bearing's result. On success `distance_km`/`lat`/`lon` are numbers;
 * on a per-bearing failure (target not reached within `max_search_km`)
 * they are `null` and `error` is set. Matches `coverage_contour()`'s
 * partial-failure design - one bad bearing must not break the map render
 * (see CLAUDE.md).
 */
export interface ContourBearing {
  bearing_deg: number;
  label: string;
  distance_km: number | null;
  lat: number | null;
  lon: number | null;
  error?: string;
}

export interface ContourResponse {
  /** Keyed by the same labels passed in `targets`. */
  contours: Record<string, ContourBearing[]>;
}

// --- POST /api/coverage/profile ---------------------------------------

export interface ProfileRequest {
  tx_lat: number;
  tx_lon: number;
  freq_khz: number;
  rms_at_1km_mvm: number;
  n_radials?: number;
  max_distance_km?: number;
  n_points?: number;
  sample_interval_km?: number;
}

export interface ProfilePoint {
  distance_km: number;
  field_mvm: number;
  lat: number;
  lon: number;
}

export interface ProfileBearing {
  bearing_deg: number;
  label: string;
  points: ProfilePoint[];
}

export interface ProfileResponse {
  profile: ProfileBearing[];
}

// --- Errors -------------------------------------------------------------

/** Every non-2xx response body from the API is `{ "error": string }`. */
export interface ApiErrorBody {
  error: string;
}
