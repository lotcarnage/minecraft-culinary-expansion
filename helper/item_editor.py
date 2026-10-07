"""Tkinter item comparison table with a separate editing pane; save one JSON project and generate Forge resources."""
import argparse
from copy import deepcopy
from pathlib import Path
import struct
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, filedialog, messagebox, simpledialog
import webbrowser
import item_project as model

FIELDS = [
 ('表示','enabled','組込み',bool,['有','無']),
 ('表示', 'name', '代表名', str, None),('表示','ja_name','日本語名',str,None),('表示','en_name','英語名',str,None),
 ('食事','stack_size','最大スタック数',int,None),('食事','nutrition','満腹度回復量',int,None),
 ('食事','saturation_modifier','隠し満腹度係数',float,None),('食事','always_edible','満腹時使用',bool,['可','不可']),
 ('食事','consume_seconds','食事時間（秒）',float,None),('食事','effect','追加効果',str,list(model.EFFECTS)),
 ('食事','effect_ticks','効果時間（tick）',int,None),('食事','effect_level','効果レベル（1始まり）',int,None),
 ('食事','effect_probability','効果発生確率（0～1）',float,None),('食事','remainder','使用後の残り物',str,list(model.REMAINDERS)),
 ('調理','smelting','かまど対応',bool,['可','不可']),('調理','smoking','燻製器対応',bool,['可','不可']),
 ('調理','cooking_ticks','基準調理時間（tick）',int,None),('調理','campfire_ticks','焚き火（tick / 不可）',int,None),
 ('調理','cooking_ingredient','調理素材ID（タグは#）',str,None),('調理','experience','調理経験値',float,None),
 ('調理','cooking_output','調理出力個数',int,None),('クラフト','crafting','クラフト方式',str,['クラフト不可','定型','不定形']),
 ('クラフト','crafting_output','クラフト出力個数',int,None)]


