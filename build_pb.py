#!/usr/bin/env python3
"""Build index.pb, the protobuf index modern clients read.

index.min.json is the legacy format; Tachimanga and Mihon fetch this one. The
schema is keiyoushi/extensions-source/.github/scripts/index.proto. Encoding it
by hand keeps the repository free of a protobuf runtime dependency, matching
the hand-rolled decoder in build_index.py.
"""
import gzip
import json
from pathlib import Path

from build_index import REPO_BADGE, REPO_BASE_URL, REPO_NAME, REPO_WEBSITE, ROOT, badging

# ContentWarning enum: UNSPECIFIED, SAFE, MIXED, NSFW.
CONTENT_WARNING_MAX = 3


def varint(value):
    if value < 0:
        raise ValueError('Protobuf varints in this schema are non-negative')
    out = bytearray()
    while True:
        byte = value & 127
        value >>= 7
        out.append(byte | 128 if value else byte)
        if not value:
            return bytes(out)


def tag(number, wire):
    return varint(number << 3 | wire)


def scalar(number, value):
    """Encode a varint field, omitting proto3 default values."""
    return b'' if not value else tag(number, 0) + varint(value)


def text(number, value):
    """Encode a string field, omitting proto3 default values."""
    if not value:
        return b''
    encoded = value.encode('utf-8')
    return tag(number, 2) + varint(len(encoded)) + encoded


def message(number, body):
    return tag(number, 2) + varint(len(body)) + body


def source(entry):
    identifier = int(entry['id'])
    if not 0 < identifier <= 2**63 - 1:
        raise ValueError(f'Source id out of range: {identifier}')
    return (scalar(1, identifier) + text(2, entry['name'])
            + text(3, entry['lang']) + text(4, entry['baseUrl']))


def extension(meta, apk):
    warning = meta['contentWarning']
    if not 0 <= warning <= CONTENT_WARNING_MAX:
        raise ValueError(f'{meta["packageName"]}: unknown contentWarning {warning}')
    resources = (text(1, f'{REPO_BASE_URL}/apk/{apk.name}')
                 + text(2, f'{REPO_BASE_URL}/icon/{meta["packageName"]}.png')
                 + text(501, f'{REPO_BASE_URL}/apk/{apk.with_suffix(".jar").name}'))
    return (text(1, meta['name']) + text(2, meta['packageName']) + message(3, resources)
            + text(4, meta['extensionLib']) + scalar(5, meta['versionCode'])
            + text(6, meta['versionName']) + scalar(7, warning)
            + b''.join(message(8, source(s)) for s in meta['sources']))


def build_pb():
    extensions = b''
    count = 0
    for apk in sorted((ROOT / 'apk').glob('*.apk')):
        info, _ = badging(apk)
        meta = json.loads((ROOT / 'metadata' / f'{info["pkg"]}.json').read_text(encoding='utf-8'))
        if meta['versionName'] != info['version'] or meta['packageName'] != info['pkg']:
            raise ValueError(f'{apk.name}: metadata does not match the APK')
        if not (ROOT / 'apk' / apk.with_suffix('.jar').name).exists():
            raise ValueError(f'{apk.name}: jar missing; run build_jars.py first')
        extensions += message(1, extension(meta, apk))
        count += 1
    if not count:
        raise ValueError('No APKs to index')
    contact = text(1, REPO_WEBSITE) + text(2, REPO_WEBSITE)
    index = (text(1, REPO_NAME) + text(2, REPO_BADGE)
             + text(3, (ROOT / 'signing-certificate.sha256').read_text(encoding='utf-8').strip())
             + message(4, contact) + message(101, extensions))
    output = ROOT / 'index.pb'
    temporary = output.with_suffix('.pb.tmp')
    # mtime=0 keeps rebuilds byte-reproducible.
    temporary.write_bytes(gzip.compress(index, mtime=0))
    temporary.replace(output)
    print(f'{output.name}: {count} extensions, {output.stat().st_size} bytes')


if __name__ == '__main__':
    build_pb()
