"""Settings dialog."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..config import CORNERS, MONITOR_MODES, Config
from .icons import make_app_icon

PRESET_COLORS = {
    "Black": "#000000", "White": "#ffffff", "Gray": "#808080", "Red": "#e53935",
    "Blue": "#1e88e5", "Green": "#43a047", "Purple": "#8e24aa",
}
_CORNER_LABELS = {"top_left": "Top Left", "top_right": "Top Right",
                  "bottom_left": "Bottom Left", "bottom_right": "Bottom Right",
                  "random": "Random"}
_MONITOR_LABELS = {"current": "Current Monitor", "all": "All Monitors",
                   "random": "Random Monitor"}


class ColorPicker(QWidget):
    """Preset names + 'Custom…' with a live swatch."""

    changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value = "#000000"
        self._combo = QComboBox()
        self._combo.addItems([*PRESET_COLORS, "Custom…"])
        self._swatch = QLabel()
        self._swatch.setFixedSize(28, 18)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._combo, 1)
        layout.addWidget(self._swatch)
        self._combo.activated.connect(self._on_activated)

    def value(self) -> str:
        return self._value

    def set_value(self, hex_color: str) -> None:
        self._value = hex_color.lower()
        names = {v: k for k, v in PRESET_COLORS.items()}
        self._combo.setCurrentText(names.get(self._value, "Custom…"))
        self._swatch.setStyleSheet(
            f"background:{self._value}; border:1px solid #888; border-radius:3px;")

    def _on_activated(self, index: int) -> None:
        name = self._combo.itemText(index)
        if name == "Custom…":
            color = QColorDialog.getColor(QColor(self._value), self, "Choose color")
            if not color.isValid():
                self.set_value(self._value)
                return
            self.set_value(color.name())
        else:
            self.set_value(PRESET_COLORS[name])
        self.changed.emit(self._value)


class SettingsWindow(QDialog):
    applied = Signal(object)        # Config
    test_requested = Signal()

    def __init__(self, config: Config, backend_text: str = "") -> None:
        super().__init__(None)
        self.setWindowTitle("Idle Spider — Settings")
        self.setWindowIcon(make_app_icon())
        self.setMinimumWidth(420)

        self.enabled = QCheckBox("Enable animation")
        self.timeout = QSpinBox()
        self.timeout.setRange(5, 86_400)
        self.timeout.setSuffix(" seconds")
        self.spider_color = ColorPicker()
        self.web_color = ColorPicker()
        self.opacity = QSlider(Qt.Orientation.Horizontal)
        self.opacity.setRange(5, 100)
        self.opacity_label = QLabel()
        self.opacity.valueChanged.connect(lambda v: self.opacity_label.setText(f"{v}%"))
        self.size = QSpinBox()
        self.size.setRange(8, 48)
        self.size.setSuffix(" px")
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.25, 3.0)
        self.speed.setSingleStep(0.25)
        self.speed.setSuffix(" ×")
        self.density = QSlider(Qt.Orientation.Horizontal)
        self.density.setRange(1, 10)
        self.max_webs = QSpinBox()
        self.max_webs.setRange(1, 12)
        self.corner = QComboBox()
        for key in CORNERS:
            self.corner.addItem(_CORNER_LABELS[key], key)
        self.monitor = QComboBox()
        for key in MONITOR_MODES:
            self.monitor.addItem(_MONITOR_LABELS[key], key)
        self.autostart = QCheckBox("Start with system (on login)")

        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self.opacity, 1)
        opacity_row.addWidget(self.opacity_label)

        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow("Idle timeout", self.timeout)
        form.addRow("Spider color", self.spider_color)
        form.addRow("Web color", self.web_color)
        form.addRow("Web opacity", opacity_row)
        form.addRow("Spider size", self.size)
        form.addRow("Animation speed", self.speed)
        form.addRow("Web density", self.density)
        form.addRow("Maximum webs", self.max_webs)
        form.addRow("Start animation from", self.corner)
        form.addRow("Multi monitor mode", self.monitor)
        form.addRow(self.autostart)

        self._backend = QLabel(backend_text)
        self._backend.setWordWrap(True)
        self._backend.setStyleSheet("color:gray;")

        test = QPushButton("Test Animation")
        defaults = QPushButton("Defaults")
        apply_btn = QPushButton("Apply")
        ok = QPushButton("OK")
        ok.setDefault(True)
        close = QPushButton("Close")
        test.clicked.connect(self._on_test)
        defaults.clicked.connect(lambda: self.load(Config()))
        apply_btn.clicked.connect(self._on_apply)
        ok.clicked.connect(self._on_ok)
        close.clicked.connect(self.close)
        buttons = QHBoxLayout()
        buttons.addWidget(test)
        buttons.addWidget(defaults)
        buttons.addStretch(1)
        for b in (apply_btn, ok, close):
            buttons.addWidget(b)

        root = QVBoxLayout(self)
        root.addLayout(form)
        root.addWidget(self._backend)
        root.addLayout(buttons)
        self.load(config)

    def set_backend_text(self, text: str) -> None:
        self._backend.setText(text)

    def load(self, c: Config) -> None:
        self.enabled.setChecked(c.enabled)
        self.timeout.setValue(c.idle_timeout)
        self.spider_color.set_value(c.spider_color)
        self.web_color.set_value(c.web_color)
        self.opacity.setValue(round(c.web_opacity * 100))
        self.opacity_label.setText(f"{self.opacity.value()}%")
        self.size.setValue(c.spider_size)
        self.speed.setValue(c.animation_speed)
        self.density.setValue(c.web_density)
        self.max_webs.setValue(c.max_webs)
        self.corner.setCurrentIndex(self.corner.findData(c.start_corner))
        self.monitor.setCurrentIndex(self.monitor.findData(c.monitor_mode))
        self.autostart.setChecked(c.autostart)

    def to_config(self) -> Config:
        return Config(
            enabled=self.enabled.isChecked(),
            idle_timeout=self.timeout.value(),
            spider_color=self.spider_color.value(),
            web_color=self.web_color.value(),
            web_opacity=self.opacity.value() / 100.0,
            spider_size=self.size.value(),
            animation_speed=self.speed.value(),
            web_density=self.density.value(),
            start_corner=self.corner.currentData(),
            monitor_mode=self.monitor.currentData(),
            autostart=self.autostart.isChecked(),
            max_webs=self.max_webs.value(),
        ).normalize()

    def _on_apply(self) -> None:
        self.applied.emit(self.to_config())

    def _on_ok(self) -> None:
        self._on_apply()
        self.accept()

    def _on_test(self) -> None:
        self._on_apply()
        self.test_requested.emit()
