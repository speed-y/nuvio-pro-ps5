import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_release_version as crv  # noqa: E402


def write_meta(repo: Path, version: str, content_version: str) -> None:
    (repo / 'VERSION').write_text(version + '\n', encoding='utf-8')
    sce_sys = repo / 'sce_sys'
    sce_sys.mkdir(exist_ok=True)
    (sce_sys / 'param.json').write_text(
        json.dumps({'titleId': 'PPSA99996', 'contentVersion': content_version}, indent=2) + '\n',
        encoding='utf-8',
    )


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ['git', *args], cwd=repo, text=True, stderr=subprocess.STDOUT
    ).strip()


def commit_meta(repo: Path, message: str, version: str, content_version: str) -> str:
    write_meta(repo, version, content_version)
    git(repo, 'add', 'VERSION', 'sce_sys/param.json')
    git(repo, 'commit', '-m', message)
    return git(repo, 'rev-parse', 'HEAD')


class ReleaseVersionTests(unittest.TestCase):
    def make_repo(self, version='0.2.0-alpha.2', content_version='01.000.009', tag='v0.2.0-alpha.2'):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        git(repo, 'init', '-b', 'main')
        git(repo, 'config', 'user.name', 'Test User')
        git(repo, 'config', 'user.email', 'test@example.com')
        sha = commit_meta(repo, 'Initial release', version, content_version)
        if tag:
            git(repo, 'tag', tag)
        return repo, sha

    def test_semver_ordering(self):
        ordered = [
            '0.1.0-alpha.7',
            '0.2.0-alpha.1',
            '0.2.0-alpha.2',
            '0.2.0-alpha.10',
            '0.2.0-beta.1',
            '0.2.0-rc.1',
            '0.2.0',
            '0.2.1',
        ]
        keys = [crv.parse_semver(v)[0] for v in ordered]
        self.assertEqual(keys, sorted(keys))
        self.assertTrue(crv.parse_semver('0.2.0-alpha.3')[1])
        self.assertFalse(crv.parse_semver('0.2.0')[1])

    def test_accepts_bumped_version_and_content_version(self):
        repo, base = self.make_repo()
        commit_meta(repo, 'Release 0.2.0-alpha.3', '0.2.0-alpha.3', '01.000.010')
        info = crv.validate_release_bump(repo, base_ref=base)
        self.assertEqual(info['tag'], 'v0.2.0-alpha.3')
        self.assertEqual(info['prev_tag'], 'v0.2.0-alpha.2')
        self.assertEqual(info['content_version'], '01.000.010')
        self.assertEqual(info['is_prerelease'], 'true')

    def test_rejects_unbumped_version(self):
        repo, base = self.make_repo()
        commit_meta(repo, 'Change without version bump', '0.2.0-alpha.2', '01.000.010')
        with self.assertRaises(RuntimeError) as ctx:
            crv.validate_release_bump(repo, base_ref=base)
        self.assertIn('already exists', str(ctx.exception))

    def test_rejects_unbumped_content_version(self):
        repo, base = self.make_repo()
        commit_meta(repo, 'Forget param.json bump', '0.2.0-alpha.3', '01.000.009')
        with self.assertRaises(RuntimeError) as ctx:
            crv.validate_release_bump(repo, base_ref=base)
        self.assertIn('contentVersion', str(ctx.exception))

    def test_rejects_version_below_higher_tag_even_if_bumped_above_base(self):
        repo, base = self.make_repo('0.2.0-alpha.1', '01.000.008', tag='v0.2.0-alpha.1')
        commit_meta(repo, 'Other branch release', '0.2.0-alpha.3', '01.000.010')
        git(repo, 'tag', 'v0.2.0-alpha.3')
        git(repo, 'reset', '--hard', base)
        commit_meta(repo, 'Stale bump', '0.2.0-alpha.2', '01.000.009')
        with self.assertRaises(RuntimeError) as ctx:
            crv.validate_release_bump(repo, base_ref=base)
        self.assertIn('v0.2.0-alpha.3', str(ctx.exception))

    def test_allows_head_tag_when_triggered_by_tag_push(self):
        repo, base = self.make_repo()
        commit_meta(repo, 'Release 0.2.0', '0.2.0', '01.000.010')
        git(repo, 'tag', 'v0.2.0')
        info = crv.validate_release_bump(repo, base_ref=base, allow_head_tag=True)
        self.assertEqual(info['tag'], 'v0.2.0')
        self.assertEqual(info['prev_tag'], 'v0.2.0-alpha.2')
        self.assertEqual(info['is_prerelease'], 'false')

    def test_rejects_invalid_version_or_content_version_format(self):
        repo, base = self.make_repo()
        commit_meta(repo, 'Bad format', '0.2.0-alpha.3', '1.0.10')
        with self.assertRaises(ValueError):
            crv.validate_release_bump(repo, base_ref=base)


if __name__ == '__main__':
    unittest.main()
