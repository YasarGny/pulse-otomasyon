"""Valid runtime caches must avoid network installs; bad caches must recover."""
import os
from pathlib import Path
import subprocess
import tempfile
import textwrap
import unittest


class RuntimeSetupTests(unittest.TestCase):
    def test_cached_environment_is_checked_and_missing_environment_is_built_without_apt_when_tools_exist(self):
        action=(Path(__file__).resolve().parents[1]/'.github/actions/setup-runtime/action.yml').read_text()
        raw=action[action.index('        runtime_python='):].split('    - uses:',1)[0]
        script=textwrap.dedent(raw)
        subprocess.run(['bash','-n'],input=script,text=True,check=True)
        for valid in (True,False):
            with self.subTest(valid=valid),tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);bin_dir=root/'bin';bin_dir.mkdir()
                runtime=root/'.pulse-runtime/bin/python';runtime.parent.mkdir(parents=True)
                # Fail if any code attempts an unnecessary apt call.
                (bin_dir/'sudo').write_text('#!/bin/sh\nexit 99\n');(bin_dir/'sudo').chmod(0o755)
                good='#!/bin/sh\nprintf "%s\\n" "$*" >> "$TRACE"\nif [ "$1" = "-" ]; then cat >/dev/null; fi\nexit 0\n'
                (root/'good').write_text(good)
                runtime.write_text(good if valid else '#!/bin/sh\nexit 1\n');runtime.chmod(0o755)
                (bin_dir/'python').write_text('#!/bin/sh\nprintf "create-venv\\n" >> "$TRACE"\ncp "$GITHUB_WORKSPACE/good" "$GITHUB_WORKSPACE/.pulse-runtime/bin/python"\nchmod +x "$GITHUB_WORKSPACE/.pulse-runtime/bin/python"\n')
                (bin_dir/'python').chmod(0o755)
                for tool in ('ffmpeg','ffprobe'):
                    (bin_dir/tool).write_text('#!/bin/sh\nexit 0\n');(bin_dir/tool).chmod(0o755)
                env={**os.environ,'GITHUB_WORKSPACE':str(root),'GITHUB_PATH':str(root/'path'),
                     'TRACE':str(root/'trace'),'PATH':str(bin_dir)+':'+os.environ['PATH']}
                subprocess.run(['bash','-eo','pipefail','-c',script],cwd=root,env=env,check=True,capture_output=True,text=True)
                trace=(root/'trace').read_text()
                self.assertIn('-m pip check',trace)
                self.assertEqual('create-venv' in trace,not valid)
                self.assertEqual('-m pip install -r requirements.txt' in trace,not valid)
                self.assertEqual((root/'path').read_text().strip(),str(runtime.parent))
