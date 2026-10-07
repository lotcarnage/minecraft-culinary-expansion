"""Canonical item project and generation of Forge 26.3 item resources."""
from copy import deepcopy
import json
import math
from pathlib import Path
import re
import struct
import tempfile
import zlib

ROOT = Path(__file__).resolve().parent.parent
PROJECT = ROOT / 'source/items_project.json'
NS = 'culinary_expansion'
JAVA = 'source/main/java/dev/lotcarnage/culinaryexpansion/'
ASSETS = f'source/main/resources/assets/{NS}/'
DATA = f'source/main/resources/data/{NS}/'
EFFECTS = {'なし': None, '移動速度上昇': 'SPEED', '再生能力': 'REGENERATION', '耐火': 'FIRE_RESISTANCE',
           '暗視': 'NIGHT_VISION', '攻撃力上昇': 'STRENGTH', '毒': 'POISON', '空腹': 'HUNGER', '衰弱': 'WITHER'}
REMAINDERS = {'なし': None, 'ボウル': 'BOWL', 'ガラス瓶': 'GLASS_BOTTLE', 'バケツ': 'BUCKET'}
SLOTS = [f'{r}:{c}' for r in range(1, 4) for c in range(1, 4)]


def default_item(name):
    return {'name': name, 'enabled': True, 'ja_name': name, 'en_name': name.replace('_', ' ').title(),
            'stack_size': 64, 'nutrition': 5, 'saturation_modifier': 0.6,
            'always_edible': False, 'consume_seconds': 1.6, 'effect': 'なし',
            'effect_ticks': 200, 'effect_level': 1, 'effect_probability': 1.0, 'remainder': 'なし',
            'smelting': True, 'smoking': True, 'cooking_ticks': 200, 'experience': 0.35,
            'cooking_ingredient': 'minecraft:egg', 'cooking_output': 1, 'campfire_ticks': None,
            'crafting': 'クラフト不可', 'crafting_output': 1, 'crafting_slots': ['不要'] * 9}


def ensure_texture(item, root=ROOT):
    """Create a 16px placeholder only when the item's texture does not exist."""
    validate({'schema_version': 1, 'items': [item]})
    path = Path(root) / derived(item)['テクスチャ']
    if path.exists():
        return path

    def chunk(kind, data):
        checksum = zlib.crc32(kind + data) & 0xffffffff
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', checksum)

    # Indexed PNG: transparent background (0), opaque black (1), opaque white (2).
    scanlines = bytearray()
    for y in range(16):
        scanlines.append(0)  # PNG filter: None
        for x in range(16):
            distance = (2*x - 15)**2 + (2*y - 15)**2
            scanlines.append(2 if distance <= 144 else (1 if distance <= 196 else 0))
    png = (b'\x89PNG\r\n\x1a\n'
           + chunk(b'IHDR', struct.pack('>IIBBBBB', 16, 16, 8, 3, 0, 0, 0))
           + chunk(b'PLTE', bytes((0, 0, 0, 0, 0, 0, 255, 255, 255)))
           + chunk(b'tRNS', bytes((0, 255, 255)))
           + chunk(b'IDAT', zlib.compress(scanlines)) + chunk(b'IEND', b''))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        file = path.open('xb')  # Exclusive creation also protects a concurrent writer.
    except FileExistsError:
        return path
    try:
        with file:
            file.write(png)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path


