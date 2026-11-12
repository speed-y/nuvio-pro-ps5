#!/usr/bin/env python3
"""Verify that VERSION and sce_sys/param.json contentVersion advance over the prior release."""
from pathlib import Path
import argparse
import json
import re
import subprocess
import sys

SEMVER_RE = re.compile(r'^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$')
CONTENT_VERSION_RE = re.compile(r'^(\d{2})\.(\d{3})\.(\d{3})$')


def parse_semver(text):
    """Return a SemVer comparison key and prerelease flag for a version string."""
    match = SEMVER_RE.fullmatch(text.strip())
    if not match:
        raise ValueError(f'Invalid VERSION format: {text!r}')
    major, minor, patch = (int(match.group(i)) for i in (1, 2, 3))
    pre_raw = match.group(4)
    if pre_raw is None:
        return (major, minor, patch, 1, ()), False
    parts = []
    for token in pre_raw.split('.'):
        if token == '':
            raise ValueError(f'Empty prerelease identifier in VERSION: {text!r}')
        # SemVer 2.0.0: numeric identifiers sort below non-numeric identifiers.
        if token.isdigit():
            parts.append((0, int(token), ''))
        else:
            parts.append((1, 0, token))
    return (major, minor, patch, 0, tuple(parts)), True


def parse_content_version(text):
    """Return numeric (major, minor, patch) for PS5 NN.NNN.NNN contentVersion."""
    match = CONTENT_VERSION_RE.fullmatch(str(text).strip())
    if not match:
        raise ValueError(f'Invalid sce_sys/param.json contentVersion: {text!r}')
    return tuple(int(match.group(i)) for i in (1, 2, 3))


def git_output(repo_root, *args, check=True):
    proc = subprocess.run(
        ['git', *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=check,
    )
    return proc.stdout


def read_ref_metadata(repo_root, ref):
    version = git_output(repo_root, 'show', f'{ref}:VERSION').strip()
    param = json.loads(git_output(repo_root, 'show', f'{ref}:sce_sys/param.json'))
    return version, str(param['contentVersion']).strip()


def read_worktree_metadata(repo_root):
    version = (repo_root / 'VERSION').read_text().strip()
    param = json.loads((repo_root / 'sce_sys/param.json').read_text())
    return version, str(param['contentVersion']).strip()


def list_version_tags(repo_root):
    raw = git_output(repo_root, 'tag', '-l', 'v[0-9]*')
    tags = []
    for line in raw.splitlines():
        tag = line.strip()
        if not tag:
            continue
        try:
            key, _ = parse_semver(tag[1:])
        except ValueError:
            continue
        tags.append((key, tag))
    tags.sort(key=lambda item: item[0])
    return tags


def validate_release_bump(repo_root, base_ref=None, allow_head_tag=False):
    version, content_version = read_worktree_metadata(repo_root)
    ver_key, is_pre = parse_semver(version)
    cv_key = parse_content_version(content_version)
    tag = f'v{version}'

    all_tags = list_version_tags(repo_root)
    existing_names = {name for _, name in all_tags}
    if tag in existing_names and not allow_head_tag:
        raise RuntimeError(
            f'Release tag {tag} already exists; bump VERSION in VERSION before releasing'
        )

    prior_tags = [(key, name) for key, name in all_tags if name != tag]
    prev_tag = prior_tags[-1][1] if prior_tags else ''
    prev_version = ''
    prev_cv = ''

    comparisons = []
    if prev_tag:
        prev_version, prev_cv = read_ref_metadata(repo_root, prev_tag)
        comparisons.append((f'previous release {prev_tag}', prev_version, prev_cv))

    zero_sha = '0' * 40
    if base_ref and base_ref != zero_sha:
        has_base = subprocess.run(
            ['git', 'cat-file', '-e', f'{base_ref}^{{commit}}'],
            cwd=repo_root,
            capture_output=True,
        ).returncode == 0
        if has_base:
            base_version, base_cv = read_ref_metadata(repo_root, base_ref)
            comparisons.append((f'base commit {base_ref[:12]}', base_version, base_cv))

    for label, ref_version, ref_cv in comparisons:
        ref_ver_key, _ = parse_semver(ref_version)
        ref_cv_key = parse_content_version(ref_cv)
        if ver_key <= ref_ver_key:
            raise RuntimeError(
                f'VERSION {version} is not bumped above {label} ({ref_version})'
            )
        if cv_key <= ref_cv_key:
            raise RuntimeError(
                f'sce_sys/param.json contentVersion {content_version} is not bumped above {label} ({ref_cv})'
            )

    return {
        'version': version,
        'tag': tag,
        'content_version': content_version,
        'prev_tag': prev_tag,
        'prev_version': prev_version,
        'prev_content_version': prev_cv,
        'is_prerelease': 'true' if is_pre else 'false',
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--repo-root', default='.', help='Repository root directory')
    ap.add_argument('--base-ref', default=None, help='Optional prior branch commit/ref to compare against')
    ap.add_argument('--allow-head-tag', action='store_true', help='Allow v<VERSION> tag when running on that tag')
    ap.add_argument('--github-output', default=None, help='Optional GITHUB_OUTPUT path')
    args = ap.parse_args()

    try:
        info = validate_release_bump(
            Path(args.repo_root).resolve(),
            base_ref=args.base_ref,
            allow_head_tag=args.allow_head_tag,
        )
    except Exception as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    if args.github_output:
        with open(args.github_output, 'a', encoding='utf-8') as out:
            for key, value in info.items():
                out.write(f'{key}={value}\n')

    print(
        f"Verified release bump: {info['tag']} (contentVersion {info['content_version']})"
        + (f" > {info['prev_tag']} ({info['prev_content_version']})" if info['prev_tag'] else '')
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
