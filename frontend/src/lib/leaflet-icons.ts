/**
 * Leaflet's default marker icon paths are resolved relative to the CSS at
 * runtime, which breaks under a bundler (Vite) - markers render as broken
 * images. Re-point them at the actual bundled asset URLs once, at startup.
 *
 * The app currently uses `CircleMarker` for the transmitter (no image
 * needed), but this keeps `<Marker>` working if it's added later.
 */
import L from 'leaflet';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

delete (L.Icon.Default.prototype as { _getIconUrl?: unknown })._getIconUrl;

L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
});
