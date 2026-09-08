import gc
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from publish_cloud import Publisher

class PublisherDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.publisher=Publisher.__new__(Publisher)
        self.publisher.dbpath=Path(self.temp.name)/'uploads.sqlite'
    def tearDown(self):self.temp.cleanup()
    def test_commits_rolls_back_and_closes_even_on_failure(self):
        with self.publisher.db() as db:
            db.execute('CREATE TABLE values_test(value INTEGER)')
            db.execute('INSERT INTO values_test VALUES(1)')
        with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
        with self.assertRaises(ValueError):
            with self.publisher.db() as failed:
                failed.execute('INSERT INTO values_test VALUES(2)')
                raise ValueError('abort')
        with self.assertRaises(sqlite3.ProgrammingError):failed.execute('SELECT 1')
        with self.publisher.db() as db:
            self.assertEqual(db.execute('SELECT value FROM values_test').fetchall(),[(1,)])
    @unittest.skipUnless(Path('/proc/self/fd').exists(),'Linux file descriptor accounting')
    def test_sustained_transactions_do_not_depend_on_garbage_collection(self):
        gc.collect();was_enabled=gc.isenabled();gc.disable()
        try:
            before=len(os.listdir('/proc/self/fd'))
            for _ in range(1200):
                with self.publisher.db() as db:db.execute('SELECT 1').fetchone()
            self.assertLessEqual(len(os.listdir('/proc/self/fd')),before+1)
        finally:
            if was_enabled:gc.enable()
            gc.collect()

if __name__=='__main__':unittest.main()
