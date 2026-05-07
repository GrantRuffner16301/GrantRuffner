"""Maestro Notepad.

This file keeps the main app together, while helper files hold the parts
that were pulled out during refactoring.
"""

from __future__ import annotations

import re
import sys
import math

from PyQt6.QtCore import QObject, QPointF, QRectF, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QAction,
    QColor,
    QBrush,
    QFont,
    QImage,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QShortcut,
    QTextCursor,
    QTextCharFormat,
    QTextDocument,
    QSyntaxHighlighter,
    QUndoCommand,
    QUndoStack,
)
from PyQt6.QtPrintSupport import QPrintDialog, QPrinter
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFontComboBox,
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from autosave_manager import AutoSaveManager
from canvas_widget import (
    PAGE_GAP,
    PAGE_HEIGHT,
    PAGE_WIDTH,
    TEXT_MARGIN,
    build_page_bundle,
    deserialize_draw_item,
    page_scene_rect,
    render_page_to_image,
    serialize_draw_item,
)
from file_manager import FileManager
from toolbar import ToolbarManager


class GlobalSignals(QObject):
    """A tiny signal hub.

    Think of this like a classroom hand-raise button that lets far-away parts
    of the app politely say, "Please toggle ghost mode now."
    """

    toggle_ghost = pyqtSignal()


class SpellCheckHighlighter(QSyntaxHighlighter):
    """Underline misspelled words while the user types.

    This works like a teacher's pencil mark under words that need another look.
    """

    word_pattern = re.compile(r"[A-Za-z][A-Za-z'\-]*")

    def __init__(self, document, spell_checker):
        super().__init__(document)
        self.spell_checker = spell_checker
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineColor(QColor("#d62828"))
        self.error_format.setUnderlineStyle(
            QTextCharFormat.UnderlineStyle.SpellCheckUnderline
        )

    def highlightBlock(self, text):
        """Check one line of text and underline words the dictionary does not know."""

        if self.spell_checker is None:
            return

        for match in self.word_pattern.finditer(text):
            word = match.group(0).lower().strip("-'")
            if len(word) <= 1:
                continue

            try:
                if self.spell_checker.unknown([word]):
                    self.setFormat(
                        match.start(),
                        len(match.group(0)),
                        self.error_format,
                    )
            except Exception:
                return


class FindReplaceDialog(QDialog):
    """A small stay open search window for finding and replacing text."""

    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("Find and Replace")
        self.setModal(False)
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Find text")
        self.replace_input = QLineEdit()
        self.replace_input.setPlaceholderText("Replace with")

        layout.addWidget(QLabel("Find"))
        layout.addWidget(self.find_input)
        layout.addWidget(QLabel("Replace"))
        layout.addWidget(self.replace_input)

        button_row = QHBoxLayout()
        self.find_button = QPushButton("Find Next")
        self.replace_button = QPushButton("Replace")
        self.replace_all_button = QPushButton("Replace All")
        self.close_button = QPushButton("Close")

        for button in (
            self.find_button,
            self.replace_button,
            self.replace_all_button,
            self.close_button,
        ):
            button_row.addWidget(button)

        layout.addLayout(button_row)

        self.find_button.clicked.connect(self.find_next)
        self.replace_button.clicked.connect(self.replace_one)
        self.replace_all_button.clicked.connect(self.replace_all)
        self.close_button.clicked.connect(self.hide)
        self.find_input.returnPressed.connect(self.find_next)
        self.replace_input.returnPressed.connect(self.replace_one)

    def show_for_phrase(self, phrase=""):
        """Show the dialog without blocking the main app window."""

        if phrase:
            self.find_input.setText(phrase)
            self.find_input.selectAll()

        self.show()
        self.raise_()
        self.activateWindow()
        self.find_input.setFocus()

    def find_next(self):
        """Jump to the next matching word or phrase."""

        phrase = self.find_input.text().strip()
        if phrase and not self.window.canvas.find_text(phrase, start_after_current=True):
            QMessageBox.information(self, "Find", f"Could not find: {phrase}")

    def replace_one(self):
        """Replace the current match and then move to the next one."""

        phrase = self.find_input.text().strip()
        if not phrase:
            return

        if not self.window.canvas.replace_current_match(phrase, self.replace_input.text()):
            QMessageBox.information(self, "Replace", f"No selected match for: {phrase}")
            return

        self.window.canvas.find_text(phrase, start_after_current=True)

    def replace_all(self):
        """Replace every match in every searchable text box."""

        phrase = self.find_input.text().strip()
        if not phrase:
            return

        count = self.window.canvas.replace_all_matches(phrase, self.replace_input.text())
        QMessageBox.information(self, "Replace All", f"Replaced {count} match(es).")


def mark_canvas_dirty_from_scene(scene):
    """Find the canvas that owns a scene and flag it as changed."""

    if scene is None:
        return

    for view in scene.views():
        if hasattr(view, "mark_dirty"):
            view.mark_dirty()


class AddItemCommand(QUndoCommand):
    """Undo command for adding a note or drawing to the scene."""

    def __init__(self, scene, item, text="Add Item"):
        super().__init__(text)
        self.scene = scene
        self.item = item

    def undo(self):
        """Undo means taking the item back out of the scene."""

        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)
            mark_canvas_dirty_from_scene(self.scene)

    def redo(self):
        """Redo means putting the item back into the scene."""

        if self.item.scene() is None:
            self.scene.addItem(self.item)
            mark_canvas_dirty_from_scene(self.scene)


class RemoveItemCommand(QUndoCommand):
    """Undo command for removing a note or drawing from the scene."""

    def __init__(self, scene, item, text="Remove Item"):
        super().__init__(text)
        self.scene = scene
        self.item = item

    def undo(self):
        """Undo means the deleted item gets to come back."""

        if self.item.scene() is None:
            self.scene.addItem(self.item)
            mark_canvas_dirty_from_scene(self.scene)

    def redo(self):
        """Redo means the item is removed again."""

        if self.item.scene() is self.scene:
            self.scene.removeItem(self.item)
            mark_canvas_dirty_from_scene(self.scene)


class MoveItemCommand(QUndoCommand):
    """Undo command for moving a floating cloud note."""

    def __init__(self, item, old_pos, new_pos):
        super().__init__("Move Item")
        self.item = item
        self.old_pos = old_pos
        self.new_pos = new_pos

    def undo(self):
        self.item.setPos(self.old_pos)
        scene = self.item.scene()
        mark_canvas_dirty_from_scene(scene)

    def redo(self):
        self.item.setPos(self.new_pos)
        scene = self.item.scene()
        mark_canvas_dirty_from_scene(scene)


class ResizeCloudCommand(QUndoCommand):
    """Undo command for resizing a thought cloud."""

    def __init__(self, cloud, old_width, old_height, new_width, new_height):
        super().__init__("Resize Cloud")
        self.cloud = cloud
        self.old_width = old_width
        self.old_height = old_height
        self.new_width = new_width
        self.new_height = new_height

    def _apply(self, width, height):
        self.cloud.fixed_width = width
        self.cloud.body_height = height
        self.cloud.text_item.setTextWidth(self.cloud.fixed_width - (self.cloud.pad * 2))
        self.cloud.sync_idea_notes_shape()

    def undo(self):
        self._apply(self.old_width, self.old_height)
        scene = self.cloud.scene()
        mark_canvas_dirty_from_scene(scene)

    def redo(self):
        self._apply(self.new_width, self.new_height)
        scene = self.cloud.scene()
        mark_canvas_dirty_from_scene(scene)


class TailMoveCommand(QUndoCommand):
    """Undo command for moving the little cloud tail handle."""

    def __init__(self, cloud, old_ratio, new_ratio):
        super().__init__("Move Tail")
        self.cloud = cloud
        self.old_ratio = old_ratio
        self.new_ratio = new_ratio

    def _apply(self, ratio):
        self.cloud.tail_control_ratio = ratio
        self.cloud.sync_idea_notes_shape()

    def undo(self):
        self._apply(self.old_ratio)
        scene = self.cloud.scene()
        mark_canvas_dirty_from_scene(scene)

    def redo(self):
        self._apply(self.new_ratio)
        scene = self.cloud.scene()
        mark_canvas_dirty_from_scene(scene)


class EraseStrokeCommand(QUndoCommand):
    """Undo command for one eraser drag across one or more drawing items."""

    def __init__(self, scene, edits):
        super().__init__("Erase")
        self.scene = scene
        self.edits = edits
        self._first_redo = True

    def _apply_edit(self, edit, use_new_state):
        item = edit["item"]
        if edit["kind"] == "path":
            state = edit["new"] if use_new_state else edit["old"]
            if state is None:
                if item.scene() is self.scene:
                    self.scene.removeItem(item)
                return

            if item.scene() is None:
                self.scene.addItem(item)
            item.setPath(QPainterPath(state))
            return

        if edit["kind"] == "item":
            if use_new_state:
                if item.scene() is self.scene:
                    self.scene.removeItem(item)
            else:
                if item.scene() is None:
                    self.scene.addItem(item)

    def undo(self):
        for edit in self.edits:
            self._apply_edit(edit, use_new_state=False)
        mark_canvas_dirty_from_scene(self.scene)

    def redo(self):
        if self._first_redo:
            self._first_redo = False
            mark_canvas_dirty_from_scene(self.scene)
            return

        for edit in self.edits:
            self._apply_edit(edit, use_new_state=True)
        mark_canvas_dirty_from_scene(self.scene)


class AddPageCommand(QUndoCommand):
    """Undo command for creating one new notebook page."""

    def __init__(self, canvas):
        super().__init__("Add Page")
        self.canvas = canvas
        self.page_snapshot = None
        self.page_index = None

    def redo(self):
        """The first redo makes a new page. Later redos restore the saved page."""

        if self.page_snapshot is None:
            self.page_index = self.canvas.append_page()
        else:
            self.canvas.restore_page_snapshot(self.page_snapshot)
        self.canvas.mark_dirty()

    def undo(self):
        """Undo removes the page and remembers what was on it."""

        if self.page_index is not None and self.page_index < len(self.canvas.pages):
            self.page_snapshot = self.canvas.remove_page_at(self.page_index)
            self.canvas.mark_dirty()


