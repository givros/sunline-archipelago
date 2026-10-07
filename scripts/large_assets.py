"""Store large originals in ordinary Git chunks and restore verified exact bytes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'large-assets.json'
CHUNK_SIZE = 48 * 1024 * 1024
EXCLUDED = {'.git', 'node_modules', 'dist', 'tools_py', '__pycache__', 'large-assets'}


def digest(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def contained(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or path == root.resolve():
        raise ValueError(f'Invalid asset path: {relative}')
    return path


def pack() -> None:
    records = []
    for path in sorted((ROOT / 'artifacts').rglob('*')):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in EXCLUDED for part in relative.parts):
            continue
        if path.suffix in {'.blend1', '.blend2', '.log', '.tmp'} or path.stat().st_size <= CHUNK_SIZE:
            continue
        parts = []
        total_hash = hashlib.sha256()
        folder = ROOT / 'large-assets' / relative
        folder.mkdir(parents=True, exist_ok=True)
        with path.open('rb') as stream:
            index = 0
            while data := stream.read(CHUNK_SIZE):
                target = folder / f'{index:04d}.part'
                part_hash = hashlib.sha256(data).hexdigest()
                if not target.exists() or digest(target) != part_hash:
                    target.write_bytes(data)
                total_hash.update(data)
                parts.append({'path': target.relative_to(ROOT).as_posix(), 'bytes': len(data), 'sha256': part_hash})
                index += 1
        records.append({'path': relative.as_posix(), 'bytes': path.stat().st_size,
                        'sha256': total_hash.hexdigest(), 'parts': parts})
    MANIFEST.write_text(json.dumps({'version': 1, 'chunk_bytes': CHUNK_SIZE,
                                  'encoding': 'raw; no compression or quality change', 'files': records}, indent=2) + '\n', encoding='utf-8')
    ignore = ROOT / '.gitignore'
    marker = '# Generated large-asset paths\n'
    text = ignore.read_text(encoding='utf-8').split(marker)[0].rstrip() + '\n\n' + marker
    ignore.write_text(text + ''.join('/' + item['path'] + '\n' for item in records), encoding='utf-8')
    print(f'Packed {len(records)} files into {sum(len(r["parts"]) for r in records)} lossless parts.')


def restore(destination: Path, prefix: str, verify_only: bool) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    selected = [item for item in manifest['files'] if item['path'].startswith(prefix)]
    if not selected:
        raise ValueError(f'No assets match prefix: {prefix!r}')
    for item in selected:
        output = contained(destination, item['path'])
        if not verify_only and output.exists():
            if output.stat().st_size == item['bytes'] and digest(output) == item['sha256']:
                print(f'Already verified: {item["path"]}')
                continue
            raise FileExistsError(f'Refusing to overwrite a modified asset: {output}')
        temporary = output.with_name(output.name + '.restore.tmp')
        if not verify_only:
            output.parent.mkdir(parents=True, exist_ok=True)
            if temporary.exists():
                raise FileExistsError(f'Incomplete restore already exists: {temporary}')
        combined = hashlib.sha256()
        size = 0
        target = None
        try:
            if not verify_only:
                target = temporary.open('xb')
            for part in item['parts']:
                source = contained(ROOT, part['path'])
                data = source.read_bytes()
                if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                    raise ValueError(f'Corrupt asset part: {part["path"]}')
                combined.update(data)
                size += len(data)
                if target:
                    target.write(data)
            if size != item['bytes'] or combined.hexdigest() != item['sha256']:
                raise ValueError(f'Asset reconstruction mismatch: {item["path"]}')
            if target:
                target.close()
                target = None
                temporary.replace(output)
        finally:
            if target:
                target.close()
        print(f'Verified exact bytes: {item["path"]}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['pack', 'restore', 'verify'])
    parser.add_argument('--prefix', default='')
    parser.add_argument('--destination', type=Path, default=ROOT)
    args = parser.parse_args()
    if args.command == 'pack':
        pack()
    else:
        restore(args.destination.resolve(), args.prefix, args.command == 'verify')
