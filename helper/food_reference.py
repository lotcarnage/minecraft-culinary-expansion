"""Read-only vanilla food reference window, using standard Tkinter widgets."""
import json
import tkinter as tk
from tkinter import ttk


class FoodReference:
    COLUMNS=(('name','表示名',180),('id','アイテムID',290),('nutrition','満腹度',85),
             ('icons','アイコン数',95),('saturation_modifier','隠し満腹度係数',135),
             ('saturation','隠し満腹度回復量',145),('always_edible','満腹時使用',110))

    def __init__(self,parent,path):
        data=json.loads(path.read_text(encoding='utf-8'))
        self.items=[dict(item,icons=item['nutrition']/2,saturation=round(item['nutrition']*item['saturation_modifier']*2,4)) for item in data['items']]
        self.sort_key='name';self.reverse=False
        self.window=tk.Toplevel(parent);self.window.title(f'公式食料の参考値 — Minecraft {data["minecraft_version"]}')
        self.window.geometry('1080x620');self.window.transient(parent)
        top=ttk.Frame(self.window,padding=8);top.pack(fill='x')
        ttk.Label(top,text='名前・IDで検索').pack(side='left')
        self.query=tk.StringVar();ttk.Entry(top,textvariable=self.query).pack(side='left',fill='x',expand=True,padx=8)
        self.count=ttk.Label(top);self.count.pack(side='right')
        frame=ttk.Frame(self.window);frame.pack(fill='both',expand=True)
        self.table=ttk.Treeview(frame,columns=[c[0] for c in self.COLUMNS],show='headings',selectmode='browse')
        for key,label,width in self.COLUMNS:
            self.table.heading(key,text=label,command=lambda field=key:self.sort(field))
            self.table.column(key,width=width,minwidth=60,stretch=False,anchor='e' if key in ('nutrition','icons','saturation_modifier','saturation') else 'w')
        vertical=ttk.Scrollbar(frame,command=self.table.yview);horizontal=ttk.Scrollbar(frame,orient='horizontal',command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        self.table.grid(row=0,column=0,sticky='nsew');vertical.grid(row=0,column=1,sticky='ns');horizontal.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        ttk.Label(self.window,text='満腹度2＝アイコン1個。隠し満腹度回復量＝満腹度 × 係数 × 2（食後の満腹度が蓄積上限）。列見出しで並べ替え。',padding=8,wraplength=1040).pack(fill='x')
        ttk.Label(self.window,text=data['scope']+'  対象バージョンの公式定義から取得した参考値です。',padding=8,wraplength=1040).pack(fill='x')
        self.query.trace_add('write',self.refresh);self.refresh()

    def sort(self,key):
        self.reverse=not self.reverse if key==self.sort_key else False
        self.sort_key=key;self.refresh()

    def refresh(self,*args):
        query=self.query.get().strip().casefold()
        items=[item for item in self.items if query in item['name'].casefold() or query in item['id'].casefold()]
        items.sort(key=lambda item:item[self.sort_key],reverse=self.reverse)
        self.table.delete(*self.table.get_children())
        for item in items:
            values=[]
            for key,label,width in self.COLUMNS:
                value=item[key]
                if isinstance(value,bool):value='可' if value else '不可'
                elif isinstance(value,float):value=f'{value:g}'
                values.append(value)
            self.table.insert('','end',iid=item['id'],values=values)
        self.count.configure(text=f'{len(items)}件')
