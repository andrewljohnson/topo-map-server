import maplibregl from 'maplibre-gl';
import { installDeviceTerrain } from '../terrainRuntime';
import { terrainWorkerSource } from '../terrainWorkerSource';

type DemSpec = {
  tileUrl: string;
  minZoom: number;
  maxZoom: number;
  bounds: [number, number, number, number];
  tileSize: number;
  attribution?: string;
  coverage?: Record<string, number[][]>;
};
export async function addReviewContours(
  map: maplibregl.Map,
  release: string,
  signal: AbortSignal,
) {
  const response = await fetch(
    `/releases/${encodeURIComponent(release)}/metadata`,
    { signal },
  );
  if (!response.ok) throw Error('Contour metadata unavailable');
  const metadata = (await response.json()) as { tilesets?: { dem?: DemSpec } };
  const spec = metadata.tilesets?.dem;
  if (!spec) throw Error('No elevation data for this review');
  if (signal.aborted) return;
  const style: maplibregl.StyleSpecification = {
    version: 8,
    sources: {},
    layers: [
      {
        id: 'contours',
        type: 'line',
        source: 'contours',
        'source-layer': 'contour',
        paint: { 'line-color': '#633e1d' },
      },
      {
        id: 'contour-index',
        type: 'line',
        source: 'contours',
        'source-layer': 'contour',
        paint: { 'line-color': '#4b2b13' },
      },
      {
        id: 'contour-labels',
        type: 'symbol',
        source: 'contours',
        'source-layer': 'contour',
        minzoom: 13,
        layout: {
          'symbol-placement': 'line',
          'text-field': ['concat', ['to-string', ['get', 'ele_ft']], ' ft'],
          'text-font': ['Arial', 'sans-serif'],
          'text-size': 11,
        },
        paint: {
          'text-color': '#422912',
          'text-halo-color': '#fff8e7',
          'text-halo-width': 1.2,
        },
      },
    ],
  };
  const terrain = installDeviceTerrain(
    maplibregl,
    style,
    { ...spec, renderBounds: undefined },
    async (key, controller) => {
      const [z, x, y] = key.split('/');
      const url = spec.tileUrl
        .replace('{z}', z)
        .replace('{x}', x)
        .replace('{y}', y);
      const r = await fetch(url, { signal: controller.signal });
      if (!r.ok) throw Error(`DEM ${r.status}`);
      return r.arrayBuffer();
    },
    terrainWorkerSource,
  );
  if (!terrain) return;
  try {
    // Reuse DEM-generated contours without tint or hillshade over the photography.
    map.addSource('contours', style.sources.contours);
    for (const layer of style.layers.filter(
      (l) => 'source' in l && l.source === 'contours',
    )) {
      if (layer.type === 'line') {
        layer.paint = {
          ...layer.paint,
          'line-opacity': layer.id === 'contour-index' ? 0.85 : 0.6,
        };
      }
      map.addLayer(layer, 'source-0');
    }
    return () => terrain.dispose();
  } catch (error) {
    terrain.dispose();
    throw error;
  }
}
