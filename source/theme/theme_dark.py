# source/theme/theme_dark.py
DARK_STYLESHEET = """
* {
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    font-size: 11pt;
}
QMainWindow {
    background-color: #121212;
}
QWidget {
    background-color: #121212;
    color: #f5f5f5;
}
QFrame#NavFrame {
    background-color: #0d0d0d;
}
QPushButton {
    background-color: #1f1f1f;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px 12px;
    color: #f5f5f5;
}
QPushButton:hover {
    background-color: #272727;
}
QPushButton:pressed {
    background-color: #0f766e;
}
QPushButton#NavButton {
    background-color: transparent;
    border: none;
    padding: 8px 12px;
    text-align: left;
}
QPushButton#NavButton:hover {
    background-color: #1f2937;
}
QPushButton#NavButton:checked {
    background-color: #0f172a;
    color: #22c55e;
}
QLineEdit, QComboBox {
    background-color: #1e1e1e;
    border: 1px solid #333333;
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: #0f766e;
}
QGroupBox {
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    margin-top: 20px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #9ca3af;
}
QLabel#TitleLabel {
    font-size: 20px;
    font-weight: 600;
}
QLabel#SubtitleLabel {
    font-size: 11pt;
    color: #9ca3af;
}
QStatusBar {
    background-color: #0b0b0b;
}
QStatusBar QLabel {
    color: #9ca3af;
}

QProgressBar {
    background-color: #1e1e1e;
    border: 1px solid #444;
    border-radius: 4px;
}

QProgressBar::chunk {
    background-color: #3ba99c;
    border-radius: 4px;
}

#LoadingIndicator {
    border-top: 1px solid #333;
}

"""