def validate(project):
    if project.get('schema_version') != 1 or not isinstance(project.get('items'), list):
        raise ValueError('Unsupported project schema')
    version=project.get('version', '0.1.0')
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,63}',version):
        raise ValueError('Invalid project version: use 1..64 filename-safe letters, digits, ., _, + or -')
    names = set()
    def number(item, key, low, high, integer=False):
        v = item[key]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high or (integer and not isinstance(v, int)):
            raise ValueError(f'{item["name"]}: {key} must be {low}..{high}')
    def reference(v):
        if not isinstance(v, str) or not re.fullmatch(r'#?[a-z0-9_.-]+:[a-z0-9_/.-]+', v):
            raise ValueError(f'Invalid material ID: {v}')
    for item in project['items']:
        if set(item) != set(default_item('example')):
            raise ValueError('Missing or unknown item fields')
        name = item['name']
        if not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,63}', name) or name in names:
            raise ValueError(f'Invalid or duplicate representative name: {name}')
        names.add(name)
        for k in ('ja_name', 'en_name'):
            if not isinstance(item[k], str) or not item[k].strip(): raise ValueError(f'{k} is required')
        for k,lo,hi,integer in [('stack_size',1,99,True),('nutrition',0,100,True),('saturation_modifier',0,10,False),
                               ('consume_seconds',0.05,120,False),('effect_ticks',1,2147483647,True),
                               ('effect_level',1,256,True),('effect_probability',0,1,False),('cooking_ticks',1,2147483647,True),
                               ('experience',0,100,False),('cooking_output',1,99,True),('crafting_output',1,99,True)]:
            number(item,k,lo,hi,integer)
        for k in ('enabled','always_edible','smelting','smoking'):
            if not isinstance(item[k],bool):raise ValueError(f'{k} must be boolean')
        if item['campfire_ticks'] is not None: number(item,'campfire_ticks',1,2147483647,True)
        if item['effect'] not in EFFECTS or item['remainder'] not in REMAINDERS:raise ValueError('Unknown effect or remainder')
        if item['crafting'] not in ('クラフト不可','定型','不定形'):raise ValueError('Unknown crafting type')
        reference(item['cooking_ingredient'])
        slots=item['crafting_slots']
        if not isinstance(slots,list) or len(slots)!=9:raise ValueError('Exactly 9 crafting slots required')
        for slot in slots:
            if slot != '不要':reference(slot)
        if item['crafting']!='クラフト不可' and all(s=='不要' for s in slots):raise ValueError('Crafting requires materials')
        if item['cooking_output'] > item['stack_size'] or item['crafting_output'] > item['stack_size']:
            raise ValueError('Output count cannot exceed stack size')
    return project


def load(path=PROJECT):
    project=json.loads(Path(path).read_text(encoding='utf-8-sig'))
    project.setdefault('version','0.1.0')
    for item in project.get('items', []):
        item.setdefault('enabled', item.get('nutrition', 0) > 0)
    return validate(project)


