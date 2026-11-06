import io
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from scripts.camera_management_recovery import pack, unpack, crypt, restore, destinations


FIXTURE = {'remote/ssh_config': b'fixture config', 'remote/ssh/mini-jump': b'fixture jump key',
           'remote/ssh/air-admin': b'fixture Air key'}


class ManagementRecoveryTests(unittest.TestCase):
    def test_archive_roundtrip_and_restore_under_new_account_paths(self):
        items=unpack(pack(FIXTURE))
        self.assertEqual(items,FIXTURE)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve()
            targets=destinations(root/'new-home',root/'new-project')
            restore(items,targets)
            for name,body in items.items():
                self.assertEqual(targets[name].read_bytes(),body)
                self.assertEqual(targets[name].stat().st_mode&0o777,0o600)
            self.assertEqual(targets['remote/ssh_config'],root/'new-home/.ssh/camera-management/config')

    def test_existing_different_key_aborts_before_any_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp).resolve();targets=destinations(root/'home',root/'project')
            key=targets['remote/ssh/air-admin'];key.parent.mkdir(parents=True);key.write_bytes(b'existing');key.chmod(0o600)
            with self.assertRaises(ValueError):restore(FIXTURE,targets)
            self.assertFalse(targets['remote/ssh_config'].exists())
            self.assertEqual(key.read_bytes(),b'existing')

    def test_tar_link_traversal_duplicate_and_size_are_rejected(self):
        for name,kind,size in [('../outside',tarfile.REGTYPE,1),('remote/ssh/mini-jump',tarfile.SYMTYPE,0),
                               ('remote/ssh/mini-jump',tarfile.REGTYPE,1024*1024+1)]:
            output=io.BytesIO()
            with tarfile.open(fileobj=output,mode='w:gz') as tar:
                info=tarfile.TarInfo(name);info.type=kind;info.size=size;info.linkname='/outside'
                tar.addfile(info,io.BytesIO(b'x'*size) if size else None)
            with self.subTest(name=name,kind=kind),self.assertRaises(ValueError):unpack(output.getvalue())
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as tar:
            for _ in range(2):
                info=tarfile.TarInfo('remote/ssh/mini-jump');info.size=1;tar.addfile(info,io.BytesIO(b'x'))
        with self.assertRaises(ValueError):unpack(output.getvalue())

    def test_manifest_must_match_contents(self):
        output=io.BytesIO()
        with tarfile.open(fileobj=output,mode='w:gz') as tar:
            body=b'{"version":1,"sha256":{}}';info=tarfile.TarInfo('manifest.json');info.size=len(body);tar.addfile(info,io.BytesIO(body))
        with self.assertRaises(ValueError):unpack(output.getvalue())

    @unittest.skipUnless(shutil.which('gpg'),'GnuPG is required for the cryptographic integration gate')
    def test_real_gpg_roundtrip_wrong_password_and_tamper(self):
        password='fixture-only-recovery-password'
        encrypted=crypt(pack(FIXTURE),password)
        self.assertEqual(unpack(crypt(encrypted,password,True)),FIXTURE)
        with self.assertRaises(ValueError):crypt(encrypted,'wrong-fixture-password',True)
        changed=bytearray(encrypted);changed[len(changed)//2]^=1
        with self.assertRaises(ValueError):crypt(bytes(changed),password,True)
