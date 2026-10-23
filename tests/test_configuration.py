"""Production checks must support the same optional folder ID without writes."""
import unittest
from unittest.mock import Mock

from pulse.configuration import backup_folder

FOLDER = {'id':'folder-id','mimeType':'application/vnd.google-apps.folder',
          'trashed':False,'capabilities':{'canAddChildren':True}}


class ConfigurationTests(unittest.TestCase):
    def drive(self):
        drive=Mock();drive.api='https://www.googleapis.com/drive/v3/files'
        drive.children.return_value=[dict(FOLDER)]
        drive.request.return_value.json.return_value=dict(FOLDER)
        return drive

    def test_optional_id_discovers_existing_folder_and_only_reads(self):
        drive=self.drive()
        self.assertEqual(backup_folder(drive),FOLDER)
        drive.children.assert_called_once_with('root','PULSE')
        self.assertEqual(drive.request.call_count,1)
        self.assertEqual(drive.request.call_args.args,('GET',drive.api+'/folder-id'))

    def test_explicit_id_reads_that_folder_without_discovery(self):
        drive=self.drive();backup_folder(drive,'configured-id')
        drive.children.assert_not_called()
        self.assertEqual(drive.request.call_args.args,('GET',drive.api+'/configured-id'))

    def test_missing_ambiguous_or_nonfolder_never_creates_any_resource(self):
        for rows in ([],[FOLDER,FOLDER],[{'id':'file','mimeType':'application/zip'}]):
            drive=self.drive();drive.children.return_value=rows
            with self.subTest(rows=rows),self.assertRaises(ValueError):backup_folder(drive)
            drive.request.assert_not_called();drive.folder.assert_not_called()

    def test_unsafe_deleted_or_unwritable_folder_is_rejected(self):
        drive=self.drive()
        with self.assertRaises(ValueError):backup_folder(drive,'../other')
        drive.request.assert_not_called()
        for change in ({'trashed':True},{'mimeType':'application/zip'},
                       {'capabilities':{'canAddChildren':False}},{'capabilities':{}}):
            drive=self.drive();drive.request.return_value.json.return_value={**FOLDER,**change}
            with self.subTest(change=change),self.assertRaises(ValueError):backup_folder(drive)
            self.assertEqual(drive.request.call_args.args[0],'GET')
