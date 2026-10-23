"""Public artifacts must expose only authenticated ciphertext."""
import base64
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from pulse.secure_state import artifact_payload, decrypt, encrypt, extract, pack, require_key
from scripts.state import unpack


class SecureStateTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'PULSE_STATE_KEY':base64.b64encode(b'a'*32).decode(),
                                           'PULSE_REQUIRE_ENCRYPTED_STATE':'true'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_roundtrip_restores_date_scoped_paid_checkpoints_without_public_plaintext(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'private';day=source/'2026-10-24'
            day.mkdir(parents=True);(day/'research.json').write_text('{"private":"source evidence"}')
            (day/'api-usage.jsonl').write_text('{"tokens":17}\n')
            (day/'podcast.mp3').write_bytes(b'cached-audio')
            encrypted=root/'state.enc'
            self.assertTrue(pack(source,encrypted))
            self.assertNotIn(b'source evidence',encrypted.read_bytes())
            wrapper=io.BytesIO()
            with zipfile.ZipFile(wrapper,'w') as z:z.write(encrypted,'state.enc')
            unpack(artifact_payload(wrapper.getvalue()),root/'restore','2026-10-24')
            self.assertEqual((root/'restore/2026-10-24/research.json').read_bytes(),(day/'research.json').read_bytes())
            self.assertEqual((root/'restore/2026-10-24/podcast.mp3').read_bytes(),b'cached-audio')

    def test_nonce_changes_and_tampering_or_wrong_key_never_returns_plaintext(self):
        original=encrypt(b'private')
        self.assertNotEqual(original,encrypt(b'private'))
        altered=bytearray(original);altered[-1]^=1
        with self.assertRaises(ValueError):decrypt(bytes(altered))
        with patch.dict(os.environ,{'PULSE_STATE_KEY':base64.b64encode(b'b'*32).decode()}):
            with self.assertRaises(ValueError):decrypt(original)

    def test_missing_or_malformed_key_is_blocked_before_paid_generation(self):
        for value in ('','not base64',base64.b64encode(b'short').decode()):
            with self.subTest(value=value),patch.dict(os.environ,{'PULSE_STATE_KEY':value}):
                with self.assertRaises(ValueError):require_key()

    def test_existing_app_key_derives_a_separate_stable_key_without_new_secret(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        private=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        results=[]
        for fmt in (serialization.PrivateFormat.PKCS8,serialization.PrivateFormat.TraditionalOpenSSL):
            pem=private.private_bytes(serialization.Encoding.PEM,fmt,serialization.NoEncryption()).decode()
            with patch.dict(os.environ,{'PULSE_STATE_KEY':pem}):
                results.append(require_key())
                self.assertEqual(decrypt(encrypt(b'checkpoint')),b'checkpoint')
        self.assertEqual(results[0],results[1]);self.assertEqual(len(results[0]),32)
        with patch.dict(os.environ,{'PULSE_STATE_KEY':'-----BEGIN PRIVATE KEY-----\ninvalid'}):
            with self.assertRaises(ValueError):require_key()

    def test_public_restore_rejects_legacy_or_mixed_plaintext_artifacts(self):
        for contents in ({'2026-10-24/research.json':b'private'},
                         {'state.enc':encrypt(b'private'),'leaked.txt':b'private'}):
            raw=io.BytesIO()
            with zipfile.ZipFile(raw,'w') as z:
                for name,value in contents.items():z.writestr(name,value)
            with self.assertRaisesRegex(ValueError,'Unencrypted'):artifact_payload(raw.getvalue())

    def test_authenticated_archive_cannot_escape_destination(self):
        raw=io.BytesIO()
        with zipfile.ZipFile(raw,'w') as z:z.writestr('../escape.txt','private')
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'state.enc';source.write_bytes(encrypt(raw.getvalue()))
            with self.assertRaisesRegex(ValueError,'Unsafe'):extract(source,Path(tmp)/'target')
            self.assertFalse((Path(tmp)/'escape.txt').exists())

    def test_missing_empty_or_symlinked_state_is_not_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'state';output=root/'state.enc'
            self.assertFalse(pack(source,output));source.mkdir()
            self.assertFalse(pack(source,output))
            (source/'link').symlink_to('/etc/passwd')
            with self.assertRaisesRegex(ValueError,'symlinks'):pack(source,output)
            self.assertFalse(output.exists())

    def test_all_private_checkpoint_uploads_use_encryption_and_keep_schedule_control(self):
        root=Path(__file__).resolve().parents[1]
        for name in ('daily-publish.yml','complete-chapters.yml','publish-ready.yml','podcast-chapters.yml'):
            text=(root/'.github/workflows'/name).read_text()
            self.assertIn('uses: ./.github/actions/save-state',text)
            self.assertIn('PULSE_REQUIRE_ENCRYPTED_STATE: "true"',text)
            self.assertNotIn('path: .pulse-work/',text)
            self.assertNotIn('path: .chapter-state/',text)
            self.assertNotIn('path: .chapter-recovery/',text)
        for name in ('daily-publish.yml','publish-ready.yml'):
            self.assertIn("vars.PULSE_AUTOMATION_ENABLED != 'false'",(root/'.github/workflows'/name).read_text())
