"""Keep newly acquired source windows inside an explicitly disposable job spool.

Existing canonical inputs always win and are never moved or removed here.
Without TOPO_SCRATCH_ROOT, normal persistent server caching is unchanged.
The publisher may prune only its own verified shard directory after upload.
"""
import os
from pathlib import Path


def working_path(path):
    path=Path(path)
    scratch=os.environ.get('TOPO_SCRATCH_ROOT')
    if not scratch or path.exists():return path
    root=Path(os.environ.get('TILE_DATA_DIR',Path(__file__).parent/'data')).resolve()
    original=path.resolve();scratch=Path(scratch).resolve()
    # Explicit external caches and already redirected paths keep their contract.
    if not original.is_relative_to(root) or original.is_relative_to(scratch):return path
    return scratch/'source-cache'/original.relative_to(root)
