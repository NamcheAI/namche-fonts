#!/usr/bin/env python3
"""Validate actual candidate URLs without Fontspector 1.9.0's HTML-token bug.

Supplementary validation only. The official report and open finding stay intact.
"""
import argparse
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from fontTools.ttLib import TTFont
from build_googlefonts import REPOSITORY

CREDITS = {'https://github.com/fizzybubbele', 'https://ruhmetc.com'}
UPSTREAM = 'https://github.com/vercel/geist-font'


def canonical(url):
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.username or parts.password or parts.port:
        raise ValueError(f'Expected a plain HTTPS URL: {url}')
    path = parts.path.rstrip('/')
    if path.endswith('.git'):
        path = path[:-4]
    return f'https://{parts.netloc.lower()}{path}'


class Links(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href')
            if not href:
                raise ValueError('Description anchor is missing href')
            self.urls.append(canonical(href))


def validate_description(text, repository=REPOSITORY):
    parser = Links()
    parser.feed(text)
    urls = set(parser.urls)
    required = {canonical(repository), *CREDITS}
    if missing := required - urls:
        raise ValueError(f'Missing repository or designer credit links: {sorted(missing)}')
    for url in urls:
        if urlsplit(url).hostname == 'github.com' and url not in required | {UPSTREAM}:
            raise ValueError(f'Unexpected GitHub destination: {url}')
    return sorted(urls)


def validate_family(family):
    metadata = (family / 'METADATA.pb').read_text()
    repositories = re.findall(r'^\s*repository_url:\s*("(?:[^"\\]|\\.)*")', metadata, re.M)
    if len(repositories) != 1 or canonical(json.loads(repositories[0])) != REPOSITORY:
        raise ValueError('METADATA.pb source must identify the project repository')
    urls = validate_description((family / 'DESCRIPTION.en_us.html').read_text())
    fonts = list(family.glob('*.ttf'))
    if len(fonts) != 2:
        raise ValueError('Expected both candidate TTFs')
    texts = {'OFL.txt': (family / 'OFL.txt').read_text()}
    for path in fonts:
        with TTFont(path) as font:
            texts[path.name] = font['name'].getDebugName(0) or ''
    for name, text in texts.items():
        notices = re.findall(r'Copyright[^\n]*?\((https://[^)]+)\)', text)
        if [canonical(u) for u in notices] != [REPOSITORY, UPSTREAM]:
            raise ValueError(f'{name}: missing or changed project/upstream copyright links')
    return {'status': 'PASS', 'description_links': urls, 'copyright_links': [REPOSITORY, UPSTREAM],
            'scope': 'Supplementary semantic URL and attribution validation; not a replacement for official Fontspector or GF approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('family', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = validate_family(args.family)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print('PASS semantic candidate URLs and retained designer/upstream credits')


if __name__ == '__main__':
    main()
