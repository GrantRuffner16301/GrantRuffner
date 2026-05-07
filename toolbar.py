"""Toolbar builder for Maestro Notepad."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QActionGroup
from PyQt6.QtWidgets import QComboBox, QFontComboBox, QLabel, QSlider, QToolBar


class ToolbarManager:
    """Build and hold the left and right toolbars.

    The main window tells us what each button should do.
    """

    def __init__(self, parent, canvas):
        self.parent = parent
        self.canvas = canvas
        self.left_toolbar = None
        self.right_toolbar = None
        self.tool_action_group = QActionGroup(parent)
        self.tool_action_group.setExclusive(True)
        self.tool_actions = {}
        self.slider = None
        self.pen_size_box = None
        self.font_box = None
        self.size_box = None
        self.ghost_action = None


    def _handle_font_change(self, font):
        # 1. Actually change the font
        self.parent.set_font_family(font)
    
        # 2. Force the font box to stop listening to the keyboard
        self.font_box.clearFocus()
    
        # 3. Tell the main window to put the blinking cursor back on the page
        self.parent.activate_text_mode()

    def build(self):
        """Create both toolbars and attach them to the main window."""

        self.left_toolbar = QToolBar("Left")
        self.right_toolbar = QToolBar("Right")

        for toolbar in (self.left_toolbar, self.right_toolbar):
            toolbar.setMovable(False)
            toolbar.setStyleSheet(self._toolbar_style())

        self.parent.addToolBar(Qt.ToolBarArea.LeftToolBarArea, self.left_toolbar)
        self.parent.addToolBar(Qt.ToolBarArea.RightToolBarArea, self.right_toolbar)

        self._build_left_toolbar()
        self._build_right_toolbar()

    def checked_tool_action(self):
        """Tell the window which drawing tool button is active right now."""

        return self.tool_action_group.checkedAction()

    def clear_tool_selection(self):
        """Uncheck the drawing buttons when the user goes back to typing."""

        checked_action = self.tool_action_group.checkedAction()
        if checked_action is not None:
            checked_action.setChecked(False)

    def _toolbar_style(self):
        """Keep the look in one place so the bars match each other."""

        return """
            QToolBar   { background: #1e1e1e; border-right: 3px solid #333; border-left: 3px solid #333; padding-top: 10px; }
            QToolButton{ color: white; background: #2a2a2a; border-radius: 3px; margin: 2px; padding: 9px; font-weight: bold; font-size: 13px; }
            QLabel     { color: #777; font-size: 13px; font-weight: bold; margin: 3px; }
            QComboBox  { background: darkblue; color: white; border: 1px solid #444; font-size: 9px; }
            QFontComboBox { background: darkblue; color: white; border: 1px solid #444; font-size: 9px; }
        """

    def _add_action(self, toolbar, text, handler, checkable=False, action_group=None):
        """Create one button and connect it to a Python function."""

        action = QAction(text, self.parent)
        action.setCheckable(checkable)
        action.triggered.connect(handler)
        toolbar.addAction(action)

        if action_group is not None:
            action_group.addAction(action)

        return action

    def _build_left_toolbar(self):
        bar = self.left_toolbar
        bar.addSeparator()
        bar.addWidget(QLabel(" 🪟 GLASS "))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimum(10)
        self.slider.setMaximum(100)
        self.slider.setFixedWidth(130)
        self.slider.setValue(int(self.parent.current_opacity * 100))
        self.slider.valueChanged.connect(self.parent.update_opacity)
        bar.addWidget(self.slider)
        bar.addSeparator()
        
        self.ghost_action = self._add_action(bar, " 👻 INFO ", self.parent.show_ghost_help)
        bar.addSeparator()
        
        self._add_action(bar, " 🔍 FIND ", self.parent.find_text)
        bar.addSeparator()
        
        self._add_action(bar, " 🪄 SPELL ", self.parent.correct_spelling)
        bar.addSeparator()
        
        self._add_action(bar, " 🗒️ PAGE ", self.parent.add_page)
        self._add_action(bar, " ❌ PAGE ", self.parent.delete_page)
        bar.addSeparator()

        self._add_action(bar, " 💬 NOTE ", self.canvas.add_smart_bubble)
        self._add_action(bar, " ❌ NOTE ", self.canvas.delete_selected)
        bar.addSeparator()

        # We wrap save/load so Qt's `triggered(bool)` signal does not accidentally
        # pass a True/False value into file-path arguments.
        self._add_action(bar, " 💾 SAVE ", lambda *_: self.parent.save_project())
        bar.addSeparator()
        
        self._add_action(bar, " 🖨️ PRINT ", self.parent.print_document)
        bar.addSeparator()
        
        self._add_action(bar, " 📂 LOAD ", lambda *_: self.parent.load_project())
        bar.addSeparator()
        
        self._add_action(bar, " 🆓 PDF ", self.parent.export_pdf)
        bar.addSeparator()

        self._add_action(bar, "🚪 EXIT ", self.parent.close)
        bar.addSeparator()
        bar.addWidget(QLabel(" 🕹️ MOVE ME "))

    def _build_right_toolbar(self):
        bar = self.right_toolbar
   
        bar.addSeparator()

        bar.addWidget(QLabel(" ✍🏼 Fonts "))
        self.font_box = QFontComboBox()
        self.font_box.currentFontChanged.connect(self._handle_font_change)
        bar.addWidget(self.font_box)
        bar.addSeparator()

        bar.addWidget(QLabel(" 📏 SIZE "))
        self.size_box = QComboBox()
        self.size_box.addItems(["12", "14", "18", "24", "36", "48", "56", "64", "72", "86", "98", "128"])
        self.size_box.setCurrentText("24")
        self.size_box.currentTextChanged.connect(self.canvas.change_font_size)
        bar.addWidget(self.size_box)
        bar.addSeparator()
        
        bar.addWidget(QLabel(" 🖊️ PEN "))
        self.pen_size_box = QComboBox()
        self.pen_size_box.addItems(["1", "2.5", "5", "10", "20", "30", "40", "50"])
        self.pen_size_box.setCurrentText("10")
        self.pen_size_box.currentTextChanged.connect(self.canvas.set_pen_width)
        bar.addWidget(self.pen_size_box)
        bar.addSeparator()
        
        self._add_action(bar, " 🎨 COLOR ", self.canvas.set_global_color)
        bar.addSeparator()

        self.tool_actions["draw"] = self._add_action(
            bar,
            " ✏️  DRAW ",
            lambda checked: self.parent.activate_tool("draw", checked),
            checkable=True,
            action_group=self.tool_action_group,
        )

        bar.addSeparator()
        self._add_action(bar, " 🔤  TEXT  ", self.parent.activate_text_mode)
        
        bar.addSeparator()
        self.tool_actions["eraser"] = self._add_action(
            bar,
            " 🧽 ERASE ",
            lambda checked: self.parent.activate_tool("eraser", checked),
            checkable=True,
            action_group=self.tool_action_group,
        )

        bar.addSeparator()
        self.tool_actions["rect"] = self._add_action(
            bar,
            "◻️ SQUARE ",
            lambda checked: self.parent.activate_tool("rect", checked),
            checkable=True,
            action_group=self.tool_action_group,
        )
        
        bar.addSeparator()
        self.tool_actions["ellipse"] = self._add_action(
            bar,
            "⚪ ELLIPSE",
            lambda checked: self.parent.activate_tool("ellipse", checked),
            checkable=True,
            action_group=self.tool_action_group,
        )
       
        bar.addSeparator()
        self.tool_actions["highlighter"] = self._add_action(
            bar,
            "🖍 Hi-LITE",
            lambda checked: self.parent.activate_tool("highlighter", checked),
            checkable=True,
            action_group=self.tool_action_group,
        )

        bar.addSeparator()
        self._add_action(bar, " UNDERLINE ", self.parent.toggle_underline, checkable=True)
        
        bar.addSeparator()
        self._add_action(bar, " 𝐁📄 Bold  ", self.parent.toggle_bold)
        
        bar.addSeparator()
        self._add_action(bar, "𝐼`✍️ Italic ", self.parent.toggle_italic)
        
        bar.addSeparator()
        bar.addWidget(QLabel(" 🕹️ MOVE ME "))
