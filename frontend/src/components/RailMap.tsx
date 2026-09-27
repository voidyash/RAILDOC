import { useEffect, useMemo, useState } from 'react';
import { MapContainer, Marker, Polyline, Popup, TileLayer, useMap } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import {
  getAssets,
  getBlockWindows,
  getCorridors,
  getCurrentPlan,
  getTasks,
  getTrains,
} from '../api/client';
import type {
  Asset, BlockWindow, MaintenanceBlock, MaintenanceTask, Train,
} from '../types';

/** Deterministic pseudo-geolocation: each corridor gets a base coordinate
 * (roughly along real Indian rail cities) and every KM offset maps to a
 * small lat/lng delta so assets land along the line. Demo visualization
 * only — not a survey-grade GIS. */
const CORRIDOR_GEO: Record<string, { base: [number, number]; end: [number, number]; name: string }> = {
  'C-07': { base: [28.61, 77.21], end: [27.20, 77.90], name: 'Delhi-Mumbai Main Line (Delhi-Palwal)' },
  'C-12': { base: [25.32, 82.97], end: [25.45, 81.83], name: 'Howrah-Delhi Line (Mughal Sarai-Allahabad)' },
  'C-19': { base: [21.15, 79.09], end: [21.70, 76.30], name: 'Chennai-Mumbai Line (Nagpur-Bhusawal)' },
};

const FALLBACK_GEO = { base: [28.61, 77.21] as [number, number], end: [27.20, 77.90] as [number, number], name: 'Corridor' };

function kmToLatLng(corridorId: string, km: number, maxKm = 200): [number, number] {
  const g = CORRIDOR_GEO[corridorId] ?? FALLBACK_GEO;
  const t = Math.min(1, Math.max(0, km / maxKm));
  return [
    g.base[0] + (g.end[0] - g.base[0]) * t,
    g.base[1] + (g.end[1] - g.base[1]) * t,
  ];
}

function parseKm(location: string): number {
  const m = /KM\s*(\d+(?:\.\d+)?)/i.exec(location || '');
  return m ? parseFloat(m[1]) : 100;
}

const MARKER_COLORS: Record<string, string> = {
  green: '#16a34a',
  yellow: '#d97706',
  red: '#dc2626',
  blue: '#2563eb',
};

function pinIcon(color: string): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<span style="display:block;width:12px;height:12px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,.4)"></span>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

function FitBounds({ points }: { points: [number, number][] }) {
  const map = useMap();
  useEffect(() => {
    if (points.length > 1) {
      map.fitBounds(L.latLngBounds(points), { padding: [30, 30] });
    }
  }, [map, points]);
  return null;
}

