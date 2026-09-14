"""Repeatable lexical jsoup audit. Requires Python 3 and a JDK with javap.

python audit_jsoup.py --javap "C:/Program Files/Java/jdk-25.0.3/bin/javap.exe"
Findings are candidates, not a Kotlin type-check or an APK certification.
"""
import argparse
import collections
import json
from pathlib import Path
import re
import subprocess
import urllib.request
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('extensions-source'))
    parser.add_argument('--out', type=Path, default=Path('audit'))
    parser.add_argument('--javap', default='javap')
    parser.add_argument('--baseline', default='1.14.3')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    versions = (args.repo / 'gradle/libs.versions.toml').read_text(encoding='utf-8')
    current = re.search(r'jsoup = .*version = "([^"]+)"', versions)[1]
    apis = {}
    for version in dict.fromkeys([args.baseline, current]):
        jar = args.out / f'jsoup-{version}.jar'
        if not jar.exists():
            urllib.request.urlretrieve(
                f'https://repo.maven.apache.org/maven2/org/jsoup/jsoup/{version}/{jar.name}', jar)
        with zipfile.ZipFile(jar) as archive:
            classes = [n[:-6].replace('/', '.') for n in archive.namelist()
                       if n.endswith('.class') and not n.startswith('META-INF')]
        output = subprocess.check_output(
            [args.javap, '-public', '-classpath', str(jar), *classes], encoding='utf-8')
        (args.out / f'api-{version}.txt').write_text(output, encoding='utf-8')
        api = collections.defaultdict(list)
        owner = ''
        for line in output.splitlines():
            match = re.search(r'(?:class|interface) (org\.jsoup\.[\w.$]+)', line)
            if match:
                owner = match[1]
            if '(' in line and line.strip().startswith('public '):
                api[owner].append(line.strip())
        apis[version] = api
    diff = {c: [s for s in signatures if s not in apis[args.baseline].get(c, [])]
            for c, signatures in apis[current].items()}
    (args.out / 'api-diff.json').write_text(json.dumps(diff, indent=2), encoding='utf-8')
    names = collections.defaultdict(list)
    for owner, signatures in diff.items():
        for signature in signatures:
            match = re.search(r' ([\w.$]+)\(', signature)
            if match:
                names[match[1].split('.')[-1]].append(signature)
    pattern = re.compile(r'\b(' + '|'.join(map(re.escape, names)) + r')\s*(?:\(|\b(?=\s*[,)}]))')
    roots = ['src/pt', 'src/en', 'src/es', 'src/all', 'lib-multisrc', 'lib', 'core', 'common']
    files = sorted(p for root in roots for p in (args.repo / root).rglob('*')
                   if p.suffix in ('.kt', '.java'))
    candidates, focused, inventory = [], [], collections.Counter()
    for file in files:
        relative = file.relative_to(args.repo).as_posix()
        scope = '/'.join(relative.split('/')[:2]) if relative.startswith('src/') else relative.split('/')[0]
        inventory[scope] += 1
        lines = file.read_text(encoding='utf-8').splitlines()
        for number, line in enumerate(lines, 1):
            record = dict(file=relative, line=number, code=line.strip())
            for match in pattern.finditer(line):
                candidates.append(dict(record, name=match[1], possible_signatures=names[match[1]]))
            if re.search(r':(?:is|where|containsWholeText|containsWholeOwnText|matchesWholeText|matchesWholeOwnText)\(', line):
                focused.append(dict(record, kind='CSS newer syntax; review literal and parser support'))
            match = re.search(r'(\w+)\??\.selectFirst\(', line)
            if match:
                variable = re.escape(match[1])
                declarations = [x.strip() for x in lines if re.search(
                    r'\b(?:val|var)\s+' + variable + r'\b|\b' + variable + r'\s*:\s*Elements\b', x)]
                if any(re.search(r'\.select\(|:\s*Elements\b', x) for x in declarations):
                    focused.append(dict(record, kind='Possible Elements receiver; review scopes and terminal operation', declarations=declarations))
    themes = collections.defaultdict(list)
    modules = collections.Counter()
    for lang in ('pt', 'en', 'es', 'all'):
        for build in sorted((args.repo / 'src' / lang).glob('*/build.gradle.kts')):
            modules[lang] += 1
            match = re.search(r'theme\s*=\s*"([^"]+)"', build.read_text(encoding='utf-8'))
            if match:
                themes[match[1]].append(f'{lang}/{build.parent.name}')
    metadata = dict(
        commit=subprocess.check_output(['git', '-C', str(args.repo), 'rev-parse', 'HEAD'], text=True).strip(),
        baseline=args.baseline, compiled_jsoup=current, files=len(files), inventory=inventory,
        modules=modules, theme_consumers=themes,
        limitations='Lexical candidates include comments, same-name non-jsoup APIs, inherited methods and overloads. No Kotlin type resolution, generated code, APKs, reflection or external dependency traversal. All multilingual modules and shared themes are a conservative superset; dependency mapping uses theme declarations only. Baseline is not the verified Tachimanga runtime version.')
    for name, value in [('candidates.json', candidates), ('focused.json', focused), ('inventory.json', metadata)]:
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(files=len(files), inventory=inventory, modules=modules, focused=len(focused)), indent=2))


if __name__ == '__main__':
    main()
