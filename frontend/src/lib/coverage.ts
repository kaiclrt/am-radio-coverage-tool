/**
 * Front-end domain model for the two composed inputs described in
 * `docs/web_ui_design.md`:
 *
 *   - Target field strength: Primary Service Contour / Day-Night Protection
 *     Contours / Custom Contour
 *   - Power / RMS: Licensed-or-Measured RMS / Estimate from Transmitter Power
 *
 * The two are independent - any target mode pairs with either power mode -
 * so they are modelled as two separate discriminated unions and only
 * combined when building the API request.
 */
import type { ContourRequest } from '@/types/api';

// --- Target field strength -------------------------------------------------

export type TargetMode = 'primary' | 'dayNight' | 'custom';

/** The fixed 1 mV/m primary service contour (47 CFR - see design doc). */
export const PRIMARY_SERVICE_MVM = 1.0;

export interface TargetState {
  mode: TargetMode;
  /** Day-Night mode only, both in mV/m (permit values are often given in
   *  uV/m and must be divided by 1000 - the UI notes this, it does not
   *  convert automatically). */
  dayMvm: string;
  nightMvm: string;
  /** Custom mode only, mV/m. */
  customMvm: string;
}

// --- Power / RMS -------------------------------------------------------

export type PowerMode = 'rms' | 'power';

export interface PowerState {
  mode: PowerMode;
  /** Licensed/measured field intensity at 1 km, mV/m. Also the field the
   *  "Estimate from Power" result is written into - it stays editable so
   *  the user can knock it down for real-world losses. */
  rmsMvm: string;
  /** Transmitter power, kW (Estimate-from-Power mode input). */
  powerKw: string;
}

// --- Whole form -----------------------------------------------------

export interface CoverageFormState {
  txLat: string;
  txLon: string;
  freqKhz: string;
  nRadials: string;
  maxSearchKm: string;
  /** Distance between terrain-conductivity samples along each radial, km.
   *  Lower = finer but more network lookups on the API side. */
  sampleIntervalKm: string;
  target: TargetState;
  power: PowerState;
}

/** The API rejects a request whose
 *  `n_radials × (max_search_km / sample_interval_km)` exceeds this, since
 *  each sample is a live terrain lookup (see docs/api.md "Hardening" #2).
 *  Mirrored here so the UI can warn before the round-trip. */
export const MAX_SAMPLES_PER_REQUEST = 2000;

export const DEFAULT_FORM: CoverageFormState = {
  // Manila, Philippines - the coordinates the propagation engine's own
  // end-to-end test uses (see CHANGELOG.md).
  txLat: '14.6',
  txLon: '121.0',
  freqKhz: '1140',
  // 8 radials × (150 km / 2 km) = 600 samples, well under the API's 2000
  // ceiling. 150 km is comfortably past a typical primary-service contour
  // while keeping samples near land for this coastal example; raise it (and
  // the interval, to stay under budget) for a wider search.
  nRadials: '8',
  maxSearchKm: '150',
  sampleIntervalKm: '2',
  target: { mode: 'primary', dayMvm: '0.5', nightMvm: '2.5', customMvm: '0.5' },
  power: { mode: 'rms', rmsMvm: '223.6', powerKw: '5' },
};

/** Fixed display colours per contour label (also defined as CSS vars in
 *  index.css for the map polygons). */
export const CONTOUR_COLORS: Record<string, string> = {
  primary: '#2563eb',
  day: '#f59e0b',
  night: '#7c3aed',
  custom: '#059669',
};

export const CONTOUR_LABELS: Record<string, string> = {
  primary: 'Primary service (1 mV/m)',
  day: 'Daytime',
  night: 'Nighttime',
  custom: 'Custom',
};

// --- Validation + request building -----------------------------------

export interface BuiltRequest {
  request: ContourRequest;
  /** The RMS actually used - surfaced so the UI can echo it. */
  rmsUsed: number;
}

export class FormValidationError extends Error {}

function num(label: string, raw: string): number {
  const value = Number(raw);
  if (raw.trim() === '' || Number.isNaN(value)) {
    throw new FormValidationError(`${label} must be a number.`);
  }
  return value;
}

/** Turn validated form state into a `/api/coverage/contour` request body.
 *  Throws `FormValidationError` with a user-facing message on bad input;
 *  the API re-validates everything server-side regardless. */
export function buildContourRequest(form: CoverageFormState): BuiltRequest {
  const txLat = num('Transmitter latitude', form.txLat);
  const txLon = num('Transmitter longitude', form.txLon);
  const freqKhz = num('Frequency', form.freqKhz);
  const nRadials = num('Number of radials', form.nRadials);
  const maxSearchKm = num('Max search distance', form.maxSearchKm);
  const sampleIntervalKm = num('Sample interval', form.sampleIntervalKm);

  if (txLat < -90 || txLat > 90)
    throw new FormValidationError('Latitude must be between -90 and 90.');
  if (txLon < -180 || txLon > 180)
    throw new FormValidationError('Longitude must be between -180 and 180.');
  if (freqKhz < 530 || freqKhz > 1710)
    throw new FormValidationError('AM frequency should be between 530 and 1710 kHz.');
  if (nRadials < 1 || nRadials > 360)
    throw new FormValidationError('Number of radials must be between 1 and 360.');
  if (sampleIntervalKm < 0.5)
    throw new FormValidationError('Sample interval must be at least 0.5 km.');

  // Mirror the API's combined-budget guard so the user gets an instant,
  // actionable message instead of a 400 after the request.
  const samples = Math.round((nRadials * maxSearchKm) / sampleIntervalKm);
  if (samples > MAX_SAMPLES_PER_REQUEST)
    throw new FormValidationError(
      `These settings need ~${samples} terrain samples; the API allows ${MAX_SAMPLES_PER_REQUEST}. ` +
        `Lower the radial count, raise the sample interval, or shorten the max search distance.`,
    );

  let rmsUsed: number;
  if (form.power.mode === 'rms') {
    rmsUsed = num('Licensed/measured RMS', form.power.rmsMvm);
  } else {
    // The editable estimated value is what actually gets sent - the raw
    // power figure is only used to seed it (via /api/estimate-rms).
    rmsUsed = num('Estimated field at 1 km', form.power.rmsMvm);
  }
  if (rmsUsed <= 0) throw new FormValidationError('Field intensity at 1 km must be positive.');

  const targets: Record<string, number> = {};
  switch (form.target.mode) {
    case 'primary':
      targets.primary = PRIMARY_SERVICE_MVM;
      break;
    case 'dayNight': {
      const day = num('Daytime target', form.target.dayMvm);
      const night = num('Nighttime target', form.target.nightMvm);
      if (day <= 0 || night <= 0)
        throw new FormValidationError('Day/night targets must be positive (mV/m).');
      targets.day = day;
      targets.night = night;
      break;
    }
    case 'custom': {
      const custom = num('Custom target', form.target.customMvm);
      if (custom <= 0) throw new FormValidationError('Custom target must be positive (mV/m).');
      targets.custom = custom;
      break;
    }
  }

  return {
    rmsUsed,
    request: {
      tx_lat: txLat,
      tx_lon: txLon,
      freq_khz: freqKhz,
      rms_at_1km_mvm: rmsUsed,
      targets,
      n_radials: nRadials,
      max_search_km: maxSearchKm,
      sample_interval_km: sampleIntervalKm,
    },
  };
}
