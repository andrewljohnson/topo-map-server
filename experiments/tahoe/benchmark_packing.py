#!/usr/bin/env python3
"""Compare packing against a trusted local Git commit using identical retained inputs.

Example: python experiments/tahoe/benchmark_packing.py --baseline-ref 6706795
 --parents /tmp/pilot-parents.json --derived PATH/derived --output /tmp/packing.json

The comparison executes the repository's historical build.py. No tiles are
published or overwritten. Direct recreation is prepared with current source
code once per parent and passed to both packers. Raw-source cache misses may
still be fetched by that preparation. CPU and task elapsed time are separate.
"""
import argparse, importlib, json, multiprocessing, re, subprocess, sys, time, types
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'experiments/tahoe'))
import build
import mapbox_vector_tile as mvt

baseline = None
derived = None


def initialize(code, directory):
    global baseline, derived
    baseline = types.ModuleType('packing_baseline')
    # Historical build.py resolves data paths relative to its repository path.
    baseline.__file__ = str(ROOT / 'experiments/tahoe/build.py')
    exec(compile(code, '<trusted Git packing baseline>', 'exec'), baseline.__dict__)
    derived = Path(directory)


def compare(parent):
    x, y = parent
    children = []
    for source in build.SOURCES:
        if source == 'recreation':
            module = importlib.import_module(build.SOURCES[source])
            blob = module.render_tile(12, x, y, detail_zoom=14, extent=build.EXTENT)
            children.append((source, None, None, blob))
        else:
            children.extend((source, dx, dy,
                (derived / source / '14' / str(x * 4 + dx) / f'{y * 4 + dy}.pbf').read_bytes())
                for dy in range(4) for dx in range(4))
    results = {}
    # Alternate order so first-call effects do not always favor the candidate.
    for name, module in ([('before', baseline), ('after', build)] if (x + y) % 2
                         else [('after', build), ('before', baseline)]):
        wall, cpu = time.perf_counter(), time.process_time()
        blob, counts = module.merge_tiles(children)
        results[name] = (blob, counts, time.perf_counter() - wall, time.process_time() - cpu)
    a, b = results['before'], results['after']
    assert a[1] == b[1], f'Feature counts changed at {parent}'
    assert mvt.decode(a[0]) == mvt.decode(b[0]), f'Decoded content changed at {parent}'
    return {'key': list(parent), 'bytes': len(b[0]), 'byteIdentical': a[0] == b[0],
            'decodedIdentical': True, 'beforeTaskSeconds': a[2], 'afterTaskSeconds': b[2],
            'beforeCpuSeconds': a[3], 'afterCpuSeconds': b[3]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline-ref', required=True, help='Trusted local commit SHA')
    parser.add_argument('--parents', required=True, type=Path)
    parser.add_argument('--derived', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--workers', type=int, default=16, choices=range(1, 33))
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{7,40}', args.baseline_ref):
        parser.error('Use a trusted local commit SHA, not an arbitrary script or ref expression')
    parents = json.loads(args.parents.read_text())
    if not 1 <= len(parents) <= 512 or any(len(p) != 2 or any(type(v) is not int or not 0 <= v < 4096 for v in p) for p in parents):
        parser.error('Use 1–512 valid z12 parents')
    code = subprocess.check_output(['git', 'show', args.baseline_ref + ':experiments/tahoe/build.py'], cwd=ROOT, text=True)
    started = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers, mp_context=multiprocessing.get_context('spawn'),
                             initializer=initialize, initargs=(code, str(args.derived.resolve()))) as pool:
        rows = list(pool.map(compare, parents))
    report = {'baselineCommit': args.baseline_ref, 'parents': len(rows), 'workers': args.workers,
              'wallSeconds': time.perf_counter() - started, 'byteIdentical': sum(r['byteIdentical'] for r in rows),
              **{key: sum(r[key] for r in rows) for key in ('beforeTaskSeconds', 'afterTaskSeconds', 'beforeCpuSeconds', 'afterCpuSeconds')},
              'rows': rows}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, indent=2))


if __name__ == '__main__':
    main()
