#!/usr/bin/env python3
"""Gate candidate QA on all required checks and narrowly recorded open GF findings.

An accepted local baseline is NOT Google Fonts approval. The JSON status retains
submission_ready=false while any FAIL is present; no check is skipped or hidden.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

BASELINE = Path(__file__).resolve().parent.parent / 'sources/googlefonts/qa-open-findings.json'
REQUIRED = {
    'name/family_and_style_max_length': 2,
    'googlefonts/font_names': 2,
    'googlefonts/fvar_instances': 2,
    'googlefonts/metadata/axes': 1,
    'googlefonts/metadata/consistent_with_fonts': 1,
    'googlefonts/metadata/familyname': 1,
    'googlefonts/glyph_coverage': 1,
    'googlefonts/family/has_license': 1,
    'googlefonts/name/license': 1,
}


def normalize(message: str) -> str:
    # The check iterates a HashSet; only the printed subset order is unstable.
    return re.sub(r'any of the subsets ([^:\n]+):',
                  lambda m: 'any of the subsets ' + ', '.join(sorted(m[1].split(', '))) + ':', message)


def findings(report: dict) -> list[dict]:
    return [dict(check=c['check_id'], code=r.get('code'), severity=r['severity'],
                 message=normalize(r.get('message', '')))
            for sections in report['results'].values() for checks in sections.values()
            for c in checks for r in c['subresults'] if r['severity'] in ('FAIL', 'ERROR', 'FATAL')
            or (c['check_id'] == 'googlefonts/metadata/subsets_correct' and r['severity'] == 'WARN')]


def validate(report: dict, baseline: dict) -> dict:
    passes = Counter(c['check_id'] for sections in report['results'].values()
                     for checks in sections.values() for c in checks if c['worst_status'] == 'PASS')
    for check, minimum in REQUIRED.items():
        if passes[check] < minimum:
            raise ValueError(f'Required submission check did not pass: {check}')
    subset_checks = [c for sections in report['results'].values() for checks in sections.values()
                     for c in checks if c['check_id'] == 'googlefonts/metadata/subsets_correct']
    if not subset_checks or any(c['worst_status'] not in ('PASS', 'WARN') for c in subset_checks):
        raise ValueError('Required subset check did not run successfully')
    for check in {f["check"] for f in baseline["findings"]}:
        executed = [c for sections in report["results"].values() for checks in sections.values()
                    for c in checks if c["check_id"] == check]
        if not executed or any(c["worst_status"] == "SKIP" for c in executed):
            raise ValueError(f"Known open check was skipped or missing: {check}")
    remaining = findings(report)
    allowed = Counter(json.dumps(f, sort_keys=True) for f in baseline['findings'])
    for finding in remaining:
        key = json.dumps(finding, sort_keys=True)
        if finding['severity'] in ('ERROR', 'FATAL') or allowed[key] == 0:
            raise ValueError(f'Unexpected Google Fonts finding: {finding}')
        allowed[key] -= 1
    return {'submission_ready': not remaining, 'open_findings': remaining,
            'note': 'Local candidate regression gate only; open FAILs still require resolution or explicit Google Fonts approval.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    args = parser.parse_args()
    status = validate(json.loads(args.report.read_text()), json.loads(BASELINE.read_text()))
    (args.report.parent / 'QA_STATUS.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS candidate regression gate; submission_ready={status["submission_ready"]}; open findings={len(status["open_findings"])}')
    for finding in status['open_findings']:
        print(f'::warning title=Open Google Fonts submission finding::{finding["check"]}: {finding["code"]}')


if __name__ == '__main__':
    main()
