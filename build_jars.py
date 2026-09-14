#!/usr/bin/env python3
"""Convert each APK into the .jar layout Tachimanga loads.

Tachimanga runs on iOS and cannot execute Android bytecode, so it downloads the
jarUrl rather than the apkUrl. A jar is the APK with two substitutions:

  * classes*.dex replaced by the equivalent JVM .class files (dex2jar), and
  * the binary AndroidManifest.xml replaced by its plain-text XML form.

Shipping a renamed APK instead makes the client fail with "Content is not
allowed in prolog", because it parses AndroidManifest.xml as text XML and gets
the binary AXML magic. Mirrors the layout of the official Keiyoushi jars.
"""
import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

from pyaxmlparser.axmlprinter import AXMLPrinter

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / 'tools'
DEX_TOOLS_VERSION = 'v2.4'
DEX_TOOLS_URL = (f'https://github.com/pxb1988/dex2jar/releases/download/{DEX_TOOLS_VERSION}'
                 f'/dex-tools-{DEX_TOOLS_VERSION}.zip')
DEX2JAR_MAIN = 'com.googlecode.dex2jar.tools.Dex2jarCmd'
# Keiyoushi stamps a fixed timestamp so rebuilds are byte-reproducible.
ENTRY_DATE = (2024, 1, 6, 0, 0, 0)
XML_PROLOG = '<?xml version="1.0" encoding="utf-8"?>\n'


def dex_tools_lib():
    """Return the dex2jar lib directory, downloading the release if needed."""
    lib = TOOLS / f'dex-tools-{DEX_TOOLS_VERSION}' / 'lib'
    if not lib.is_dir():
        TOOLS.mkdir(exist_ok=True)
        print(f'downloading {DEX_TOOLS_URL}')
        payload = urllib.request.urlopen(DEX_TOOLS_URL, timeout=120).read()
        zipfile.ZipFile(io.BytesIO(payload)).extractall(TOOLS)
    if not lib.is_dir():
        raise FileNotFoundError(f'{lib}: dex2jar release layout changed')
    return lib


def dex2jar(apk, destination, lib):
    separator = ';' if os.name == 'nt' else ':'
    classpath = separator.join(str(jar) for jar in sorted(lib.glob('*.jar')))
    subprocess.run([shutil.which('java') or 'java', '-cp', classpath, DEX2JAR_MAIN,
                    '-f', '-o', str(destination), str(apk)],
                   check=True, capture_output=True)


def manifest_xml(apk):
    """Decode the binary AndroidManifest.xml of an APK into text XML."""
    with zipfile.ZipFile(apk) as archive:
        xml = AXMLPrinter(archive.read('AndroidManifest.xml')).get_xml().decode('utf-8')
    # AXML stores extensionLib as a float, which decodes to "1.600000"; the
    # client compares it against the supported lib range as a version string.
    xml = re.sub(r'(android:value=")(\d+)\.(\d*?)0*(")',
                 lambda m: f'{m[1]}{m[2]}.{m[3] or "0"}{m[4]}', xml)
    return XML_PROLOG + xml


def build_jar(apk, lib, work):
    classes = work / f'{apk.stem}-classes.jar'
    dex2jar(apk, classes, lib)
    target = apk.with_suffix('.jar')
    temporary = target.with_suffix('.jar.tmp')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as out:
        def add(name, data):
            info = zipfile.ZipInfo(name, date_time=ENTRY_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, data)

        add('AndroidManifest.xml', manifest_xml(apk))
        with zipfile.ZipFile(classes) as source:
            for name in source.namelist():
                if name.endswith('/'):
                    continue
                add(name, source.read(name))
        with zipfile.ZipFile(apk) as source:
            for name in source.namelist():
                # The dex is now redundant and the manifest was replaced above.
                if name.endswith('/') or name == 'AndroidManifest.xml':
                    continue
                if re.fullmatch(r'classes\d*\.dex', name):
                    continue
                add(name, source.read(name))
    temporary.replace(target)
    return target


def main(apks=None):
    lib = dex_tools_lib()
    work = TOOLS / 'work'
    work.mkdir(parents=True, exist_ok=True)
    selected = sorted((ROOT / 'apk').glob('*.apk'))
    if apks:
        wanted = set(apks)
        selected = [apk for apk in selected if apk.name in wanted or apk.stem in wanted]
        if not selected:
            raise SystemExit(f'no APK matched {sorted(wanted)}')
    for apk in selected:
        jar = build_jar(apk, lib, work)
        with zipfile.ZipFile(jar) as archive:
            classes = sum(1 for name in archive.namelist() if name.endswith('.class'))
        if not classes:
            raise SystemExit(f'{jar.name}: no classes were converted')
        print(f'{jar.name}: {classes} classes, {jar.stat().st_size} bytes')
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('apk', nargs='*', help='APK names to convert (default: all)')
    main(parser.parse_args().apk)
