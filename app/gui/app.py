"""StegoNexus application bootstrap."""
from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QApplication

from app import APP_NAME, APP_ORG, APP_VERSION, __version__
from app.core.config import get_config
from app.core.exceptions import StegoNexusError
from app.core.logger import get_logger
from app.gui.main_window import MainWindow
from app.gui.themes import qt_palette, stylesheet
from app.modules.settings import service as settings

LOG = get_logger(__name__)


def build_app(argv: list[str] | None = None) -> tuple[QApplication, MainWindow]:
    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)

    icon_path = get_config().resources_dir / "branding" / "stegonexus-icon.png"
    if icon_path.exists():
        app.setWindowIcon(QIcon(QPixmap(str(icon_path))))

    theme = settings.current().get("theme", "dark")
    app.setPalette(qt_palette(theme))
    app.setStyleSheet(stylesheet(theme))

    window = MainWindow()
    window.theme_button.setText("Light" if theme == "dark" else "Dark")
    window.refresh()
    return app, window


def run_gui(argv: list[str] | None = None) -> int:
    try:
        app, window = build_app(argv)
    except StegoNexusError as exc:
        print(f"StegoNexus failed to start: {exc}", file=sys.stderr)
        return 1
    window.show()
    LOG.info("GUI started (%s)", __version__)
    return app.exec()


def run_cli(argv: list[str] | None = None) -> int:
    from app.cli import app as cli_app

    return cli_app.run_cli(argv)


def run_diagnostics() -> int:
    """Headless diagnostics: print the live tool health matrix."""
    from app.services.tool_health import health

    rows = health.summary()["rows"]
    width = max(len(row["name"]) for row in rows)
    print(f"{APP_NAME} {APP_VERSION} - tool health ({len(rows)} tracked)")
    print("-" * 72)
    for row in rows:
        print(f"{row['name'].ljust(width)}  {row['status']:<12} "
              f"{row['classification']:<12} {row['version'] or row['path'] or ''}")
    return 0
