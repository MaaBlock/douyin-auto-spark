QSS_STYLE = """
QMainWindow {
    background-color: #0b0f19;
}
QWidget {
    font-family: "Segoe UI", "Microsoft YaHei", sans-serif;
    color: #f1f5f9;
}
QFrame.Card {
    background-color: #131d31;
    border: 1.5px solid #1e293b;
    border-radius: 18px;
}
QFrame.CardGlow {
    background-color: #131d31;
    border: 1.5px solid #f43f5e;
    border-radius: 18px;
}
QFrame.TipBox {
    background-color: #0d1527;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 14px;
}
QLabel {
    color: #f8fafc;
}
QLabel.Title {
    font-size: 18px;
    font-weight: bold;
    color: #ffffff;
}
QLabel.Subtitle {
    color: #cbd5e1;
    font-size: 13px;
}
QLabel.Muted {
    color: #94a3b8;
    font-size: 12px;
}
QLineEdit, QTextEdit, QSpinBox {
    background-color: #090d16;
    border: 1.5px solid #334155;
    border-radius: 10px;
    padding: 10px 14px;
    color: #f8fafc;
    font-size: 13px;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {
    border: 1.5px solid #f43f5e;
}
QPushButton {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 10px 20px;
    color: #f8fafc;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #334155;
    border-color: #475569;
}
QPushButton.Primary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f43f5e, stop:1 #e11d48);
    border: none;
    color: #ffffff;
    font-size: 14px;
}
QPushButton.Primary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fb7185, stop:1 #f43f5e);
}
QPushButton.Success {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #059669);
    border: none;
    color: #ffffff;
    font-size: 14px;
}
QPushButton.Success:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #34d399, stop:1 #10b981);
}
QPushButton.Star {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);
    border: none;
    color: #090d16;
    font-size: 14px;
    font-weight: bold;
}
QPushButton.Star:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #fbbf24, stop:1 #f59e0b);
}
QPushButton.Secondary {
    background-color: #1e293b;
    color: #94a3b8;
    font-size: 12px;
}
QPushButton.Secondary:hover {
    color: #f1f5f9;
}
QCheckBox {
    spacing: 8px;
    color: #f1f5f9;
    font-size: 13px;
}
QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 1.5px solid #475569;
    background-color: #090d16;
}
QCheckBox::indicator:checked {
    background-color: #f43f5e;
    border-color: #f43f5e;
}
QRadioButton {
    spacing: 8px;
    color: #f1f5f9;
    font-size: 13px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
    border-radius: 8px;
    border: 1.5px solid #475569;
    background-color: #090d16;
}
QRadioButton::indicator:checked {
    background-color: #f43f5e;
    border-color: #f43f5e;
}
QListWidget {
    background-color: #090d16;
    border: 1px solid #1e293b;
    border-radius: 14px;
    padding: 6px;
}
QListWidget::item {
    background-color: #131d31;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin: 3px 0px;
    padding: 8px 12px;
}
QListWidget::item:selected {
    background-color: #1e1b4b;
    border: 1.5px solid #6366f1;
}
QProgressBar {
    border: 1px solid #1e293b;
    border-radius: 8px;
    background-color: #090d16;
    text-align: center;
    color: #f8fafc;
    font-size: 11px;
}
QProgressBar::chunk {
    background-color: #f43f5e;
    border-radius: 7px;
}
QScrollBar:vertical {
    border: none;
    background: #090d16;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 20px;
    border-radius: 4px;
}
"""
