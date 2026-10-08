"""Local Minecraft material catalog and a standard Tkinter selection dialog."""
import json
from contextlib import ExitStack
import os
from pathlib import Path
import tkinter as tk
from error_messages import japanese_error
from tkinter import ttk, filedialog, messagebox
import zipfile


def minecraft_version(root):
    properties=(root/'build/gradle.properties').read_text(encoding='utf-8')
    return next((line.split('=',1)[1].strip() for line in properties.splitlines() if line.startswith('minecraft_version=')), '')


def find_client_resources(root):
    version=minecraft_version(root)
    candidates=sorted((root/'intermediate/forge-maven/net/minecraft/client-extra').glob(f'{version}-*/*.jar'))
    return candidates[-1] if candidates else None


def local_japanese_names(root):
    """Read the target game's Japanese asset without downloading or copying it."""
    homes=[Path.home()/'.minecraft',Path.home()/'Library/Application Support/minecraft']
    if os.environ.get('APPDATA'):homes.insert(0,Path(os.environ['APPDATA'])/'.minecraft')
    version=minecraft_version(root)
    for home in homes:
        try:
            metadata=json.loads((home/f'versions/{version}/{version}.json').read_text(encoding='utf-8'))
            index_id=metadata['assetIndex']['id']
            index=json.loads((home/f'assets/indexes/{index_id}.json').read_text(encoding='utf-8'))
            digest=index['objects']['minecraft/lang/ja_jp.json']['hash']
            if len(digest)!=40 or any(c not in '0123456789abcdef' for c in digest):continue
            return json.loads((home/f'assets/objects/{digest[:2]}/{digest}').read_text(encoding='utf-8'))
        except (OSError,ValueError,KeyError):continue
    return {}


class MaterialCatalog:
    def __init__(self,root,items,jar=None):
        self.root=Path(root);self.items=items;self.jar=jar
        self.entries={'不要':'不要（空きマス）'}
        self.names=set();self.translations={}
        if jar:
            with zipfile.ZipFile(jar) as archive:
                self.names=set(archive.namelist())
                for language in ('en_us','ja_jp'):
                    path=f'assets/minecraft/lang/{language}.json'
                    if path in self.names:self.translations.update(json.loads(archive.read(path)))
            self.translations.update(local_japanese_names(self.root))
            for path in sorted(self.names):
                if path.startswith('assets/minecraft/items/') and path.endswith('.json'):
                    name=Path(path).stem
                    self.entries[f'minecraft:{name}']=self.translations.get(f'item.minecraft.{name}',self.translations.get(f'block.minecraft.{name}',name))
        for item in items:self.entries[f'culinary_expansion:{item["name"]}']=item['ja_name']
        self.search_entries=[(key,key.casefold(),label.casefold()) for key,label in self.entries.items()]

    def texture(self,item_id,archive=None):
        namespace,name=item_id.split(':',1) if ':' in item_id else ('','')
        if namespace=='culinary_expansion':
            path=self.root/f'source/main/resources/assets/{namespace}/textures/item/{name}.png'
            return path.read_bytes() if path.is_file() else None
        if namespace!='minecraft' or not self.jar:return None
        if archive is None:
            with zipfile.ZipFile(self.jar) as opened:
                return self.texture(item_id,opened)
        # Display ordinary 2D item textures. Complex/3D models remain selectable by name.
        definition=json.loads(archive.read(f'assets/minecraft/items/{name}.json'))
        model=definition.get('model',{})
        if model.get('type')!='minecraft:model':return None
        reference=model.get('model','')
        textures={};seen=set()
        for _ in range(16):
            if reference in seen:break
            seen.add(reference)
            parts=reference.split(':',1)
            if len(parts)!=2:break
            path=f'assets/{parts[0]}/models/{parts[1]}.json'
            if path not in self.names:break
            data=json.loads(archive.read(path))
            for key,value in data.get('textures',{}).items():textures.setdefault(key,value)
            reference=data.get('parent','')
        texture=textures.get('layer0','')
        parts=texture.split(':',1)
        if len(parts)!=2:return None
        path=f'assets/{parts[0]}/textures/{parts[1]}.png'
        return archive.read(path) if path in self.names else None


