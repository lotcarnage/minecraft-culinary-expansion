"""Editor errors remain understandable without English library messages."""
import json
import struct
import tkinter as tk
import unittest
import zipfile
from error_messages import japanese_error
import item_project


class JapaneseErrorTests(unittest.TestCase):
    def test_duplicate_name_and_numeric_errors_explain_fields(self):
        item=item_project.default_item('flour')
        with self.assertRaisesRegex(ValueError,'同じ代表名が登録済み'):
            item_project.validate({'schema_version':1,'items':[item,item.copy()]})
        item['nutrition']=-1
        with self.assertRaisesRegex(ValueError,'満腹度回復量は0〜100'):
            item_project.validate({'schema_version':1,'items':[item]})

    def test_library_errors_are_translated(self):
        cases=[(FileNotFoundError(2,'No such file','project.json'),'見つかりません'),
               (PermissionError(13,'Permission denied','project.json'),'アクセスできません'),
               (json.JSONDecodeError('Expecting value','{',1),'1行目、2文字目'),
               (zipfile.BadZipFile('File is not a zip file'),'形式が正しくありません'),
               (struct.error('unpack requires a buffer'),'正常なPNG'),
               (tk.TclError('could not recognize image data'),'画面や画像')]
        for error,expected in cases:
            with self.subTest(error=type(error).__name__):
                message=japanese_error(error)
                self.assertIn(expected,message)
                self.assertNotIn(str(error),message)

    def test_japanese_validation_is_preserved_and_unknown_errors_are_localized(self):
        self.assertEqual(japanese_error(ValueError('素材を指定してください。')),'素材を指定してください。')
        with self.assertLogs('error_messages',level='ERROR'):
            message=japanese_error(RuntimeError('unexpected internal failure'))
        self.assertIn('予期しないエラー',message)
        self.assertNotIn('unexpected internal failure',message)


if __name__=='__main__':unittest.main()
