"""Material loading and paging tests without a graphical display."""
import json
from pathlib import Path
import tempfile
import tkinter as tk
import unittest
from unittest.mock import Mock, patch
import zipfile

from material_picker import MaterialCatalog, MaterialPicker


class MaterialPickerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.jar=self.root/'resources.jar'
        with zipfile.ZipFile(self.jar,'w') as archive:
            for name in ('apple','bread'):
                archive.writestr(f'assets/minecraft/items/{name}.json',json.dumps(
                    {'model':{'type':'minecraft:model','model':f'minecraft:item/{name}'}}))
                archive.writestr(f'assets/minecraft/models/item/{name}.json',json.dumps(
                    {'parent':'minecraft:item/base'}))
            archive.writestr('assets/minecraft/models/item/base.json',json.dumps(
                {'textures':{'layer0':'minecraft:item/shared'}}))
            archive.writestr('assets/minecraft/textures/item/shared.png',b'texture bytes')
            archive.writestr('assets/minecraft/items/complex.json',json.dumps(
                {'model':{'type':'minecraft:composite'}}))
        with patch('material_picker.local_japanese_names',return_value={}):
            self.catalog=MaterialCatalog(self.root,[],self.jar)

    def picker(self):
        picker=MaterialPicker.__new__(MaterialPicker)
        picker.catalog=self.catalog;picker.images={};picker.page=0
        picker.search=Mock();picker.search.get.return_value=''
        picker.list=Mock();picker.list.get_children.return_value=()
        picker.window=Mock()
        for name in ('previous','next','page_info','notice'):
            setattr(picker,name,Mock())
        return picker

    def test_shared_archive_preserves_parent_texture_and_complex_fallback(self):
        self.assertEqual(self.catalog.texture('minecraft:apple'),b'texture bytes')
        with zipfile.ZipFile(self.jar) as archive:
            self.assertEqual(self.catalog.texture('minecraft:bread',archive),b'texture bytes')
            self.assertIsNone(self.catalog.texture('minecraft:complex',archive))

    def test_page_opens_archive_once_and_cached_page_does_not_reopen(self):
        picker=self.picker()
        image=Mock();image.width.return_value=32;image.height.return_value=32
        with patch('material_picker.zipfile.ZipFile',wraps=zipfile.ZipFile) as opened, patch('material_picker.tk.PhotoImage',return_value=image):
            picker.populate()
            self.assertEqual(opened.call_count,1)
            picker.populate()
            self.assertEqual(opened.call_count,1)
        self.assertEqual(len(picker.images),4)
        self.assertIsNone(picker.images['minecraft:complex'])

    def test_unavailable_archive_still_displays_selectable_rows(self):
        picker=self.picker()
        self.jar.unlink()
        picker.populate()
        self.assertEqual(picker.list.insert.call_count,4)
        self.assertTrue(all(image is None for image in picker.images.values()))

    def test_search_matches_casefolded_ids(self):
        picker=self.picker();picker.search.get.return_value='APPLE'
        with patch('material_picker.tk.PhotoImage',side_effect=tk.TclError('no image')):
            picker.populate()
        self.assertEqual(picker.matches,['minecraft:apple'])


if __name__=='__main__':unittest.main()