class DeletePageCommand(QUndoCommand):
    """Undo command for deleting one page and all items on it."""

    def __init__(self, canvas, page_index):
        super().__init__("Delete Page")
        self.canvas = canvas
        self.page_index = page_index
        self.page_snapshot = None

    def redo(self):
        """Delete the page and remember its full contents."""

        if 0 <= self.page_index < len(self.canvas.pages):
            self.page_snapshot = self.canvas.remove_page_at(self.page_index)
            self.canvas.mark_dirty()

    def undo(self):
        """Bring the deleted page back exactly where it was."""

        if self.page_snapshot is not None:
            self.canvas.restore_page_snapshot(self.page_snapshot)
            self.canvas.mark_dirty()


class MaestroCanvas(QGraphicsView):
    """The big note taking area where text, drawings, and clouds live."""

    markdown_patterns = (
        re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE),
        re.compile(r"\*\*.+?\*\*"),
        re.compile(r"(?<!\*)\*[^*\n]+\*(?!\*)"),
        re.compile(r"^\s*[-*]\s", re.MULTILINE),
        re.compile(r"^\s*\d+\.\s", re.MULTILINE),
        re.compile(r"`[^`\n]+`"),
        re.compile(r"\[[^\]]+\]\([^)]+\)"),
    )

    def __init__(self):
        super().__init__()
        self.undo_enabled = True
        self.mode = "text"
        self.current_tool = "none"
        self.draw_color = QColor(255, 50, 50)
        self.current_text_color = QColor(0, 0, 0)
        self.draw_size = 10.0
        self.current_font_size = 24.0
        self.p_w = PAGE_WIDTH
        self.p_h = PAGE_HEIGHT
        self.gap = PAGE_GAP
        self.pages = []
        self.last_focused_text = None
        self._currently_focused_text = None
        self.clipboard = []
        self.current_page_index = 0
        self.spell_checker = None
        self.spell_highlighters = {}
        self._dirty = False
        self._suspend_dirty_tracking = False
        self._state_change_callback = None

        # The scene is like the giant tabletop where every page and drawing sits.
        self.scene = DrawingCanvas(self)
        self.setScene(self.scene)
        self.undo_stack = QUndoStack(self)

        self.setStyleSheet("background: #121212; border: none;")
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.verticalScrollBar().valueChanged.connect(self.handle_scroll_focus)

        self.append_page()
        self.mark_clean()

    def set_state_change_callback(self, callback):
        """Let the window know when the canvas clean/dirty state changes."""

        self._state_change_callback = callback

    def _notify_state_change(self):
        """Ping the window when the dirty state changes."""

        if callable(self._state_change_callback):
            self._state_change_callback()

    def mark_dirty(self):
        """Remember that the notebook has unsaved work."""

        if self._suspend_dirty_tracking:
            return

        if not self._dirty:
            self._dirty = True
            self._notify_state_change()

    def mark_clean(self):
        """Remember that the notebook matches the last real save/load state."""

        if self._dirty:
            self._dirty = False
            self._notify_state_change()
        else:
            self._dirty = False

    def is_dirty(self):
        """Tell the window whether the notebook has unsaved changes."""

        return getattr(self, "_dirty", False)

    def settle_clean_state_soon(self):
        """Ignore one short burst of load-time housekeeping edits."""

        self._suspend_dirty_tracking = True

        def finish_settling():
            self._suspend_dirty_tracking = False
            self.mark_clean()

        QTimer.singleShot(0, finish_settling)

    def handle_scroll_focus(self):
        """Track which page is in the middle of the screen right now."""

        viewport_rect = self.viewport().rect()
        center_in_scene = self.mapToScene(viewport_rect.center())

        for index, page_data in enumerate(self.pages):
            if page_data["paper"].sceneBoundingRect().contains(center_in_scene):
                self.current_page_index = index
                self.last_focused_text = page_data["text"]
                break

    def apply_markdown(self):
        """Turn markdown-style typing into formatted rich text."""

        item = self.active_text_item()
        if not item:
            return

        self.apply_markdown_to_text_item(item)

    def set_tool(self, tool):
        """Switch from typing mode into one drawing tool."""

        self.mode = "draw"
        self.current_tool = tool
        self._set_text_editable(False)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def switch_to_text_mode(self):
        """Put the user back into typing mode on the page they are viewing."""

        self.mode = "text"
        self.current_tool = "none"
        self.scene.clearSelection()
        self._set_text_editable(True)
        self.unsetCursor()

        target_text_item = None
        viewport_rect = self.viewport().rect()
        view_center = self.mapToScene(viewport_rect.center())

        for page_data in self.pages:
            if page_data["paper"].sceneBoundingRect().contains(view_center):
                target_text_item = page_data["text"]
                break

        if target_text_item is None and self.pages:
            target_text_item = self.pages[0]["text"]

        if target_text_item is not None:
            target_text_item.setFocus()
            cursor = target_text_item.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            target_text_item.setTextCursor(cursor)
            self.ensureVisible(target_text_item)

    def _set_text_editable(self, editable):
        """Turn text editing on or off for every page."""

        flag = (
            Qt.TextInteractionFlag.TextEditorInteraction
            if editable
            else Qt.TextInteractionFlag.NoTextInteraction
        )

        for page in self.pages:
            page["text"].setTextInteractionFlags(flag)
            if not editable:
                page["text"].clearFocus()

    def configure_spellchecker(self, spell_checker):
        """Attach live spell checking to every text document we know about."""

        self.spell_checker = spell_checker
        self.spell_highlighters.clear()

        for text_item in self.searchable_text_items():
            self._install_spellchecker(text_item)

    def _install_spellchecker(self, text_item):
        """Keep a spell highlighter alive for one text document."""

        if self.spell_checker is None or text_item is None:
            return

        self.spell_highlighters[id(text_item)] = SpellCheckHighlighter(
            text_item.document(),
            self.spell_checker,
        )

    def _register_text_item(self, text_item):
        """Set up one text item so focus, markdown, and spell tools all work."""

        text_item.installEventFilter(self)
        self._install_spellchecker(text_item)
        text_item.document().contentsChanged.connect(self._on_document_contents_changed)

    def _on_document_contents_changed(self):
        """Any text edit means the notebook now has unsaved work."""

        self.mark_dirty()

    def looks_like_markdown(self, text):
        """Guess whether the user typed markdown marks instead of plain prose."""

        if "<" in text and ">" in text:
            return False

        return any(pattern.search(text) for pattern in self.markdown_patterns)

    def apply_markdown_to_text_item(self, text_item):
        """Render markdown text into rich text without losing the editing location."""

        if not isinstance(text_item, QGraphicsTextItem):
            return False

        plain_text = text_item.toPlainText()
        if not plain_text.strip() or not self.looks_like_markdown(plain_text):
            return False

        cursor = text_item.textCursor()
        old_position = cursor.position()
        text_item.document().setMarkdown(plain_text)

        new_cursor = text_item.textCursor()
        new_cursor.setPosition(min(old_position, len(text_item.toPlainText())))
        text_item.setTextCursor(new_cursor)
        return True

    def _build_page(self, html=""):
        """Create one page bundle and start watching its text box."""

        bundle = build_page_bundle(self.scene, 0, self.current_font_size, html)
        self._register_text_item(bundle["text"])
        return bundle

    def append_page(self):
        """Add a brand-new blank page to the end of the notebook."""

        bundle = self._build_page()
        self.pages.append(bundle)
        self._reflow_pages()
        return len(self.pages) - 1

    def _reflow_pages(self):
        """Stack every page neatly with the same gap between them."""

        for index, page in enumerate(self.pages):
            y_pos = index * (self.p_h + self.gap)
            page["paper"].setRect(0, 0, self.p_w, self.p_h)
            page["paper"].setPos(0, y_pos)
            page["text"].setPos(TEXT_MARGIN, y_pos + TEXT_MARGIN)

        self.scene.setSceneRect(page_scene_rect(len(self.pages)))
        self.current_page_index = min(self.current_page_index, max(len(self.pages) - 1, 0))

    def _page_bounds(self, page_index):
        """Return the top and bottom Y values for one page."""

        top = page_index * (self.p_h + self.gap)
        return top, top + self.p_h

    def _iter_page_items(self, page_index):
        """Yield top-level notes and drawings that belong to one page."""

        top, bottom = self._page_bounds(page_index)
        page_paper = self.pages[page_index]["paper"]
        page_text = self.pages[page_index]["text"]

        for item in self.scene.items():
            if item in {page_paper, page_text}:
                continue
            if item.parentItem() is not None:
                continue

            center_y = item.sceneBoundingRect().center().y()
            if top <= center_y < bottom:
                yield item

    def _shift_floating_items_from(self, y_threshold, delta_y):
        """Move notes and drawings when pages are inserted or removed."""

        for item in self.scene.items():
            if item.parentItem() is not None:
                continue
            if any(item in {page["paper"], page["text"]} for page in self.pages):
                continue

            center_y = item.sceneBoundingRect().center().y()
            if center_y >= y_threshold:
                item.moveBy(0, delta_y)

    def snapshot_page(self, page_index):
        """Collect everything on one page into plain saveable data."""

        page = self.pages[page_index]
        snapshot = {
            "index": page_index,
            "text_html": page["text"].document().toHtml(),
            "notes": [],
            "drawings": [],
        }

        for item in self._iter_page_items(page_index):
            if isinstance(item, CloudIdeaNote):
                snapshot["notes"].append(item.to_dict())
            else:
                draw_data = serialize_draw_item(item)
                if draw_data is not None:
                    snapshot["drawings"].append(draw_data)

        return snapshot

    def remove_page_at(self, page_index):
        """Delete a page and shift the later pages upward."""

        snapshot = self.snapshot_page(page_index)
        page_items = list(self._iter_page_items(page_index))
        top, bottom = self._page_bounds(page_index)
        page = self.pages.pop(page_index)
        shift_amount = self.p_h + self.gap

        for item in page_items:
            self.scene.removeItem(item)

        self.scene.removeItem(page["paper"])
        self.scene.removeItem(page["text"])
        self._shift_floating_items_from(bottom, -shift_amount)
        self._reflow_pages()
        self.current_page_index = min(page_index, max(len(self.pages) - 1, 0))
        return snapshot

    def restore_page_snapshot(self, snapshot):
        """Put back a deleted page and all of its saved items."""

        page_index = min(snapshot["index"], len(self.pages))
        insert_top = page_index * (self.p_h + self.gap)
        shift_amount = self.p_h + self.gap

        self._shift_floating_items_from(insert_top, shift_amount)

        bundle = self._build_page(snapshot.get("text_html", ""))
        self.pages.insert(page_index, bundle)
        self._reflow_pages()

        for note_data in snapshot.get("notes", []):
            note = CloudIdeaNote.from_dict(note_data)
            self.scene.addItem(note)
            self._register_text_item(note.text_item)

        for draw_data in snapshot.get("drawings", []):
            draw_item = deserialize_draw_item(draw_data)
            if draw_item is not None:
                self.scene.addItem(draw_item)

        self.current_page_index = page_index

    def serialize(self):
        """Turn the whole notebook into plain data that can be saved as JSON."""

        pages_data = []
        for page_index, page in enumerate(self.pages):
            snapshot = self.snapshot_page(page_index)
            pages_data.append(
                {
                    "text_html": snapshot["text_html"],
                    "notes": snapshot["notes"],
                    "drawings": snapshot["drawings"],
                }
            )

        return {
            "page_width": self.p_w,
            "page_height": self.p_h,
            "gap": self.gap,
            "pages": pages_data,
        }

    def deserialize(self, data):
        """Rebuild the notebook from saved project data."""

        self.undo_enabled = False
        self._suspend_dirty_tracking = True
        self.scene.clear()
        self.pages = []
        self.last_focused_text = None
        self._currently_focused_text = None
        self.p_w = data.get("page_width", PAGE_WIDTH)
        self.p_h = data.get("page_height", PAGE_HEIGHT)
        self.gap = data.get("gap", PAGE_GAP)

        for page_info in data.get("pages", []):
            bundle = self._build_page(page_info.get("text_html", ""))
            self.pages.append(bundle)

        if not self.pages:
            self.append_page()
        else:
            self._reflow_pages()

        for page_info in data.get("pages", []):
            for note_data in page_info.get("notes", []):
                note = CloudIdeaNote.from_dict(note_data)
                self.scene.addItem(note)
                self._register_text_item(note.text_item)

            for draw_data in page_info.get("drawings", []):
                draw_item = deserialize_draw_item(draw_data)
                if draw_item is not None:
                    self.scene.addItem(draw_item)

        self.scene.setSceneRect(page_scene_rect(len(self.pages)))
        self.undo_enabled = True
        self._suspend_dirty_tracking = False
        self.undo_stack.clear()
        self.current_page_index = 0
        self.mark_clean()
        self.switch_to_text_mode()

    def searchable_text_items(self):
        """List page text boxes first, then cloud notes from top to bottom."""

        cloud_text_items = [
            item.text_item
            for item in sorted(
                (scene_item for scene_item in self.scene.items() if isinstance(scene_item, CloudIdeaNote)),
                key=lambda note: (note.scenePos().y(), note.scenePos().x()),
            )
        ]
        return [page["text"] for page in self.pages] + cloud_text_items

    def apply_markdown_to_all(self):
        """Render markdown for every text box before saving or exporting."""

        for text_item in self.searchable_text_items():
            self.apply_markdown_to_text_item(text_item)

    def selected_cloud_note(self):
        """Return the selected cloud note, if there is one."""

        for item in self.scene.selectedItems():
            if isinstance(item, CloudIdeaNote):
                return item
        return None

    def focus_text_item(self, text_item):
        """Move keyboard focus into a chosen text item."""

        if text_item is None:
            return None

        if self.mode != "text":
            self.mode = "text"
            self.current_tool = "none"
            self._set_text_editable(True)
            self.unsetCursor()

        if isinstance(text_item.parentItem(), CloudIdeaNote):
            text_item.parentItem().begin_text_editing()
        else:
            text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
            text_item.setFocus()

        self.last_focused_text = text_item
        self._currently_focused_text = text_item
        self.ensureVisible(text_item)
        return text_item

    def focused_text_item(self):
        """Return the text item that truly has keyboard focus right now."""

        scene_focus = self.scene.focusItem()
        if isinstance(scene_focus, QGraphicsTextItem):
            return scene_focus
        if isinstance(self._currently_focused_text, QGraphicsTextItem):
            return self._currently_focused_text
        return None

    def ensure_text_item_for_formatting(self):
        """Pick the best text box to receive font, color, and style changes."""

        focus_item = self.focused_text_item()
        if isinstance(focus_item, QGraphicsTextItem):
            self.last_focused_text = focus_item
            return self.focus_text_item(focus_item)

        # When the user clicks the toolbar, the text box can lose focus for a
        # moment. We still remember the last box they were editing so the font
        # tool changes the right words instead of jumping to some other place.
        if isinstance(self.last_focused_text, QGraphicsTextItem):
            return self.focus_text_item(self.last_focused_text)

        selected_note = self.selected_cloud_note()
        if selected_note is not None:
            return self.focus_text_item(selected_note.text_item)

        if self.pages:
            target_text = self.pages[self.current_page_index]["text"]
            cursor = target_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            target_text.setTextCursor(cursor)
            return self.focus_text_item(target_text)

        return None

    def _apply_typing_color_to_text_item(self, text_item):
        """Set the color for new typing without repainting older text."""

        if not isinstance(text_item, QGraphicsTextItem):
            return

        previous_suspend = self._suspend_dirty_tracking
        self._suspend_dirty_tracking = True
        try:
            cursor = text_item.textCursor()
            fmt = cursor.charFormat()
            fmt.setForeground(QBrush(self.current_text_color))
            cursor.mergeCharFormat(fmt)
            text_item.setTextCursor(cursor)
        finally:
            self._suspend_dirty_tracking = previous_suspend

    def _apply_char_format(self, text_item, configure_format):
        """Apply a character-format change to the selection or current typing point."""

        if not isinstance(text_item, QGraphicsTextItem):
            return False

        cursor = text_item.textCursor()
        fmt = cursor.charFormat()
        configure_format(fmt)
        cursor.mergeCharFormat(fmt)
        text_item.setTextCursor(cursor)
        return True

    def effective_text_font(self, text_item):
        """Figure out the best font to treat as the current typing font."""

        if not isinstance(text_item, QGraphicsTextItem):
            return QFont("Arial", int(self.current_font_size))

        cursor = text_item.textCursor()
        fmt = cursor.charFormat()
        current_font = QFont(fmt.font())

        if not current_font.family():
            current_font = QFont(text_item.document().defaultFont())

        if current_font.pointSizeF() <= 0:
            if fmt.fontPointSize() > 0:
                current_font.setPointSizeF(fmt.fontPointSize())
            elif text_item.document().defaultFont().pointSizeF() > 0:
                current_font.setPointSizeF(text_item.document().defaultFont().pointSizeF())
            else:
                current_font.setPointSizeF(self.current_font_size)

        return current_font

    def restore_text_focus_soon(self, text_item=None):
        """Give the keyboard back to the last text box after toolbar clicks."""

        target = text_item
        if not isinstance(target, QGraphicsTextItem):
            target = self.focused_text_item()
        if not isinstance(target, QGraphicsTextItem):
            target = self.last_focused_text
        if not isinstance(target, QGraphicsTextItem):
            return

        # The toolbar popup closes after the signal fires, so we wait one tiny
        # turn of the event loop before putting the cursor back where the user
        # was typing.
        QTimer.singleShot(0, lambda: self.focus_text_item(target))

    def render_page_image(self, page_index):
        """Draw one page into a picture file."""

        if page_index < 0 or page_index >= len(self.pages):
            return None

        y_pos = page_index * (self.p_h + self.gap)
        return render_page_to_image(self.scene, y_pos)

    def set_global_color(self):
        """Pick a new drawing color and apply it to selected text if possible."""

        from PyQt6.QtWidgets import QColorDialog

        color = QColorDialog.getColor(self.draw_color, self)
        if not color.isValid():
            return

        self.draw_color = color
        self.current_text_color = color

        focus_item = self.focused_text_item()
        if focus_item is None:
            selected_note = self.selected_cloud_note()
            if selected_note is not None:
                focus_item = self.focus_text_item(selected_note.text_item)
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        self._apply_char_format(
            focus_item,
            lambda fmt: fmt.setForeground(QBrush(color)),
        )
        self.focus_text_item(focus_item)

    def set_pen_width(self, width_str):
        """Change how thick future drawing strokes should be."""

        self.draw_size = float(width_str)

    def change_font_size(self, size):
        """Change text size for the current text box or selection."""

        self.current_font_size = float(size)
        focus_item = self.ensure_text_item_for_formatting()
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        self._apply_char_format(
            focus_item,
            lambda fmt: fmt.setFontPointSize(self.current_font_size),
        )
        self.restore_text_focus_soon(focus_item)

    def add_smart_bubble(self):
        """Add a thought cloud near the center of the visible page."""

        center = self.mapToScene(self.viewport().rect().center())
        note = CloudIdeaNote(center.x() - 140, center.y() - 40)
        self._register_text_item(note.text_item)

        if self.undo_enabled:
            self.undo_stack.push(AddItemCommand(self.scene, note, "Add Your Note Here"))

    def eventFilter(self, watched, event):
        """Remember which text box the user clicked into last."""

        from PyQt6.QtCore import QEvent

        if isinstance(watched, QGraphicsTextItem) and event.type() == QEvent.Type.FocusIn:
            self.last_focused_text = watched
            self._currently_focused_text = watched
            if getattr(watched, "_is_placeholder", False):
                watched.setPlainText("")
                watched._is_placeholder = False
            self._apply_typing_color_to_text_item(watched)

        if isinstance(watched, QGraphicsTextItem) and event.type() == QEvent.Type.FocusOut:
            if self._currently_focused_text is watched:
                self._currently_focused_text = None
            self.apply_markdown_to_text_item(watched)

        return super().eventFilter(watched, event)

    def find_text(self, phrase, start_after_current=True):
        """Search across page text and cloud notes for the next matching phrase."""

        if not phrase:
            return False

        targets = self.searchable_text_items()
        if not targets:
            return False

        active_item = self.active_text_item()
        start_index = targets.index(active_item) if active_item in targets else 0

        cursor_start = 0
        if active_item in targets and start_after_current:
            active_cursor = active_item.textCursor()
            cursor_start = (
                active_cursor.selectionEnd()
                if active_cursor.hasSelection()
                else active_cursor.position()
            )

        search_order = [start_index] + list(range(start_index + 1, len(targets))) + list(range(0, start_index))

        for index in search_order:
            text_item = targets[index]
            start_position = cursor_start if index == start_index else 0
            found_cursor = text_item.document().find(phrase, start_position)
            if found_cursor.isNull() and index == start_index and start_position > 0:
                found_cursor = text_item.document().find(phrase, 0)

            if found_cursor.isNull():
                continue

            self.focus_text_item(text_item)
            text_item.setTextCursor(found_cursor)
            return True

        return False

    def active_text_item(self):
        """Return the text box the user is currently working in."""

        focus_item = self.scene.focusItem()
        if isinstance(focus_item, QGraphicsTextItem):
            return focus_item
        return self.last_focused_text

    def replace_current_match(self, phrase, replacement):
        """Replace the selected match if it is the phrase the user searched for."""

        item = self.active_text_item()
        if item is None:
            return False

        cursor = item.textCursor()
        if not cursor.hasSelection() or cursor.selectedText() != phrase:
            # If focus drifted or the selection was cleared, try to rebuild the
            # current match once so the Replace button still behaves kindly.
            if not self.find_text(phrase, start_after_current=False):
                return False
            item = self.active_text_item()
            if item is None:
                return False
            cursor = item.textCursor()
            if not cursor.hasSelection() or cursor.selectedText() != phrase:
                return False

        cursor.insertText(replacement)
        item.setTextCursor(cursor)
        return True

    def replace_all_matches(self, phrase, replacement):
        """Replace all copies of a phrase in every searchable text box."""

        if not phrase:
            return 0

        total_replaced = 0
        for text_item in self.searchable_text_items():
            document = text_item.document()
            cursor = document.find(phrase, 0)
            while not cursor.isNull():
                cursor.beginEditBlock()
                cursor.insertText(replacement)
                cursor.endEditBlock()
                total_replaced += 1
                cursor = document.find(phrase, cursor.position())

        return total_replaced

    def delete_selected(self):
        """Delete selected notes or drawings."""

        if not self.undo_enabled:
            return

        for item in self.scene.selectedItems():
            if isinstance(
                item,
                (CloudIdeaNote, QGraphicsPathItem, QGraphicsRectItem, QGraphicsEllipseItem),
            ):
                self.undo_stack.push(RemoveItemCommand(self.scene, item, "Delete Item"))

    def cut_selection(self):
        """Copy notes first, then remove the selected items."""

        if not self.undo_enabled:
            return

        self.copy_selection()
        for item in self.scene.selectedItems():
            if isinstance(
                item,
                (CloudIdeaNote, QGraphicsPathItem, QGraphicsRectItem, QGraphicsEllipseItem),
            ):
                self.undo_stack.push(RemoveItemCommand(self.scene, item, "Cut Item"))

    def remove_selected_page(self):
        """Delete the page that is currently in view after asking the user first."""

        if len(self.pages) <= 1:
            QMessageBox.information(
                self,
                "Maestro Says...",
                "Whoops! You cannot delete the only page left.",
            )
            return

        page_index = self.current_page_index
        message_box = QMessageBox(self.window())
        message_box.setWindowTitle("Delete Page")
        message_box.setText(f"Delete page {page_index + 1}?")
        message_box.setInformativeText("This removes the whole page and everything on it.")
        message_box.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        message_box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        message_box.setStyleSheet(
            "QMessageBox { background-color: white; }"
            "QLabel { color: black; min-width: 260px; }"
            "QPushButton { background-color: #dddddd; color: black; padding: 8px 12px; border-radius: 6px; min-width: 110px; }"
        )

        if message_box.exec() != QMessageBox.StandardButton.Yes:
            return

        self.scene.clearSelection()
        self.undo_stack.push(DeletePageCommand(self, page_index))

    def select_all(self):
        """Select every item on the scene."""

        for item in self.scene.items():
            item.setSelected(True)

    def copy_selection(self):
        """Copy selected thought clouds into a simple in-memory clipboard."""

        self.clipboard = []

        for item in self.scene.selectedItems():
            if isinstance(item, CloudIdeaNote):
                self.clipboard.append(("note", item.to_dict()))

    def paste_selection(self):
        """Paste copied thought clouds a little offset from the original."""

        for item_type, data in self.clipboard:
            if item_type != "note":
                continue

            note = CloudIdeaNote.from_dict(data)
            note.moveBy(20, 20)
            self._register_text_item(note.text_item)
            if self.undo_enabled:
                self.undo_stack.push(AddItemCommand(self.scene, note, "Paste Note"))
            else:
                self.scene.addItem(note)

    def load_demo_content(self):
        """Fill the notebook with sample pages for classroom-style demos."""

        self.deserialize(build_demo_project_data())


