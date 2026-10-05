"""Model and resource lifecycle checks; run python -m unittest discover -s helper -p test_item_project.py."""
import json
from pathlib import Path
import tempfile
import struct
import unittest
import zlib
from unittest.mock import patch
import item_project as m

class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.path=self.root/'source/items_project.json'
        self.project={'schema_version':1,'items':[m.default_item('fried_egg')],'generated_files':[]}
        m.save(self.project,self.path)
    def tearDown(self):self.temp.cleanup()
    def test_placeholder_texture_and_existing_texture(self):
        item=m.default_item('test_disk')
        texture=m.ensure_texture(item,self.root)
        self.assertEqual(texture,self.root/(m.ASSETS+'textures/item/test_disk.png'))
        png=texture.read_bytes()
        self.assertEqual(png[:8],b'\x89PNG\r\n\x1a\n')
        self.assertEqual(struct.unpack('>II',png[16:24]),(16,16))
        self.assertEqual(png[24:26],bytes((8,3)))
        offset=8;compressed=b'';palette=b'';alpha=b''
        while offset<len(png):
            size=struct.unpack('>I',png[offset:offset+4])[0]
            kind=png[offset+4:offset+8];data=png[offset+8:offset+8+size]
            crc=struct.unpack('>I',png[offset+8+size:offset+12+size])[0]
            self.assertEqual(crc,zlib.crc32(kind+data)&0xffffffff)
            if kind==b'IDAT':compressed+=data
            if kind==b'PLTE':palette=data
            if kind==b'tRNS':alpha=data
            offset+=12+size
        rows=zlib.decompress(compressed)
        self.assertEqual(len(rows),16*17)
        self.assertEqual(alpha,bytes((0,255,255)))
        colors=[tuple(palette[i*3:i*3+3])+(alpha[i],) for i in range(3)]
        pixels=[colors[rows[y*17+1+x]] for y in range(16) for x in range(16)]
        self.assertEqual(set(pixels),{(255,255,255,255),(0,0,0,255),(0,0,0,0)})
        self.assertEqual(pixels[8*16+8],(255,255,255,255))
        self.assertEqual(pixels[1*16+8],(0,0,0,255))
        self.assertEqual(pixels[0],(0,0,0,0))
        self.assertEqual(pixels,list(reversed(pixels)))
        texture.write_bytes(b'existing custom image')
        m.ensure_texture(item,self.root)
        self.assertEqual(texture.read_bytes(),b'existing custom image')

    def test_add_edit_remove_preserves_texture_and_unrelated_files(self):
        m.export(self.project,self.path,self.root)
        texture=self.root/m.derived(self.project['items'][0])['テクスチャ'];texture.parent.mkdir(parents=True);texture.write_bytes(b'keep texture')
        unrelated=self.root/(m.DATA+'recipe/unrelated.json');unrelated.write_text('{}')
        lang=self.root/(m.ASSETS+'lang/ja_jp.json');values=json.loads(lang.read_text(encoding="utf-8"));values['item.culinary_expansion.manual']='手動';lang.write_text(json.dumps(values), encoding="utf-8")
        self.project['items'][0]['name']='omelette';m.export(self.project,self.path,self.root)
        self.assertFalse((self.root/(m.ASSETS+'items/fried_egg.json')).exists())
        self.assertTrue((self.root/(m.ASSETS+'items/omelette.json')).exists())
        self.project['items']=[];m.export(self.project,self.path,self.root)
        self.assertEqual(texture.read_bytes(),b'keep texture');self.assertTrue(unrelated.exists())
        self.assertEqual(json.loads(lang.read_text(encoding="utf-8"))['item.culinary_expansion.manual'],'手動')
        self.assertFalse((self.root/(m.DATA+'recipe/omelette_from_smelting.json')).exists())
    def test_crafting_and_effects(self):
        item=self.project['items'][0];item.update(crafting='定型',effect='毒',effect_level=2,remainder='ボウル',campfire_ticks=600)
        item['crafting_slots']=['不要','minecraft:egg','不要','minecraft:sugar','minecraft:egg','不要','不要','不要','不要']
        files=m.generated(self.project,self.root);r=json.loads(files[m.DATA+'recipe/fried_egg_from_crafting.json'])
        self.assertEqual(r['pattern'],[' A','BA']);self.assertEqual(r['key'],{'A':'minecraft:egg','B':'minecraft:sugar'})
        java=files[m.JAVA+'ModItems.java'].decode();self.assertIn('MobEffects.POISON, 200, 1',java);self.assertIn('usingConvertsTo(Items.BOWL)',java)
        item['crafting']='不定形';r=json.loads(m.generated(self.project,self.root)[m.DATA+'recipe/fried_egg_from_crafting.json'])
        self.assertEqual(r['ingredients'],['minecraft:egg','minecraft:sugar','minecraft:egg'])
        self.assertEqual(json.loads(files[m.DATA+'recipe/fried_egg_from_smoking.json'])['cookingtime'],200)
    def test_chocolate_registration_and_any_material_unlock(self):
        item=m.default_item('chocolate')
        item.update(smelting=False,smoking=False,crafting='不定形')
        item['crafting_slots']=['minecraft:sugar','minecraft:cocoa_beans']+['不要']*7
        self.project['items']=[item]
        files=m.generated(self.project,self.root)
        recipe=json.loads(files[m.DATA+'recipe/chocolate_from_crafting.json'])
        self.assertEqual(recipe['type'],'minecraft:crafting_shapeless')
        self.assertEqual(recipe['category'],'misc')
        self.assertEqual(recipe['ingredients'],['minecraft:sugar','minecraft:cocoa_beans'])
        advancement=json.loads(files[m.DATA+'advancement/recipes/food/chocolate_from_crafting.json'])
        self.assertEqual(advancement['requirements'],[['has_the_recipe','has_material_0','has_material_1']])
        self.assertEqual(advancement['criteria']['has_material_1']['conditions']['items'],[{'items':'minecraft:cocoa_beans'}])
        java=files[m.JAVA+'ModItems.java'].decode()
        self.assertIn('ITEMS.register("chocolate"',java)
        self.assertIn('CreativeModeTabs.FOOD_AND_DRINKS',java)
        self.assertIn('event.accept(CHOCOLATE)',java)
    def test_all_recipes_unlock_from_any_enabled_material(self):
        item=self.project['items'][0]
        item.update(crafting='不定形',campfire_ticks=600)
        item['crafting_slots']=['minecraft:sugar','#minecraft:logs','minecraft:sugar']+['不要']*6
        files=m.generated(self.project,self.root)
        for kind in ('smelting','smoking','campfire_cooking','crafting'):
            advancement=json.loads(files[m.DATA+f'advancement/recipes/food/fried_egg_from_{kind}.json'])
            materials=[value['conditions']['items'][0]['items'] for key,value in advancement['criteria'].items() if key.startswith('has_material_')]
            self.assertEqual(materials,['minecraft:egg','minecraft:sugar','#minecraft:logs'])
            self.assertEqual(advancement['requirements'],[list(advancement['criteria'])])
        item.update(smelting=False,smoking=False,campfire_ticks=None)
        advancement=json.loads(m.generated(self.project,self.root)[m.DATA+'advancement/recipes/food/fried_egg_from_crafting.json'])
        materials=[value['conditions']['items'][0]['items'] for key,value in advancement['criteria'].items() if key.startswith('has_material_')]
        self.assertEqual(materials,['minecraft:sugar','#minecraft:logs'])
    def test_validation_and_manifest(self):
        for name in ('../escape','Invalid Name',''):
            self.project['items'][0]['name']=name
            with self.assertRaises(ValueError):m.validate(self.project)
        self.project['items'][0]['name']='fried_egg'
        self.project['generated_files']=['../escape'];m.save(self.project,self.path)
        with self.assertRaises(ValueError):m.export(self.project,self.path,self.root)
    def test_export_rolls_back(self):
        m.export(self.project,self.path,self.root)
        before={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.project['items'][0]['name']='renamed'
        with patch.object(m,'save',side_effect=OSError('injected write failure')):
            with self.assertRaises(OSError):m.export(self.project,self.path,self.root)
        after={p:p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

if __name__=='__main__':unittest.main()
