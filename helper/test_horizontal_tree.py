"""Viewport geometry checks independent of Tcl/Tk installation."""
import unittest
from unittest.mock import Mock
from horizontal_tree import HorizontalTreeViewport,visible_columns


class HorizontalViewportTests(unittest.TestCase):
    def test_partial_columns_and_exact_edges(self):
        self.assertEqual(visible_columns([100,200,100],0,.25),(0,1,0,300))
        self.assertEqual(visible_columns([100,200,100],.25,.75),(1,2,100,100))
        self.assertEqual(visible_columns([100,200,100],.125,.875),(0,3,0,0))
        self.assertEqual(visible_columns([100,200,100],.75,1),(2,3,300,0))

    def test_whole_table_fits(self):
        self.assertEqual(visible_columns([100,200,100],0,1),(0,3,0,0))

    def test_scroll_range_remains_constant(self):
        widths=[80,200,50,300,120]
        for first,last in ((0,.2),(.1,.3),(.5,.8),(.8,1)):
            start,stop,left,right=visible_columns(widths,first,last)
            self.assertEqual(left+sum(widths[start:stop])+right,sum(widths))

    def test_updates_only_when_visible_columns_change(self):
        tree=Mock();tree.column.side_effect=lambda column,option=None,**kwargs:100 if option=='width' else None
        scrollbar=Mock()
        viewport=HorizontalTreeViewport(tree,('a','b','c','d'),scrollbar)
        tree.configure.reset_mock()
        viewport.update('0','.25')
        tree.configure.assert_called_once_with(displaycolumns=('a',viewport.RIGHT))
        viewport.update('0','.25')
        self.assertEqual(tree.configure.call_count,1)
        viewport.update('.75','1')
        tree.configure.assert_called_with(displaycolumns=(viewport.LEFT,'d'))


if __name__=='__main__':unittest.main()