class CloudIdeaNote(QGraphicsPathItem):
    """A movable thought cloud with editable text, a resize handle, and a tail."""

    def __init__(self, x_pos, y_pos, initial_width=280):
        super().__init__()
        self.setPos(x_pos, y_pos)
        self._start_pos_for_move = None
        self._is_updating = False
        self.tail_direction = "down"
        self.pad = 30
        self.puff = 20
        self.fixed_width = initial_width
        self.current_h = 100
        self.body_height = 100
        self.tail_control_ratio = QPointF(0.5, 0.82)

        self.setZValue(200)
        self.setBrush(QBrush(QColor(255, 255, 205, 250)))
        self.setPen(QPen(QColor(180, 180, 140), 1.5))

        self.text_item = CloudTextItem(self)
        self.text_item.setPos(self.pad, self.pad)
        self.text_item.setDefaultTextColor(QColor(0, 0, 0))

        self.doc = QTextDocument()
        self.doc.setDefaultFont(QFont("Verdana", 24))
        self.text_item.setDocument(self.doc)
        self.text_item.setTextWidth(self.fixed_width - (self.pad * 2))
        self.text_item.setHtml("<b>Note:</b><br>Type here...")
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)

        self.handle = CloudHandle(self)
        self.tail_handle = TailHandle(self)
        self.tail_handle.hide()

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )

        self.doc.contentsChanged.connect(self.sync_idea_notes_shape)
        self.sync_idea_notes_shape()

    def to_dict(self):
        """Turn one cloud into saveable plain data."""

        return {
            "x": self.x(),
            "y": self.y(),
            "fixed_width": self.fixed_width,
            "body_height": self.body_height,
            "html": self.doc.toHtml(),
            "tail_direction": self.tail_direction,
            "tail_control_ratio": [self.tail_control_ratio.x(), self.tail_control_ratio.y()],
        }

    @staticmethod
    def from_dict(data):
        """Build a cloud note from saved plain data."""

        note = CloudIdeaNote(data["x"], data["y"], data.get("fixed_width", 280))
        note.doc.setHtml(data.get("html", ""))
        note.text_item._is_placeholder = False
        note.tail_direction = data.get("tail_direction", "down")
        note.body_height = max(80, data.get("body_height", 100))

        ratio = data.get("tail_control_ratio")
        if isinstance(ratio, (list, tuple)) and len(ratio) == 2:
            note.tail_control_ratio = QPointF(float(ratio[0]), float(ratio[1]))
        else:
            note.tail_control_ratio = note._ratio_from_direction(note.tail_direction)

        note.sync_idea_notes_shape()
        return note

    def mousePressEvent(self, event):
        """A click inside the text area starts typing instead of moving."""

        if self._text_rect().contains(event.pos()):
            self.setSelected(True)
            self.begin_text_editing(event.pos() - self.text_item.pos())
            event.accept()
            return

        self.finish_text_editing()
        self.setFocus()
        self.setSelected(True)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        """A double click behaves like a text click for younger users."""

        self.mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """When a cloud stops moving, we save that move to undo history."""

        if self._start_pos_for_move is not None and self.pos() != self._start_pos_for_move:
            scene = self.scene()
            view = scene.views()[0] if scene and scene.views() else None
            if view and getattr(view, "undo_enabled", True):
                view.undo_stack.push(
                    MoveItemCommand(self, self._start_pos_for_move, self.pos())
                )

        self._start_pos_for_move = None
        super().mouseReleaseEvent(event)

    def focusOutEvent(self, event):
        """Stop editing when focus leaves the cloud."""

        if not self.text_item.hasFocus():
            self.finish_text_editing()
        super().focusOutEvent(event)

    def itemChange(self, change, value):
        """React when selection or movement state changes."""

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if self._start_pos_for_move is None:
                self._start_pos_for_move = self.pos()

        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            selected = bool(value)
            self.handle.setVisible(selected)
            self.tail_handle.setVisible(selected)
            if not selected:
                self.finish_text_editing()

        return super().itemChange(change, value)

    def _text_rect(self):
        """Map the child text box into the cloud's own coordinate space."""

        return self.text_item.mapRectToParent(self.text_item.boundingRect())

    def begin_text_editing(self, local_pos=None):
        """Turn on typing inside the cloud and place the cursor carefully."""

        self.setSelected(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
        self.text_item.setFocus(Qt.FocusReason.MouseFocusReason)

        if local_pos is not None:
            hit = self.doc.documentLayout().hitTest(local_pos, Qt.HitTestAccuracy.FuzzyHit)
            if hit >= 0:
                cursor = self.text_item.textCursor()
                cursor.setPosition(hit, QTextCursor.MoveMode.MoveAnchor)
                self.text_item.setTextCursor(cursor)

    def finish_text_editing(self):
        """Turn typing off and let the cloud move again."""

        self.text_item.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.text_item.clearFocus()
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    def rescale_cloud(self, handle_pos):
        """Resize the cloud while keeping safe minimum sizes."""

        if self._is_updating:
            return

        self.fixed_width = max(160, handle_pos.x())
        self.body_height = max(80, handle_pos.y())
        self.text_item.setTextWidth(self.fixed_width - (self.pad * 2))
        self.position_tail_handle(self.fixed_width, self.body_height)
        self.sync_idea_notes_shape()

    def add_tail(self, path, width, height):
        """Add the little bubble trail that points to an idea."""

        sizes = [18, 12, 8]
        center = QPointF(width * 0.5, height * 0.5)
        control = self._tail_control_point(width, height)
        dx = control.x() - center.x()
        dy = control.y() - center.y()

        if abs(dx) < 1 and abs(dy) < 1:
            dx, dy = 0, 1

        edge = self._tail_edge_point(center, dx, dy, width, height)
        length = max((dx * dx + dy * dy) ** 0.5, 1.0)
        unit_x = dx / length
        unit_y = dy / length

        for index, size in enumerate(sizes, start=1):
            px = edge.x() + (unit_x * (index * 16))
            py = edge.y() + (unit_y * (index * 16))
            path.addEllipse(px - (size / 2), py - (size / 2), size, size)

    def sync_idea_notes_shape(self):
        """Rebuild the cloud outline after text or handle changes."""

        if self._is_updating:
            return

        self._is_updating = True

        text_height = self.text_item.boundingRect().height()
        width = self.fixed_width
        height = max(self.body_height, text_height + (self.pad * 2))
        self.current_h = height
        self.body_height = height
        puff = self.puff

        path = QPainterPath()
        path.moveTo(puff, 0)
        path.cubicTo(width / 3, -puff, (width * 2) / 3, -puff, width - puff, 0)
        path.cubicTo(width + puff, height / 3, width + puff, (height * 2) / 3, width - puff, height)
        path.cubicTo((width * 2) / 3, height + puff, width / 3, height + puff, puff, height)
        path.cubicTo(-puff, (height * 2) / 3, -puff, height / 3, puff, 0)
        path.closeSubpath()

        self.add_tail(path, width, height)
        self.setPath(path)
        self.handle.setPos(width, height)
        self.position_tail_handle(width, height)
        self.prepareGeometryChange()
        self._is_updating = False

    def position_tail_handle(self, width, height):
        """Place the tail handle using saved percentage ratios."""

        point = QPointF(self.tail_control_ratio.x() * width, self.tail_control_ratio.y() * height)
        self.tail_handle.setPos(self._clamp_tail_point(point, width, height))

    def _clamp_tail_point(self, point, width=None, height=None):
        """Keep the tail handle safely on the cloud body."""

        width = self.fixed_width if width is None else width
        height = self.current_h if height is None else height
        margin = 24
        return QPointF(
            min(max(point.x(), margin), max(margin, width - margin)),
            min(max(point.y(), margin), max(margin, height - margin)),
        )

    def _tail_control_point(self, width, height):
        """Turn saved ratios into a real point inside the cloud."""

        point = QPointF(self.tail_control_ratio.x() * width, self.tail_control_ratio.y() * height)
        return self._clamp_tail_point(point, width, height)

    def _ratio_from_direction(self, direction):
        """Fallback tail positions for older saved files."""

        positions = {
            "down": QPointF(0.5, 0.82),
            "up": QPointF(0.5, 0.18),
            "left": QPointF(0.18, 0.5),
            "right": QPointF(0.82, 0.5),
            "downright": QPointF(0.75, 0.75),
            "downleft": QPointF(0.25, 0.75),
            "upright": QPointF(0.75, 0.25),
            "upleft": QPointF(0.25, 0.25),
        }
        return positions.get(direction, QPointF(0.5, 0.82))

    def _tail_edge_point(self, center, dx, dy, width, height):
        """Find the point where the tail should leave the cloud body."""

        scales = []
        if dx > 0:
            scales.append((width - center.x()) / dx)
        elif dx < 0:
            scales.append((0 - center.x()) / dx)

        if dy > 0:
            scales.append((height - center.y()) / dy)
        elif dy < 0:
            scales.append((0 - center.y()) / dy)

        scale = min(scale for scale in scales if scale > 0) if scales else 1.0
        return QPointF(center.x() + (dx * scale), center.y() + (dy * scale))

    def update_tail_control(self, handle_pos):
        """Move the tail handle and remember the matching direction."""

        clamped = self._clamp_tail_point(handle_pos)
        width = max(self.fixed_width, 1)
        height = max(self.current_h, 1)
        self.tail_control_ratio = QPointF(clamped.x() / width, clamped.y() / height)

        dx = clamped.x() - (width * 0.5)
        dy = clamped.y() - (height * 0.5)
        if abs(dx) > abs(dy) * 1.5:
            self.tail_direction = "right" if dx > 0 else "left"
        elif abs(dy) > abs(dx) * 1.5:
            self.tail_direction = "down" if dy > 0 else "up"
        else:
            if dx >= 0 and dy >= 0:
                self.tail_direction = "downright"
            elif dx < 0 <= dy:
                self.tail_direction = "downleft"
            elif dx >= 0 and dy < 0:
                self.tail_direction = "upright"
            else:
                self.tail_direction = "upleft"

        self.sync_idea_notes_shape()
        return clamped


class CloudHandle(QGraphicsRectItem):
    """The blue square used to resize a cloud."""

    def __init__(self, parent):
        super().__init__(-12, -12, 24, 24, parent)
        self.setBrush(QBrush(QColor(0, 122, 255)))
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        self.setZValue(9999)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.hide()
        self._start_width = None
        self._start_height = None

    def mousePressEvent(self, event):
        """Remember the old size before resizing starts."""

        parent = self.parentItem()
        if parent:
            parent.tail_handle.setSelected(False)
            parent.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            self._start_width = parent.fixed_width
            self._start_height = parent.body_height

        self.setSelected(True)
        self.setFocus()
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event):
        """Resize the cloud as the handle moves."""

        parent = self.parentItem()
        if parent:
            parent.rescale_cloud(self.pos())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Store the resize in undo history when the drag ends."""

        self.ungrabMouse()
        parent = self.parentItem()
        if parent:
            parent.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
            scene = parent.scene()
            view = scene.views()[0] if scene and scene.views() else None
            if view and getattr(view, "undo_enabled", True) and self._start_width is not None:
                if (
                    parent.fixed_width != self._start_width
                    or parent.body_height != self._start_height
                ):
                    view.undo_stack.push(
                        ResizeCloudCommand(
                            parent,
                            self._start_width,
                            self._start_height,
                            parent.fixed_width,
                            parent.body_height,
                        )
                    )

        self._start_width = None
        self._start_height = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Keep the resize handle glued to the lower-right corner."""

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            parent = self.parentItem()
            if parent:
                return QPointF(parent.fixed_width, parent.body_height)
        return super().itemChange(change, value)


