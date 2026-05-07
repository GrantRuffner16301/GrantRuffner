"""File helpers for saving, loading, exporting, and autosave paths."""

from __future__ import annotations

import json
import zipfile

from PyQt6.QtCore import QBuffer, QByteArray, QIODevice, QRectF
from PyQt6.QtGui import QPageSize, QPainter
from PyQt6.QtPrintSupport import QPrinter


class FileManager:
    """Handle the jobs that talk to files on disk.

    Keeping these jobs here lets the window focus on buttons and user actions.
    """

    project_suffix = ".maestro"

    def normalize_project_path(self, path):
        """Make sure project files always end with `.maestro`."""

        clean_path = str(path)
        if not clean_path.endswith(self.project_suffix):
            clean_path += self.project_suffix
        return clean_path

    def autosave_path_for(self, project_path):
        """Create a matching autosave file name for one project."""

        project_file = self.normalize_project_path(project_path)
        if project_file.endswith(".maestro"):
            return project_file[: -len(".maestro")] + ".autosave.maestro"
        return project_file + ".autosave.maestro"

    def save_project(self, canvas, path):
        """Save the canvas data and preview pictures into one zip file."""

        clean_path = self.normalize_project_path(path)
        data = canvas.serialize()
        json_bytes = json.dumps(data, indent=2).encode("utf-8")

        with zipfile.ZipFile(clean_path, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("project.json", json_bytes)

            for page_index in range(len(canvas.pages)):
                image = canvas.render_page_image(page_index)
                if image is None:
                    continue

                # We save page previews in memory so we do not leave temp files behind.
                png_bytes = QByteArray()
                buffer = QBuffer(png_bytes)
                buffer.open(QIODevice.OpenModeFlag.WriteOnly)
                if image.save(buffer, "PNG"):
                    archive.writestr(f"page_{page_index + 1}.png", bytes(png_bytes))
                buffer.close()

        return clean_path

    def load_project(self, canvas, path):
        """Read a saved project file and hand the data back to the canvas."""

        clean_path = self.normalize_project_path(path)
        with zipfile.ZipFile(clean_path, "r") as archive:
            with archive.open("project.json") as project_file:
                data = json.loads(project_file.read().decode("utf-8"))

        canvas.deserialize(data)
        return clean_path

    def export_pdf(self, canvas, path):
        """Print every page into one PDF file."""

        clean_path = str(path)
        if not clean_path.lower().endswith(".pdf"):
            clean_path += ".pdf"

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(clean_path)
        printer.setPageSize(QPageSize(QPageSize.PageSizeId.A4))

        painter = QPainter(printer)
        page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
        scale = page_rect.width() / canvas.p_w
        painter.scale(scale, scale)

        for page_index, page_data in enumerate(canvas.pages):
            if page_index > 0:
                printer.newPage()

            # The paper rectangle itself always starts at 0, 0 inside the item,
            # so we must use the item's scene position to find the real page.
            y_pos = page_data["paper"].sceneBoundingRect().top()
            source_rect = QRectF(0, y_pos, canvas.p_w, canvas.p_h)
            target_rect = QRectF(0, 0, canvas.p_w, canvas.p_h)
            painter.setClipRect(target_rect)
            canvas.scene.render(painter, target_rect, source_rect)

        painter.end()
        return clean_path
