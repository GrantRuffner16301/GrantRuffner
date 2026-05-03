"""Helper tools for building and saving the Maestro canvas.

These helpers keep the main window file smaller and easier to teach from.
"""

from __future__ import annotations

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QBrush, QFont, QImage, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsRectItem,
    QGraphicsTextItem,
)


PAGE_WIDTH = 816
PAGE_HEIGHT = 1056
PAGE_GAP = 50
TEXT_MARGIN = 60


def build_page_bundle(scene, y_pos, font_size, html=""):
    """Create one paper page and its text box.

    We return both objects together because they always travel as a pair.
    """

    paper = QGraphicsRectItem(0, y_pos, PAGE_WIDTH, PAGE_HEIGHT)
    paper.setBrush(QBrush(QColor(255, 255, 255)))
    paper.setZValue(-20)
    scene.addItem(paper)

    text_item = QGraphicsTextItem()
    text_item.setPos(TEXT_MARGIN, y_pos + TEXT_MARGIN)
    text_item.setTextWidth(PAGE_WIDTH - (TEXT_MARGIN * 2))
    text_item.setFlags(
        QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
        | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
    )
    text_item.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)
    text_item.setZValue(-10)
    text_item.document().setDefaultFont(QFont("Arial", int(font_size)))

    if html:
        text_item.setHtml(html)
        text_item._is_placeholder = False
    else:
        text_item.setHtml("<p style='font-size:24pt;'>Maestro Notepad Click Here and Start Typing</p>")
        text_item._is_placeholder = True

    text_item.setDefaultTextColor(QColor(0, 0, 0))
    scene.addItem(text_item)

    return {"paper": paper, "text": text_item, "drawings": []}


def page_scene_rect(page_count):
    """Tell Qt how tall the scrolling area should be for all pages."""

    return QRectF(
        -50,
        -50,
        PAGE_WIDTH + 100,
        (page_count * (PAGE_HEIGHT + PAGE_GAP)) + 100,
    )


def render_page_to_image(scene, y_pos):
    """Turn one page of the scene into an image we can save or print."""

    source_rect = QRectF(0, y_pos, PAGE_WIDTH, PAGE_HEIGHT)
    image = QImage(QSize(PAGE_WIDTH, PAGE_HEIGHT), QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)

    painter = QPainter(image)
    scene.render(painter, QRectF(0, 0, PAGE_WIDTH, PAGE_HEIGHT), source_rect)
    painter.end()
    return image


def serialize_draw_item(item):
    """Convert a drawing item into plain data that JSON can store."""

    item_type = item.data(0)
    if item_type in {"draw", "highlighter"}:
        path = item.path()
        points = []
        for index in range(path.elementCount()):
            element = path.elementAt(index)
            points.append([element.x, element.y, int(element.type.value)])

        return {
            "type": item_type,
            "path": points,
            "color": item.pen().color().name(QColor.NameFormat.HexArgb),
            "width": item.pen().widthF(),
        }

    if item_type in {"rect", "ellipse"}:
        rect = item.rect()
        return {
            "type": item_type,
            "rect": [rect.x(), rect.y(), rect.width(), rect.height()],
            "color": item.pen().color().name(QColor.NameFormat.HexArgb),
            "width": item.pen().widthF(),
        }

    return None


def deserialize_draw_item(draw_data):
    """Build a real Qt drawing object from saved JSON data."""

    item_type = draw_data.get("type")
    color = QColor(draw_data.get("color", "#ffff3232"))
    width = float(draw_data.get("width", 2.0))

    if item_type in {"draw", "highlighter"}:
        points = draw_data.get("path", [])
        if len(points) < 2:
            return None

        path = QPainterPath()
        for point in points:
            x_pos, y_pos = point[0], point[1]
            point_type = point[2] if len(point) >= 3 else int(QPainterPath.ElementType.LineToElement.value)
            if point_type == int(QPainterPath.ElementType.MoveToElement.value) or path.elementCount() == 0:
                path.moveTo(x_pos, y_pos)
            else:
                path.lineTo(x_pos, y_pos)

        item = QGraphicsPathItem(path)
        item.setPen(
            QPen(
                color,
                width,
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin,
            )
        )
        item.setData(0, item_type)
        return item

    if item_type == "rect":
        x_pos, y_pos, rect_width, rect_height = draw_data.get("rect", [0, 0, 0, 0])
        item = QGraphicsRectItem(x_pos, y_pos, rect_width, rect_height)
        item.setPen(QPen(color, width))
        item.setData(0, "rect")
        return item

    if item_type == "ellipse":
        x_pos, y_pos, rect_width, rect_height = draw_data.get("rect", [0, 0, 0, 0])
        item = QGraphicsEllipseItem(x_pos, y_pos, rect_width, rect_height)
        item.setPen(QPen(color, width))
        item.setData(0, "ellipse")
        return item

    return None
