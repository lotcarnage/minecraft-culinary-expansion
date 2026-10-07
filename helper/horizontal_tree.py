"""Limit a wide Treeview's displayed columns without changing its scroll range."""
from bisect import bisect_right, bisect_left


def visible_columns(widths,first,last):
    """Return intersecting column indices and the widths outside the viewport."""
    edges=[0]
    for width in widths:edges.append(edges[-1]+width)
    total=edges[-1]
    start=min(len(widths),bisect_right(edges,float(first)*total)-1)
    stop=max(start,min(len(widths),bisect_left(edges,float(last)*total)))
    return start,stop,edges[start],total-edges[stop]


class HorizontalTreeViewport:
    LEFT='_viewport_left'
    RIGHT='_viewport_right'

    def __init__(self,tree,columns,scrollbar):
        self.tree=tree;self.columns=tuple(columns);self.scrollbar=scrollbar
        self.widths=tuple(int(tree.column(column,'width')) for column in self.columns)
        self.displayed=None
        for column in (self.LEFT,self.RIGHT):
            tree.heading(column,text='')
            tree.column(column,width=0,minwidth=0,stretch=False)
        tree.configure(xscrollcommand=self.update)
        # Column separator dragging changes the total width of the comparison table.
        tree.bind('<ButtonRelease-1>',self.resize_columns,add='+')

    def update(self,first,last):
        self.scrollbar.set(first,last)
        start,stop,left,right=visible_columns(self.widths,first,last)
        displayed=((self.LEFT,) if left else ())+self.columns[start:stop]+((self.RIGHT,) if right else ())
        state=(displayed,left,right)
        if state==self.displayed:return
        self.displayed=state
        self.tree.column(self.LEFT,width=left)
        self.tree.column(self.RIGHT,width=right)
        self.tree.configure(displaycolumns=displayed)

    def resize_columns(self,event=None):
        widths=tuple(int(self.tree.column(column,'width')) for column in self.columns)
        if widths!=self.widths:
            self.widths=widths;self.displayed=None
            self.update(*self.tree.xview())
