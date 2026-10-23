"""A small, non-activating progress pill for an in-flight rewrite.

The rewrite itself runs off the Qt thread, so the window is free. Without a
visible surface the app looks dead for as long as the model takes. This pill
appears the moment an action is chosen, counts elapsed time so the user can
tell a slow model from a hang, and offers one way out.
"""

from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

from rework.theme import Palette, current_palette

PILL_WIDTH = 300
SCREEN_MARGIN = 12


class _Spinner(QtWidgets.QWidget):
    def __init__(self, palette: Palette, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self._palette = palette
        self._angle = 0
        self.setFixedSize(18, 18)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(70)
        self._timer.timeout.connect(self._advance)
        self._timer.start()

    def _advance(self) -> None:
        self._angle = (self._angle + 30) % 360
        self.update()

    def stop(self) -> None:
        self._timer.stop()

    def paintEvent(self, event) -> None:  # noqa: N802 (Qt signature)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        rect = QtCore.QRectF(2.0, 2.0, 14.0, 14.0)

        track = QtGui.QPen(QtGui.QColor(self._palette.hairline))
        track.setWidthF(2.0)
        painter.setPen(track)
        painter.drawEllipse(rect)

        arc = QtGui.QPen(QtGui.QColor(self._palette.accent))
        arc.setWidthF(2.0)
        arc.setCapStyle(QtCore.Qt.PenCapStyle.RoundCap)
        painter.setPen(arc)
        painter.drawArc(rect, -self._angle * 16, 100 * 16)
        painter.end()


class WorkingPill(QtWidgets.QWidget):
    """Elapsed-time progress for one rewrite. Never takes focus."""

    cancelled = QtCore.Signal()

    def __init__(
        self,
        option: str,
        palette: Palette | None = None,
        parent: QtWidgets.QWidget | None = None,
    ):
        super().__init__(parent)
        self._palette = palette or current_palette()
        self._option = option
        self._stage = "Reading selection"
        self._started = QtCore.QElapsedTimer()
        self._started.start()

        self.setWindowFlags(
            QtCore.Qt.WindowType.Tool
            | QtCore.Qt.WindowType.FramelessWindowHint
            | QtCore.Qt.WindowType.WindowStaysOnTopHint
            | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setWindowTitle(f"{option} in progress")
        self.setAccessibleName(f"Writing Tools is working on {option}")
        self.setFixedWidth(PILL_WIDTH + 24)
        self.setStyleSheet(self._stylesheet())

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        self.card = QtWidgets.QFrame()
        self.card.setObjectName("pill")
        root.addWidget(self.card)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 5)
        shadow.setColor(
            QtGui.QColor(0, 0, 0, 50 if self._palette.mode == "light" else 120)
        )
        self.card.setGraphicsEffect(shadow)

        row = QtWidgets.QHBoxLayout(self.card)
        row.setContentsMargins(14, 10, 10, 10)
        row.setSpacing(10)

        self._spinner = _Spinner(self._palette)
        row.addWidget(self._spinner, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        text_column = QtWidgets.QVBoxLayout()
        text_column.setSpacing(1)
        self.title_label = QtWidgets.QLabel(self._headline())
        self.title_label.setObjectName("pillTitle")
        text_column.addWidget(self.title_label)

        self.stage_label = QtWidgets.QLabel(f"{self._stage} \u00b7 0.0s")
        self.stage_label.setObjectName("pillStage")
        text_column.addWidget(self.stage_label)
        row.addLayout(text_column, 1)

        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.cancel_button.setObjectName("pillCancel")
        self.cancel_button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        self.cancel_button.setAccessibleName("Cancel this rewrite")
        self.cancel_button.clicked.connect(self._on_cancel)
        row.addWidget(self.cancel_button, 0, QtCore.Qt.AlignmentFlag.AlignVCenter)

        self._tick_timer = QtCore.QTimer(self)
        self._tick_timer.setInterval(100)
        self._tick_timer.timeout.connect(self._tick)
        self._tick_timer.start()

        self.adjustSize()

    def _headline(self) -> str:
        if self._option == "Custom":
            return "Applying your change\u2026"
        return f"{self._option}\u2026"

    def _stylesheet(self) -> str:
        p = self._palette
        return f"""
            QFrame#pill {{
                background: {p.surface};
                border: 1px solid {p.hairline};
                border-radius: 12px;
            }}
            QLabel#pillTitle {{
                color: {p.ink};
                font-size: 13px;
                font-weight: 600;
            }}
            QLabel#pillStage {{
                color: {p.muted};
                font-size: 12px;
            }}
            QPushButton#pillCancel {{
                color: {p.muted};
                background: transparent;
                border: 1px solid transparent;
                border-radius: 6px;
                padding: 4px 8px;
                font-size: 12px;
            }}
            QPushButton#pillCancel:hover {{
                color: {p.ink};
                background: {p.surface_alt};
            }}
            QPushButton#pillCancel:pressed {{
                color: {p.accent};
            }}
            QPushButton#pillCancel:focus {{
                border: 1px solid {p.accent};
            }}
        """

    def set_stage(self, stage: str) -> None:
        self._stage = stage
        self._tick()

    def _tick(self) -> None:
        seconds = self._started.elapsed() / 1000.0
        self.stage_label.setText(f"{self._stage} \u00b7 {seconds:.1f}s")
        self.setAccessibleName(
            f"Writing Tools is working on {self._option}, {self._stage}, {seconds:.0f} seconds"
        )

    def _on_cancel(self) -> None:
        self._tick_timer.stop()
        self._spinner.stop()
        self.cancelled.emit()
        self.close()

    def show_near(self, position: QtCore.QPoint) -> None:
        self.adjustSize()
        screen = QtGui.QGuiApplication.screenAt(position) or QtGui.QGuiApplication.primaryScreen()
        x = position.x() + 18
        y = position.y() + 18
        if screen is not None:
            available = screen.availableGeometry()
            x = max(available.left() + SCREEN_MARGIN,
                    min(x, available.right() - self.width() - SCREEN_MARGIN))
            y = max(available.top() + SCREEN_MARGIN,
                    min(y, available.bottom() - self.height() - SCREEN_MARGIN))
        self.move(x, y)
        self.show()
        self.raise_()

    def stop(self) -> None:
        self._tick_timer.stop()
        self._spinner.stop()
        self.close()
