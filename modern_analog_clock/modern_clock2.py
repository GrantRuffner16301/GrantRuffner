''' 
A simple clock made for the MacBook Air M4
It features a clean round edge design, 
includes a right click menu with options to 
add and remove tick marks, change color themes, 
and make is translutant. This gives it a modern 
feel for the MacBook
Version 2: for MacBook Air M4
Made By: Grant Ruffner
Email: ruffnergrant@gmail.com
'''

import sys
from PyQt6.QtWidgets import QApplication, QWidget, QMenu
from PyQt6.QtCore import QTimer, Qt, QPoint, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont
from math import sin, cos, pi
from datetime import datetime

class ModernClock(QWidget):
    def __init__(self):
        super().__init__()
        
        # ---== Main setting for clock ==---
        self.bg_color = QColor("#2c3e50")    
        self.accent_color = QColor("#3498db") 
        self.show_ticks = True  
        self.opacity = 1.0 
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(300, 300)
        self.oldPos = self.pos()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(1000)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        painter.setOpacity(self.opacity) 

        # ---== Draw the main face ==---
        painter.setPen(QPen(self.accent_color, 4))
        painter.setBrush(self.bg_color)
        painter.drawEllipse(10, 10, 280, 280)

        # ---== Put the tick marks around the edge of the clock ==---
        if self.show_ticks:
            for i in range(60):
                angle = (i * 6) - 90
                rad = angle * pi / 180
                if i % 5 == 0:
                    inner_dist, outer_dist = 130, 140
                    painter.setPen(QPen(self.accent_color, 3))
                else:
                    inner_dist, outer_dist = 135, 140
                    painter.setPen(QPen(QColor("#95a5a6"), 1))
                
                x1, y1 = 150 + inner_dist * cos(rad), 150 + inner_dist * sin(rad)
                x2, y2 = 150 + outer_dist * cos(rad), 150 + outer_dist * sin(rad)
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))

        text_color = QColor("white") if self.bg_color.lightness() < 130 else QColor("black")
        painter.setPen(text_color)
        painter.setFont(QFont("Helvetica", 22, QFont.Weight.Bold))
        for i in range(1, 13):
            angle = (i * 30) - 90
            rad = angle * pi / 180
            x, y = 150 + 100 * cos(rad), 150 + 100 * sin(rad)
            painter.drawText(QRect(int(x-20), int(y-20), 40, 40), Qt.AlignmentFlag.AlignCenter, str(i))
        painter.setPen(QColor("#bdc3c7"))
        # ---== Makers mark just above pin ==---
        painter.setFont(QFont("Helvetica", 14, QFont.Weight.Bold, italic=True))
        painter.drawText(0, 125, 300, 30, Qt.AlignmentFlag.AlignCenter, "Grant Ruffner")

        # ---== Clock hands ==---
        now = datetime.now()
        h, m, s = now.hour % 12, now.minute, now.second
        hand_main = QColor("#ecf0f1") if self.bg_color.lightness() < 130 else QColor("#2c3e50")
        
        self.draw_hand(painter, (h * 30 + m * 0.5) - 90, 60, 6, hand_main)
        self.draw_hand(painter, (m * 6) - 90, 90, 4, QColor("#bdc3c7"))
        self.draw_hand(painter, (s * 6) - 90, 110, 2, QColor("#e74c3c"))

        # ---== Center pin ==---
        painter.setBrush(QColor("#e74c3c"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(145, 145, 10, 10)

    def draw_hand(self, painter, angle, length, width, color):
        rad = angle * pi / 180
        painter.setPen(QPen(color, width, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(150, 150, int(150 + length * cos(rad)), int(150 + length * sin(rad)))

        # ---== Right click menu ==---
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1a1a1a; color: white; border: 1px solid #555; } QMenu::item:selected { background-color: #34495e; }")

        tick_action = menu.addAction("Minute Marks On/Off")
        tick_action.triggered.connect(self.toggle_ticks)

        opac_menu = menu.addMenu("Set Transparency")
        for val in [100, 80, 60, 40, 20]:
            action = opac_menu.addAction(f"{val}% Opacity")
            action.triggered.connect(lambda checked, v=val: self.set_opacity(v))

        theme_menu = menu.addMenu("Change Theme")
        themes = {
            "Midnight Blue": ("#2c3e50", "#3498db"),
            "Forest Green": ("#1b2e1b", "#27ae60"),
            "Stealth Gray": ("#2f3640", "#7f8c8d"),
            "Mahogany Wood": ("#3e2723", "#d4af37"),
            "Standard B&W": ("#ffffff", "#000000"),
            "Tuxedo (Dark)": ("#000000", "#ffffff"),
        }
        for name, colors in themes.items():
            t_action = theme_menu.addAction(name)
            t_action.triggered.connect(lambda checked, c=colors: self.set_theme(c))

        menu.addSeparator()
        quit_action = menu.addAction("Quit Clock")
        
        action = menu.exec(self.mapToGlobal(event.pos()))
        if action == quit_action:
            self.close()

    def toggle_ticks(self):
        self.show_ticks = not self.show_ticks
        self.update()

    def set_opacity(self, value):
        self.opacity = value / 100.0
        self.update()

    def set_theme(self, colors):
        self.bg_color = QColor(colors[0])
        self.accent_color = QColor(colors[1])
        self.update()
    # ---== Mouse drag ==---    
    def mousePressEvent(self, event):
        self.oldPos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        delta = QPoint(event.globalPosition().toPoint() - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = event.globalPosition().toPoint()

# ---== Run the Clock ==---
if __name__ == '__main__':
    app = QApplication(sys.argv)
    clock = ModernClock()
    clock.show()
    sys.exit(app.exec())

# Never stop learning, knowledge is for everyone willing to seek it out.
