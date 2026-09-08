"""Bounded, non-recursive warming driven only by foreground map requests."""
from collections import OrderedDict
from contextlib import contextmanager
import threading
import time

SOURCES = ('osm', 'dem', 'amenities', 'boundaries', 'waterways', 'landcover', 'trails', 'recreation')
MIN_ZOOM = dict(osm=0, dem=3, amenities=10, boundaries=8, waterways=6, landcover=6, trails=5, recreation=10)

def neighborhood(z, x, y):
    """A one-tile halo and the four children; never expand recursively."""
    coordinates = [(z, x, y)]
    coordinates += [(z, (x+dx) % 2**z, y+dy) for dx, dy in
                    ((-1,0),(1,0),(0,-1),(0,1),(-1,-1),(1,-1),(-1,1),(1,1))]
    if 10 <= z < 14:
        coordinates += [(z+1, x*2+dx, y*2+dy) for dx in (0,1) for dy in (0,1)]
    for zoom, col, row in coordinates:
        if not 0 <= row < 2**zoom:
            continue
        for source in SOURCES:
            # Broad overviews must not trigger expensive continent-sized overlays.
            if MIN_ZOOM[source] <= zoom <= (13 if source=='dem' else 14) and (source == 'osm' or zoom >= 10):
                yield source, zoom, col, row

class ViewportWarmer:
    def __init__(self, render, cached, valid, limit=1024, ttl=600, clock=time.monotonic, quiet_seconds=2):
        self.render, self.cached, self.valid = render, cached, valid
        self.limit, self.ttl, self.clock = limit, ttl, clock
        self.condition = threading.Condition()
        self.quiet_seconds=quiet_seconds
        self.foreground_active=0
        self.last_foreground=float("-inf")
        self.pending = OrderedDict()
        self.active = set()
        self.cooldown = OrderedDict()
        self.stopped = False
        self.completed = self.failed = self.dropped = 0
        self.errors = []
        self.threads = []

    @contextmanager
    def foreground(self):
        with self.condition:
            self.foreground_active+=1
        try:yield
        finally:
            with self.condition:
                self.foreground_active-=1
                self.last_foreground=self.clock()
                self.condition.notify_all()

    def observe(self, z, x, y):
        now = self.clock()
        with self.condition:
            if self.stopped:
                return
            for key in neighborhood(z, x, y):
                source, zoom, col, row = key
                if not self.valid(zoom, col, row, source) or self.cached(key):
                    continue
                if key in self.active or self.cooldown.get(key, 0) > now:
                    continue
                self.pending[key] = now + self.ttl
                self.pending.move_to_end(key)
                while len(self.pending) > self.limit:
                    self.pending.popitem(last=False)
                    self.dropped += 1
            self.condition.notify_all()

    @staticmethod
    def lane(key):
        return 'terrain' if key[0] in ('osm','dem') else key[0]

    def take(self, lane):
        now = self.clock()
        with self.condition:
            if self.foreground_active or now-self.last_foreground<self.quiet_seconds:return None
            for key, deadline in reversed(list(self.pending.items())):
                if deadline < now:
                    del self.pending[key]
                    self.dropped += 1
                elif self.lane(key) == lane:
                    del self.pending[key]
                    self.active.add(key)
                    return key

    def run(self, lane):
        while True:
            with self.condition:
                if self.stopped:
                    return
                key = self.take(lane)
                if key is None:
                    self.condition.wait(timeout=1)
                    continue
            try:
                if not self.cached(key):
                    self.render(key)
                with self.condition:
                    self.completed += 1
            except Exception as exc:
                with self.condition:
                    self.failed += 1
                    self.cooldown[key] = self.clock() + 120
                    self.cooldown.move_to_end(key)
                    while len(self.cooldown) > self.limit:
                        self.cooldown.popitem(last=False)
                    self.errors = (self.errors + [{'tile':list(key),'error':str(exc)[:200]}])[-5:]
            finally:
                with self.condition:
                    self.active.discard(key)

    def start(self):
        for lane in ('terrain','amenities','boundaries','waterways','landcover','trails','recreation'):
            thread = threading.Thread(target=self.run, args=(lane,), daemon=True, name='warm-'+lane)
            self.threads.append(thread)
            thread.start()

    def stop(self):
        with self.condition:
            self.stopped = True
            self.pending.clear()
            self.condition.notify_all()

    def status(self):
        with self.condition:
            return {'status':'stopped' if self.stopped else 'running', 'queued':len(self.pending),
                    'active':[list(key) for key in self.active], 'completed':self.completed,
                    'failed':self.failed, 'dropped':self.dropped, 'recentErrors':list(self.errors),
                    'foregroundActive':self.foreground_active,'idleSeconds':min(86400,max(0,self.clock()-self.last_foreground)),'quietSeconds':self.quiet_seconds,'queueLimit':self.limit, 'expirySeconds':self.ttl}
