import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

import setup_jdk


class SetupJdkTests(unittest.TestCase):
    def test_download_verify_extract_and_reuse(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            for name in ('java.exe', 'javac.exe'):
                archive.writestr('jdk-25.0.4.1+1/bin/' + name, b'executable')
        payload = data.getvalue()
        checksum = (hashlib.sha256(payload).hexdigest() +
                    '  microsoft-jdk-25.0.4.1-windows-x64.zip\n').encode()
        with tempfile.TemporaryDirectory() as directory, \
                patch('setup_jdk.platform.system', return_value='Windows'), \
                patch('setup_jdk.platform.machine', return_value='AMD64'), \
                patch('setup_jdk.urllib.request.urlopen', side_effect=[io.BytesIO(checksum), io.BytesIO(payload)]) as download:
            home = setup_jdk.ensure_jdk(Path(directory))
            self.assertTrue((home / 'bin/javac.exe').is_file())
            self.assertIn(setup_jdk.URL, (home / 'download-source.txt').read_text())
            self.assertEqual(setup_jdk.ensure_jdk(Path(directory)), home)
            self.assertEqual(download.call_count, 2)
            self.assertEqual(download.call_args_list[0].args[0],
                             setup_jdk.URL + '.sha256sum.txt')

    def test_checksum_mismatch_does_not_install(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('setup_jdk.platform.system', return_value='Windows'), \
                patch('setup_jdk.platform.machine', return_value='AMD64'), \
                patch('setup_jdk.urllib.request.urlopen', side_effect=[io.BytesIO(b'0' * 64), io.BytesIO(b'invalid')]):
            with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                setup_jdk.ensure_jdk(Path(directory))
            self.assertEqual(list((Path(directory) / 'intermediate/jdk25').iterdir()), [])
