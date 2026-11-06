import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import zipfile
from scripts import metadata_backup as backup
from scripts.metadata_backup_download import arguments


class MetadataBackupTest(unittest.TestCase):
    def archive(self):
        output = io.BytesIO()
        backup.archive_metadata(output, {n: b'{"fixture":true}' for n in backup.CONFIG_NAMES},
                                [sys.executable, '-c', 'import sys;sys.stdout.buffer.write(b"PGDMP-fixture")'])
        return output.getvalue()

    def test_stream_archive_validates_and_contains_only_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'backup.zip'
            path.write_bytes(self.archive())
            manifest = backup.validate_archive(path)
            self.assertEqual(manifest['files']['database.dump']['bytes'], 13)
            with zipfile.ZipFile(path) as archive:
                self.assertEqual(set(archive.namelist()), {*backup.CONFIG_NAMES, 'database.dump', 'manifest.json'})

    def test_dump_failure_cannot_produce_successful_backup(self):
        with self.assertRaises(RuntimeError):
            backup.archive_metadata(io.BytesIO(), {n: b'{}' for n in backup.CONFIG_NAMES},
                                    [sys.executable, '-c', 'import sys;sys.stdout.write("partial");sys.exit(1)'])

    def test_rejects_checksum_mismatch_extra_duplicate_and_symlink_members(self):
        original = self.archive()
        for mode in ('tamper', 'traversal', 'duplicate', 'symlink'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'bad.zip'
                with zipfile.ZipFile(io.BytesIO(original)) as src, zipfile.ZipFile(path, 'w') as dst:
                    for item in src.infolist():
                        data = src.read(item)
                        if mode == 'tamper' and item.filename == 'database.dump':
                            data = b'bad-dump'
                        if mode == 'symlink' and item.filename == 'server.json':
                            item.external_attr = (stat.S_IFLNK | 0o600) << 16
                        dst.writestr(item, data)
                    if mode in ('traversal', 'duplicate'):
                        # Duplicate warning is expected input corruption, not a suppressed check.
                        dst.writestr('../escape' if mode == 'traversal' else 'manifest.json', b'{}')
                with self.assertRaises(ValueError):
                    backup.validate_archive(path)

    def test_retention_preserves_foreign_legacy_and_symlink_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for stamp in ('20200101T000000Z', '20990101T000000Z'):
                name = 'metadata-' + stamp + '-0123abcd.zip.gpg'
                file = root / name
                file.write_bytes(b'ciphertext')
                file.chmod(0o600)
                with file.open('rb') as source:
                    backup.atomic_json(root / (name + '.json'), {'name': name, **backup.digest_stream(source)})
            legacy = root / 'camera-old.tar.gz.gpg'
            legacy.write_bytes(b'legacy')
            foreign = root / 'metadata-20200101T000000Z-11111111.zip.gpg'
            foreign.symlink_to(legacy)
            backup.prune(root, 14)
            self.assertFalse((root / 'metadata-20200101T000000Z-0123abcd.zip.gpg').exists())
            self.assertTrue((root / 'metadata-20990101T000000Z-0123abcd.zip.gpg').exists())
            self.assertEqual(legacy.read_bytes(), b'legacy')
            self.assertTrue(foreign.is_symlink())

    def test_names_cannot_escape_backup_directory(self):
        for name in ('../server.json', '/etc/passwd', 'metadata-invalid.zip.gpg', 'metadata-20261103T000000Z-0123abcd.zip.gpg;id'):
            self.assertIsNone(backup.NAME.fullmatch(name))

    def test_forced_ssh_command_rejects_shell_and_other_operations(self):
        self.assertEqual(arguments('list'), ['list'])
        name = 'metadata-20261103T000000Z-0123abcd.zip.gpg'
        self.assertEqual(arguments('stream ' + name), ['stream', name])
        for command in ('', 'sh', 'create', 'list;id', 'stream ../server.json', 'stream '+name+';id', 'stream '+name+'\n'):
            with self.assertRaises(ValueError):
                arguments(command)
