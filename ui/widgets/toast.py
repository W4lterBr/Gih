# -*- coding: utf-8 -*-
"""Notificação toast não intrusiva."""

from __future__ import annotations

from typing import Any, Optional, cast

from PyQt6.QtCore import QEasingCurve, QPoint, QPropertyAnimation, QTimer, Qt
from PyQt6.QtWidgets import QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QWidget


# -----------------------------
# Utils de UI: Toast
# -----------------------------
class Toast(QFrame):
    """Pequena notificação flutuante no canto inferior direito."""
    def __init__(self, parent: Optional[QWidget], text: str, duration_ms: int = 2200) -> None:
        super().__init__(parent)
        self.setObjectName("Toast")
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.ToolTip)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        lay = QHBoxLayout(self)
        lbl = QLabel(text)
        lay.addWidget(lbl)
        lay.setContentsMargins(14, 10, 14, 10)
        self.setStyleSheet("""
        #Toast { background: rgba(20,24,36,0.95); color: #fff; border-radius: 10px; border:1px solid #2a3350; }
        #Toast QLabel { color: #ffffff; }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(18)
        shadow.setOffset(0, 6)
        self.setGraphicsEffect(shadow)
        self._duration = duration_ms
        self._anim = QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(280)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def show_near_bottom_right(self) -> None:
        parent = self.parentWidget()
        if not parent:
            self.show()
            return
        geom = parent.frameGeometry()
        self.adjustSize()
        x = geom.width() - self.width() - 24
        y = geom.height() - self.height() - 24
        start = QPoint(x, y + 24)
        end = QPoint(x, y)
        self.move(start)
        self.show()
        self.raise_()
        self._anim.stop()
        self._anim.setStartValue(start)
        self._anim.setEndValue(end)
        self._anim.start()
        cast(Any, QTimer).singleShot(cast(Any, self._duration), cast(Any, self.close))
