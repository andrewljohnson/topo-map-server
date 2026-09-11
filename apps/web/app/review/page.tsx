'use client';
import Link from 'next/link';
import { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import './review.css';

type Case = {
  id: string;
  name: string;
  region: string;
  kind: string;
  tile: number[];
  center: [number, number];
  agencies: string[];
  overlapM: number;
  shorterCoverage: number;
  url: string;
  sourceIds: string[][];
  geometry: {
    type: 'FeatureCollection';
    features: {
      type: 'Feature';
      properties: Record<string, string | number | boolean | null>;
      geometry:
        | { type: 'LineString'; coordinates: number[][] }
        | { type: 'MultiLineString'; coordinates: number[][][] };
    }[];
  };
};
type Decision = {
  action: string;
  preferredSource?: string;
  reason: string;
  confidence: string;
  updatedAt: string;
};
type Report = { release: string; candidates: Case[] };
const KEY = 'topo-conflict-review-v1';
const actions = [
  ['prefer', 'Same feature — prefer one source'],
  ['separate', 'Keep both — genuinely separate'],
  ['partial', 'Partial overlap — needs a merge'],
  ['neither', 'Neither looks right'],
  ['uncertain', 'Need more evidence'],
];
const colors = ['#007d8a', '#bf4275'];
export default function Review() {
  const [report, setReport] = useState<Report | null>(null),
    [index, setIndex] = useState(0),
    [decisions, setDecisions] = useState<Record<string, Decision>>({}),
    [filter, setFilter] = useState('all'),
    [error, setError] = useState(''),
    [notice, setNotice] = useState(''),
    [dirty, setDirty] = useState(false),
    [context, setContext] = useState(false),
    [visible, setVisible] = useState([true, true]);
  const [action, setAction] = useState(''),
    [preferred, setPreferred] = useState(''),
    [reason, setReason] = useState(''),
    [confidence, setConfidence] = useState('medium');
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (dirty) {
        e.preventDefault();
      }
    };
    window.addEventListener('beforeunload', warn);
    return () => window.removeEventListener('beforeunload', warn);
  }, [dirty]);
  const mapRoot = useRef<HTMLDivElement>(null),
    map = useRef<maplibregl.Map | null>(null),
    file = useRef<HTMLInputElement>(null);
  const c = report?.candidates[index];
  useEffect(() => {
    fetch('/review/candidates.json')
      .then((r) => {
        if (!r.ok) throw Error('Could not load review cases');
        return r.json() as Promise<Report>;
      })
      .then((r: Report) => {
        let loaded: Record<string, Decision> = {};
        try {
          const saved = JSON.parse(localStorage.getItem(KEY) || '{}');
          if (saved.schemaVersion === 1) loaded = saved.decisions || {};
        } catch {
          setError('Could not read saved reviews.');
        }
        setDecisions(loaded);
        setReport(r);
        const id = new URLSearchParams(location.search).get('case');
        const i = r.candidates.findIndex((c) => c.id === id);
        const selected = Math.max(0, i);
        setIndex(selected);
        const item = r.candidates[selected],
          d = loaded[item.id];
        setAction(d?.action || '');
        setPreferred(d?.preferredSource || item.agencies[0]);
        setReason(d?.reason || '');
        setConfidence(d?.confidence || 'medium');
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    if (!c || !mapRoot.current) return;
    history.replaceState(null, '', `?case=${c.id}`);
    const m = new maplibregl.Map({
      container: mapRoot.current,
      attributionControl: false,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#f3f0e8' },
          },
        ],
      },
      center: c.center,
      zoom: 15,
    });
    map.current = m;
    m.addControl(new maplibregl.NavigationControl(), 'top-right');
    m.addControl(
      new maplibregl.AttributionControl({
        customAttribution:
          '<a href="https://www.openstreetmap.org/copyright">© OpenStreetMap contributors</a> · USFS / NPS',
      }),
    );
    m.on('load', () => {
      m.addSource('conflict', { type: 'geojson', data: c.geometry });
      c.agencies.forEach((agency, i) => {
        m.addLayer({
          id: `source-${i}`,
          type: 'line',
          source: 'conflict',
          filter: ['==', ['get', 'agency'], agency],
          paint: {
            'line-color': colors[i],
            'line-width': i === 0 ? 6 : 3,
            'line-opacity': 0.9,
            ...(i === 1 ? { 'line-dasharray': [2, 1] } : {}),
          },
        });
      });
      m.addSource('focus', {
        type: 'geojson',
        data: {
          type: 'Feature',
          properties: {},
          geometry: { type: 'Point', coordinates: c.center },
        },
      });
      m.addLayer({
        id: 'focus',
        type: 'circle',
        source: 'focus',
        paint: {
          'circle-radius': 7,
          'circle-color': '#fff',
          'circle-stroke-color': '#39463e',
          'circle-stroke-width': 2,
          'circle-opacity': 0.5,
        },
      });
    });
    return () => {
      map.current = null;
      m.remove();
    };
  }, [c]);
  function persist(next: Record<string, Decision>) {
    try {
      localStorage.setItem(
        KEY,
        JSON.stringify({
          schemaVersion: 1,
          release: report?.release,
          decisions: next,
        }),
      );
      setDecisions(next);
      setDirty(false);
      setError('');
      return true;
    } catch {
      setError(
        'Browser storage is unavailable or full. This decision was not saved.',
      );
      return false;
    }
  }
  function canLeave() {
    return (
      !dirty || window.confirm('Leave this case without saving your changes?')
    );
  }
  function selectCase(i: number) {
    if (!report) return;
    const item = report.candidates[i],
      d = decisions[item.id];
    setIndex(i);
    setDirty(false);
    setVisible([true, true]);
    setAction(d?.action || '');
    setPreferred(d?.preferredSource || item.agencies[0]);
    setReason(d?.reason || '');
    setConfidence(d?.confidence || 'medium');
    setNotice('');
  }
  function move(delta: number) {
    if (!report || !canLeave()) return;
    for (let n = 1; n <= report.candidates.length; n++) {
      const i =
        (index + delta * n + report.candidates.length * 2) %
        report.candidates.length;
      if (filter === 'all' || !decisions[report.candidates[i].id]) {
        selectCase(i);
        return;
      }
    }
    setNotice('No unreviewed cases remain.');
  }
  function save() {
    if (!c || !action) return;
    if (
      persist({
        ...decisions,
        [c.id]: {
          action,
          ...(action === 'prefer' ? { preferredSource: preferred } : {}),
          reason,
          confidence,
          updatedAt: new Date().toISOString(),
        },
      })
    )
      setNotice(
        'Saved on this device. Export reviews to share or back them up.',
      );
  }
  function exportPayload() {
    return {
      schemaVersion: 1,
      reviewSet: report?.release,
      exportedAt: new Date().toISOString(),
      decisions: report?.candidates
        .filter((c) => decisions[c.id])
        .map((c) => ({
          caseId: c.id,
          release: report.release,
          name: c.name,
          region: c.region,
          tile: c.tile,
          sourceIds: c.sourceIds,
          agencies: c.agencies,
          ...decisions[c.id],
        })),
    };
  }
  async function copyReviews() {
    try {
      await navigator.clipboard.writeText(
        JSON.stringify(exportPayload(), null, 2),
      );
      setNotice('Saved reviews copied. Paste them into our conversation.');
    } catch {
      setError('Clipboard access failed. Use Export reviews instead.');
    }
  }
  function download() {
    const payload = exportPayload();
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(payload, null, 2)], {
        type: 'application/json',
      }),
    );
    const a = document.createElement('a');
    a.href = url;
    a.download = `map-reviews-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  async function importFile(f: File) {
    try {
      const payload = JSON.parse(await f.text());
      if (
        payload.schemaVersion !== 1 ||
        payload.reviewSet !== report?.release ||
        !Array.isArray(payload.decisions)
      )
        throw Error('This file is not a review export for this dataset.');
      const next = { ...decisions };
      let n = 0;
      for (const d of payload.decisions) {
        const match = report!.candidates.find((c) => c.id === d.caseId);
        if (
          !match ||
          !actions.some((a) => a[0] === d.action) ||
          typeof d.reason !== 'string' ||
          !['low', 'medium', 'high'].includes(d.confidence) ||
          !Number.isFinite(Date.parse(d.updatedAt)) ||
          (d.action === 'prefer' && !match.agencies.includes(d.preferredSource))
        )
          throw Error(
            'The file contains an invalid decision. Nothing was imported.',
          );
        if (
          !next[d.caseId] ||
          Date.parse(d.updatedAt) > Date.parse(next[d.caseId].updatedAt)
        ) {
          next[d.caseId] = {
            action: d.action,
            preferredSource: d.preferredSource,
            reason: d.reason,
            confidence: d.confidence,
            updatedAt: d.updatedAt,
          };
          n++;
        }
      }
      if (persist(next)) {
        setNotice(
          `Imported ${n} newer decisions. Select a case to review them.`,
        );
        const d = c && next[c.id];
        if (d) {
          setAction(d.action);
          setPreferred(d.preferredSource || c!.agencies[0]);
          setReason(d.reason);
          setConfidence(d.confidence);
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed');
    }
  }
  const count = report?.candidates.filter((c) => decisions[c.id]).length || 0;
  return (
    <main className="review-shell">
      <header>
        <div>
          <Link href="/">← Map</Link>
          <h1>Source conflict review</h1>
          <p>
            Make your judgment first. We’ll compare it with an independent
            automated review later.
          </p>
        </div>
        <div className="review-tools">
          <strong>
            {count} / {report?.candidates.length || 51} reviewed
          </strong>
          <button onClick={download} disabled={!report}>
            Export reviews
          </button>
          <button onClick={copyReviews} disabled={!report}>
            Copy reviews
          </button>
          <button
            onClick={() => {
              if (canLeave()) file.current?.click();
            }}
          >
            Import
          </button>
          <input
            ref={file}
            type="file"
            accept="application/json"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void importFile(f);
              e.target.value = '';
            }}
          />
        </div>
      </header>
      {error && (
        <p role="alert" className="review-error">
          {error}
        </p>
      )}
      {!c ? (
        <p>Loading review cases…</p>
      ) : (
        <>
          <nav className="review-nav">
            <button onClick={() => move(-1)}>← Previous</button>
            <select
              aria-label="Review case"
              value={index}
              onChange={(e) => {
                if (canLeave()) {
                  selectCase(Number(e.target.value));
                  setNotice('');
                }
              }}
            >
              {report!.candidates.map((v, i) => (
                <option key={v.id} value={i}>
                  {decisions[v.id] ? '✓ ' : ''}
                  {i + 1}. {v.name} · {v.region}
                </option>
              ))}
            </select>
            <button onClick={() => move(1)}>Next →</button>
            <label>
              <input
                type="checkbox"
                checked={filter === 'pending'}
                onChange={(e) =>
                  setFilter(e.target.checked ? 'pending' : 'all')
                }
              />{' '}
              Skip reviewed
            </label>
          </nav>
          <div className="review-body">
            <section className="review-evidence">
              <div className="review-title">
                <h2>{c.name}</h2>
                <span>
                  {c.region} · {c.kind} · Case {index + 1}
                </span>
              </div>
              <div className="review-toggles">
                {c.agencies.map((a, i) => (
                  <label key={a} style={{ color: colors[i] }}>
                    <input
                      type="checkbox"
                      checked={visible[i]}
                      onChange={(e) => {
                        const checked = e.target.checked;
                        setVisible((v) =>
                          v.map((x, j) => (j === i ? checked : x)),
                        );
                        if (map.current?.getLayer(`source-${i}`))
                          map.current.setLayoutProperty(
                            `source-${i}`,
                            'visibility',
                            checked ? 'visible' : 'none',
                          );
                      }}
                    />
                    {a} {i === 0 ? '— solid' : '┄ dashed'}
                  </label>
                ))}
                <button
                  onClick={() =>
                    map.current?.flyTo({ center: c.center, zoom: 15 })
                  }
                >
                  Conflict center
                </button>
                <button
                  onClick={() => {
                    const bounds = new maplibregl.LngLatBounds();
                    function add(v: number[] | number[][] | number[][][]) {
                      if (typeof v[0] === 'number')
                        bounds.extend(v as [number, number]);
                      else (v as number[][] | number[][][]).forEach(add);
                    }
                    c.geometry.features.forEach((f) => {
                      add(f.geometry.coordinates);
                    });
                    if (!bounds.isEmpty())
                      map.current?.fitBounds(bounds, {
                        padding: 45,
                        maxZoom: 17,
                      });
                  }}
                >
                  Fit source fragments
                </button>
              </div>
              <div ref={mapRoot} className="review-map" />
              <p className="review-caption">
                Actual published source geometry, clipped to one z12 tile. Line
                thickness and dashes identify sources; they are not trail
                classifications. The circle marks the detected overlap.
                Tile-edge endpoints are not necessarily trail ends.
              </p>
              <button onClick={() => setContext((v) => !v)}>
                {context ? 'Hide topo context' : 'Show topo context'}
              </button>
              {context && (
                <iframe
                  title="Live topo context"
                  src={c.url}
                  className="review-map"
                  style={{ width: '100%', marginTop: 12 }}
                />
              )}
              <a
                className="review-context"
                href={c.url}
                target="_blank"
                rel="noreferrer"
              >
                Open this location on the live topo map ↗
              </a>
              <details>
                <summary>Evidence and source records</summary>
                <p>
                  {c.overlapM.toLocaleString()} m of proximity overlap ·{' '}
                  {Math.round(c.shorterCoverage * 100)}% of shorter geometry
                  within the detector’s 50 m corridor. This is a candidate, not
                  proof of duplication.
                </p>
                <p>
                  Frozen release: {report!.release}. The live map may change
                  independently.
                </p>
                <pre>
                  {JSON.stringify(
                    c.geometry.features.map((f) => f.properties),
                    null,
                    2,
                  )}
                </pre>
              </details>
            </section>
            <aside>
              <h2>Your decision</h2>
              <p>
                Are these the same physical feature, distinct paths, or partly
                overlapping?
              </p>
              <fieldset>
                <legend>What should happen?</legend>
                {actions.map(([value, label]) => (
                  <label className="review-choice" key={value}>
                    <input
                      type="radio"
                      name="action"
                      value={value}
                      checked={action === value}
                      onChange={() => {
                        setAction(value);
                        setDirty(true);
                        setNotice('Unsaved changes');
                      }}
                    />
                    {label}
                  </label>
                ))}
              </fieldset>
              {action === 'prefer' && (
                <label className="review-field">
                  Preferred geometry source
                  <select
                    value={preferred}
                    onChange={(e) => {
                      setPreferred(e.target.value);
                      setDirty(true);
                      setNotice('Unsaved changes');
                    }}
                  >
                    {c.agencies.map((a) => (
                      <option key={a}>{a}</option>
                    ))}
                  </select>
                </label>
              )}
              <label className="review-field">
                Confidence
                <select
                  value={confidence}
                  onChange={(e) => {
                    setConfidence(e.target.value);
                    setDirty(true);
                    setNotice('Unsaved changes');
                  }}
                >
                  <option value="low">Low — tentative</option>
                  <option value="medium">Medium</option>
                  <option value="high">High — clear evidence</option>
                </select>
              </label>
              <label className="review-field">
                Reason / which sections?{' '}
                <textarea
                  rows={5}
                  value={reason}
                  onChange={(e) => {
                    setReason(e.target.value);
                    setDirty(true);
                    setNotice('Unsaved changes');
                  }}
                  placeholder="What convinced you? For partial merges, describe which branch or section to retain. Links to evidence are welcome."
                />
              </label>
              <button className="review-save" disabled={!action} onClick={save}>
                Save decision
              </button>
              <button
                disabled={!decisions[c.id]}
                onClick={() => {
                  const next = { ...decisions };
                  delete next[c.id];
                  if (persist(next)) {
                    setAction('');
                    setReason('');
                    setNotice('Decision cleared.');
                  }
                }}
              >
                Clear saved decision
              </button>
              <output>
                {notice ||
                  (decisions[c.id]
                    ? 'Saved decision loaded.'
                    : 'Not reviewed yet.')}
              </output>
              <p className="review-caption">
                Saved in this browser only. Export before switching devices or
                clearing storage. Reviews do not change the public map. Use
                “Save decision” before moving to another case.
              </p>
            </aside>
          </div>
        </>
      )}
    </main>
  );
}
