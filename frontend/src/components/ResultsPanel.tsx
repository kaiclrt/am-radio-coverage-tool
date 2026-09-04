import { useMemo } from 'react';

import type { ContourResponse } from '@/types/api';
import { CONTOUR_COLORS, CONTOUR_LABELS } from '@/lib/coverage';

interface Props {
  result: ContourResponse | null;
  rmsUsed: number | null;
}

export function ResultsPanel({ result, rmsUsed }: Props) {
  const summary = useMemo(() => {
    if (!result) return [];
    return Object.entries(result.contours).map(([label, bearings]) => {
      const reached = bearings.filter((b) => b.distance_km !== null);
      const distances = reached.map((b) => b.distance_km as number);
      return {
        label,
        reached: reached.length,
        total: bearings.length,
        min: distances.length ? Math.min(...distances) : null,
        max: distances.length ? Math.max(...distances) : null,
        avg: distances.length ? distances.reduce((a, b) => a + b, 0) / distances.length : null,
        failures: bearings.filter((b) => b.distance_km === null),
      };
    });
  }, [result]);

  if (!result) {
    return (
      <p className="text-muted-foreground text-sm">
        Enter transmitter details and press <span className="font-medium">Calculate coverage</span>.
      </p>
    );
  }

  return (
    <div className="space-y-4 text-sm">
      {rmsUsed !== null && (
        <p className="text-muted-foreground text-xs">
          RMS used: <span className="font-medium">{rmsUsed} mV/m</span> at 1 km
        </p>
      )}

      {summary.map((s) => (
        <div key={s.label} className="space-y-2">
          <div className="flex items-center gap-2">
            <span
              className="inline-block h-2 w-4 rounded-sm"
              style={{ backgroundColor: CONTOUR_COLORS[s.label] ?? '#dc2626' }}
            />
            <h3 className="font-semibold">{CONTOUR_LABELS[s.label] ?? s.label}</h3>
            <span className="text-muted-foreground text-xs">
              {s.reached}/{s.total} bearings reached target
            </span>
          </div>

          {s.min !== null ? (
            <dl className="grid grid-cols-3 gap-2 text-xs">
              <Stat label="Min" value={`${s.min.toFixed(1)} km`} />
              <Stat label="Mean" value={`${s.avg!.toFixed(1)} km`} />
              <Stat label="Max" value={`${s.max!.toFixed(1)} km`} />
            </dl>
          ) : (
            <p className="text-destructive text-xs">
              No bearing reached this target within the search distance.
            </p>
          )}

          {s.failures.length > 0 && (
            <details className="text-xs">
              <summary className="text-muted-foreground cursor-pointer">
                {s.failures.length} bearing{s.failures.length > 1 ? 's' : ''} did not reach target
              </summary>
              <ul className="mt-1 space-y-0.5 pl-4">
                {s.failures.map((f) => (
                  <li key={f.bearing_deg} className="text-muted-foreground">
                    {f.label} ({f.bearing_deg.toFixed(0)}°): {f.error ?? 'target not reached'}
                  </li>
                ))}
              </ul>
            </details>
          )}

          <details className="text-xs">
            <summary className="text-muted-foreground cursor-pointer">
              Per-bearing distances
            </summary>
            <div className="mt-1 overflow-x-auto">
              <table className="w-full border-collapse">
                <thead>
                  <tr className="text-muted-foreground text-left">
                    <th className="py-1 pr-3 font-medium">Bearing</th>
                    <th className="py-1 pr-3 font-medium">Distance</th>
                    <th className="py-1 font-medium">Endpoint</th>
                  </tr>
                </thead>
                <tbody>
                  {result.contours[s.label].map((b) => (
                    <tr key={b.bearing_deg} className="border-t">
                      <td className="py-1 pr-3">
                        {b.label} ({b.bearing_deg.toFixed(0)}°)
                      </td>
                      <td className="py-1 pr-3">
                        {b.distance_km !== null ? (
                          `${b.distance_km.toFixed(1)} km`
                        ) : (
                          <span className="text-destructive">—</span>
                        )}
                      </td>
                      <td className="text-muted-foreground py-1">
                        {b.lat !== null && b.lon !== null
                          ? `${b.lat.toFixed(3)}, ${b.lon.toFixed(3)}`
                          : ''}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ))}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-muted rounded-md p-2">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="font-semibold">{value}</dd>
    </div>
  );
}