export default function RailMap() {
  const [corridors, setCorridors] = useState<Array<{ corridor_id: string; name: string; section: string }>>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [tasks, setTasks] = useState<MaintenanceTask[]>([]);
  const [trains, setTrains] = useState<Train[]>([]);
  const [blocks, setBlocks] = useState<MaintenanceBlock[]>([]);
  const [windows, setWindows] = useState<BlockWindow[]>([]);
  const [showTrains, setShowTrains] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [c, a, t, tr, plan, w] = await Promise.all([
          getCorridors(),
          getAssets(),
          getTasks(),
          getTrains(),
          getCurrentPlan(),
          getBlockWindows(),
        ]);
        setCorridors(c);
        setAssets(a);
        setTasks(t);
        setTrains(tr);
        setBlocks((plan?.blocks ?? []) as MaintenanceBlock[]);
        setWindows(w);
      } catch {
        /* leave panels empty on failure */
      }
    })();
  }, []);

  // Build per-asset status map from defect tasks (Pending/Defect = red,
  // anything scheduled = yellow, else green by availability).
  const assetStatus = useMemo(() => {
    const map: Record<string, 'green' | 'yellow' | 'red'> = {};
    for (const t of tasks) {
      if (t.task_type === 'Defect' && t.status === 'Pending') {
        map[t.asset_id] = 'red';
      } else if (t.status === 'Scheduled' && map[t.asset_id] !== 'red') {
        map[t.asset_id] = 'yellow';
      }
    }
    return map;
  }, [tasks]);

  const defectCount = useMemo(() => Object.values(assetStatus).filter((s) => s === 'red').length, [assetStatus]);

  const corridorLines = useMemo(
    () =>
      corridors.map((c) => {
        const g = CORRIDOR_GEO[c.corridor_id] ?? FALLBACK_GEO;
        return { id: c.corridor_id, path: [g.base, g.end] as [number, number][], name: g.name };
      }),
    [corridors]
  );

  const assetPoints = useMemo(
    () =>
      assets.map((a) => {
        const corridor = a.corridor_id;
        const km = parseKm(a.location);
        const status = assetStatus[a.asset_id] ?? 'green';
        return {
          id: a.asset_id,
          corridor,
          km,
          pos: kmToLatLng(corridor, km),
          status,
          criticality: a.criticality,
          assetType: a.asset_type,
          location: a.location,
        };
      }),
    [assets, assetStatus]
  );

  const blockMarkers = useMemo(
    () =>
      blocks.map((b) => ({
        id: b.block_id,
        pos: kmToLatLng(b.corridor_id, parseKm('KM 100.0')),
        corridor: b.corridor_id,
        start: b.start_time,
        end: b.end_time,
        status: b.status,
      })),
    [blocks]
  );

  const trainMarkers = useMemo(
    () =>
      showTrains
        ? trains.slice(0, 60).map((t, i) => ({
            id: `${t.train_id}-${i}`,
            pos: kmToLatLng(t.corridor_id, 40 + (i % 8) * 18),
            trainId: t.train_id,
            type: t.train_type,
            time: t.scheduled_time,
          }))
        : [],
    [trains, showTrains]
  );

  const allPoints = useMemo(
    () => [...corridorLines.flatMap((c) => c.path), ...assetPoints.map((a) => a.pos)],
    [corridorLines, assetPoints]
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-900 dark:text-gray-100">Geospatial View</h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-0.5">
            Demonstration visualization — asset positions are illustrative, mapped by corridor and KM marker.
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2">
          <input type="checkbox" checked={showTrains} onChange={(e) => setShowTrains(e.target.checked)} />
          Show trains
        </label>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <LegendCard label="Healthy assets" count={assetPoints.filter((a) => a.status === 'green').length} color={MARKER_COLORS.green} />
        <LegendCard label="Maintenance scheduled" count={assetPoints.filter((a) => a.status === 'yellow').length} color={MARKER_COLORS.yellow} />
        <LegendCard label="Critical defects" count={defectCount} color={MARKER_COLORS.red} />
        <LegendCard label="Planned blocks" count={blocks.length} color={MARKER_COLORS.blue} />
      </div>

      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden" style={{ height: 520 }}>
        <MapContainer
          center={[24.5, 79.5]}
          zoom={5}
          scrollWheelZoom
          style={{ height: '100%', width: '100%' }}
        >
          {/* Same OpenStreetMap basemap in both themes: CARTO's dark tiles now
              carry an "API key required" watermark, so we avoid them. */}
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds points={allPoints} />

          {corridorLines.map((c) => (
            <Polyline key={c.id} positions={c.path} pathOptions={{ color: '#475569', weight: 3, opacity: 0.7 }}>
              <Popup>
                <b>{c.id}</b>
                <br />
                {c.name}
              </Popup>
            </Polyline>
          ))}

          {assetPoints.map((a) => (
            <Marker key={a.id} position={a.pos} icon={pinIcon(MARKER_COLORS[a.status])}>
              <Popup>
                <div className="text-xs">
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{a.id}</p>
                  <p className="text-gray-500 dark:text-gray-400">{a.assetType} · {a.location}</p>
                  <p className="mt-1">
                    Corridor {a.corridor} · criticality {Math.round(a.criticality)}
                  </p>
                  <p className={`mt-1 font-medium ${a.status === 'red' ? 'text-red-600 dark:text-red-400' : a.status === 'yellow' ? 'text-amber-600 dark:text-amber-300' : 'text-green-600 dark:text-green-400'}`}>
                    {a.status === 'red' ? 'Critical defect open' : a.status === 'yellow' ? 'Maintenance scheduled' : 'Operational'}
                  </p>
                </div>
              </Popup>
            </Marker>
          ))}

          {blockMarkers.map((b) => (
            <Marker key={b.id} position={b.pos} icon={pinIcon(MARKER_COLORS.blue)}>
              <Popup>
                <div className="text-xs">
                  <p className="font-semibold text-gray-900 dark:text-gray-100">{b.id}</p>
                  <p>Corridor {b.corridor} · {b.start}–{b.end}</p>
                  <p className="text-blue-600 dark:text-blue-400 font-medium">{b.status}</p>
                </div>
              </Popup>
            </Marker>
          ))}

          {trainMarkers.map((t) => (
            <Marker key={t.id} position={t.pos} icon={pinIcon('#7c3aed')}>
              <Popup>
                <div className="text-xs">
                  <p className="font-semibold">{t.trainId}</p>
                  <p>{t.type} · sched {t.time}</p>
                </div>
              </Popup>
            </Marker>
          ))}
        </MapContainer>
      </div>

      <p className="text-[11px] text-gray-400 dark:text-gray-300">
        {windows.length} block windows configured across {corridors.length} corridors. Map layer is for
        visualization/testing only (PRD §14) — not survey-grade inspection data.
      </p>
    </div>
  );
}

function LegendCard({ label, count, color }: { label: string; count: number; color: string }) {
  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 px-4 py-3 flex items-center gap-3">
      <span className="w-3 h-3 rounded-full" style={{ background: color }} />
      <div>
        <p className="text-lg font-bold text-gray-900 dark:text-gray-100 leading-none">{count}</p>
        <p className="text-[11px] text-gray-500 dark:text-gray-400 mt-1">{label}</p>
      </div>
    </div>
  );
}
