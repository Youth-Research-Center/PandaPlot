"""GUI components.

Import a component from its own module, e.g.
``pandaplot.gui.components.sidebar.sidebar``. This package deliberately
re-exports nothing: importing any leaf widget (such as the shared combo box)
initialises this package first, and re-exporting the sidebar and tab container
here made every such import load the whole sidebar, tabs and commands, which
turned dialogs importing a shared widget into an import cycle.

MainMenu is likewise not imported here, to defer matplotlib loading.
"""
