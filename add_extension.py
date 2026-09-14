#!/usr/bin/env python3
"""Rebuild, verify and index a source. Does not commit or push automatically."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

from build_index import ROOT, badging, build_index, fetch_official
from verify_apk import verify

SOURCE = ROOT / 'extensions-source'
BASE = 'a1a1d8ccfb31f3fa9c8cf2fab3e4f1cd67071b1f'


def run(args, cwd=ROOT, **kwargs):
    return subprocess.run([str(x) for x in args], cwd=cwd, check=True, **kwargs)


def prepare_source():
    if not SOURCE.exists():
        run(['git', 'init', str(SOURCE)])
        run(['git', 'remote', 'add', 'origin', 'https://github.com/keiyoushi/extensions-source'], cwd=SOURCE)
        run(['git', 'fetch', '--depth', '1', 'origin', BASE], cwd=SOURCE)
        run(['git', 'checkout', '--detach', 'FETCH_HEAD'], cwd=SOURCE)
    head = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
    if head != BASE:
        raise ValueError('Unexpected source revision. Rebase patches explicitly before using another revision.')
    marker = SOURCE / '.tachimanga-ready'
    if not marker.exists():
        patch = ROOT / 'patches/tachimanga.patch'
        applied = subprocess.run(['git', 'apply', '--reverse', '--check', str(patch)], cwd=SOURCE,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        if not applied:
            run(['git', 'apply', '--check', str(patch)], cwd=SOURCE)
            run(['git', 'apply', str(patch)], cwd=SOURCE)
        marker.write_text(BASE + '\n')
    sdk = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
    if not sdk and os.name == 'nt':
        sdk = str(Path.home() / 'AppData/Local/Android/Sdk')
    if sdk and Path(sdk).is_dir():
        os.environ['ANDROID_HOME'] = sdk
        (SOURCE / 'local.properties').write_text('sdk.dir=' + Path(sdk).as_posix() + '\n')


def collect(module):
    build = SOURCE / 'src' / module / 'build'
    info = json.loads((build / 'keiyoushi-source-info.json').read_text(encoding='utf-8'))
    apks = list((build / 'outputs/apk/release').glob('*.apk'))
    matching = [p for p in apks if badging(p)[0]['version'] == info['versionName']]
    if len(matching) != 1:
        raise ValueError(f'{module}: expected exactly one matching APK')
    apk = matching[0]
    result = verify(apk)
    # Metadata is generated from the same DSL as the entry point, then checked against upstream.
    (ROOT / 'metadata').mkdir(exist_ok=True)
    (ROOT / 'verification').mkdir(exist_ok=True)
    (ROOT / 'apk').mkdir(exist_ok=True)
    (ROOT / 'icon').mkdir(exist_ok=True)
    # Do not overwrite a previously released version with different bytes.
    destination = ROOT / 'apk' / apk.name
    if destination.exists() and destination.read_bytes() != apk.read_bytes():
        raise ValueError(f'{apk.name}: version already exists with different bytes; increment version first')
    # Keep old builds outside the served index (reversible, local archive).
    for old in (ROOT / 'apk').glob('*.apk'):
        if old.name != apk.name and badging(old)[0]['pkg'] == info['packageName']:
            archive = ROOT / 'build/previous-apks'
            archive.mkdir(parents=True, exist_ok=True)
            old.replace(archive / old.name)
            alias = old.with_suffix('.jar')
            if alias.exists():
                alias.replace(archive / alias.name)
    shutil.copyfile(apk, destination)
    (ROOT / 'metadata' / f'{info["packageName"]}.json').write_text(json.dumps(info, indent=2) + '\n', encoding='utf-8')
    (ROOT / 'verification' / f'{apk.stem}.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    _, badge = badging(apk)
    icon = re.search(r"application-icon-320:'([^']+)'", badge) or re.search(r"application-icon-160:'([^']+)'", badge)
    if icon:
        with zipfile.ZipFile(apk) as z:
            (ROOT / 'icon' / f'{info["packageName"]}.png').write_bytes(z.read(icon[1]))
    print(f'Collected {apk.name}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('lang')
    parser.add_argument('name')
    args = parser.parse_args()
    if not re.fullmatch(r'[a-z]{2,3}', args.lang) or not re.fullmatch(r'[a-z0-9]+', args.name):
        parser.error('Use a repository language code and a lowercase alphanumeric extension directory')
    if not (ROOT / 'keystore/keystore.properties').exists():
        raise SystemExit('Restore the original keystore/ directory first. Never generate a replacement signing key.')
    if os.name == 'nt' and not os.environ.get('JAVA_HOME'):
        installed = sorted(Path('C:/Program Files/Java').glob('jdk-*'),
                           key=lambda p: [int(n) for n in re.findall(r'\d+', p.name)])
        if installed:
            os.environ['JAVA_HOME'] = str(installed[-1])
    prepare_source()
    module = f'{args.lang}/{args.name}'
    script = SOURCE / 'src' / module / 'build.gradle.kts'
    text = script.read_text(encoding='utf-8')
    official = fetch_official()
    pkg_match = re.search(r'pkgName\s*=\s*"([^"]+)"', text)
    pkg = 'eu.kanade.tachiyomi.extension.' + (pkg_match[1] if pkg_match else module.replace('/', '.'))
    remote_code = int(official[pkg]['version'].split('.')[-1])
    theme = re.search(r'theme\s*=\s*"([^"]+)"', text)
    base = 0
    if theme:
        theme_text = (SOURCE / 'lib-multisrc' / theme[1] / 'build.gradle.kts').read_text(encoding='utf-8')
        base = int(re.search(r'baseVersionCode\s*=\s*(\d+)', theme_text)[1])
    match = re.search(r'\bversionCode\s*=\s*(\d+)', text)
    local_code = int(match[1])
    published = json.loads((ROOT / 'index.min.json').read_text(encoding='utf-8'))
    prior_code = max((e['code'] for e in published if e['pkg'] == pkg), default=0)
    new_code = max(local_code, remote_code + 1 - base, prior_code + 1 - base)
    text = text[:match.start(1)] + str(new_code) + text[match.end(1):]
    script.write_text(text, encoding='utf-8', newline='\n')
    gradle = SOURCE / ('gradlew.bat' if os.name == 'nt' else 'gradlew')
    path = ':src:' + module.replace('/', ':')
    tasks = [path + ':assembleRelease', path + ':lintRelease']
    if theme:
        tasks.append(':lib-multisrc:' + theme[1] + ':lintRelease')
    run([gradle, '-Pextensions=' + module.replace('/', ':'), *tasks,
         '--console=plain', '--max-workers=4'], cwd=SOURCE)
    collect(module)
    build_index(offline=True)
    patch = subprocess.check_output(['git', 'diff', '--binary', 'HEAD'], cwd=SOURCE)
    (ROOT / 'patches/tachimanga.patch').write_bytes(patch)
    print('Ready for review and git commit/push. APKs have not been tested on iOS.')


if __name__ == '__main__':
    main()
