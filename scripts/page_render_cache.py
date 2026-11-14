"""Optional content addressed memoization at each renderer's original stage.

Cached HTML is data, never a replacement for page inventory or final validation.
No finalized site is used as an input to an earlier stage.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import stat
import tempfile

VERSION = 1
MAX_ENTRY_BYTES = 16 * 1024 * 1024
MAX_CACHE_BYTES = 512 * 1024 * 1024
MAX_CACHE_ENTRIES = 10000


def encoded(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def code_dependencies(extra=()):
    # Rendering helpers import one another, including policy and identity rules.
    # A conservative digest of local Python code prevents an omitted transitive
    # helper from silently retaining old HTML. Exact external source bytes join it.
    scripts = Path(__file__).resolve().parent
    paths = sorted(scripts.glob('*.py'))
    files = [('scripts/' + p.name, hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths]
    files.extend((f'external/{i}/{Path(p).name}', hashlib.sha256(Path(p).read_bytes()).hexdigest())
                 for i, p in enumerate(extra))
    return digest({'files': files, 'python': list(sys.version_info[:3]), 'version': VERSION})


def valid_value(value, expected_paths):
    if expected_paths is None:
        return type(value) is str
    return (type(value) is dict and set(value) == set(expected_paths)
            and all(type(path) is str and re.fullmatch(r'/(?:[a-z0-9-]+/)*', path)
                    and type(content) is str for path, content in value.items()))


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.render-', delete=False) as stream:
            name = stream.name
            stream.write(encoded(value))
        os.replace(name, path)
    finally:
        if name is not None:
            Path(name).unlink(missing_ok=True)


def has_symlink(path):
    return any(part.is_symlink() for part in (path, *path.parents))


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate render cache key')
        result[key] = value
    return result


class RenderCache:
    def __init__(self, stage, *, root=None, report=None, extra_code=(), code=None, public_root=None):
        configured = os.environ.get('KC_BUILD_CACHE_DIR') if root is None else root
        self.root = None
        self.disabled_reason = ''
        if configured:
            configured_raw = Path(configured).absolute()
            # Resolve platform aliases such as /tmp, while refusing a cache
            # root or cache member that is itself a symlink.
            candidate = configured_raw.parent.resolve() / configured_raw.name / 'renders' / 'v1'
            public = Path(public_root or Path.cwd() / '_site').resolve()
            configured_path = Path(configured).resolve()
            if configured_path == public or public in configured_path.parents:
                raise ValueError('Render cache must be outside the public output')
            if has_symlink(candidate):
                self.disabled_reason = 'symlink cache root'
            else:
                self.root = candidate.resolve()
        self.stage = stage
        self.report = Path(report) if report else None
        self.code = (code if code is not None else code_dependencies(extra_code)) if self.root else ''
        self.counts = dict(hits=0, misses=0, corrupt=0, writes=0, disabled=0, writeErrors=0)

    def render(self, renderer, inputs, generate, *, expected_paths=None):
        if self.root is None:
            self.counts['disabled'] += 1
            return generate()
        key = digest({'version': VERSION, 'stage': self.stage, 'renderer': renderer,
                      'code': self.code, 'inputs': inputs, 'paths': sorted(expected_paths) if expected_paths is not None else None})
        target = self.root / (key + '.json')
        try:
            if has_symlink(target):
                raise ValueError('Render cache entry must not use symlinks')
            info = target.stat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Render cache entry must be a regular file')
            if info.st_size > MAX_ENTRY_BYTES:
                raise ValueError('Oversized render cache entry')
            record = json.loads(target.read_text(encoding='utf-8'), object_pairs_hook=unique_object)
            if type(record) is not dict:
                raise ValueError('Render cache entry must be an object')
            value = record['value']
            if (record.get('version') != VERSION or record.get('key') != key
                    or record.get('sha256') != digest(value) or not valid_value(value, expected_paths)):
                raise ValueError('Invalid render cache entry')
            self.counts['hits'] += 1
            return value
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            self.counts['corrupt'] += 1
        self.counts['misses'] += 1
        value = generate()
        if not valid_value(value, expected_paths):
            raise ValueError('Renderer returned an unexpected output shape or page inventory')
        record = {'version': VERSION, 'key': key, 'sha256': digest(value), 'value': value}
        if len(encoded(record)) <= MAX_ENTRY_BYTES:
            try:
                if has_symlink(self.root):
                    raise OSError('Render cache directory changed to a symlink')
                atomic_json(target, record)
                self.counts['writes'] += 1
            except OSError:
                self.counts['writeErrors'] += 1
        return value

    def wrap(self, renderer, function, *, context):
        @functools.wraps(function)
        def cached(*args, **kwargs):
            return self.render(renderer, {'args': args, 'kwargs': kwargs, 'context': context()},
                               lambda: function(*args, **kwargs))
        return cached

    def finish(self):
        # Storage maintenance uses age only for eviction, never for validity.
        if self.root and not has_symlink(self.root) and self.root.exists():
            try:
                entries = [(p.stat().st_mtime_ns, p.stat().st_size, p) for p in self.root.glob('*.json') if not p.is_symlink() and p.is_file()]
                size, count = sum(row[1] for row in entries), len(entries)
                for _, length, path in sorted(entries):
                    if size <= MAX_CACHE_BYTES and count <= MAX_CACHE_ENTRIES:
                        break
                    path.unlink(missing_ok=True)
                    size -= length
                    count -= 1
            except OSError:
                pass
        if self.report:
            try:
                try:
                    if self.report.is_symlink() or not self.report.is_file() or self.report.stat().st_size > MAX_ENTRY_BYTES:
                        raise ValueError('Invalid render report file')
                    report = json.loads(self.report.read_text(), object_pairs_hook=unique_object)
                    if type(report) is not dict or report.get('version') != VERSION or type(report.get('stages')) is not dict:
                        raise ValueError('Invalid render report')
                except (OSError, ValueError, RecursionError):
                    report = {'version': VERSION, 'stages': {}}
                report['stages'][self.stage] = dict(self.counts, enabled=self.root is not None, disabledReason=self.disabled_reason)
                atomic_json(self.report, report)
            except OSError:
                pass
        return dict(self.counts, enabled=self.root is not None, disabledReason=self.disabled_reason)