class ItemEditor:
    def __init__(self, window, path=model.PROJECT):
        self.window=window;self.path=Path(path);self.project=model.load(self.path)
        self.dirty=False;self.cells={};self.preview_image=None;self.reference_window=None
        self.edit_target=None;self.original_values={};self.edit_values={};self.inputs={};self.material_buttons={}
        window.title('Culinary Expansion アイテムエディター');window.geometry('1440x900')
        window.protocol('WM_DELETE_WINDOW',self.close)
        bar=ttk.Frame(window,padding=6);bar.pack(fill='x')
        for label,command in [('開く',self.open),('保存',self.save),('名前を付けて保存',self.save_as),
                              ('追加',self.add),('削除',self.delete),('定義へ反映',self.apply),('テクスチャ取込',self.import_texture),
                              ('一覧を開く',self.dashboard),('公式食料の参考値',self.show_food_reference)]:
            ttk.Button(bar,text=label,command=command).pack(side='left',padx=2)
        metadata_bar=ttk.Frame(window,padding=6);metadata_bar.pack(fill='x')
        ttk.Label(metadata_bar,text='プロジェクトバージョン').pack(side='left')
        self.version_value=tk.StringVar(value=self.project['version'])
        ttk.Entry(metadata_bar,textvariable=self.version_value,width=24).pack(side='left',padx=8)
        ttk.Label(metadata_bar,text='手動で更新するメタ情報。JARファイル名に反映します。').pack(side='left')
        self.version_value.trace_add('write',self.edit_version)
        ttk.Label(window,text='アイテムの行を選択し、右側の各項目を直接編集して「変更を反映」。保存＝JSON保存、定義へ反映＝Java・レシピ・翻訳を生成。削除は定義へ即時反映（画像は保持）。',padding=8).pack(fill='x')
        pane=ttk.Panedwindow(window,orient='horizontal');pane.pack(fill='both',expand=True)
        self.pane=pane
        self.initial_split_set=False
        frame=ttk.Frame(pane);pane.add(frame,weight=5)
        self.columns=[('item_id','アイテムID',None,None,None)]
        self.columns.extend((key,label,key,kind,choices) for group,key,label,kind,choices in FIELDS)
        self.columns.extend((f'slot{i}',f'素材 {slot}',i,str,None) for i,slot in enumerate(model.SLOTS))
        self.tree=ttk.Treeview(frame,columns=tuple(c[0] for c in self.columns),show='headings',selectmode='browse')
        self.tree.tag_configure('disabled_item',background='#e8e8e8')
        style=ttk.Style(window)
        heading_font=tkfont.Font(root=window,font=style.lookup('Treeview.Heading','font') or 'TkHeadingFont')
        cell_font=tkfont.Font(root=window,font=style.lookup('Treeview','font') or 'TkDefaultFont')
        for column,label,key,kind,choices in self.columns:
            self.tree.heading(column,text=label)
            values=[]
            for item in self.project['items']:
                if key is None:value=f'{model.NS}:{item["name"]}'
                elif isinstance(key,int):value=item['crafting_slots'][key] if item['crafting']!='クラフト不可' else '不可'
                else:value=self.display(item,key)
                values.append(value)
            width=max(heading_font.measure(label),max((cell_font.measure(value) for value in values),default=0))+8
            self.tree.column(column,width=width,minwidth=24,stretch=False,anchor='e' if kind in (int,float) else 'w')
        ys=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview);xs=ttk.Scrollbar(frame,orient='horizontal',command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set,xscrollcommand=xs.set)
        self.tree.grid(row=0,column=0,sticky='nsew');ys.grid(row=0,column=1,sticky='ns');xs.grid(row=1,column=0,sticky='ew')
        frame.rowconfigure(0,weight=1);frame.columnconfigure(0,weight=1)
        sidebar=ttk.Frame(pane);pane.add(sidebar,weight=0)
        self.edit_item=ttk.Label(sidebar,text='アイテムを選択',padding=8)
        self.edit_item.pack(fill='x')
        texture=ttk.LabelFrame(sidebar,text='テクスチャ',padding=8)
        texture.pack(fill='x',padx=8,pady=4)
        self.preview=ttk.Label(texture);self.preview.pack(side='left',padx=(0,12))
        self.image_info=ttk.Label(texture,wraplength=300);self.image_info.pack(side='left',anchor='n')
        ttk.Button(texture,text='画像を取り込む',command=self.import_texture).pack(side='right',anchor='s')
        buttons=ttk.Frame(sidebar,padding=6);buttons.pack(fill='x')
        self.commit_button=ttk.Button(buttons,text='変更を反映',command=self.commit_edit)
        self.commit_button.pack(side='left')
        ttk.Button(buttons,text='変更を取消',command=self.cancel_edit).pack(side='left',padx=4)
        # Canvas window items are Tkinter's standard way to scroll a form frame.
        self.form_canvas=tk.Canvas(sidebar,highlightthickness=0)
        form_scroll=ttk.Scrollbar(sidebar,orient='vertical',command=self.form_canvas.yview)
        form_scroll.pack(side='right',fill='y');self.form_canvas.pack(fill='both',expand=True)
        self.form_canvas.configure(yscrollcommand=form_scroll.set)
        form=ttk.Frame(self.form_canvas,padding=8)
        form_window=self.form_canvas.create_window(0,0,window=form,anchor='nw')
        form.bind('<Configure>',lambda event:self.form_canvas.configure(scrollregion=self.form_canvas.bbox('all')))
        self.form_canvas.bind('<Configure>',lambda event:self.form_canvas.itemconfigure(form_window,width=event.width))
        form.columnconfigure(0,weight=1)
        form.columnconfigure(1,weight=1)
        left_column=ttk.Frame(form);left_column.grid(row=0,column=0,sticky='new',padx=(0,4))
        right_column=ttk.Frame(form);right_column.grid(row=0,column=1,sticky='new',padx=(4,0))
        groups={};group_rows={}
        for group,key,label,kind,choices in FIELDS:
            if group not in groups:
                parent=left_column if group in ('表示','食事') else right_column
                groups[group]=ttk.LabelFrame(parent,text=group,padding=6)
                groups[group].pack(fill='x',pady=4)
                groups[group].columnconfigure(2,weight=1);group_rows[group]=0
            row=group_rows[group];group_rows[group]+=1
            ttk.Label(groups[group],text=label).grid(row=row,column=0,sticky='w',padx=(0,8),pady=2)
            variable=tk.StringVar();self.edit_values[key]=variable
            if key=='enabled':
                widget=ttk.Checkbutton(groups[group],variable=variable,onvalue='有',offvalue='無')
            elif choices:
                width=max(5,max(sum(2 if ord(character)>127 else 1 for character in value) for value in choices)+2)
                widget=ttk.Combobox(groups[group],textvariable=variable,values=choices,state='readonly',width=width)
            else:
                numeric=kind in (int,float)
                width=(10 if key.endswith('ticks') else 7) if numeric else 20
                widget=ttk.Entry(groups[group],textvariable=variable,width=width,justify='right' if numeric else 'left')
            widget.grid(row=row,column=1,sticky='ew',pady=2);self.inputs[key]=widget
        slots=ttk.LabelFrame(right_column,text='クラフト素材（空きマスは「不要」）',padding=6)
        slots.pack(fill='x',pady=4)
        for index,slot in enumerate(model.SLOTS):
            cell=ttk.Frame(slots);cell.grid(row=index//3,column=index%3,sticky='ew',padx=2,pady=2)
            slots.columnconfigure(index%3,weight=1)
            ttk.Label(cell,text=slot).pack(anchor='w')
            variable=tk.StringVar();self.edit_values[index]=variable
            widget=ttk.Entry(cell,textvariable=variable,width=12);widget.pack(anchor='w');self.inputs[index]=widget
            button=ttk.Button(cell,text='素材を選択',command=lambda slot_index=index:self.choose_material(slot_index))
            button.pack(fill='x',pady=2);self.material_buttons[index]=button
        self.edit_values['crafting'].trace_add('write',self.update_crafting_inputs)
        metadata=ttk.LabelFrame(form,text='管理情報',padding=8);metadata.grid(row=1,column=0,columnspan=2,sticky='ew',pady=4)
        self.metadata_info=ttk.Label(metadata,wraplength=440);self.metadata_info.pack(anchor='w')
        # Use each group's widest requested input width, including combobox chrome.
        window.update_idletasks()
        for group,frame_group in groups.items():
            width=max(self.inputs[key].winfo_reqwidth() for field_group,key,*rest in FIELDS if field_group==group)
            frame_group.columnconfigure(1,minsize=width)
        window.update_idletasks()
        self.editor_pane_width=form.winfo_reqwidth()+form_scroll.winfo_reqwidth()
        self.form_canvas.configure(width=form.winfo_reqwidth())
        self.status=tk.StringVar();ttk.Label(window,textvariable=self.status,padding=6).pack(fill='x')
        self.tree.bind('<Button-1>',self.select_cell);self.tree.bind('<<TreeviewSelect>>',self.selection)
        pane.bind('<Configure>',self.initialize_split)
        self.refresh()

    def initialize_split(self,event):
        if self.initial_split_set or event.width<=1:return
        # Set the initial split after layout has assigned the actual window width.
        # Subsequent resizing preserves the user's adjustable split.
        self.pane.sashpos(0,max(event.width//3,event.width-self.editor_pane_width))
        self.initial_split_set=True

    def display(self,item,key):
        v=item[key]
        if key=='enabled':return '有' if v else '無'
        if isinstance(v,bool):return '可' if v else '不可'
        if v is None:return '不可'
        return str(v)

    def edit_version(self,*args):
        value=self.version_value.get()
        if value!=self.project['version']:
            self.project['version']=value;self.dirty=True
            self.status.set(f'{self.path} | 未保存')

    def refresh(self,select=None):
        self.version_value.set(self.project['version'])
        horizontal=self.tree.xview()[0];vertical=self.tree.yview()[0]
        self.tree.delete(*self.tree.get_children());self.cells={}
        for index,item in enumerate(self.project['items']):
            row=f'item{index}';values=[]
            for column,label,key,kind,choices in self.columns:
                if key is None:value=f'{model.NS}:{item["name"]}'
                elif isinstance(key,int):value=item['crafting_slots'][key] if item['crafting']!='クラフト不可' else '不可'
                else:value=self.display(item,key)
                values.append(value)
                if key is not None:self.cells[(row,column)]=(index,key,kind,choices)
            self.tree.insert('', 'end',iid=row,values=values,tags=() if item['enabled'] else ('disabled_item',))
        self.tree.xview_moveto(horizontal);self.tree.yview_moveto(vertical)
        if select is not None and select<len(self.project['items']):self.tree.selection_set(f'item{select}')
        self.status.set(f'{self.path} | {len(self.project["items"])}アイテム' + (' | 未保存' if self.dirty else ''))
        self.selection()
        self.load_edit()

    def selected(self):
        selection=self.tree.selection()
        if not selection:return None
        row=selection[0]
        return int(row[4:])

    def selection(self,event=None):
        index=self.selected()
        if self.edit_target is not None and self.edit_target!=index and self.has_pending_edit():
            self.tree.selection_set(f'item{self.edit_target}')
            return
        self.load_edit()
        if index is None:
            self.preview_image=None;self.preview.configure(image='')
            self.image_info.configure(text='アイテムを選択');self.metadata_info.configure(text='')
            return
        item=self.project['items'][index];path=model.ROOT/model.derived(item)['テクスチャ']
        self.metadata_info.configure(text='\n'.join(f'{key}: {value}' for key,value in model.derived(item).items()))
        try:
            image=tk.PhotoImage(file=str(path));w,h=image.width(),image.height()
            scale=max(1,(max(w,h)+127)//128)
            image=image.subsample(scale) if scale>1 else image.zoom(max(1,128//max(w,h)))
            self.preview_image=image;self.preview.configure(image=image)
            self.image_info.configure(text=f'{path.name}\n{w}×{h} px')
        except tk.TclError:
            self.preview_image=None
            self.preview.configure(image='');self.image_info.configure(text=f'{path.name}\n画像未配置')

    def has_pending_edit(self):
        return self.edit_target is not None and any(
            variable.get()!=self.original_values[key] for key,variable in self.edit_values.items())

    def select_cell(self,event):
        row=self.tree.identify_row(event.y)
        if row and int(row[4:])!=self.edit_target and self.pending():return 'break'

    def update_crafting_inputs(self,*args):
        enabled=self.edit_target is not None and self.edit_values['crafting'].get()!='クラフト不可'
        for index in range(9):
            self.inputs[index].configure(state='normal' if enabled else 'disabled')
            self.material_buttons[index].configure(state='normal' if enabled else 'disabled')

    def choose_material(self,slot_index):
        if self.edit_target is None or self.edit_values['crafting'].get()=='クラフト不可':return
        from material_picker import MaterialPicker
        try:
            MaterialPicker(self.window,model.ROOT,self.project['items'],self.edit_values[slot_index].get(),
                           self.edit_values[slot_index].set)
        except Exception as error:
            messagebox.showerror('素材一覧エラー',str(error),parent=self.window)

    def load_edit(self):
        index=self.selected()
        if index==self.edit_target and self.has_pending_edit():return
        self.edit_target=index
        self.commit_button.configure(state='normal' if index is not None else 'disabled')
        self.edit_item.configure(text=f'{model.NS}:{self.project["items"][index]["name"]}' if index is not None else 'アイテムを選択')
        for key,variable in self.edit_values.items():
            if index is None:value=''
            else:
                item=self.project['items'][index]
                value=item['crafting_slots'][key] if isinstance(key,int) else self.display(item,key)
            variable.set(value)
            self.original_values[key]=value
            choices=isinstance(self.inputs[key],ttk.Combobox)
            self.inputs[key].configure(state=('readonly' if choices else 'normal') if index is not None else 'disabled')
        self.update_crafting_inputs()

    def cancel_edit(self,event=None):
        for key,value in self.original_values.items():self.edit_values[key].set(value)
        self.update_crafting_inputs()

    def commit_edit(self,event=None):
        if self.edit_target is None:return False
        index=self.edit_target
        candidate=deepcopy(self.project);target=candidate['items'][index]
        try:
            for group,key,label,kind,choices in FIELDS:
                raw=self.edit_values[key].get().strip()
                if choices and raw not in choices:raise ValueError(f'{label}: 選択肢から指定してください')
                try:target[key]=(raw==('有' if key=='enabled' else '可')) if kind is bool else (None if key=='campfire_ticks' and raw=='不可' else kind(raw))
                except ValueError:raise ValueError(f'{label}: 入力値を確認してください') from None
            target['crafting_slots']=[self.edit_values[i].get().strip() for i in range(9)]
            model.validate(candidate)
        except (ValueError,TypeError) as error:
            messagebox.showerror('入力エラー',str(error),parent=self.window)
            return False
        if candidate!=self.project:
            self.project=candidate;self.dirty=True
        self.edit_target=None
        self.refresh(index)
        return True

    def pending(self):
        if self.has_pending_edit():
            messagebox.showinfo('未反映の入力','編集ペインの「変更を反映」または「変更を取消」を実行してください。',parent=self.window)
            return True
        return False

    def save(self):
        if self.pending():return False
        try:model.save(self.project,self.path);self.dirty=False;self.refresh(self.selected());return True
        except Exception as error:messagebox.showerror('保存エラー',str(error),parent=self.window);return False

    def save_as(self):
        if self.pending():return
        filename=filedialog.asksaveasfilename(parent=self.window,defaultextension='.json',filetypes=[('JSON project','*.json')])
        if filename:
            old=self.path;self.path=Path(filename)
            if not self.save():self.path=old

    def discard(self):
        return not self.dirty or messagebox.askyesno('未保存の変更','未保存の変更を破棄しますか？',parent=self.window)

    def open(self):
        if self.pending() or not self.discard():return
        filename=filedialog.askopenfilename(parent=self.window,filetypes=[('JSON project','*.json')])
        if filename:
            try:project=model.load(filename)
            except Exception as error:messagebox.showerror('読込エラー',str(error),parent=self.window);return
            self.path=Path(filename);self.project=project;self.dirty=False;self.refresh()

    def add(self):
        if self.pending():return
        name=simpledialog.askstring('アイテム追加','代表名（例: fried_egg。小文字英数字と_）',parent=self.window)
        if name is None:return
        candidate=deepcopy(self.project);candidate['items'].append(model.default_item(name.strip()))
        try:
            model.validate(candidate)
            model.ensure_texture(candidate['items'][-1])
        except Exception as error:messagebox.showerror('追加エラー',str(error),parent=self.window);return
        self.project=candidate;self.dirty=True;self.refresh(len(candidate['items'])-1)

    def apply(self):
        if self.pending():return False
        try:
            count=model.export(self.project,self.path)
            self.dirty=False;self.refresh(self.selected())
            # Resource export is committed; a dashboard error must not undo GUI state.
            try:
                import generate_item_dashboard as dashboard
                if self.project['items']:dashboard.generate(model.ROOT/'document/item_dashboard.html')
                else:
                    for name in ('item_dashboard.html','resource_dashboard.html'):
                        (model.ROOT/'document'/name).write_text('<!doctype html><meta charset="utf-8"><title>アイテム一覧</title><h1>登録アイテムなし</h1>',encoding='utf-8')
            except Exception as error:
                messagebox.showwarning('一覧生成',f'定義は反映済みです。一覧の生成に失敗しました: {error}',parent=self.window)
            self.status.set(f'{count}定義ファイルを生成しました。ゲームへの反映には再ビルドしてください。')
            return True
        except Exception as error:messagebox.showerror('反映エラー',str(error),parent=self.window);return False

    def delete(self):
        if self.pending():return
        index=self.selected()
        if index is None:return
        name=self.project['items'][index]['name']
        if not messagebox.askyesno('アイテム削除',f'{name}を削除し、現在のプロジェクトを定義へ反映します。\n関連レシピ・モデル・翻訳も削除します。テクスチャは保持します。',parent=self.window):return
        previous=deepcopy(self.project);del self.project['items'][index];self.dirty=True
        if not self.apply():self.project=previous;self.refresh()

    def import_texture(self):
        if self.pending():return
        index=self.selected()
        if index is None:return
        filename=filedialog.askopenfilename(parent=self.window,filetypes=[('PNG image','*.png')])
        if not filename:return
        try:
            data=Path(filename).read_bytes()
            if data[:8]!=b'\x89PNG\r\n\x1a\n':raise ValueError('PNG画像を指定してください')
            width,height=struct.unpack('>II',data[16:24])
            if width<1 or height<1:raise ValueError('Invalid image dimensions')
            target=model.ROOT/model.derived(self.project['items'][index])['テクスチャ']
            target.parent.mkdir(parents=True,exist_ok=True);temp=target.with_suffix('.png.tmp');temp.write_bytes(data);temp.replace(target)
            self.selection();self.status.set(f'テクスチャを配置: {target.name} ({width}×{height})')
        except Exception as error:messagebox.showerror('画像エラー',str(error),parent=self.window)

    def show_food_reference(self):
        if self.reference_window and self.reference_window.window.winfo_exists():
            self.reference_window.window.deiconify();self.reference_window.window.lift()
            return
        from food_reference import FoodReference
        try:
            self.reference_window=FoodReference(self.window,model.ROOT/'source/vanilla_food_reference.json')
        except (OSError,ValueError) as error:
            messagebox.showerror('参考値の読み込みエラー',str(error),parent=self.window)

    def dashboard(self):
        target=model.ROOT/'document/item_dashboard.html'
        if target.exists():webbrowser.open(target.as_uri())

    def close(self):
        if not self.pending() and self.discard():self.window.destroy()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--project',type=Path,default=model.PROJECT)
    args=parser.parse_args();window=tk.Tk()
    try:ItemEditor(window,args.project)
    except Exception as error:messagebox.showerror('起動エラー',str(error),parent=window);window.destroy();raise SystemExit(1)
    window.mainloop()