class MaterialPicker:
    PAGE_SIZE=100

    def __init__(self,parent,root,items,current,on_select):
        self.root=Path(root);self.items=items;self.on_select=on_select
        self.catalog=MaterialCatalog(self.root,items,find_client_resources(self.root))
        self.window=tk.Toplevel(parent);self.window.title('クラフト素材を選択');self.window.geometry('760x640')
        self.window.transient(parent)
        self.images={};self.page=0
        top=ttk.Frame(self.window,padding=8);top.pack(fill='x')
        ttk.Label(top,text='名前・素材IDで検索').pack(side='left')
        self.search=tk.StringVar();ttk.Entry(top,textvariable=self.search).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(top,text='Minecraft JARを指定',command=self.choose_jar).pack(side='right')
        self.notice=ttk.Label(self.window,padding=8,wraplength=730);self.notice.pack(fill='x')
        frame=ttk.Frame(self.window);frame.pack(fill='both',expand=True)
        self.list=ttk.Treeview(frame,columns=('name','id'),show='tree headings',selectmode='browse')
        self.list.heading('#0',text='画像');self.list.column('#0',width=55,stretch=False)
        self.list.heading('name',text='表示名');self.list.column('name',width=220)
        self.list.heading('id',text='素材ID');self.list.column('id',width=330)
        ttk.Style(self.window).configure('Materials.Treeview',rowheight=40)
        self.list.configure(style='Materials.Treeview')
        scroll=ttk.Scrollbar(frame,command=self.list.yview);self.list.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');self.list.pack(fill='both',expand=True)
        bottom=ttk.Frame(self.window,padding=8);bottom.pack(fill='x')
        self.previous=ttk.Button(bottom,text='前へ',command=lambda:self.turn(-1));self.previous.pack(side='left')
        self.next=ttk.Button(bottom,text='次へ',command=lambda:self.turn(1));self.next.pack(side='left')
        self.page_info=ttk.Label(bottom);self.page_info.pack(side='left',padx=8)
        ttk.Button(bottom,text='選択',command=self.select).pack(side='right')
        ttk.Button(bottom,text='閉じる',command=self.window.destroy).pack(side='right',padx=4)
        self.list.bind('<Double-1>',self.select);self.list.bind('<Return>',self.select)
        self.search.trace_add('write',self.filter)
        if current in self.catalog.entries:
            self.page=list(self.catalog.entries).index(current)//self.PAGE_SIZE
        self.populate()
        if current in self.matches:
            self.list.selection_set(current);self.list.see(current)
        self.window.grab_set()

    def choose_jar(self):
        path=filedialog.askopenfilename(parent=self.window,title='Minecraftクライアントのリソースを含むJAR',filetypes=[('JAR','*.jar')])
        if not path:return
        try:
            catalog=MaterialCatalog(self.root,self.items,Path(path))
            if not any(key.startswith('minecraft:') for key in catalog.entries):raise ValueError('Minecraftのアイテム定義がありません')
        except (OSError,ValueError,zipfile.BadZipFile) as error:
            messagebox.showerror('読み込みエラー',japanese_error(error),parent=self.window);return
        self.catalog=catalog;self.images={};self.page=0;self.populate()

    def filter(self,*args):self.page=0;self.populate()

    def turn(self,amount):self.page+=amount;self.populate()

    def populate(self):
        query=self.search.get().strip().casefold()
        self.matches=[key for key,search_id,search_label in self.catalog.search_entries if query in search_id or query in search_label]
        self.list.delete(*self.list.get_children())
        keys=self.matches[self.page*self.PAGE_SIZE:(self.page+1)*self.PAGE_SIZE]
        # Keep one archive open for this page, and close it even if loading fails.
        with ExitStack() as stack:
            archive=None;archive_error=False
            if self.catalog.jar and any(key.startswith('minecraft:') and key not in self.images for key in keys):
                try:archive=stack.enter_context(zipfile.ZipFile(self.catalog.jar))
                except (OSError,ValueError,zipfile.BadZipFile):archive_error=True
            self.populate_rows(keys,archive,archive_error)
        self.previous.configure(state='normal' if self.page else 'disabled')
        self.next.configure(state='normal' if (self.page+1)*self.PAGE_SIZE<len(self.matches) else 'disabled')
        self.page_info.configure(text=f'{len(self.matches)}件 / {self.page+1}ページ')
        self.notice.configure(text='ローカルの公式リソースを使用。日本語はインストール済みMinecraftの言語データから読み込みます。立体・複合モデルは画像なしで表示します。' if self.catalog.jar else '公式リソースがありません。ビルド後に開くか、Minecraft JARを指定してください。自作アイテムと「不要」は選択できます。')

    def populate_rows(self,keys,archive,archive_error=False):
        for key in keys:
            if key not in self.images:
                image=None
                try:
                    data=None if archive_error and key.startswith('minecraft:') else self.catalog.texture(key,archive)
                    if data:
                        image=tk.PhotoImage(master=self.window,data=data)
                        largest=max(image.width(),image.height())
                        image=image.subsample(max(1,(largest+31)//32)) if largest>32 else image.zoom(max(1,32//largest))
                except (OSError,ValueError,KeyError,tk.TclError,zipfile.BadZipFile):pass
                self.images[key]=image
            image=self.images[key]
            self.list.insert('','end',iid=key,text='' if image else '画像なし',image=image or '',values=(self.catalog.entries[key],key))

    def select(self,event=None):
        selected=self.list.selection()
        if selected:self.on_select(selected[0]);self.window.destroy()
