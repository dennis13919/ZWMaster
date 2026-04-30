#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
紫微斗數排盤系統 (ZWMaster) - Main
"""
import sys
import os
import csv
import copy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QGridLayout,
    QGroupBox, QPushButton, QLabel, QDialog, QMessageBox, QButtonGroup,
    QCheckBox, QMenu, QToolButton, QFrame, QSizePolicy, QColorDialog, QFileDialog,
    QSlider, QSpacerItem
)
from PySide6.QtGui import QAction, QFont, QColor, QPalette, QIcon, QShortcut, QKeySequence, QPainter, QPen, QBrush, \
    QPainterPath
from PySide6.QtCore import Qt, QSize, QSettings, Signal, QPoint, QRect, QSizeF
from ui import ZiweiChartWidget, BirthInfoDialog, DatabaseManagerDialog, CategorySelectionDialog, SettingsDialog
from logic import ZiweiCalculator
from database import ZiweiDatabase

ABOUT_TEXT = """
<h2>紫微斗數排盤系統 (ZWMaster)</h2>
<p><b>版本：</b>V6.0 (南北派整合版)</p>
<p><b>開發者：：</b>Dennis19319</p>
<p><b>技術核心：</b> Google Gemini 3 Flash Preview</p>
<p><b>版權所有：：</b>© 2026 Dennis19319. All Rights Reserved.</p>
<hr>  
<p>本系統提供專業的南北派紫微斗數排盤功能，包含動態大限流年切換、
繪圖標記工具以及完整的資料庫管理系統。V6.0 強化資料庫匯入匯出功能。</p>
<p>本軟體僅供免費交流，若您是付費取得，請立即向來源要求退款並檢舉</p>
<p>【授權與使用條款】</p>
<p>免費原則：本軟體免費提供予大眾個人學習與研究使用。</p>
<p>禁止營利：未經作者授權，禁止將本軟體用於商業營利行為。</p>
<p>禁止更動：禁止對本軟體進行反編譯、修改、或修改開發資訊後重新發佈。</p>
<p>若有授權需求，請聯繫 https://bit.ly/AuthZWM </p>
"""


class SlotState:
    """儲存命盤 Slot 狀態的結構"""

    def __init__(self, full_chart_data=None, drawing_paths=None, ui_state=None, birth_data=None, snapshot=None):
        self.full_chart_data = full_chart_data
        self.drawing_paths = drawing_paths if drawing_paths else []
        self.ui_state = ui_state if ui_state else {}
        self.birth_data = birth_data  # 原始輸入資料 (包含 lunar_month, lunar_day, calc_hour 等計算後資訊)
        self.snapshot = snapshot  # QPixmap 縮圖
        self.is_locked = False

    def is_empty(self):
        return self.full_chart_data is None

    def get_display_text(self):
        if self.is_empty():
            return "空"
        name = self.full_chart_data["center_info"].get("name", "匿名")
        solar = self.full_chart_data["center_info"].get("solar_line", "")
        # 簡化顯示文字
        return f"{name}\n{solar.replace('西元 ', '')}"


class SlotButton(QPushButton):
    """自定義 Slot 按鈕，支援縮圖、右鍵、中鍵與懸停預覽"""
    clicked_left = Signal(int)
    clicked_right = Signal(int)
    clicked_middle = Signal(int)

    def __init__(self, index, parent=None):
        super().__init__(parent)
        self.index = index
        self.setMouseTracking(True)
        self.setFixedSize(106, 60)
        self.preview_label = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked_left.emit(self.index)
        elif event.button() == Qt.RightButton:
            self.clicked_right.emit(self.index)
        elif event.button() == Qt.MiddleButton:
            self.clicked_middle.emit(self.index)
        super().mousePressEvent(event)

    def enterEvent(self, event):
        main_win = self.window()
        if not hasattr(main_win, "slots"): return
        slot = main_win.slots[self.index]
        if slot.is_empty() or not slot.snapshot: return

        if not self.preview_label:
            self.preview_label = QLabel(main_win)
            self.preview_label.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint)
            self.preview_label.setStyleSheet("border: 2px solid #2196F3; background: #333;")
            self.preview_label.setAttribute(Qt.WA_ShowWithoutActivating)

        preview_size = self.size() * 1.5
        thumb = slot.snapshot
        scaled_preview = thumb.scaled(preview_size * self.devicePixelRatio(),
                                      Qt.KeepAspectRatio,
                                      Qt.SmoothTransformation)
        scaled_preview.setDevicePixelRatio(self.devicePixelRatio())

        self.preview_label.setPixmap(scaled_preview)
        self.preview_label.adjustSize()
        pos = self.mapToGlobal(QPoint(0, self.height() + 5))
        self.preview_label.move(pos)
        self.preview_label.show()

    def leaveEvent(self, event):
        if self.preview_label:
            self.preview_label.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            main_win = self.window()
            slot = main_win.slots[self.index] if hasattr(main_win, "slots") else None
            rect = self.rect()
            dpr = self.devicePixelRatioF()

            painter.setBrush(QBrush(QColor("#222")))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 4, 4)

            if not slot or slot.is_empty():
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(QColor("#666"), 1, Qt.DashLine))
                painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), 4, 4)
                painter.setPen(QColor("#888"))
                painter.setFont(QFont("Arial", 10))
                painter.drawText(rect, Qt.AlignCenter, "Empty")
            else:
                if slot.snapshot:
                    # 使用邏輯尺寸繪製 Pixmap，Qt 會根據 Pixmap 內部的 DPR 自動縮放
                    painter.drawPixmap(rect, slot.snapshot)

                # 繪製姓名
                name = slot.full_chart_data["center_info"].get("name", "匿名")
                font = QFont("Microsoft JhengHei", 9, QFont.Bold)
                painter.setFont(font)
                path = QPainterPath()
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(name)
                tx = (rect.width() - text_w) / 2
                ty = rect.bottom() - 5
                path.addText(tx, ty, font, name)
                painter.setPen(QPen(Qt.white, 2.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                painter.drawPath(path)
                painter.fillPath(path, QBrush(Qt.black))

            if slot and slot.is_locked:
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(244, 67, 54, 200))
                lock_rect = QRect(rect.right() - 22, rect.top() + 4, 18, 18)
                painter.drawRoundedRect(lock_rect, 3, 3)
                painter.setPen(Qt.white)
                painter.drawText(lock_rect, Qt.AlignCenter, "🔒")

            border_color = "#F44336" if slot and slot.is_locked else (
                "#2196F3" if slot and not slot.is_empty() else "#444")
            painter.setPen(QPen(QColor(border_color), 2))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 4, 4)
        finally:
            painter.end()  # 確保繪圖物件正確關閉


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_birth_year = None
        self.current_start_age = 2
        self.full_chart_data = None
        self.current_birth_data = None  # 儲存當前排盤的原始輸入資料 (包含 lunar_month, lunar_day, calc_hour 等計算後資訊)

        # 取得程式進入點所在的目錄
        if hasattr(sys, '_MEIPASS'):
            # PyInstaller 打包後的暫存路徑
            base_path = sys._MEIPASS
        else:
            # 一般開發環境下的路徑
            base_path = os.path.abspath(".")

        icon_path = os.path.join(base_path, "ZWMaster.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        else:
            print(f"Warning: Icon file not found at {icon_path}")

        # 初始化 Slot
        self.slots = [SlotState() for _ in range(5)]
        self.slot_btns = []

        # 初始化設定
        self.settings = QSettings("MyZiweiApp", "Settings")
        # 讀取儲存的筆觸粗細，預設值為 3
        self.saved_thickness = int(self.settings.value("pen_thickness", 3))

        # 初始化資料庫
        self.db = ZiweiDatabase()
        self.db_dialog = None  # 保持對資料庫對話框的引用

        # 繪圖相關狀態
        self.user_custom_color = QColor(Qt.red)
        # 工具映射 (顯示標籤 -> 工具識別碼)
        self.tool_info = [
            ("✎", "pen"),
            ("↗", "arrow"),
            ("○", "circle"),
            ("☐", "rect"),
            ("T", "text")
        ]

        self.daxian_btns = []
        self.liunian_btns = []
        self.color_btns = []

        self.init_ui()
        self.setup_window_size()
        self.apply_global_styles()

        QShortcut(QKeySequence("Ctrl+Z"), self, self.undo_drawing)
        QShortcut(QKeySequence("Ctrl+X"), self, self.clear_drawing)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self.delete_selected_drawing)
        QShortcut(QKeySequence("Ctrl+A"), self, self.show_birth_dialog)
        QShortcut(QKeySequence("Ctrl+Q"), self, self.show_database_dialog)

        # self.chart_widget = ZiweiChartWidget()
        # self.layout.addWidget(self.chart_widget)
        self.chart_widget.drawing_layer.tool_deactivated.connect(self.deactivate_drawing_tools)

    def deactivate_drawing_tools(self):
        """取消所有繪圖工具的選取狀態"""
        for btn in self.draw_group.buttons():
            btn.setChecked(False)
        # 確保繪圖層的工具類型也已重置 (雖然 DrawingLayer 內部已做，但這裡再次確認)
        self.chart_widget.drawing_layer.set_tool_type(None)
        self.update()  # 觸發 UI 更新，確保按鈕狀態正確顯示

    def apply_global_styles(self):
        style = """
            /* --- 主視窗基礎設定 --- */
            QMainWindow { background-color: #f0f0f0; color: black; }
            QMainWindow QLabel, QMainWindow QGroupBox { color: black; }

            /* --- 核取方塊 (Checkmark 效果) --- */
            QCheckBox { color: black; background: transparent; spacing: 12px; min-width: 100px; }
            QCheckBox::indicator {
                border: 2px solid #666;
                background-color: white;
                width: 13px;
                height: 13px;
                border-radius: 3px;
                margin: 2px;
            }
            QCheckBox::indicator:checked {
                background-color: white;
                border: 2px solid #4CAF50;
                image: url(non_existent_to_force_padding); /* 觸發 padding 渲染 */
                padding: 2px;
                background-clip: content;
                background-color: #4CAF50; /* 內部填充綠色塊模擬打勾 */
            }

            /* --- 單選鈕 (Centered Dot 效果) --- */
            QRadioButton { color: black; background: transparent; spacing: 12px; min-width: 100px; }
            QRadioButton::indicator {
                border: 2px solid #666;
                background-color: white;
                width: 13px;
                height: 13px;
                border-radius: 8px;
                margin: 2px;
            }
            QRadioButton::indicator:checked {
                background-color: white;
                border: 2px solid #2196F3;
                padding: 3px;
                background-clip: content;
                background-color: #2196F3; /* 內部填充藍點 */
            }

            /* --- 選單 (QMenu) 修復：解決 Dark Mode 紅白不分問題 --- */
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                padding: 2px;
            }
            QMenu::item {
                color: black;
                background-color: white;
                padding: 5px 25px;
                border-radius: 2px;
            }
            QMenu::item:selected {
                color: white;
                background-color: #2196F3;
            }
            QMenu::separator {
                height: 1px;
                background: #ddd;
                margin: 4px 10px;
            }

            /* --- 對話框 (QDialog) 強修 --- */
            QDialog { 
                background-color: #f5f5f5; 
            }
            QDialog QLabel, QDialog QCheckBox, QDialog QRadioButton { 
                color: black !important; 
            }

            /* 文字輸入框 */
            QDialog QLineEdit, QInputDialog QLineEdit { 
                background-color: white !important; 
                color: black !important; 
                border: 1px solid #999999 !important;
                padding: 4px;
            }

            /* 對話框按鈕：強制實色背景與黑色文字 */
            QDialog QPushButton, QInputDialog QPushButton { 
                background-color: #e0e0e0 !important; 
                color: black !important; 
                border: 1px solid #777777 !important; 
                border-radius: 4px;
                padding: 6px 16px;
                min-width: 75px;
                font-weight: bold;
            }
            QDialog QPushButton:hover, QInputDialog QPushButton:hover { 
                background-color: #d5d5d5 !important; 
                border: 1px solid #555 !important;
            }

            /* --- 表格與標籤 --- */
            QTableWidget { 
                background-color: white; 
                color: black; 
                gridline-color: #ccc;
                selection-background-color: #2196F3;
                selection-color: white;
            }
            QTableWidget::item:selected {
                background-color: #2196F3;
                color: white;
            }
            QHeaderView::section { 
                background-color: #e8e8e8; 
                color: black; 
                padding: 5px; 
                border: 1px solid #ccc; 
                font-weight: bold;
            }
            QTabWidget::pane { border: 1px solid #ccc; background: white; }
            QTabBar::tab { background: #ddd; color: black; padding: 10px 20px; border-top-left-radius: 4px; border-top-right-radius: 4px; }
            QTabBar::tab:selected { background: white; font-weight: bold; border-bottom-color: white; }
        """
        self.setStyleSheet(style)

    def init_ui(self):
        self.setWindowTitle("紫微斗數排盤系統 (ZWMaster) 免費推廣版 - 禁止商業用途")
        central_widget = QWidget()
        central_widget.setObjectName("centralWidget")
        self.setCentralWidget(central_widget)
        central_widget.setStyleSheet("background-color: #f0f0f0;")
        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        top_panel = self.create_top_panel()
        root_layout.addWidget(top_panel)
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)
        left_panel = self.create_left_panel()
        content_layout.addWidget(left_panel)
        # 1. 先建立 chart_widget
        chart_container = QWidget()
        chart_container_layout = QVBoxLayout(chart_container)
        self.chart_widget = ZiweiChartWidget()
        self.chart_widget.setStyleSheet("background-color: transparent;")
        chart_container_layout.addWidget(self.chart_widget)

        # 2. 再建立工具欄 (現在它找得到 self.chart_widget 了)
        draw_toolbar = self.create_drawing_toolbar()
        content_layout.addWidget(draw_toolbar)

        # 3. 最後把容器加進去
        content_layout.addWidget(chart_container)

        content_layout.setStretch(0, 0)
        content_layout.setStretch(1, 0)
        content_layout.setStretch(2, 1)
        root_layout.addWidget(content_widget)

    def create_top_panel(self):
        panel = QFrame()
        panel.setStyleSheet("QFrame { background-color: #e0e0e0; border-bottom: 1px solid #bbb; }")
        panel.setFixedHeight(80)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)

        left_container = QWidget()
        left_layout = QVBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(5)
        left_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 第一列：選單與功能按鈕
        menu_row = QWidget()
        menu_row_layout = QHBoxLayout(menu_row)
        menu_row_layout.setContentsMargins(0, 0, 0, 0)
        menu_row_layout.setSpacing(10)
        menu_row_layout.setAlignment(Qt.AlignLeft)

        # 檔案選單
        btn_file = QToolButton()
        btn_file.setText("檔案(F)")
        btn_file.setPopupMode(QToolButton.InstantPopup)
        btn_file.setStyleSheet(
            "QToolButton { font-weight: bold; border: 1px solid #999; border-radius: 4px; padding: 4px 12px; color: black; background: #f5f5f5; } QToolButton:hover { background-color: #e0e0e0; }")
        menu_file = QMenu(btn_file)

        action_import_csv = QAction("匯入 CSV", self)
        action_import_csv.triggered.connect(self.import_csv)
        menu_file.addAction(action_import_csv)

        action_export_csv = QAction("匯出 CSV", self)
        action_export_csv.triggered.connect(self.export_csv)
        menu_file.addAction(action_export_csv)
        menu_file.addSeparator()

        # 功能：圖片匯出
        action_export_base = QAction("輸出本命盤", self)
        action_export_base.triggered.connect(lambda: self.export_chart_image(include_drawing=False))
        menu_file.addAction(action_export_base)

        action_export_full = QAction("輸出排盤及註解", self)
        action_export_full.triggered.connect(lambda: self.export_chart_image(include_drawing=True))
        menu_file.addAction(action_export_full)
        btn_file.setMenu(menu_file)

        # 獨立按鈕
        btn_db = QPushButton("開啟資料庫")
        btn_db.setStyleSheet(
            "QPushButton { background-color: #2196F3; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #1976D2; }")
        btn_db.clicked.connect(self.show_database_dialog)

        btn_setting = QPushButton("設定")
        btn_setting.setStyleSheet(
            "QPushButton { background-color: #757575; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #616161; }")
        btn_setting.clicked.connect(self.show_settings_dialog)

        btn_about = QPushButton("關於")
        btn_about.setStyleSheet(
            "QPushButton { background-color: #9C27B0; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #7B1FA2; }")
        btn_about.clicked.connect(lambda: QMessageBox.about(self, "關於系統", ABOUT_TEXT))

        # --- 新增：南北派切換按鈕 ---
        self.school_group = QButtonGroup(self)
        self.school_group.setExclusive(True)

        btn_north = QPushButton("北派")
        btn_south = QPushButton("南派")
        school_style = """
                    QPushButton { background-color: #f5f5f5; color: #333; border: 1px solid #999; border-radius: 4px; padding: 4px 10px; font-weight: bold; }
                    QPushButton:checked { background-color: #FF9800; color: white; border: 1px solid #E65100; }
                """
        btn_north.setStyleSheet(school_style)
        btn_south.setStyleSheet(school_style)
        btn_north.setCheckable(True)
        btn_south.setCheckable(True)

        # 讀取初始設定
        current_school = self.settings.value("school", "北派")
        if current_school == "北派":
            btn_north.setChecked(True)
        else:
            btn_south.setChecked(True)

        self.school_group.addButton(btn_north)
        self.school_group.addButton(btn_south)

        btn_north.clicked.connect(lambda: self.change_school("北派"))
        btn_south.clicked.connect(lambda: self.change_school("南派"))
        # --------------------------
        # 各個按鈕 檔案 資料庫 設定 關於
        menu_row_layout.addWidget(btn_file)
        menu_row_layout.addWidget(btn_db)
        menu_row_layout.addWidget(btn_setting)
        menu_row_layout.addWidget(btn_about)

        line_sep = QFrame()
        line_sep.setFrameShape(QFrame.VLine)
        line_sep.setFrameShadow(QFrame.Sunken)
        line_sep.setStyleSheet("background-color: #bbb;")
        menu_row_layout.addWidget(line_sep)  # 加入垂直分隔線

        menu_row_layout.addWidget(btn_north)
        menu_row_layout.addWidget(btn_south)

        # 第二列：排盤輸入與隱私設定
        tool_row = QWidget()
        tool_row_layout = QHBoxLayout(tool_row)
        tool_row_layout.setContentsMargins(0, 0, 0, 0)
        tool_row_layout.setSpacing(20)
        tool_row_layout.setAlignment(Qt.AlignLeft)

        btn_input = QPushButton("輸入生辰")
        btn_input.setStyleSheet(
            "QPushButton { background-color: #4CAF50; color: white; font-weight: bold; border-radius: 4px; padding: 4px 12px; } QPushButton:hover { background-color: #45a049; }")
        btn_input.clicked.connect(self.show_birth_dialog)

        self.cb_name = QCheckBox("隱藏姓名")
        self.cb_birth = QCheckBox("隱藏生辰")
        self.cb_part = QCheckBox("部分生辰")
        self.cb_all = QCheckBox("全部隱藏")
        self.cb_name.stateChanged.connect(self.update_privacy)
        self.cb_birth.stateChanged.connect(self.update_privacy)
        self.cb_part.stateChanged.connect(self.update_privacy)
        self.cb_all.stateChanged.connect(self.update_privacy)

        tool_row_layout.addWidget(btn_input)
        line = QFrame()
        line.setFrameShape(QFrame.VLine)
        line.setFrameShadow(QFrame.Sunken)
        tool_row_layout.addWidget(line)
        tool_row_layout.addWidget(self.cb_name)
        tool_row_layout.addWidget(self.cb_birth)
        tool_row_layout.addWidget(self.cb_part)
        tool_row_layout.addWidget(self.cb_all)
        tool_row_layout.addStretch()  # 新增 Spacer，讓 Slot 區塊更有呼吸空間

        left_layout.addWidget(menu_row)
        left_layout.addWidget(tool_row)

        right_container = QWidget()
        right_layout = QHBoxLayout(right_container)
        right_layout.setContentsMargins(10, 0, 0, 0)  # 給予 Slot 區塊左邊距
        right_layout.setSpacing(8)
        right_layout.setAlignment(Qt.AlignLeft)

        for i in range(5):
            slot_btn = SlotButton(i)
            slot_btn.clicked_left.connect(self.on_slot_clicked)
            slot_btn.clicked_right.connect(self.on_slot_right_clicked)
            slot_btn.clicked_middle.connect(self.on_slot_middle_clicked)
            right_layout.addWidget(slot_btn)
            self.slot_btns.append(slot_btn)
        self.update_slot_buttons()

        layout.addWidget(left_container)
        layout.addWidget(right_container)
        layout.addStretch()
        return panel

    def change_school(self, school_name):
        """切換流派並重新排盤"""
        self.settings.setValue("school", school_name)
        # 如果目前畫面上已經有排盤資料，則立即重新計算
        if self.current_birth_data:
            self.process_chart_calculation(self.current_birth_data, push_to_history=False)
        else:
            # 如果還沒排盤，僅更新 UI 狀態（可選）
            print(f"流派已切換為: {school_name}")

    def create_left_panel(self):
        panel = QWidget()
        panel.setFixedWidth(180)
        panel.setStyleSheet("""
            QWidget { background-color: #f5f5f5; }
            QPushButton { background-color: #e0e0e0; border: 1px solid #a0a0a0; border-radius: 4px; min-height: 25px; color: black; font-family: "Microsoft JhengHei"; }
            QPushButton:hover { background-color: #d0d0d0; }
            QPushButton:checked { background-color: #2196F3; color: white; border: 1px solid #0056b3; font-weight: bold; }
            QGroupBox { font-weight: bold; border: 1px solid #ccc; border-radius: 5px; margin-top: 12px; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; color: #222222; }
        """)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)

        group_daxian = QGroupBox("大限 (歲數)")
        layout_daxian = QGridLayout(group_daxian)
        layout_daxian.setSpacing(5)
        self.daxian_group = QButtonGroup(self)
        self.daxian_group.setExclusive(False)
        for i in range(10):
            btn = QPushButton(f"{i + 1}限")
            btn.setCheckable(True)
            layout_daxian.addWidget(btn, i // 2, i % 2)
            self.daxian_group.addButton(btn, i)
            self.daxian_btns.append(btn)
            btn.clicked.connect(lambda checked, idx=i: self.on_daxian_clicked(idx))
        layout.addWidget(group_daxian)

        self.group_liunian = QGroupBox("流年 (西元)")
        layout_liunian = QGridLayout(self.group_liunian)
        layout_liunian.setSpacing(5)
        self.liunian_group = QButtonGroup(self)
        self.liunian_group.setExclusive(True)
        for i in range(10):
            btn = QPushButton("")
            btn.setCheckable(True)
            btn.setEnabled(False)
            layout_liunian.addWidget(btn, i // 2, i % 2)
            self.liunian_group.addButton(btn, i)
            self.liunian_btns.append(btn)
            btn.clicked.connect(self.on_liunian_clicked)
        layout.addWidget(self.group_liunian)
        layout.addStretch()
        return panel

    def create_drawing_toolbar(self):
        bar = QWidget()
        bar.setFixedWidth(40)
        bar.setStyleSheet(
            "QWidget { background-color: #ddd; border-right: 1px solid #bbb; border-left: 1px solid #bbb; }")
        layout = QVBoxLayout(bar)
        layout.setContentsMargins(2, 5, 2, 5)
        layout.setSpacing(5)

        self.draw_group = QButtonGroup(self)
        self.draw_group.setExclusive(False)
        btn_style = """
            QPushButton { background-color: transparent; border: none; font-size: 16px; padding: 4px; color: black; }
            QPushButton:hover { background-color: #ccc; border-radius: 4px; }
            QPushButton:checked { background-color: #999; border: 1px solid #666; border-radius: 4px; }
        """
        for i, (label, tool_id) in enumerate(self.tool_info):
            btn = QPushButton(label)
            btn.setStyleSheet(btn_style)
            btn.setCheckable(True)
            self.draw_group.addButton(btn, i)
            btn.clicked.connect(lambda checked, idx=i: self.on_tool_clicked(idx))
            layout.addWidget(btn)

        btn_color = QPushButton("🎨")
        btn_color.setStyleSheet(btn_style)
        btn_color.clicked.connect(self.open_color_picker)
        layout.addWidget(btn_color)

        # 粗細控制
        layout.addSpacing(5)
        self.thickness_slider = QSlider(Qt.Vertical)
        self.thickness_slider.setRange(1, 10)
        self.thickness_slider.setValue(self.saved_thickness)  # 使用讀取的數值
        # 確保初始化時繪圖層也取得正確粗細
        self.chart_widget.drawing_layer.set_thickness(self.saved_thickness)
        self.thickness_slider.setTickPosition(QSlider.TicksRight)
        self.thickness_slider.setTickInterval(1)
        self.thickness_slider.setToolTip("筆觸粗細")
        self.thickness_slider.valueChanged.connect(self.on_thickness_changed)
        layout.addWidget(self.thickness_slider, 0, Qt.AlignHCenter)
        layout.addSpacing(5)

        btn_undo = QPushButton("⟲")
        btn_undo.setStyleSheet(btn_style)
        btn_undo.setToolTip("復原 (Ctrl+Z)")
        btn_undo.clicked.connect(self.undo_drawing)
        layout.addWidget(btn_undo)

        btn_clear = QPushButton("✖")
        btn_clear.setStyleSheet(btn_style)
        btn_clear.setToolTip("清空 (Ctrl+X)")
        btn_clear.clicked.connect(self.clear_drawing)
        layout.addWidget(btn_clear)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        self.color_data = [
            (self.user_custom_color, "custom"),
            (QColor(Qt.red), Qt.red),
            (QColor(Qt.black), Qt.black),
            (QColor(Qt.blue), Qt.blue),
            (QColor(Qt.green), Qt.green)
        ]
        for i, (qcolor, tag) in enumerate(self.color_data):
            btn = QPushButton()
            btn.setFixedSize(24, 24)
            btn.setCheckable(True)
            self.color_btns.append(btn)
            self.update_color_btn_style(btn, qcolor)
            self.color_group.addButton(btn, i)
            layout.addWidget(btn)
            btn.clicked.connect(lambda checked, idx=i: self.on_color_selected(idx))
        self.color_group.button(0).setChecked(True)
        layout.addStretch()
        return bar

    def update_color_btn_style(self, btn, color):
        hex_code = color.name()
        style = f"""
            QPushButton {{ background-color: {hex_code}; border: 2px solid #999; border-radius: 2px; }}
            QPushButton:hover {{ border: 2px solid #666; }}
            QPushButton:checked {{ border: 3px solid #FFFF00; }}
        """
        btn.setStyleSheet(style)

    def on_thickness_changed(self, value):
        if hasattr(self, 'chart_widget'):
            self.chart_widget.drawing_layer.set_thickness(value)
            # 即時儲存粗細設定
            self.settings.setValue("pen_thickness", value)

    def on_tool_clicked(self, btn_id):
        sender = self.draw_group.button(btn_id)
        is_checked = sender.isChecked()
        if is_checked:
            for btn in self.draw_group.buttons():
                if btn != sender: btn.setChecked(False)
            tool_id = self.tool_info[btn_id][1]
            self.chart_widget.drawing_layer.set_tool_type(tool_id)
        else:
            self.chart_widget.drawing_layer.set_tool_type(None)

    def open_color_picker(self):
        color = QColorDialog.getColor(self.user_custom_color, self, "選擇顏色")
        if color.isValid():
            self.user_custom_color = color
            custom_btn = self.color_group.button(0)
            self.update_color_btn_style(custom_btn, color)
            self.color_data[0] = (color, "custom")
            custom_btn.setChecked(True)
            self.chart_widget.drawing_layer.set_pen_color(color)

    def on_color_selected(self, idx):
        color, tag = self.color_data[idx]
        self.chart_widget.drawing_layer.set_pen_color(color)

    def undo_drawing(self):
        self.chart_widget.drawing_layer.undo()

    def delete_selected_drawing(self):
        """刪除當前選中的繪圖物件"""
        if hasattr(self, 'chart_widget'):
            # 呼叫繪圖層的刪除方法
            self.chart_widget.drawing_layer.delete_selected()

    def clear_drawing(self):
        self.chart_widget.drawing_layer.clear()

    def create_chart_area(self):
        container = QWidget()
        container.setStyleSheet("background-color: #FFFFFF;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(1, 1, 1, 1)
        self.chart_widget = ZiweiChartWidget()
        self.chart_widget.setStyleSheet("background-color: transparent;")
        layout.addWidget(self.chart_widget)
        return container

    def setup_window_size(self):
        # 取得設定檔
        settings = QSettings("MyZiweiApp", "Settings")
        geometry = settings.value("window_geometry")
        if geometry:
            # 如果有儲存過的紀錄，直接還原 (包含大小與位置)
            self.restoreGeometry(geometry)
        else:
            screen = QApplication.primaryScreen()
            screen_geo = screen.availableGeometry()
            screen_w = screen_geo.width()
            target_w = int(screen_w * 2 / 3)
            target_h = int(target_w * 3 / 5)
            final_w = max(target_w, 1280)
            final_h = max(target_h, 720)
            self.resize(final_w, final_h)

            self.move((screen_geo.width() - final_w) // 2, (screen_geo.height() - final_h) // 2)
        # 新增這行：限制最小尺寸，讓使用者只能拉大，不能縮小過頭
        self.setMinimumSize(1280, 720)

    # --- 資料庫互動功能 ---
    def show_settings_dialog(self):
        """開啟系統設定視窗"""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            # 如果資料庫視窗正開啟，即時更新其 Tab 標籤
            if self.db_dialog and self.db_dialog.isVisible():
                self.db_dialog.refresh_categories()

            # 如果當前有排盤，重新計算以反映設定變更
            if self.current_birth_data:
                self.process_chart_calculation(self.current_birth_data)

    def show_database_dialog(self):
        """開啟資料庫管理視窗"""
        if not self.db_dialog:
            self.db_dialog = DatabaseManagerDialog(self.db, self)

        # 每次開啟前重新整理分類標籤，確保反映最新設定
        self.db_dialog.refresh_categories()

        if self.db_dialog.exec() == QDialog.Accepted:
            user = self.db_dialog.selected_user
            privacy = self.db_dialog.get_privacy_settings()

            if user:
                # 載入資料
                self.process_chart_calculation(user)

                # 套用隱私設定
                self.cb_name.setChecked(privacy["name"])
                self.cb_birth.setChecked(privacy["birth"])
                self.cb_part.setChecked(privacy["part"])
                self.cb_all.setChecked(privacy["all"])

    def export_csv(self):
        path, _ = QFileDialog.getSaveFileName(self, "匯出 CSV", "", "CSV Files (*.csv)")
        if not path: return

        try:
            users = self.db.get_all_users()
            with open(path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                writer.writerow(['姓名', '性別', '生辰', '備註', '群組'])
                for u in users:
                    birth_str = f"{u['year']}{u['month']:02d}{u['day']:02d}{u['hour']:02d}{u['minute']:02d}"
                    writer.writerow([u['name'], u['gender'], birth_str, u.get('note', ''), u.get('category', '其他')])
            QMessageBox.information(self, "成功", "資料已成功匯出。")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{str(e)}")

    def import_csv(self):
        path, _ = QFileDialog.getOpenFileName(self, "匯入 CSV", "", "CSV Files (*.csv)")
        if not path: return

        # 動態抓取當前設定的群組
        VALID_CATEGORIES = self.get_current_categories()

        cat_dialog = CategorySelectionDialog(self)
        if cat_dialog.exec() != QDialog.Accepted: return
        selected_cat = cat_dialog.get_category()

        # 若選擇"全部"或無效，強制歸類到最後一個群組
        default_category = VALID_CATEGORIES[-1]
        if selected_cat in VALID_CATEGORIES:
            default_category = selected_cat

        try:
            with open(path, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)

                success_count = 0
                for i, row in enumerate(reader, start=2):
                    if not row: continue
                    try:
                        name, gender, birth_raw = row[0].strip(), row[1].strip(), row[2].strip()
                        note = row[3].strip() if len(row) > 3 else ""

                        # 檢查 CSV 內的群組是否合法
                        csv_cat = row[4].strip() if len(row) > 4 else ""
                        final_category = csv_cat if csv_cat in VALID_CATEGORIES else default_category

                        self.db.add_user({
                            "name": name, "gender": gender, "year": int(birth_raw[0:4]),
                            "month": int(birth_raw[4:6]), "day": int(birth_raw[6:8]),
                            "hour": int(birth_raw[8:10]), "minute": int(birth_raw[10:12]),
                            "is_lunar": False, "note": note, "category": final_category
                        })
                        success_count += 1
                    except Exception:
                        continue
                QMessageBox.information(self, "匯入完成", f"成功匯入 {success_count} 筆資料。")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯入失敗：{str(e)}")

    def get_current_categories(self):
        """從 QSettings 讀取當前群組名稱 (對應 SettingsDialog 的儲存格式)"""
        # 讀取儲存的 List
        cats = self.settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])

        # 處理 QSettings 可能讀取到字串而非 List 的情況
        if isinstance(cats, str):
            import ast
            try:
                cats = ast.literal_eval(cats)
            except:
                cats = ["家人", "朋友", "同事", "名人", "其他"]

        # 確保回傳的是 List
        return cats if isinstance(cats, list) else ["家人", "朋友", "同事", "名人", "其他"]

    def show_birth_dialog(self):
        """輸入生辰視窗，包含儲存邏輯"""
        dialog = BirthInfoDialog(self)
        if dialog.exec() == QDialog.Accepted:
            birth_data = dialog.get_birth_info()

            # 如果勾選儲存，執行檢查與寫入
            if birth_data.get("save_to_db"):
                if not self.handle_save_user(birth_data):
                    # 如果使用者在重複提示按了取消，這裡就不排盤了嗎？
                    # 依據一般體驗，這裡通常只擋儲存，不擋排盤，但也可以視需求調整。
                    # 目前邏輯：取消儲存仍會繼續排盤。
                    pass

            self.process_chart_calculation(birth_data)

    def handle_save_user(self, data):
        """處理儲存使用者資料 (檢查必填與重複)"""
        # 必填檢查
        if not data["name"].strip():
            QMessageBox.warning(self, "錯誤", "姓名為必填欄位，無法儲存。")
            return False

        # 重復檢查 (Smart Strict: Name+Gender+YMDH)
        is_dup, count = self.db.check_duplicate(
            data["name"], data["gender"],
            data["year"], data["month"], data["day"], data["hour"]
        )

        if is_dup:
            reply = QMessageBox.question(
                self, "資料重複",
                f"發現生辰 (年月日時) 完全相同的資料 {count} 筆。\n是否仍要儲存?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return False

        # 寫入資料庫
        self.db.add_user(data)
        return True

    def get_current_config(self):
        """從 QSettings 讀取當前排盤設定"""
        config = {
            "late_zi_behavior": int(self.settings.value("late_zi_behavior", 0)),
            "leap_month_behavior": int(self.settings.value("leap_month_behavior", 0)),
            "sihua_wu": self.settings.value("sihua_wu", "貪陰右機"),
            "sihua_geng": self.settings.value("sihua_geng", "陽武陰同"),
            "sihua_ren": self.settings.value("sihua_ren", "梁紫左武"),
            "school": self.settings.value("school", "北派"),
            "minimal_stars": self.settings.value("minimal_stars", False, type=bool)
        }
        return config

    def grab_snapshot(self):
        """擷取當前命盤快照"""
        if not self.full_chart_data: return None
        # 擷取整個 chart_widget
        pixmap = self.chart_widget.grab()
        # Ensure the pixmap stores the correct device pixel ratio for High-DPI support
        pixmap.setDevicePixelRatio(self.devicePixelRatioF())
        return pixmap

    def export_chart_image(self, include_drawing=True):
        """匯出命盤圖片"""
        if not self.full_chart_data:
            QMessageBox.warning(self, "提示", "請先進行排盤再匯出。")
            return

        path, _ = QFileDialog.getSaveFileName(self, "匯出命盤圖片", "", "PNG Files (*.png)")
        if not path:
            return

        try:
            # 如果不包含繪圖層，暫時隱藏
            if not include_drawing:
                self.chart_widget.drawing_layer.hide()

            pixmap = self.chart_widget.grab()

            if not include_drawing:
                self.chart_widget.drawing_layer.show()

            if pixmap.save(path, "PNG"):
                QMessageBox.information(self, "成功", "圖片已成功匯出。")
            else:
                QMessageBox.critical(self, "錯誤", "圖片存檔失敗。")
        except Exception as e:
            QMessageBox.critical(self, "錯誤", f"匯出失敗：{str(e)}")

    def push_current_to_slots(self):
        """將當前工作區資料推入 Slot 1，原 Slot 依序後移 (跳過鎖定)"""
        if not self.full_chart_data:
            return

        # 擷取當前狀態
        current_state = SlotState(
            full_chart_data=copy.deepcopy(self.full_chart_data),
            drawing_paths=self.chart_widget.drawing_layer.get_state(),
            ui_state={
                "privacy": {
                    "name": self.cb_name.isChecked(),
                    "birth": self.cb_birth.isChecked(),
                    "part": self.cb_part.isChecked(),
                    "all": self.cb_all.isChecked()
                },
                "daxian_idx": self.get_active_daxian_index(),
                "liunian_year": self.get_active_liunian_year(),
                # 儲存當前 InfoLayer 的動態星曜資料，以便 Slot 恢復時能正確顯示
                "daxian_stars_data": copy.deepcopy(self.chart_widget.info_layer.daxian_stars_data),
                "liunian_stars_data": copy.deepcopy(self.chart_widget.info_layer.liunian_stars_data)
            },
            birth_data=copy.deepcopy(self.current_birth_data),  # 儲存計算後的 birth_data
            snapshot=self.grab_snapshot()
        )

        # 後推邏輯 (跳過鎖定)
        # 找出所有非鎖定的 Slot 索引
        unlocked_indices = [i for i, s in enumerate(self.slots) if not s.is_locked]

        # 從後往前推
        for i in range(len(unlocked_indices) - 1, 0, -1):
            curr_idx = unlocked_indices[i]
            prev_idx = unlocked_indices[i - 1]
            self.slots[curr_idx] = self.slots[prev_idx]

        if unlocked_indices:
            self.slots[unlocked_indices[0]] = current_state

        self.update_slot_buttons()

    def update_slot_buttons(self):
        """更新 Slot 按鈕顯示 (縮圖、文字、鎖定狀態)"""
        for i, slot in enumerate(self.slots):
            btn = self.slot_btns[i]

            # 鎖定樣式
            border_color = "#F44336" if slot.is_locked else ("#2196F3" if not slot.is_empty() else "#999")
            border_style = "solid" if not slot.is_empty() or slot.is_locked else "dashed"
            lock_icon = "🔒 " if slot.is_locked else ""

            if not slot.is_empty():
                # 設定縮圖背景
                if slot.snapshot:
                    # 縮放快照以符合按鈕大小
                    thumb = slot.snapshot.scaled(btn.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                    btn.setIcon(QIcon(thumb))
                    btn.setIconSize(btn.size())

                btn.setText(f"{lock_icon}{slot.get_display_text()}")
                btn.setStyleSheet(f"""
                    SlotButton {{
                        background-color: #fff;
                        border: 2px {border_style} {border_color};
                        border-radius: 4px;
                        color: #000;
                        font-weight: bold;
                        font-size: 10px;
                        text-align: center;
                    }}
                    SlotButton:hover {{ background-color: rgba(33, 150, 243, 0.1); }}
                """)
            else:
                btn.setIcon(QIcon())
                btn.setText(f"Slot {i + 1}\n{lock_icon}(空)")
                btn.setStyleSheet(f"""
                    SlotButton {{
                        background-color: #ddd;
                        border: 1px {border_style} {border_color};
                        border-radius: 4px;
                        color: #666;
                        font-size: 11px;
                        text-align: center;
                    }}
                    SlotButton:hover {{ background-color: #fff; border: 1px solid #666; }}
                """)

    def get_active_daxian_index(self):
        for i, btn in enumerate(self.daxian_btns):
            if btn.isChecked(): return i
        return None

    def get_active_liunian_year(self):
        for btn in self.liunian_btns:
            if btn.isChecked(): return btn.property("year")
        return None

    def on_slot_clicked(self, idx):
        """點擊 Slot 按鈕：與當前工作區對調 (原子交換)"""
        target_slot = self.slots[idx]

        # 如果工作區沒資料，且 Slot 也沒資料，則不動作
        if not self.full_chart_data and target_slot.is_empty():
            return

        # 1. 先拍照 (Snapshot A)：在修改工作區前取得快照
        snapshot_a = self.grab_snapshot()

        # 2. 封裝 (Package A)：備份當前工作區完整狀態
        current_state = SlotState(
            full_chart_data=copy.deepcopy(self.full_chart_data),
            drawing_paths=self.chart_widget.drawing_layer.get_state(),
            ui_state={
                "privacy": {
                    "name": self.cb_name.isChecked(),
                    "birth": self.cb_birth.isChecked(),
                    "part": self.cb_part.isChecked(),
                    "all": self.cb_all.isChecked()
                },
                "daxian_idx": self.get_active_daxian_index(),
                "liunian_year": self.get_active_liunian_year(),
                "daxian_stars_data": copy.deepcopy(self.chart_widget.info_layer.daxian_stars_data),
                "liunian_stars_data": copy.deepcopy(self.chart_widget.info_layer.liunian_stars_data)
            },
            birth_data=copy.deepcopy(self.current_birth_data),  # 儲存計算後的 birth_data
            snapshot=snapshot_a  # 存入剛拍好的快照
        )

        # 3. 讀取 (Package B)：從目標 Slot 取出資料
        # 注意：這裡直接使用 target_slot 引用，稍後會被覆蓋，所以 Package A 已經備份好了

        # 4. 寫入工作區：將 Package B 的資料載入
        self.apply_slot_state(target_slot)

        # 5. 寫入 Slot：將 Package A 的資料存入該 Slot
        self.slots[idx] = current_state

        # 6. 即時更新 UI
        self.update_slot_buttons()

    def on_slot_right_clicked(self, idx):
        """右鍵點擊：清空 Slot"""
        if self.slots[idx].is_locked:
            QMessageBox.warning(self, "提示", "鎖定中的 Slot 無法清空，請先解除鎖定。")
            return

        if not self.slots[idx].is_empty():
            reply = QMessageBox.question(self, "確認", f"確定要清空 Slot {idx + 1} 嗎？",
                                         QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.slots[idx] = SlotState()
                self.update_slot_buttons()

    def on_slot_middle_clicked(self, idx):
        """中鍵點擊：切換鎖定狀態"""
        slot = self.slots[idx]
        if not slot.is_locked:
            # 檢查鎖定上限
            locked_count = sum(1 for s in self.slots if s.is_locked)
            if locked_count >= 3:
                QMessageBox.warning(self, "提示", "最多只能鎖定 3 組 Slot。")
                return
            slot.is_locked = True
        else:
            slot.is_locked = False
        self.update_slot_buttons()

    def apply_slot_state(self, state):
        """將 SlotState 應用到 UI"""
        # 1. 基礎資料賦值
        self.full_chart_data = state.full_chart_data
        self.current_birth_data = state.birth_data
        self.current_birth_year = state.birth_data["year"] if state.birth_data else None

        # 2. 更新繪圖層 (手繪線條)
        self.chart_widget.drawing_layer.set_state(state.drawing_paths)

        # 3. 更新隱私設定 UI
        p = state.ui_state.get("privacy", {})
        self.cb_name.setChecked(p.get("name", False))
        self.cb_birth.setChecked(p.get("birth", False))
        self.cb_part.setChecked(p.get("part", False))
        self.cb_all.setChecked(p.get("all", False))
        self.update_privacy()

        # 4. 根據是否有資料，決定執行「載入」或「清空」
        if self.full_chart_data:
            # --- 情況 A: Slot 有資料，執行載入 ---
            self.chart_widget.set_data_directly(self.full_chart_data)

            # 更新左側面板按鈕 (大限文字)
            self.reset_panel_buttons()
            ming_desc = self.full_chart_data["center_info"].get("ming_line", "")
            self.init_daxian_buttons(ming_desc)

            # 讀取 Slot 存儲的 UI 狀態
            d_idx = state.ui_state.get("daxian_idx")
            l_year = state.ui_state.get("liunian_year")
            daxian_stars_data = state.ui_state.get("daxian_stars_data", {})
            liunian_stars_data = state.ui_state.get("liunian_stars_data", {})

            # 重新計算位置與高亮 (這部分邏輯只在有資料時執行)
            d_pos, d_gan, l_pos, l_gan = None, None, None, None

            if d_idx is not None:
                # 計算大限位置
                info = self.full_chart_data["center_info"]
                birth_ming_idx = self.full_chart_data.get("ming_index", 2)
                is_cw = (info.get("gender") == "男" and info.get("yinyang") == "陽") or \
                        (info.get("gender") == "女" and info.get("yinyang") == "陰")
                d_pos = (birth_ming_idx + d_idx) % 12 if is_cw else (birth_ming_idx - d_idx + 12) % 12
                d_gan = self.full_chart_data["palaces"][d_pos]["gan"]
                self.daxian_btns[d_idx].setChecked(True)
                self.update_liunian_buttons(self.current_start_age + (d_idx * 10))

                if l_year:
                    # 計算流年位置
                    lz_idx = (l_year - 4) % 12
                    l_zhi = ZiweiCalculator.DIZHI[lz_idx]
                    l_gan = ZiweiCalculator.TIANGAN[(l_year - 4) % 10]
                    for i, p in enumerate(self.full_chart_data["palaces"]):
                        if p["zhi"] == l_zhi:
                            l_pos = i
                            break
                    for btn in self.liunian_btns:
                        if btn.property("year") == l_year:
                            btn.setChecked(True)
                            break

            # 更新 InfoLayer 高亮與動態星曜
            self.chart_widget.info_layer.set_highlight(d_pos, d_gan, l_pos, l_gan,
                                                       daxian_stars_data=daxian_stars_data,
                                                       liunian_stars_data=liunian_stars_data)
        else:
            # --- 情況 B: Slot 是空的，執行清空 ---
            self.chart_widget.base_layer.set_data(None)
            self.chart_widget.info_layer.set_center_info({})
            self.chart_widget.info_layer.set_highlight(None, None, None, None, {}, {})
            self.reset_panel_buttons()
            self.current_birth_year = None

    def process_chart_calculation(self, birth_data, push_to_history=True):
        """核心排盤邏輯 (抽離出來供手動輸入與資料庫載入共用)"""
        # 只有在 push_to_history 為 True 時才推入 Slot
        if push_to_history:
            try:
                self.push_current_to_slots()
            except Exception as e:
                print(f"Push to slots failed: {e}")

        # current_birth_data 現在會儲存經過 ZiweiCalculator.calculate_birth_info 處理後的資料
        try:
            config = self.get_current_config()
            # 這裡的 birth_info 包含了 lunar_month, lunar_day, calc_hour 等資訊
            birth_info = ZiweiCalculator.calculate_birth_info(
                birth_data["year"], birth_data["month"], birth_data["day"],
                birth_data["hour"], birth_data["minute"], birth_data.get("is_lunar", False),  # 修正 KeyError
                config=config
            )
            user_name = birth_data.get("name", "").strip()
            birth_info["name"] = user_name if user_name else "匿名"
            birth_info["gender"] = birth_data["gender"]

            self.full_chart_data = ZiweiCalculator.calculate_chart(birth_info, config=config)
            self.current_birth_data = birth_info  # 更新 self.current_birth_data 為處理後的資訊

            self.chart_widget.set_data_directly(self.full_chart_data)
            self.chart_widget.drawing_layer.clear()

            self.current_birth_year = birth_data["year"]
            self.reset_panel_buttons()

            ming_desc = self.full_chart_data["center_info"]["ming_line"]
            self.init_daxian_buttons(ming_desc)
            self.update_privacy()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "程式錯誤", f"發生錯誤：{str(e)}")

    def update_privacy(self):
        self.chart_widget.info_layer.set_privacy(
            self.cb_name.isChecked(),
            self.cb_birth.isChecked(),
            self.cb_part.isChecked(),
            self.cb_all.isChecked()
        )

    def reset_panel_buttons(self):
        for btn in self.daxian_btns: btn.setChecked(False)
        self.clear_liunian_buttons()
        # 清空所有動態高亮與干支，以及動態星曜
        self.chart_widget.info_layer.set_highlight(None, None, None, None,
                                                   daxian_stars_data={}, liunian_stars_data={})

    def clear_liunian_buttons(self):
        self.liunian_group.setExclusive(False)
        for btn in self.liunian_btns:
            btn.setText("")
            btn.setEnabled(False)
            btn.setChecked(False)
        self.liunian_group.setExclusive(True)

    def init_daxian_buttons(self, ming_desc):
        start_age = 2
        if "二局" in ming_desc:
            start_age = 2
        elif "三局" in ming_desc:
            start_age = 3
        elif "四局" in ming_desc:
            start_age = 4
        elif "五局" in ming_desc:
            start_age = 5
        elif "六局" in ming_desc:
            start_age = 6
        self.current_start_age = start_age
        for i in range(10):
            d_start = start_age + (i * 10)
            d_end = d_start + 9
            self.daxian_btns[i].setText(f"{d_start}-{d_end}")

    def update_liunian_buttons(self, start_age):  # 修正：將此函數移回 MainWindow 類別
        if not self.current_birth_year: return
        self.liunian_group.setExclusive(False)
        for btn in self.liunian_btns:
            btn.setChecked(False)
            btn.setEnabled(True)
        self.liunian_group.setExclusive(True)
        for i in range(10):
            current_age = start_age + i
            year = self.current_birth_year + current_age - 1
            btn = self.liunian_btns[i]
            btn.setText(f"{year}")
            btn.setProperty("year", year)

    def on_daxian_clicked(self, index):
        sender_btn = self.daxian_btns[index]
        is_checked = sender_btn.isChecked()

        if is_checked:
            # 互斥處理
            for i, btn in enumerate(self.daxian_btns):
                if i != index: btn.setChecked(False)

            # 1. 計算大限命宮位置 (d_pos)
            birth_ming_idx = self.full_chart_data.get("ming_index", 2)
            info = self.full_chart_data["center_info"]
            is_cw = (info.get("gender") == "男" and info.get("yinyang") == "陽") or \
                    (info.get("gender") == "女" and info.get("yinyang") == "陰")
            d_pos = (birth_ming_idx + index) % 12 if is_cw else (birth_ming_idx - index + 12) % 12

            # 2. 取得大限天干與「大限命宮地支」
            d_gan = self.full_chart_data["palaces"][d_pos]["gan"]
            d_zhi = self.full_chart_data["palaces"][d_pos]["zhi"]

            # 3. 準備計算參數
            natal = self.current_birth_data
            hr_idx = (natal["calc_hour"] + 1) // 2 % 12

            # 4. 呼叫邏輯層
            dynamic_stars = ZiweiCalculator.calculate_dynamic_stars(
                self.full_chart_data["palaces"],
                daxian_gan=d_gan,
                daxian_zhi=d_zhi, # 修正：傳入大限命宮地支
                natal_month=natal["lunar_month"],
                natal_day=natal["lunar_day"],
                natal_hour_idx=hr_idx
            )

            # 5. 更新 UI (修正參數傳遞方式，避免 TypeError)
            # 根據你原始程式碼，前四個參數應為位置參數：d_idx, d_gan, l_idx, l_gan
            self.chart_widget.info_layer.set_highlight(
                d_pos, d_gan, None, None,
                daxian_stars_data=dynamic_stars["daxian_stars"],
                liunian_stars_data={}
            )

            # 更新流年按鈕文字
            self.update_liunian_buttons(self.current_start_age + (index * 10))
        else:
            self.reset_panel_buttons()

    def on_liunian_clicked(self):
        sender = self.sender()
        year = sender.property("year")
        if not year: return

        # 1. 準備本命基礎資訊
        natal = self.current_birth_data
        hr_idx = (natal["calc_hour"] + 1) // 2 % 12

        # 2. 計算流年干支與位置
        lz_idx = (year - 4) % 12
        l_zhi = ZiweiCalculator.DIZHI[lz_idx]
        l_gan = ZiweiCalculator.TIANGAN[(year - 4) % 10]

        l_pos = -1
        for i, p in enumerate(self.full_chart_data["palaces"]):
            if p["zhi"] == l_zhi:
                l_pos = i
                break

        # 3. 獲取當前大限資訊 (如果有的話)
        d_idx_in_ui = self.get_active_daxian_index()
        d_pos, d_gan, d_zhi = None, None, None

        if d_idx_in_ui is not None:
            # 計算大限命宮在 12 宮位中的實際索引
            birth_ming_idx = self.full_chart_data.get("ming_index", 2)
            info = self.full_chart_data["center_info"]
            is_cw = (info.get("gender") == "男" and info.get("yinyang") == "陽") or \
                    (info.get("gender") == "女" and info.get("yinyang") == "陰")
            d_pos = (birth_ming_idx + d_idx_in_ui) % 12 if is_cw else (birth_ming_idx - d_idx_in_ui + 12) % 12
            d_gan = self.full_chart_data["palaces"][d_pos]["gan"]
            d_zhi = self.full_chart_data["palaces"][d_pos]["zhi"]

        # 4. 呼叫邏輯層 (移除 natal_yinyangender 等導致報錯的參數)
        dynamic_stars = ZiweiCalculator.calculate_dynamic_stars(
            self.full_chart_data["palaces"],
            daxian_gan=d_gan,
            daxian_zhi=d_zhi,
            liunian_gan=l_gan,
            liunian_zhi=l_zhi,
            natal_month=natal["lunar_month"],
            natal_day=natal["lunar_day"],
            natal_hour_idx=hr_idx
        )

        # 5. 處理 UI 切換邏輯
        current_l_idx = self.chart_widget.info_layer.liunian_idx
        if current_l_idx == l_pos:
            # 取消流年，只保留大限
            self.chart_widget.info_layer.set_highlight(
                d_pos, d_gan, None, None,
                daxian_stars_data=dynamic_stars["daxian_stars"],
                liunian_stars_data={}
            )
            self.liunian_group.setExclusive(False)
            sender.setChecked(False)
            self.liunian_group.setExclusive(True)
        else:
            # 同時顯示大限與流年
            self.chart_widget.info_layer.set_highlight(
                d_pos, d_gan, l_pos, l_gan,
                daxian_stars_data=dynamic_stars["daxian_stars"],
                liunian_stars_data=dynamic_stars["liunian_stars"]
            )

    def closeEvent(self, event):
        """當視窗關閉時，儲存目前的視窗幾何資訊"""
        settings = QSettings("MyZiweiApp", "Settings")
        # saveGeometry 會將視窗的大小、位置、是否最大化等資訊打包成二進位資料
        settings.setValue("window_geometry", self.saveGeometry())

        # 確保資料寫入硬碟
        settings.sync()

        # 繼續執行原本的關閉程序
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    settings = QSettings("MyZiweiApp", "Settings")
    offset = int(settings.value("font_offset", 0))  # 取得偏移量
    font = app.font()
    font.setFamily("Microsoft JhengHei")
    font.setPointSize(10 + offset) # 在基礎 10 號字上加偏移
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()