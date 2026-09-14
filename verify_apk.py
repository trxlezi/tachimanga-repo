#!/usr/bin/env python3
"""Verify signing, manifest and DEX identities without rewriting an APK."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

from build_index import ROOT, android_tool, badging, varint


def dex_inventory(data):
    if not data.startswith(b'dex\n'):
        raise ValueError('Unsupported DEX container')
    def uint(offset):
        return struct.unpack_from('<I', data, offset)[0]
    string_count, string_offset = uint(56), uint(60)
    strings = []
    for i in range(string_count):
        offset = uint(string_offset + 4 * i)
        _, start = varint(data, offset)
        end = data.index(0, start)
        strings.append(data[start:end].decode('utf-8', errors='replace'))
    types = [strings[uint(uint(68) + i * 4)] for i in range(uint(64))]
    classes = [types[uint(uint(100) + i * 32)] for i in range(uint(96))]
    methods = []
    for i in range(uint(88)):
        owner, _, name = struct.unpack_from('<HHI', data, uint(92) + i * 8)
        methods.append((types[owner], strings[name]))
    return classes, methods


def verify(apk):
    apk = Path(apk)
    meta, badge = badging(apk)
    if meta['minSdk'] != 21:
        raise ValueError(f'{apk.name}: minSdk must be 21')
    signature = subprocess.check_output([android_tool('apksigner'), 'verify', '--verbose',
                                        '--print-certs', '--min-sdk-version', '21', str(apk)], encoding='utf-8')
    digest = re.search(r'certificate SHA-256 digest: (\w+)', signature)[1]
    expected = ROOT / 'signing-certificate.sha256'
    if not expected.exists():
        raise ValueError('Missing pinned signing-certificate.sha256')
    if expected.read_text().strip().lower() != digest.lower():
        raise ValueError('Signing key differs from the permanent repository identity')
    classes, methods = [], []
    with zipfile.ZipFile(apk) as archive, tempfile.TemporaryDirectory() as temporary:
        for name in archive.namelist():
            if re.fullmatch(r'classes\d*\.dex', name):
                data = archive.read(name)
                dc, dm = dex_inventory(data)
                classes.extend(dc)
                methods.extend(dm)
                dexfile = Path(temporary) / name
                dexfile.write_bytes(data)
                subprocess.run([android_tool('dexdump'), str(dexfile)], check=True, stdout=subprocess.DEVNULL)
    if not classes:
        raise ValueError('APK has no DEX classes')
    forbidden = [(c, m) for c, m in methods if c == 'Lorg/jsoup/select/Elements;' and m in ('selectFirst', 'expectFirst')]
    if forbidden:
        raise ValueError(f'Incompatible method references: {forbidden}')
    if any(c.startswith('Lkeiyoushi/source/Generated') for c in classes):
        raise ValueError('Old generated entry point still present')
    if 'Lkeiyoushi/source/TachimangaEntryPoint;' not in classes:
        raise ValueError('Personal entry point missing')
    manifest = subprocess.check_output([android_tool('aapt2'), 'dump', 'xmltree', str(apk),
                                        '--file', 'AndroidManifest.xml'], encoding='utf-8')
    if 'keiyoushi.source.TachimangaEntryPoint' not in manifest:
        raise ValueError('Manifest does not reference the personal entry point')
    source_classes = [c for c in classes if c.startswith('Leu/kanade/tachiyomi/extension/')
                      and not c.endswith('/BuildConfig;')]
    if not source_classes:
        raise ValueError('Original source classes are missing')
    if meta['pkg'].endswith('.ragnascans'):
        if 'Leu/kanade/tachiyomi/extension/es/ragnascans/RagnaScans;' not in classes:
            raise ValueError('RagnaScans class missing')
    return dict(apk=apk.name, sha256=hashlib.sha256(apk.read_bytes()).hexdigest(),
                **meta, certificateSha256=digest, classCount=len(classes),
                sourceClasses=source_classes, elementsSelectFirstReferences=0,
                entryPoint='keiyoushi.source.TachimangaEntryPoint', manifestEntryPoint='verified',
                oldGeneratedClassPresent=False, dexdump='passed', signatureVerification='passed',
                limitation='Static APK checks; iOS/OpenJ9 and live sites not tested')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apks', nargs='+', type=Path)
    args = parser.parse_args()
    output = ROOT / 'verification'
    output.mkdir(exist_ok=True)
    for apk in args.apks:
        result = verify(apk)
        (output / f'{apk.stem}.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        print(f'{apk.name}: minSdk=21, signature OK, source classes preserved, Elements.selectFirst=0')
