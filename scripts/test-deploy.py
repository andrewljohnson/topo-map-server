"""Verify release source selection without SSH, a server, or Docker."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
class DeployTests(unittest.TestCase):
    def test_local_main_then_remote_main_ignore_other_branches_and_dirty_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'repo';root.mkdir()
            def git(*args):return subprocess.check_output(['git',*args],cwd=root,stderr=subprocess.DEVNULL,text=True).strip()
            git('init','-b','main');git('config','user.name','Release test');git('config','user.email','test@example.invalid')
            for name in ('scripts/deploy.sh','scripts/deploy-cloud.py','scripts/env.sh','services/tiles/cloud_config.py'):
                target=root/name;target.parent.mkdir(exist_ok=True,parents=True);shutil.copyfile(ROOT/name,target)
            git('add','.');git('commit','-m','main')
            original=git('rev-parse','HEAD')
            git('checkout','-b','unreleased');(root/'unreleased.txt').write_text('unreleased')
            git('add','.');git('commit','-m','unreleased');(root/'dirty.txt').write_text('dirty')
            def dry():return subprocess.check_output(['bash','scripts/deploy.sh','--dry-run'],cwd=root,text=True,stderr=subprocess.DEVNULL)
            self.assertIn(original,dry())
            remote=Path(tmp)/'remote.git';git('clone','--bare',str(root),str(remote));git('remote','add','origin',str(remote))
            git('checkout','main');(root/'new-main.txt').write_text('released')
            git('add','new-main.txt');git('commit','-m','next main');new=git('rev-parse','HEAD')
            git('push','origin','main');git('checkout','unreleased')
            self.assertIn(new,dry())
            self.assertEqual(git('branch','--show-current'),'unreleased')
            self.assertEqual((root/'dirty.txt').read_text(),'dirty')
if __name__=='__main__':unittest.main()