class TailHandle(QGraphicsEllipseItem):
    """The orange handle used to move the cloud tail."""

    def __init__(self, parent_note):
        super().__init__(-8, -8, 16, 16, parent_note)
        self.note = parent_note
        self.setBrush(QBrush(QColor(255, 140, 0)))
        self.setPen(QPen(Qt.GlobalColor.white, 2))
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setZValue(9999)
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._start_ratio = None

    def mousePressEvent(self, event):
        """Remember the old tail position before dragging starts."""

        self.note.handle.setSelected(False)
        self.note.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        self._start_ratio = QPointF(
            self.note.tail_control_ratio.x(),
            self.note.tail_control_ratio.y(),
        )
        self.setSelected(True)
        self.setFocus()
        self.grabMouse()
        event.accept()

    def mouseMoveEvent(self, event):
        """Move the tail and clamp it inside the cloud body."""

        clamped = self.note.update_tail_control(self.pos())
        self.setPos(clamped)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Store the tail move in undo history when the drag ends."""

        self.ungrabMouse()
        self.note.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        scene = self.note.scene()
        view = scene.views()[0] if scene and scene.views() else None
        if view and getattr(view, "undo_enabled", True) and self._start_ratio is not None:
            new_ratio = QPointF(
                self.note.tail_control_ratio.x(),
                self.note.tail_control_ratio.y(),
            )
            if new_ratio != self._start_ratio:
                view.undo_stack.push(TailMoveCommand(self.note, self._start_ratio, new_ratio))

        self._start_ratio = None
        super().mouseReleaseEvent(event)

    def itemChange(self, change, value):
        """Let the cloud decide the best legal handle position."""

        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            if not self.note._is_updating:
                return self.note.update_tail_control(value)
        return super().itemChange(change, value)


class CloudTextItem(QGraphicsTextItem):
    """The text box that lives inside a cloud note."""

    def __init__(self, note):
        super().__init__(note)
        self.note = note
        self._is_placeholder = True

    def mousePressEvent(self, event):
        """Clicking inside the text area starts text editing."""

        self.note.begin_text_editing(event.pos())
        super().mousePressEvent(event)

    def focusInEvent(self, event):
        """Clear the starter text the first time the user edits the cloud."""

        if getattr(self, "_is_placeholder", False):
            self.setPlainText("")
            self._is_placeholder = False

        scene = self.scene()
        if scene and scene.views():
            view = scene.views()[0]
            if hasattr(view, "_currently_focused_text"):
                view._currently_focused_text = self
            if hasattr(view, "last_focused_text"):
                view.last_focused_text = self

        super().focusInEvent(event)

    def focusOutEvent(self, event):
        """Leaving focus ends text editing."""

        self.note.finish_text_editing()
        super().focusOutEvent(event)


class DrawingCanvas(QGraphicsScene):
    """The scene layer that handles pen tools, shapes, and the eraser."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.drawing = False
        self.start_pos = None
        self.temp_item = None
        self._eraser_edits = {}

    def _begin_eraser_stroke(self):
        """Start tracking one eraser drag so undo can restore it in one step."""

        self._eraser_edits = {}

    def _record_eraser_item(self, item):
        """Remember an item's original state before the eraser changes it."""

        if item in self._eraser_edits:
            return self._eraser_edits[item]

        if isinstance(item, QGraphicsPathItem):
            edit = {
                "kind": "path",
                "item": item,
                "old": QPainterPath(item.path()),
                "new": QPainterPath(item.path()),
            }
        else:
            edit = {
                "kind": "item",
                "item": item,
            }

        self._eraser_edits[item] = edit
        return edit

    def _point_in_eraser(self, point, center, radius):
        """Tell whether one point sits inside the eraser circle."""

        return math.hypot(point.x() - center.x(), point.y() - center.y()) <= radius

    def _point_on_segment(self, start, end, t_value):
        """Find one point partway along a line segment."""

        return QPointF(
            start.x() + ((end.x() - start.x()) * t_value),
            start.y() + ((end.y() - start.y()) * t_value),
        )

    def _segment_intersection_ts(self, start, end, center, radius):
        """Find where one straight line segment crosses the eraser circle."""

        dx = end.x() - start.x()
        dy = end.y() - start.y()
        fx = start.x() - center.x()
        fy = start.y() - center.y()

        a_value = (dx * dx) + (dy * dy)
        if a_value == 0:
            return []

        b_value = 2 * ((fx * dx) + (fy * dy))
        c_value = (fx * fx) + (fy * fy) - (radius * radius)
        discriminant = (b_value * b_value) - (4 * a_value * c_value)
        if discriminant < 0:
            return []

        root = math.sqrt(max(discriminant, 0.0))
        candidates = [
            (-b_value - root) / (2 * a_value),
            (-b_value + root) / (2 * a_value),
        ]

        valid = []
        for t_value in candidates:
            if 0.0 <= t_value <= 1.0:
                if not valid or abs(t_value - valid[-1]) > 1e-6:
                    valid.append(t_value)

        return sorted(valid)

    def _trim_line_segment(self, start, end, center, radius):
        """Keep only the visible parts of one line segment outside the eraser."""

        split_points = [0.0]
        split_points.extend(self._segment_intersection_ts(start, end, center, radius))
        split_points.append(1.0)
        split_points = sorted(split_points)

        kept_segments = []
        for first_t, second_t in zip(split_points, split_points[1:]):
            if second_t - first_t <= 1e-6:
                continue

            midpoint = self._point_on_segment(start, end, (first_t + second_t) * 0.5)
            if self._point_in_eraser(midpoint, center, radius):
                continue

            kept_segments.append(
                (
                    self._point_on_segment(start, end, first_t),
                    self._point_on_segment(start, end, second_t),
                )
            )

        return kept_segments

    def _trim_path_against_eraser(self, path, center, radius):
        """Cut away the parts of a stroke that pass through the eraser circle."""

        if path.elementCount() <= 1:
            return QPainterPath(), False

        new_path = QPainterPath()
        removed_any = False
        previous_point = None
        current_output_end = None

        for index in range(path.elementCount()):
            element = path.elementAt(index)
            point = QPointF(element.x, element.y)

            if index == 0 or element.type == QPainterPath.ElementType.MoveToElement:
                previous_point = point
                current_output_end = None
                continue

            kept_segments = self._trim_line_segment(previous_point, point, center, radius)
            original_kept = (
                len(kept_segments) == 1
                and math.hypot(kept_segments[0][0].x() - previous_point.x(), kept_segments[0][0].y() - previous_point.y()) <= 1e-6
                and math.hypot(kept_segments[0][1].x() - point.x(), kept_segments[0][1].y() - point.y()) <= 1e-6
            )
            if not original_kept:
                removed_any = True

            for segment_start, segment_end in kept_segments:
                if current_output_end is None or math.hypot(
                    current_output_end.x() - segment_start.x(),
                    current_output_end.y() - segment_start.y(),
                ) > 1e-6:
                    new_path.moveTo(segment_start)

                if math.hypot(
                    segment_end.x() - segment_start.x(),
                    segment_end.y() - segment_start.y(),
                ) > 1e-6:
                    new_path.lineTo(segment_end)

                current_output_end = segment_end

            if not kept_segments:
                current_output_end = None

            previous_point = point

        return new_path, removed_any

    def mousePressEvent(self, event):
        """Start a drawing action if the app is in drawing mode."""

        if self.parent.mode != "draw":
            item = self.itemAt(event.scenePos(), self.parent.transform())
            if not isinstance(item, (CloudIdeaNote, CloudHandle, TailHandle, CloudTextItem, QGraphicsTextItem)):
                for page in self.parent.pages:
                    if page["paper"].sceneBoundingRect().contains(event.scenePos()):
                        self.parent.switch_to_text_mode()
                        event.accept()
                        return
            return super().mousePressEvent(event)

        item = self.itemAt(event.scenePos(), self.parent.transform())
        if isinstance(item, (CloudIdeaNote, CloudHandle, TailHandle)):
            return super().mousePressEvent(event)

        self.drawing = True
        self.start_pos = event.scenePos()
        tool = self.parent.current_tool
        color = self.parent.draw_color
        size = self.parent.draw_size

        if tool == "draw":
            pen = QPen(
                color,
                size,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            self.temp_item = QGraphicsPathItem()
            self.temp_item.setData(0, "draw")
            self.temp_item.setPath(QPainterPath(self.start_pos))
            self.temp_item.setPen(pen)
            self.addItem(self.temp_item)

        elif tool == "highlighter":
            pen = QPen(
                QColor(255, 255, 0, 100),
                size * 4,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
            self.temp_item = QGraphicsPathItem()
            self.temp_item.setData(0, "highlighter")
            self.temp_item.setPath(QPainterPath(self.start_pos))
            self.temp_item.setPen(pen)
            self.addItem(self.temp_item)

        elif tool == "rect":
            self.temp_item = QGraphicsRectItem()
            self.temp_item.setData(0, "rect")
            self.temp_item.setPen(QPen(color, size))
            self.addItem(self.temp_item)

        elif tool == "ellipse":
            self.temp_item = QGraphicsEllipseItem()
            self.temp_item.setData(0, "ellipse")
            self.temp_item.setPen(QPen(color, size))
            self.addItem(self.temp_item)

        elif tool == "eraser":
            self._begin_eraser_stroke()
            self.erase_at(event.scenePos())

    def mouseMoveEvent(self, event):
        """Update the temporary drawing while the mouse moves."""

        if not self.drawing or self.parent.mode != "draw":
            return super().mouseMoveEvent(event)

        tool = self.parent.current_tool
        pos = event.scenePos()

        if tool in {"draw", "highlighter"} and self.temp_item is not None:
            path = self.temp_item.path()
            path.lineTo(pos)
            self.temp_item.setPath(path)

        elif tool in {"rect", "ellipse"} and self.temp_item is not None:
            self.temp_item.setRect(QRectF(self.start_pos, pos).normalized())

        elif tool == "eraser":
            self.erase_at(pos)

    def mouseReleaseEvent(self, event):
        """Finish a drawing and store it in undo history if it is real."""

        if self.drawing and self.temp_item is not None:
            keep_item = True

            if isinstance(self.temp_item, QGraphicsPathItem):
                keep_item = self.temp_item.path().elementCount() > 1
            elif isinstance(self.temp_item, (QGraphicsRectItem, QGraphicsEllipseItem)):
                keep_item = not self.temp_item.rect().isNull()

            if keep_item and self.parent.undo_enabled:
                self.parent.undo_stack.push(AddItemCommand(self, self.temp_item, "Draw"))
            elif not keep_item:
                self.removeItem(self.temp_item)

        if self.drawing and self.parent.current_tool == "eraser" and self._eraser_edits:
            edits = list(self._eraser_edits.values())
            self.parent.undo_stack.push(EraseStrokeCommand(self, edits))

        self.drawing = False
        self.start_pos = None
        self.temp_item = None
        self._eraser_edits = {}
        super().mouseReleaseEvent(event)

    def erase_at(self, pos):
        """Delete or trim drawings that touch the eraser circle."""

        radius = self.parent.draw_size * 2
        erase_rect = QRectF(pos.x() - radius, pos.y() - radius, radius * 2, radius * 2)

        for item in self.items(erase_rect):
            item_type = item.data(0)
            if item_type not in {"draw", "highlighter", "rect", "ellipse"}:
                continue
            if item.parentItem() is not None:
                continue

            if isinstance(item, QGraphicsPathItem):
                edit = self._record_eraser_item(item)
                path = item.path()
                new_path, removed_any = self._trim_path_against_eraser(path, pos, radius)

                if removed_any:
                    if new_path.elementCount() > 1:
                        item.setPath(new_path)
                        edit["new"] = QPainterPath(new_path)
                        self.parent.mark_dirty()
                    else:
                        self.removeItem(item)
                        edit["new"] = None
                        self.parent.mark_dirty()

            elif isinstance(item, (QGraphicsRectItem, QGraphicsEllipseItem)):
                if item.contains(item.mapFromScene(pos)):
                    self._record_eraser_item(item)
                    self.removeItem(item)
                    self.parent.mark_dirty()


class MainWindow(QMainWindow):
    """The main app window that brings every helper part together."""

    def __init__(self, demo_mode=False):
        super().__init__()

        try:
            from spellchecker import SpellChecker

            self.spell_checker = SpellChecker()
        except ImportError:
            self.spell_checker = None

        self.resize(1150, 950)
        self.current_opacity = 0.94
        self.is_ghost = False
        self.drag_position = None
        self.base_flags = (
            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowFlags(self.base_flags)
        self.setWindowOpacity(self.current_opacity)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.signals = GlobalSignals()
        self.signals.toggle_ghost.connect(self.handle_global_toggle)

        self.canvas = MaestroCanvas()
        self.file_manager = FileManager()
        self.current_file_path = None
        self.current_project_path = None
        self.find_dialog = None

        self.setCentralWidget(self.canvas)
        self.canvas.configure_spellchecker(self.spell_checker)
        self.canvas.set_state_change_callback(self.update_title)
        self.init_toolbar()
        self.setup_autosave()
        self.setup_shortcuts()
        self.update_title()

        try:
            self.start_keyboard_listener()
        except Exception:
            pass

        if demo_mode:
            self.canvas.load_demo_content()
            self.canvas.mark_clean()
            self.update_title()

    def set_current_file_path(self, path):
        """Keep both file-path names in sync while older code still uses one of them."""

        self.current_file_path = path
        self.current_project_path = path

    def update_title(self):
        """Show the current file name and a star when the file has unsaved work."""

        name = self.current_file_path or "Untitled"
        if self.canvas.is_dirty():
            name += " *"
        self.setWindowTitle(f"Maestro - {name}")

    def init_toolbar(self):
        """Build the side toolbars using the refactored toolbar helper."""

        self.toolbar_manager = ToolbarManager(self, self.canvas)
        self.toolbar_manager.build()
        self.toolbar = self.toolbar_manager.left_toolbar
        self.rightbar = self.toolbar_manager.right_toolbar

    def setup_autosave(self):
        """Start the background autosave helper."""

        self.autosave_manager = AutoSaveManager(
            self.canvas,
            self.file_manager,
            lambda: self.current_project_path,
            interval_ms=40000,
        )
        self.autosave_manager.start()

    def setup_shortcuts(self):
        """Connect keyboard shortcuts to classroom-friendly actions."""

        QShortcut(QKeySequence("Ctrl+C"), self, activated=self.canvas.copy_selection)
        QShortcut(QKeySequence("Ctrl+V"), self, activated=self.canvas.paste_selection)
        QShortcut(QKeySequence("Ctrl+X"), self, activated=self.canvas.cut_selection)
        QShortcut(QKeySequence("Ctrl+A"), self, activated=self.canvas.select_all)
        QShortcut(QKeySequence("Ctrl+B"), self, activated=self.toggle_bold)
        QShortcut(QKeySequence("Ctrl+I"), self, activated=self.toggle_italic)
        QShortcut(QKeySequence("Ctrl+Z"), self, activated=self.canvas.undo_stack.undo)
        QShortcut(QKeySequence("Ctrl+Shift+Z"), self, activated=self.canvas.undo_stack.redo)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self.save_project)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.load_project)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self.canvas.delete_selected)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, activated=self.canvas.delete_selected)
        QShortcut(QKeySequence("Escape"), self, activated=self.activate_text_mode)

    def add_page(self, *_):
        """Toolbar button: add one new page."""

        if self.canvas.undo_enabled:
            self.canvas.undo_stack.push(AddPageCommand(self.canvas))

    def delete_page(self, *_):
        """Toolbar button: delete the current page."""

        self.canvas.remove_selected_page()

    def activate_tool(self, tool, checked):
        """Turn a drawing tool on or off."""

        if checked:
            self.canvas.set_tool(tool)
        else:
            self.canvas.switch_to_text_mode()

    def activate_text_mode(self):
        """Leave drawing mode and go back to typing mode."""

        self.toolbar_manager.clear_tool_selection()
        self.canvas.switch_to_text_mode()

    def update_opacity(self, value):
        """Change how see-through the window looks."""

        self.current_opacity = value / 100.0
        if not self.is_ghost:
            self.setWindowOpacity(self.current_opacity)

    def mousePressEvent(self, event):
        """Allow dragging the window from the toolbar areas."""

        child = self.childAt(event.pos())
        if (
            child in {self.toolbar, self.rightbar}
            or (isinstance(child, QLabel) and (self.toolbar.isAncestorOf(child) or self.rightbar.isAncestorOf(child)))
        ) and event.button() == Qt.MouseButton.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        """Move the frameless window while dragging."""

        if event.buttons() == Qt.MouseButton.LeftButton and self.drag_position:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        """Stop dragging when the mouse button is released."""

        self.drag_position = None
        super().mouseReleaseEvent(event)

    def _reapply_flags(self):
        """Refresh window flags after ghost mode changes."""

        position = self.pos()
        if self.is_ghost:
            self.setWindowFlags(self.base_flags | Qt.WindowType.WindowTransparentForInput)
            self.setWindowOpacity(0.25)
        else:
            self.setWindowFlags(self.base_flags)
            self.setWindowOpacity(self.current_opacity)

        self.move(position)
        self.show()

    def _ask_project_save_path(self):
        """Open the Save dialog and return the chosen file path."""

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project",
            self.current_file_path or "",
            "Maestro Project (*.maestro)",
        )
        return path

    def _confirm_overwrite(self, chosen_path):
        """Ask before replacing a different existing project file."""

        normalized = self.file_manager.normalize_project_path(chosen_path)
        if not normalized:
            return False

        if normalized == self.current_file_path:
            return True

        import os

        if not os.path.exists(normalized):
            return True

        answer = QMessageBox.question(
            self,
            "Overwrite File",
            f"Replace the existing file?\n\n{normalized}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    def save_as(self):
        """Ask for a file name, warn about overwrite, then save there."""

        chosen_path = self._ask_project_save_path()
        if not chosen_path:
            return None

        if not self._confirm_overwrite(chosen_path):
            return None

        self.canvas.apply_markdown_to_all()
        saved_path = self.file_manager.save_project(self.canvas, chosen_path)
        self.set_current_file_path(saved_path)
        self.canvas.mark_clean()
        self.autosave_manager.mark_clean()
        self.autosave_manager.clear_autosave()
        self.update_title()
        self._reapply_flags()
        return saved_path

    def prompt_save_if_needed(self):
        """Ask whether to save unsaved work before risky actions."""

        if not self.canvas.is_dirty():
            return True

        autosave_path = None
        if self.current_file_path:
            autosave_path = self.autosave_manager.newer_autosave_path(self.current_file_path)

        msg = QMessageBox(self)
        msg.setWindowTitle("Unsaved Changes")
        msg.setText("You have unsaved changes.")
        if autosave_path:
            msg.setInformativeText(
                "Do you want to save before continuing?\n\nAn autosave backup exists, but the main file is still not saved."
            )
        else:
            msg.setInformativeText("Do you want to save before continuing?")
        msg.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        msg.setDefaultButton(QMessageBox.StandardButton.Save)

        choice = msg.exec()
        if choice == QMessageBox.StandardButton.Save:
            return self.save_project() is not None
        if choice == QMessageBox.StandardButton.Discard:
            return True
        return False

    def save_project(self, path=None):
        """Save the project and remember where it lives."""

        if path is not None:
            self.set_current_file_path(self.file_manager.normalize_project_path(path))
        if not self.current_file_path:
            return self.save_as()

        self.canvas.apply_markdown_to_all()
        saved_path = self.file_manager.save_project(self.canvas, self.current_file_path)
        self.set_current_file_path(saved_path)
        self.canvas.mark_clean()
        self.autosave_manager.mark_clean()
        self.autosave_manager.clear_autosave()
        self.update_title()
        self._reapply_flags()
        return saved_path

    def _recovery_choice(self, project_path):
        """Ask whether the user wants the newer autosave copy."""

        autosave_path = self.autosave_manager.newer_autosave_path(project_path)
        if autosave_path is None:
            return project_path

        answer = QMessageBox.question(
            self,
            "Recover Autosave",
            "A newer autosave was found. Do you want to open the autosave copy?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )

        if answer == QMessageBox.StandardButton.Yes:
            return autosave_path
        return project_path

    def load_project(self, path=None):
        """Open a saved Maestro project from disk."""

        if not self.prompt_save_if_needed():
            return None

        chosen_path = path
        if chosen_path is None:
            chosen_path, _ = QFileDialog.getOpenFileName(
                self,
                "Open Project",
                "",
                "Maestro Project (*.maestro)",
            )

        if not chosen_path:
            return None

        chosen_path = self._recovery_choice(chosen_path)
        loaded_path = self.file_manager.load_project(self.canvas, chosen_path)

        if loaded_path.endswith(".autosave.maestro"):
            self.set_current_file_path(loaded_path.replace(".autosave.maestro", ".maestro"))
        else:
            self.set_current_file_path(loaded_path)

        self.canvas.settle_clean_state_soon()
        self.canvas.mark_clean()
        self.autosave_manager.mark_clean()
        self.update_title()
        self._reapply_flags()
        return loaded_path

    def export_pdf(self, *_):
        """Save the notebook as a PDF file."""

        path, _ = QFileDialog.getSaveFileName(self, "Export PDF", "", "PDF Files (*.pdf)")
        if not path:
            return None

        self.canvas.apply_markdown_to_all()
        pdf_path = self.file_manager.export_pdf(self.canvas, path)
        QMessageBox.information(self, "Maestro Success", "Note exported as PDF!")
        return pdf_path

    def set_font_family(self, font):
        """Change the font family of the current text selection."""

        focus_item = self.canvas.ensure_text_item_for_formatting()
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        # We build a full font from the cursor's current font first, then swap
        # only the family name. This keeps the same size and style while
        # finally making the new typeface actually stick.
        new_font = self.canvas.effective_text_font(focus_item)
        new_font.setFamily(font.family())
        if font.styleName():
            new_font.setStyleName(font.styleName())

        self.canvas._apply_char_format(
            focus_item,
            lambda fmt: (fmt.setFontFamily(font.family()), fmt.setFont(new_font)),
        )
        self.canvas.restore_text_focus_soon(focus_item)

    def toggle_underline(self, checked=False):
        """Turn underline on or off."""

        focus_item = self.canvas.focused_text_item()
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        cursor = focus_item.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontUnderline(checked if isinstance(checked, bool) else not fmt.fontUnderline())
        cursor.mergeCharFormat(fmt)
        focus_item.setTextCursor(cursor)

    def toggle_bold(self):
        """Toggle bold text for the current text selection."""

        focus_item = self.canvas.focused_text_item()
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        cursor = focus_item.textCursor()
        fmt = cursor.charFormat()
        is_bold = fmt.fontWeight() == QFont.Weight.Bold
        fmt.setFontWeight(QFont.Weight.Normal if is_bold else QFont.Weight.Bold)
        cursor.mergeCharFormat(fmt)
        focus_item.setTextCursor(cursor)

    def toggle_italic(self):
        """Toggle italic text for the current text selection."""

        focus_item = self.canvas.focused_text_item()
        if not isinstance(focus_item, QGraphicsTextItem):
            return

        cursor = focus_item.textCursor()
        fmt = cursor.charFormat()
        fmt.setFontItalic(not fmt.fontItalic())
        cursor.mergeCharFormat(fmt)
        focus_item.setTextCursor(cursor)

    def find_text(self):
        """Show a stay-open find and replace window."""

        if self.find_dialog is None:
            self.find_dialog = FindReplaceDialog(self)

        current_phrase = ""
        active_item = self.canvas.active_text_item()
        if active_item is not None and active_item.textCursor().hasSelection():
            current_phrase = active_item.textCursor().selectedText()

        self.find_dialog.show_for_phrase(current_phrase)

    def correct_spelling(self):
        """Offer spelling suggestions for the selected word."""

        if self.spell_checker is None:
            QMessageBox.warning(
                self,
                "Spell Checker Missing",
                "Install `pyspellchecker` if you want spelling help.",
            )
            return

        text_item = self.canvas.active_text_item()
        if text_item is None:
            return

        cursor = text_item.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.SelectionType.WordUnderCursor)

        word = cursor.selectedText().strip()
        if not word:
            return

        clean_word = re.sub(r"[^A-Za-z'\-]", "", word)
        if not clean_word:
            return

        try:
            if not self.spell_checker.unknown([clean_word]):
                QMessageBox.information(self, "Spell Check", f"'{clean_word}' already looks correct.")
                return

            suggestions = list(self.spell_checker.candidates(clean_word) or [])[:5]
        except Exception as exc:
            QMessageBox.warning(self, "Spell Check", f"Spell check could not finish: {exc}")
            return

        if not suggestions:
            QMessageBox.information(self, "Spell Check", f"No suggestions found for '{clean_word}'.")
            return

        chosen, accepted = QInputDialog.getItem(
            self,
            "Maestro Spellcheck",
            f"Change '{clean_word}' to:",
            suggestions,
            0,
            False,
        )
        if accepted and chosen:
            cursor.insertText(chosen)
            text_item.setTextCursor(cursor)

    def show_ghost_help(self):
        """Show a help window that explains the app's main tools."""

        if self.toolbar_manager.ghost_action is not None:
            self.toolbar_manager.ghost_action.setText("👻\nON | OFF\nTAB+G")
            QTimer.singleShot(
                4000,
                lambda: self.toolbar_manager.ghost_action.setText(" 👻 INFO "),
            )

        dialog = QDialog(self)
        dialog.setWindowTitle("Maestro Notepad Help Guide")
        dialog.setFixedSize(500, 450)
        dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        dialog.setStyleSheet(
            "background-color: white; border: 2px solid #444; border-radius: 12px;"
        )

        layout = QVBoxLayout()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("border: none; background-color: white;")

        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)

        help_content = [
            "<b>👻 Ghost Mode:</b> Press TAB + G to let clicks pass through the window while notes stay on top.",
            "<b>🎚️ Glass Slider:</b> This changes how see-through the window is.",
            "<b>☁️ Note:</b> Adds a movable thought cloud for little reminders.",
            "<b>🗒️ Page:</b> Adds another page to the notebook.",
            "<b>🔤 Text:</b> Sends focus back to the page text box.",
            "<b>✏️ Draw:</b> Lets you sketch over the paper.",
            "<b>💾 Save:</b> Stores pages, text, clouds, and drawings in a `.maestro` file.",
            "<b>🕹️ Move Me:</b> Drag the app by empty toolbar space.",
            "<b>Shortcuts:</b> Use copy, paste, cut, bold, italic, undo, and redo with the keyboard.",
        ]

        for line in help_content:
            label = QLabel(line)
            label.setStyleSheet("color: black; font-size: 13px; padding: 5px;")
            label.setWordWrap(True)
            content_layout.addWidget(label)

        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        ok_button = QPushButton("BACK TO WORK")
        ok_button.setStyleSheet(
            """
            QPushButton {
                background-color: #2b2b2b;
                color: white;
                padding: 10px;
                border-radius: 6px;
                font-weight: bold;
                margin-top: 10px;
            }
            QPushButton:hover { background-color: #444; }
            """
        )
        ok_button.clicked.connect(dialog.accept)
        layout.addWidget(ok_button)

        dialog.setLayout(layout)
        dialog.exec()

    def start_keyboard_listener(self):
        """Listen for TAB + G even when the user is outside the app."""

        from pynput import keyboard

        self.tab_held = False

        def on_press(key):
            try:
                if key == keyboard.Key.tab:
                    self.tab_held = True
                if self.tab_held and hasattr(key, "char") and key.char and key.char.lower() == "g":
                    self.signals.toggle_ghost.emit()
            except Exception:
                pass

        def on_release(key):
            if key == keyboard.Key.tab:
                self.tab_held = False

        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.daemon = True
        listener.start()

    def handle_global_toggle(self):
        """Flip ghost mode on or off."""

        self.is_ghost = not self.is_ghost
        self._reapply_flags()
        if self.toolbar_manager.ghost_action is not None:
            self.toolbar_manager.ghost_action.setText("👻 ACTIVE" if self.is_ghost else " 👻 INFO ")

    def print_document(self):
        """Send every notebook page to a printer."""

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() != QPrintDialog.DialogCode.Accepted:
            return

        self.canvas.apply_markdown_to_all()
        painter = QPainter(printer)
        rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        scale = rect.width() / self.canvas.p_w
        painter.scale(scale, scale)

        for page_index in range(len(self.canvas.pages)):
            if page_index > 0:
                printer.newPage()

            y_pos = page_index * (self.canvas.p_h + self.canvas.gap)
            source_rect = QRectF(0, y_pos, self.canvas.p_w, self.canvas.p_h)
            target_rect = QRectF(0, 0, self.canvas.p_w, self.canvas.p_h)
            painter.setClipRect(target_rect)
            self.canvas.scene.render(painter, target_rect, source_rect)

        painter.end()

    def closeEvent(self, event):
        """Stop background timers cleanly when the app closes."""

        if not self.prompt_save_if_needed():
            event.ignore()
            return

        self.autosave_manager.stop()
        super().closeEvent(event)


