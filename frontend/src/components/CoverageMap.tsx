import { Fragment, useEffect, useMemo } from 'react';
import {
  MapContainer,
  TileLayer,
  Polygon,
  Polyline,
  CircleMarker,
  Tooltip,
  useMap,
} from 'react-leaflet';
import type { LatLngBoundsExpression } from 'leaflet';

import type { ContourResponse } from '@/types/api';
import { CONTOUR_COLORS, CONTOUR_LABELS } from '@/lib/coverage';

interface Props {
  txLat: number;
  txLon: number;
  /** null until the first successful calculation. */
  result: ContourResponse | null;
}

interface ReachedPoint {
  lat: number;
  lon: number;
  label: string;
  bearingDeg: number;
  distanceKm: number;
}

interface Ring {
  label: string;
  color: string;
  points: ReachedPoint[];
  reached: number;
  total: number;
}

/** Fit the map to the transmitter + every reached endpoint whenever they
 *  change. A child component so it has `useMap` access. */
function FitBounds({ bounds }: { bounds: LatLngBoundsExpression | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds) map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 });
  }, [map, bounds]);
  return null;
}

export function CoverageMap({ txLat, txLon, result }: Props) {
  const rings = useMemo<Ring[]>(() => {
    if (!result) return [];
    return Object.entries(result.contours).map(([label, bearings]) => ({
      label,
      color: CONTOUR_COLORS[label] ?? '#dc2626',
      reached: bearings.filter((b) => b.distance_km !== null).length,
      total: bearings.length,
      points: bearings
        .filter(
          (b): b is typeof b & { lat: number; lon: number; distance_km: number } =>
            b.lat !== null && b.lon !== null && b.distance_km !== null,
        )
        .map((b) => ({
          lat: b.lat,
          lon: b.lon,
          label: b.label,
          bearingDeg: b.bearing_deg,
          distanceKm: b.distance_km,
        })),
    }));
  }, [result]);

  const bounds = useMemo<LatLngBoundsExpression | null>(() => {
    const pts: [number, number][] = [[txLat, txLon]];
    for (const ring of rings) for (const p of ring.points) pts.push([p.lat, p.lon]);
    if (pts.length < 2) return null;
    const lats = pts.map((p) => p[0]);
    const lons = pts.map((p) => p[1]);
    return [
      [Math.min(...lats), Math.min(...lons)],
      [Math.max(...lats), Math.max(...lons)],
    ];
  }, [rings, txLat, txLon]);

  const anyPoints = rings.some((r) => r.points.length > 0);

  return (
    <div className="relative h-full w-full">
      <MapContainer center={[txLat, txLon]} zoom={9} scrollWheelZoom className="h-full w-full">
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <CircleMarker
          center={[txLat, txLon]}
          radius={6}
          pathOptions={{ color: '#111827', fillColor: '#111827', fillOpacity: 1 }}
        >
          <Tooltip>
            Transmitter · {txLat.toFixed(4)}, {txLon.toFixed(4)}
          </Tooltip>
        </CircleMarker>

        {rings.map((ring) => {
          const latlngs = ring.points.map((p) => [p.lat, p.lon] as [number, number]);
          const dashed = ring.label === 'night';
          return (
            <Fragment key={ring.label}>
              {/* Radial spokes from the transmitter to each reached endpoint -
                  visible even when too few bearings succeeded to close a ring. */}
              {ring.points.map((p) => (
                <Polyline
                  key={`${ring.label}-spoke-${p.bearingDeg}`}
                  positions={[
                    [txLat, txLon],
                    [p.lat, p.lon],
                  ]}
                  pathOptions={{ color: ring.color, weight: 1, opacity: 0.35 }}
                />
              ))}

              {/* The contour itself: a filled polygon if >=3 bearings reached
                  the target, otherwise an open polyline through what we have. */}
              {latlngs.length >= 3 ? (
                <Polygon
                  positions={latlngs}
                  pathOptions={{
                    color: ring.color,
                    weight: 2,
                    fillColor: ring.color,
                    fillOpacity: 0.12,
                    dashArray: dashed ? '6 4' : undefined,
                  }}
                >
                  <Tooltip sticky>
                    {CONTOUR_LABELS[ring.label] ?? ring.label} · {ring.reached}/{ring.total}{' '}
                    bearings
                  </Tooltip>
                </Polygon>
              ) : latlngs.length === 2 ? (
                <Polyline
                  positions={latlngs}
                  pathOptions={{
                    color: ring.color,
                    weight: 2,
                    dashArray: dashed ? '6 4' : undefined,
                  }}
                />
              ) : null}

              {/* Endpoint dots, always drawn so a single successful bearing
                  still shows something. */}
              {ring.points.map((p) => (
                <CircleMarker
                  key={`${ring.label}-pt-${p.bearingDeg}`}
                  center={[p.lat, p.lon]}
                  radius={4}
                  pathOptions={{ color: ring.color, fillColor: ring.color, fillOpacity: 0.9 }}
                >
                  <Tooltip>
                    {CONTOUR_LABELS[ring.label] ?? ring.label} · {p.label} (
                    {p.bearingDeg.toFixed(0)}
                    °) · {p.distanceKm.toFixed(1)} km
                  </Tooltip>
                </CircleMarker>
              ))}
            </Fragment>
          );
        })}

        <FitBounds bounds={bounds} />
      </MapContainer>

      {rings.length > 0 && (
        <div className="bg-background/90 absolute right-3 bottom-3 z-[1000] space-y-1 rounded-md border p-2 text-xs shadow-sm">
          {rings.map((ring) => (
            <div key={ring.label} className="flex items-center gap-2">
              <span
                className="inline-block h-2 w-4 rounded-sm"
                style={{ backgroundColor: ring.color }}
              />
              <span>
                {CONTOUR_LABELS[ring.label] ?? ring.label}{' '}
                <span className="text-muted-foreground">
                  ({ring.reached}/{ring.total})
                </span>
              </span>
            </div>
          ))}
          {!anyPoints && (
            <p className="text-muted-foreground max-w-[12rem] pt-1">
              No bearing reached its target — see Results for the per-bearing errors.
            </p>
          )}
        </div>
      )}
    </div>
  );
}
