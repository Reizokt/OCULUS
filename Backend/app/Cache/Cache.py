import hashlib, json, logging, os, threading, time
from datetime import datetime, timezone
import redis

log = logging.getLogger("cache")
_PREFIX = "mi"
_mem: dict[str, tuple[float, str]] = {}
_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()

try:
    _r = redis.Redis.from_url(
        os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        decode_responses=True, socket_connect_timeout=1, socket_timeout=2,
    )
    _r.ping()
except Exception as e:
    log.warning("Redis unavailable (%s) -> in-memory fallback", e)
    _r = None


def make_key(ns: str, **params) -> str:
    raw = json.dumps(params, sort_keys=True, default=str)
    return f"{_PREFIX}:{ns}:{hashlib.sha1(raw.encode()).hexdigest()[:12]}"


def _read(key: str):
    if _r:
        try:
            raw = _r.get(key)
            return json.loads(raw) if raw else None
        except redis.RedisError as e:
            log.warning("redis get failed: %s", e)
    item = _mem.get(key)
    if item and item[0] > time.time():
        return json.loads(item[1])
    return None


def _write(key: str, entry: dict, ttl: int):
    raw = json.dumps(entry, default=str)
    if _r:
        try:
            _r.set(key, raw, ex=ttl)
            return
        except redis.RedisError as e:
            log.warning("redis set failed: %s", e)
    _mem[key] = (time.time() + ttl, raw)


def _lock_for(key: str) -> threading.Lock:
    with _locks_guard:
        return _locks.setdefault(key, threading.Lock())


def resolve(key: str, ttl: int, fetch, force: bool = False):
    """Returns (entry, hit). entry = {"data":..., "fetched_at":...}"""
    if not force:
        e = _read(key)
        if e is not None:
            return e, True                      # 1+2: cache hit -> return it
    with _lock_for(key):                        # stops 10 requests = 10 API calls
        if not force:
            e = _read(key)                      # someone may have filled it while we waited
            if e is not None:
                return e, True
        data = fetch()                          # 3+4: miss/expired -> real call
        entry = {"data": data, "fetched_at": datetime.now(timezone.utc).isoformat()}
        _write(key, entry, ttl)                 # if fetch() raises, nothing is cached
        return entry, False


def get_or_fetch(key: str, ttl: int, fetch, force: bool = False):
    return resolve(key, ttl, fetch, force)[0]["data"]

if __name__ == "__main__":
    print("Redis connection:", _r.ping() if _r else "Redis unavailable")

    key = make_key("test", symbol="BBCA.JK")

    entry, hit = resolve(
        key,
        ttl=60,
        fetch=lambda: {"message": "Hello Redis"}
    )

    print("Data:", entry["data"])
    print("Cache hit:", hit)