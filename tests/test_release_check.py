"""The browser update check follows this fork's GitHub releases."""
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import polish

FIXTURE = ROOT / 'tests/fixtures/nuvio-1.4.4'


class ReleaseCheckTests(unittest.TestCase):
    def test_prerelease_tags_point_at_this_fork(self):
        with tempfile.TemporaryDirectory() as directory:
            tree = Path(directory)
            shutil.copytree(FIXTURE / 'js', tree / 'js')
            polish.patch_release_check(tree)
            service = (tree / 'js/core/update/appUpdateService.js').read_text()
            prompt = (tree / 'js/ui/components/appUpdatePrompt.js').read_text()
            self.assertIn('speed-y/nuvio-pro-ps5/releases?per_page=30', service)
            self.assertNotIn('NuvioMedia/NuvioTVSmart', service)
            self.assertNotIn('Nuvio TV Installer', prompt)
            self.assertIn('Download package', prompt)
            self.assertIn('Open release', prompt)
            probe = tree / 'probe.mjs'
            probe.write_text(r'''
import { chooseNewestRelease, parseLatestRelease } from "./js/core/update/appUpdateService.js";
const releases = [
  { draft: true, tag_name: "v0.2.0-alpha.9", html_url: "https://example.invalid/draft" },
  { draft: false, prerelease: true, tag_name: "pr-14-4a7e83101ad4", html_url: "https://example.invalid/pr" },
  { draft: false, prerelease: true, tag_name: "v0.2.0-alpha.7", name: "Nuvio Pro v0.2.0-alpha.7",
    html_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/tag/v0.2.0-alpha.7",
    assets: [{ name: "nuvio-pro-ps5-0.2.0-alpha.7.zip",
      browser_download_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/download/v0.2.0-alpha.7/nuvio-pro-ps5-0.2.0-alpha.7.zip" }] },
  { draft: false, prerelease: true, tag_name: "v0.2.0-alpha.8", name: "Nuvio Pro v0.2.0-alpha.8",
    html_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/tag/v0.2.0-alpha.8",
    assets: [{ name: "nuvio-pro-ps5-0.2.0-alpha.8.zip",
      browser_download_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/download/v0.2.0-alpha.8/nuvio-pro-ps5-0.2.0-alpha.8.zip" }] },
  { draft: false, prerelease: true, tag_name: "v0.2.0-alpha.9", name: "Nuvio Pro v0.2.0-alpha.9",
    html_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/tag/v0.2.0-alpha.9",
    assets: [{ name: "nuvio-pro-ps5-0.2.0-alpha.9.zip",
      browser_download_url: "https://github.com/speed-y/nuvio-pro-ps5/releases/download/v0.2.0-alpha.9/nuvio-pro-ps5-0.2.0-alpha.9.zip" }] }
];
if (chooseNewestRelease(releases, "0.2.0-alpha.9") !== null) throw new Error("current tag prompted");
const next = chooseNewestRelease(releases, "0.2.0-alpha.8");
if (next.tag !== "0.2.0-alpha.9") throw new Error(next.tag);
if (!next.downloadUrl.endsWith("nuvio-pro-ps5-0.2.0-alpha.9.zip")) throw new Error(next.downloadUrl);
const fromPrevious = chooseNewestRelease(releases.filter((release) => release.tag_name !== "v0.2.0-alpha.9"), "0.2.0-alpha.7");
if (fromPrevious.tag !== "0.2.0-alpha.8") throw new Error(fromPrevious.tag);
if (!next.releaseUrl.includes("github.com/speed-y/nuvio-pro-ps5/releases/tag/")) throw new Error(next.releaseUrl);
if (parseLatestRelease(releases[1]) !== null) throw new Error("pull-request tag was accepted");
''')
            subprocess.run(['node', str(probe)], cwd=tree, check=True, timeout=20)