def build_demo_project_data():
    """Create a ready-to-show sample project."""

    return {
        "page_width": PAGE_WIDTH,
        "page_height": PAGE_HEIGHT,
        "gap": PAGE_GAP,
        "pages": [
            {
                "text_html": """
                    <h1 style="font-size:30pt; color:#1f4e79;">Maestro Demo Page</h1>
                    <p style="font-size:18pt;">This page shows typing, highlighting, and a cloud note.</p>
                    <p style="font-size:18pt;"><b>Goal:</b> Teach how one page can hold writing and drawing at the same time.</p>
                """,
                "notes": [
                    {
                        "x": 510,
                        "y": 260,
                        "fixed_width": 260,
                        "body_height": 130,
                        "html": "<b>Teacher Tip:</b><br>Drag me around and resize me with the blue handle.",
                        "tail_direction": "downleft",
                        "tail_control_ratio": [0.25, 0.72],
                    }
                ],
                "drawings": [
                    {
                        "type": "highlighter",
                        "path": [[78, 178], [220, 178], [360, 178], [470, 178]],
                        "color": "#64ffff00",
                        "width": 28.0,
                    },
                    {
                        "type": "rect",
                        "rect": [62, 58, 690, 150],
                        "color": "#ff1f4e79",
                        "width": 4.0,
                    },
                ],
            },
            {
                "text_html": """
                    <h2 style="font-size:24pt; color:#7a2e00;">Second Demo Page</h2>
                    <p style="font-size:18pt;">Try these steps:</p>
                    <ol>
                        <li>Type in the big page area.</li>
                        <li>Click DRAW and sketch.</li>
                        <li>Add a NOTE cloud and edit its text.</li>
                        <li>Save the file as a .maestro project.</li>
                    </ol>
                """,
                "notes": [
                    {
                        "x": 120,
                        "y": 1330,
                        "fixed_width": 300,
                        "body_height": 120,
                        "html": "<b>Remember:</b><br>Press Escape to jump back to typing mode.",
                        "tail_direction": "upright",
                        "tail_control_ratio": [0.72, 0.26],
                    }
                ],
                "drawings": [
                    {
                        "type": "ellipse",
                        "rect": [430, 1260, 220, 120],
                        "color": "#ffcc5500",
                        "width": 6.0,
                    },
                    {
                        "type": "draw",
                        "path": [[460, 1450], [520, 1490], [580, 1450], [640, 1490]],
                        "color": "#ffd7263d",
                        "width": 8.0,
                    },
                ],
            },
        ],
    }


def main(argv=None):
    """Start the Qt application.

    Passing `--demo` opens the app with sample content already loaded.
    """

    argv = list(sys.argv if argv is None else argv)
    demo_mode = "--demo" in argv
    qt_args = [arg for arg in argv if arg != "--demo"]

    app = QApplication(qt_args)
    window = MainWindow(demo_mode=demo_mode)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