def save(project,path=PROJECT):
    validate(project)
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.tmp')
    temp.write_text(json.dumps(project,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)


def derived(item):
    name=item['name']
    return {'アイテムID':f'{NS}:{name}', 'Java識別子':name.upper(), 'モデルID':f'{NS}:item/{name}',
            '表示定義':ASSETS+f'items/{name}.json','モデル':ASSETS+f'models/item/{name}.json',
            'テクスチャ':ASSETS+f'textures/item/{name}.png','翻訳キー':f'item.{NS}.{name}'}


def allowed(path):
    if path in (JAVA+'CulinaryExpansion.java',JAVA+'ModItems.java',ASSETS+'lang/ja_jp.json',ASSETS+'lang/en_us.json'):return True
    patterns=[ASSETS+r'items/[a-z][a-z0-9_]*\.json',ASSETS+r'models/item/[a-z][a-z0-9_]*\.json',
              DATA+r'recipe/[a-z][a-z0-9_]*_from_(smelting|smoking|campfire_cooking|crafting)\.json',
              DATA+r'advancement/recipes/food/[a-z][a-z0-9_]*_from_(smelting|smoking|campfire_cooking|crafting)\.json']
    return any(re.fullmatch(p,path) for p in patterns)


def generated(project,root=ROOT):
    validate(project);files={}
    def add(path,data):files[path]=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    for lang,field in [('ja_jp','ja_name'),('en_us','en_name')]:
        path=ASSETS+f'lang/{lang}.json'
        existing=json.loads((root/path).read_text(encoding='utf-8-sig')) if (root/path).exists() else {}
        owned = {Path(p).stem for p in project.get('generated_files', []) if p.startswith(ASSETS+'items/')} | {i['name'] for i in project['items']}
        existing={k:v for k,v in existing.items() if k not in {f'item.{NS}.{name}' for name in owned}}
        existing.update({f'item.{NS}.{i["name"]}':i[field] for i in project['items'] if i['enabled']});add(path,existing)
    registrations=[];accept=[]
    disabled_refs={f'{NS}:{item["name"]}' for item in project['items'] if not item['enabled']}
    for item in project['items']:
        if not item['enabled']:continue
        name=item['name'];id=f'{NS}:{name}'
        food=f'new FoodProperties.Builder().nutrition({item["nutrition"]}).saturationModifier({item["saturation_modifier"]}F)'
        if item['always_edible']:food+='.alwaysEdible()'
        food+='.build()'
        consumable=f'Consumable.builder().consumeSeconds({item["consume_seconds"]}F)'
        if EFFECTS[item['effect']]:
            consumable+=f'.onConsume(new ApplyStatusEffectsConsumeEffect(new MobEffectInstance(MobEffects.{EFFECTS[item["effect"]]}, {item["effect_ticks"]}, {item["effect_level"]-1}), {item["effect_probability"]}F))'
        consumable+='.build()'
        props=f'new Item.Properties().setId(ITEMS.key("{name}")).stacksTo({item["stack_size"]}).food({food}, {consumable})'
        if REMAINDERS[item['remainder']]:props+=f'.usingConvertsTo(Items.{REMAINDERS[item["remainder"]]})'
        registrations.append(f'    public static final RegistryObject<Item> {name.upper()} = ITEMS.register("{name}", () -> new Item({props}));')
        accept.append(f'            event.accept({name.upper()});')
        add(ASSETS+f'items/{name}.json',{'model':{'type':'minecraft:model','model':f'{NS}:item/{name}'}})
        add(ASSETS+f'models/item/{name}.json',{'parent':'minecraft:item/generated','textures':{'layer0':f'{NS}:item/{name}'}})
        recipes=[]
        for enabled,kind,ticks in [(item['smelting'],'smelting',item['cooking_ticks']), (item['smoking'],'smoking',item['cooking_ticks']), (item['campfire_ticks'] is not None,'campfire_cooking',item['campfire_ticks'])]:
            if enabled:recipes.append((kind,{'type':f'minecraft:{kind}','category':'food','ingredient':item['cooking_ingredient'],'result':{'id':id,'count':item['cooking_output']},'experience':item['experience'],'cookingtime':ticks}))
        if item['crafting']!='クラフト不可':
            slots=item['crafting_slots'];recipe={'category':'misc','result':{'id':id,'count':item['crafting_output']}}
            if item['crafting']=='不定形':recipe.update(type='minecraft:crafting_shapeless',ingredients=[v for v in slots if v!='不要'])
            else:
                used=[(i//3,i%3) for i,v in enumerate(slots) if v!='不要'];minr=min(r for r,c in used);maxr=max(r for r,c in used);minc=min(c for r,c in used);maxc=max(c for r,c in used)
                refs=list(dict.fromkeys(v for v in slots if v!='不要'));keys={v:chr(65+i) for i,v in enumerate(refs)}
                pattern=[''.join(keys.get(slots[r*3+c],' ') for c in range(minc,maxc+1)) for r in range(minr,maxr+1)]
                recipe.update(type='minecraft:crafting_shaped',pattern=pattern,key={keys[v]:v for v in refs})
            recipes.append(('crafting',recipe))
        unlock_materials=[]
        if item['smelting'] or item['smoking'] or item['campfire_ticks'] is not None:
            unlock_materials.append(item['cooking_ingredient'])
        if item['crafting']!='クラフト不可':
            unlock_materials.extend(v for v in item['crafting_slots'] if v!='不要')
        unlock_materials=list(dict.fromkeys(unlock_materials))
        for kind,recipe in recipes:
            ingredients=([item['cooking_ingredient']] if kind!='crafting'
                         else [v for v in item['crafting_slots'] if v!='不要'])
            if any(ref in disabled_refs for ref in ingredients):continue
            recipe_name=f'{name}_from_{kind}';recipe_id=f'{NS}:{recipe_name}';add(DATA+f'recipe/{recipe_name}.json',recipe)
            criteria={'has_the_recipe':{'trigger':'minecraft:recipe_unlocked','conditions':{'recipes':recipe_id}}}
            for index,ref in enumerate(ref for ref in unlock_materials if ref not in disabled_refs):
                criteria[f'has_material_{index}']={'trigger':'minecraft:inventory_changed','conditions':{'items':[{'items':ref}]}}
            # A single requirement group is OR: any ingredient unlocks the recipe.
            add(DATA+f'advancement/recipes/food/{recipe_name}.json',{'parent':'minecraft:recipes/root','criteria':criteria,'requirements':[list(criteria)],'rewards':{'recipes':[recipe_id]}})
    java='''// Generated by helper/item_editor.py. Edit source/items_project.json instead.
package dev.lotcarnage.culinaryexpansion;
import net.minecraft.world.food.FoodProperties;
import net.minecraft.world.item.Item;
import net.minecraft.world.item.Items;
import net.minecraft.world.item.CreativeModeTabs;
import net.minecraft.world.item.component.Consumable;
import net.minecraft.world.item.consume_effects.ApplyStatusEffectsConsumeEffect;
import net.minecraft.world.effect.MobEffectInstance;
import net.minecraft.world.effect.MobEffects;
import net.minecraftforge.event.BuildCreativeModeTabContentsEvent;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;
public final class ModItems {
    public static final String MOD_ID = "culinary_expansion";
    public static final DeferredRegister<Item> ITEMS = DeferredRegister.create(ForgeRegistries.ITEMS, MOD_ID);
REGISTRATIONS
    public static void register(FMLJavaModLoadingContext context) {
        ITEMS.register(context.getModBusGroup());
        BuildCreativeModeTabContentsEvent.BUS.addListener(ModItems::addFood);
    }
    private static void addFood(BuildCreativeModeTabContentsEvent event) {
        if (event.getTabKey() == CreativeModeTabs.FOOD_AND_DRINKS) {
ACCEPT
        }
    }
}
'''.replace('REGISTRATIONS','\n'.join(registrations)).replace('ACCEPT','\n'.join(accept))
    files[JAVA+'ModItems.java']=java.encode()
    files[JAVA+'CulinaryExpansion.java']=b'''package dev.lotcarnage.culinaryexpansion;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.javafmlmod.FMLJavaModLoadingContext;
@Mod("culinary_expansion")
public final class CulinaryExpansion {
    public CulinaryExpansion(FMLJavaModLoadingContext context) { ModItems.register(context); }
}
'''
    return files


def export(project,path=PROJECT,root=ROOT):
    root=Path(root).resolve();files=generated(project,root)
    # Keep resource definitions for inactive items on disk; only registration is filtered.
    complete=deepcopy(project)
    for item in complete['items']:item['enabled']=True
    preserved=generated(complete,root)
    for p,data in preserved.items():
        if p not in files:files[p]=(root/p).read_bytes() if (root/p).exists() else data
    # The on-disk project is the authoritative previous ownership manifest.
    previous=load(path).get('generated_files',[]) if Path(path).exists() else []
    if any(not allowed(p) for p in previous):raise ValueError('Unsafe generated-files manifest')
    affected=set(previous)|set(files)
    backups={p:(root/p).read_bytes() if (root/p).exists() else None for p in affected}
    old_project=Path(path).read_bytes() if Path(path).exists() else None
    old_manifest=project.get('generated_files',[])[:]
    try:
        for p,data in files.items():
            target=root/p;target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_name(target.name+'.tmp');temp.write_bytes(data);temp.replace(target)
        for p in set(previous)-set(files):
            (root/p).unlink(missing_ok=True)
        project['generated_files']=sorted(files)
        save(project,path)
    except Exception:
        for p,data in backups.items():
            target=root/p
            if data is None:target.unlink(missing_ok=True)
            else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
        if old_project is not None:Path(path).write_bytes(old_project)
        else:Path(path).unlink(missing_ok=True)
        project['generated_files']=old_manifest
        raise
    return len(files)
