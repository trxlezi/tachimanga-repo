#!/usr/bin/env python3
"""Build the legacy Tachimanga index from APK metadata and official source IDs."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parent
OFFICIAL_URL = 'https://raw.githubusercontent.com/keiyoushi/extensions/repo/index.pb'
REPO_NAME = 'Tachimanga Personal Extensions'
REPO_BADGE = 'TACHI'
REPO_WEBSITE = 'https://github.com/trxlezi/tachimanga-repo'
REPO_BASE_URL = 'https://raw.githubusercontent.com/trxlezi/tachimanga-repo/repo'


def varint(data, pos):
    value = 0
    for shift in range(0, 70, 7):
        byte = data[pos]
        pos += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, pos
    raise ValueError('Invalid protobuf varint')


def fields(data):
    """Decode wire fields using upstream .github/scripts/index.proto."""
    result = {}
    pos = 0
    while pos < len(data):
        tag, pos = varint(data, pos)
        number, wire = tag >> 3, tag & 7
        if wire == 0:
            value, pos = varint(data, pos)
        elif wire == 2:
            size, pos = varint(data, pos)
            value = data[pos:pos + size]
            if len(value) != size:
                raise ValueError('Truncated protobuf')
            pos += size
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            value, pos = data[pos:pos + size], pos + size
        else:
            raise ValueError(f'Unsupported wire type {wire}')
        result.setdefault(number, []).append(value)
    return result


def string(data, field, default=''):
    return data[field][0].decode('utf-8') if field in data else default


def fetch_official():
    payload = urllib.request.urlopen(OFFICIAL_URL, timeout=60).read()
    raw = gzip.decompress(payload) if payload.startswith(b'\x1f\x8b') else payload
    index = fields(raw)
    if 101 not in index:
        raise ValueError('Official schema changed or uses external extensionListUrl')
    result = {}
    for encoded in fields(index[101][0]).get(1, []):
        ext = fields(encoded)
        sources = []
        for encoded_source in ext.get(8, []):
            source = fields(encoded_source)
            source_id = source[1][0]
            if not 0 < source_id <= 2**63 - 1:
                raise ValueError('Invalid official source ID')
            sources.append(dict(id=str(source_id), name=string(source, 2),
                                lang=string(source, 3), baseUrl=string(source, 4)))
        result[string(ext, 2)] = dict(name=string(ext, 1), version=string(ext, 6), sources=sources)
    if not result:
        raise ValueError('Empty official extension list')
    cache = ROOT / 'metadata'
    cache.mkdir(exist_ok=True)
    (cache / 'official-index.json').write_text(json.dumps(dict(
        url=OFFICIAL_URL, sha256=hashlib.sha256(payload).hexdigest(), extensions=result),
        ensure_ascii=False, indent=2), encoding='utf-8')
    return result


def android_tool(name):
    explicit = os.environ.get(name.upper())
    if explicit:
        return explicit
    found = shutil.which(name)
    if found:
        return found
    sdk = Path(os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
               or str(Path.home() / 'AppData/Local/Android/Sdk'))
    suffix = '.exe' if os.name == 'nt' and name in ('aapt2', 'dexdump', 'zipalign') else '.bat' if os.name == 'nt' else ''
    matches = sorted((sdk / 'build-tools').glob(f'*/{name}{suffix}'))
    if not matches:
        raise FileNotFoundError(f'{name}: set ANDROID_HOME or {name.upper()}')
    return str(matches[-1])


def badging(apk):
    output = subprocess.check_output([android_tool('aapt2'), 'dump', 'badging', str(apk)], encoding='utf-8')
    def extract(pattern):
        match = re.search(pattern, output)
        if not match:
            raise ValueError(f'{apk.name}: missing {pattern}')
        return match[1]
    return dict(pkg=extract(r"package: name='([^']+)'"),
                version=extract(r"versionName='([^']+)'"),
                androidCode=int(extract(r"versionCode='(\d+)'")),
                minSdk=int(extract(r"(?:minSdkVersion|sdkVersion):'(\d+)'")),
                name=extract(r"application-label:'([^']+)'")), output


def build_index(offline=False):
    official = (json.loads((ROOT / 'metadata/official-index.json').read_text(encoding='utf-8'))['extensions']
                if offline else fetch_official())
    entries, seen = [], set()
    for apk in sorted((ROOT / 'apk').glob('*.apk')):
        meta, _ = badging(apk)
        pkg = meta['pkg']
        if pkg in seen:
            raise ValueError(f'Multiple APK versions for {pkg}; move old APKs out of apk/')
        seen.add(pkg)
        upstream = official[pkg]
        built = json.loads((ROOT / 'metadata' / f'{pkg}.json').read_text(encoding='utf-8'))
        if built['packageName'] != pkg or built['versionName'] != meta['version']:
            raise ValueError(f'{pkg}: build metadata does not match APK')
        if built['versionCode'] != meta['androidCode'] or meta['minSdk'] != 21:
            raise ValueError(f'{pkg}: invalid version or minSdk')
        sources = []
        for source in built['sources']:
            match = next((s for s in upstream['sources'] if s['id'] == str(source['id'])
                          and s['name'] == source['name'] and s['lang'] == source['lang']), None)
            if match is None:
                raise ValueError(f'{pkg}: built source identity differs from official index')
            sources.append(dict(name=match['name'], lang=match['lang'],
                                id=str(match['id']), baseUrl=source['baseUrl']))
        if len(sources) != len(upstream['sources']):
            raise ValueError(f'{pkg}: source count differs from official index')
        # The package segment only approximates the language: pt/tiamanhwa is really
        # pt-BR, and the client groups the extension list by this field. Derive it from
        # the sources the way the client does, and fall back when they disagree.
        languages = {source['lang'] for source in sources}
        entries.append(dict(name=meta['name'], pkg=pkg,
                            apk=apk.name,
                            lang=languages.pop() if len(languages) == 1 else 'all',
                            code=int(meta['version'].split('.')[-1]), version=meta['version'],
                            nsfw=1 if built.get('contentWarning') == 3 else 0,
                            hasReadme=0, hasChangelog=0, sources=sources))
    if not entries:
        raise ValueError('No APKs to index')
    # repo.json is mandatory for the legacy index.min.json path: the client derives
    # its URL by replacing '/index.min.json' with '/repo.json' and fails the whole
    # store if it is missing. index_v2 points modern clients at the protobuf index.
    (ROOT / 'repo.json').write_text(json.dumps(dict(
        meta=dict(name=REPO_NAME, shortName=REPO_BADGE, website=REPO_WEBSITE,
                  signingKeyFingerprint=(ROOT / 'signing-certificate.sha256').read_text(encoding='utf-8').strip()),
        index_v2=f'{REPO_BASE_URL}/index.pb'), indent=2) + chr(10), encoding='utf-8')
    output = ROOT / 'index.min.json'
    temporary = output.with_suffix('.tmp')
    temporary.write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output)
    print(f'{output.name}: {len(entries)} extensions; all source IDs verified')
    return entries


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--offline', action='store_true', help='Use cached official metadata')
    args = parser.parse_args()
    build_index(args.offline)
