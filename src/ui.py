#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZWM紫微斗數排盤繪圖核心 (UI Core) - 整合重構版
整合：動態三層四化、宮位互動功能、保留原視覺樣式。
"""

import math
from PySide6.QtCore import Qt, QRect, QPoint, QPointF,  QEvent, Signal
from PySide6.QtGui import (
    QPainter, QFont, QPen, QColor, QPixmap,
    QPainterPath, QTransform, QBrush
)
from logic import ZiweiCalculator
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QWidget, QDialog, QDialogButtonBox, QFormLayout, QSpinBox, QComboBox,
    QRadioButton, QButtonGroup, QHBoxLayout, QLabel, QGridLayout, QLineEdit,
    QPushButton, QMessageBox, QSizePolicy, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QHeaderView, QCheckBox, QAbstractItemView, QFrame,
    QGroupBox, QTabWidget, QInputDialog
)

def get_font_offset():
    settings = QSettings("MyZiweiApp", "Settings")
    return int(settings.value("font_offset", 0))
def get_stars_per_column():
    settings = QSettings("MyZiweiApp", "Settings")
    return int(settings.value("stars_per_column", 2)) # 預設為2

class VerticalTextPainter:
    """負責繪製直排文字，保留原有的間距邏輯"""

    @staticmethod
    def draw_text(painter, x, y, text, font, color=Qt.black, spacing=18):
        painter.setFont(font)
        painter.setPen(color)
        current_y = y
        for char in text:
            if char.strip() == "":
                current_y += spacing / 2
                continue
            # 修正：確保文字在 20x20 的範圍內置中繪製
            painter.drawText(int(x - 10), int(current_y), 20, 20, Qt.AlignCenter, char)
            current_y += spacing


class LayoutParams:
    """計算排盤格子的通用參數，與原版保持一致"""
    MARGIN = 30
    COORDS = [
        (3, 2), (3, 1), (3, 0), (2, 0), (1, 0), (0, 0),
        (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3)
    ]

    @staticmethod
    def get_cell_rect(total_w, total_h, index):
        eff_w = total_w - (2 * LayoutParams.MARGIN)
        eff_h = total_h - (2 * LayoutParams.MARGIN)
        cell_w, cell_h = eff_w / 4, eff_h / 4
        row, col = LayoutParams.COORDS[index]
        x = LayoutParams.MARGIN + (col * cell_w)
        y = LayoutParams.MARGIN + (row * cell_h)
        return QRect(int(x), int(y), int(cell_w), int(cell_h))

    @staticmethod
    def get_center_rect(total_w, total_h):
        eff_w = total_w - (2 * LayoutParams.MARGIN)
        eff_h = total_h - (2 * LayoutParams.MARGIN)
        cell_w, cell_h = eff_w / 4, eff_h / 4
        x, y = LayoutParams.MARGIN + cell_w, LayoutParams.MARGIN + cell_h
        return QRect(int(x), int(y), int(cell_w * 2), int(cell_h * 2))

    @staticmethod
    def get_outward_direction(index):
        """判斷宮位向外噴射箭頭的方向"""
        row, col = LayoutParams.COORDS[index]
        if row == 0: return "UP"
        if row == 3: return "DOWN"
        if col == 0: return "LEFT"
        if col == 3: return "RIGHT"
        return "UP"


class BaseLayer(QWidget):
    """底圖層：負責宮位、本命星曜、動態四化與任務2的圖形顯示"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.full_data = None
        self.selected_idx = None  # 任務2：目前選中的宮位索引
        self.laiyin_idx = -1  # 新增
        self.shen_idx = -1  # 新增
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)  # 開啟滑鼠事件

    def set_data(self, full_data):
        self.full_data = full_data  # 先賦值
        self.selected_idx = None  # 重置選取

        if not full_data:
            # 如果是 None，重置關鍵索引並直接更新畫面
            self.laiyin_idx = -1
            self.shen_idx = -1
            self.update()  # 這會觸發 paintEvent 執行 _draw_empty_chart
            return

        # 如果有資料，才讀取索引
        self.laiyin_idx = full_data.get("laiyin_idx", -1)
        self.shen_idx = full_data.get("shen_idx", -1)
        self.update()

    def mousePressEvent(self, event):
        if not self.full_data or event.button() != Qt.LeftButton:
            return
        w, h = self.width(), self.height()
        pos = event.position().toPoint()
        clicked_idx = None
        for i in range(12):
            if LayoutParams.get_cell_rect(w, h, i).contains(pos):
                clicked_idx = i
                break
        if clicked_idx is not None:
            self.selected_idx = None if self.selected_idx == clicked_idx else clicked_idx
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        painter.fillRect(self.rect(), Qt.white)

        w, h = self.width(), self.height()
        if not self.full_data:
            self._draw_empty_chart(painter, w, h)
            return

        info_layer = self.parent().info_layer
        dx_gan = info_layer.dx_gan
        ln_gan = info_layer.ln_gan
        b_gan = self.full_data["center_info"].get("birth_year_gan", "")
        sihua_table = self.full_data.get("sihua_table")
        school = self.full_data.get("config", {}).get("school", "北派")

        # 1. 繪製十二宮位
        for i, palace_data in enumerate(self.full_data["palaces"]):
            rect = LayoutParams.get_cell_rect(w, h, i)

            # --- 美化：選中宮位填滿淡鵝黃色 ---
            if self.selected_idx == i:
                painter.fillRect(rect, QColor(255, 255, 200))  # 淡鵝黃色

            # BaseLayer 只繪製本命星曜，不處理動態流曜
            self._draw_single_palace(painter, rect, palace_data, b_gan, dx_gan, ln_gan, sihua_table, i)

        # 2. 繪製中宮邊框
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.drawRect(LayoutParams.get_center_rect(w, h))

        # 3. 繪製互動標示 (任務 2)
        if self.selected_idx is not None:
            if school == "北派":
                self._draw_beipai_flying_sihua(painter, w, h, self.selected_idx, sihua_table)
            else:
                self._draw_nanpai_sanfang(painter, w, h, self.selected_idx)

        # --- 修正 1：北派自化箭頭與飛星並存 ---
        if school == "北派":
            self._draw_self_transformations(painter)

    def _get_inner_midpoint(self, rect, index):
        """
        計算宮位指向中宮的連線點。
        邊位宮位取邊線中點，角位宮位（2, 5, 8, 11）取內側頂點。
        """
        # 根據 LayoutParams.COORDS 判斷宮位在 4x4 網格中的行列
        row, col = LayoutParams.COORDS[index]

        # --- 處理四個角落宮位 (寅申巳亥) ---
        if index == 2:  # 左下角 (3, 0) -> 取右上頂點
            return QPointF(rect.right(), rect.top())
        if index == 5:  # 左上角 (0, 0) -> 取右下頂點
            return QPointF(rect.right(), rect.bottom())
        if index == 8:  # 右上角 (0, 3) -> 取左下頂點
            return QPointF(rect.left(), rect.bottom())
        if index == 11:  # 右下角 (3, 3) -> 取左上頂點
            return QPointF(rect.left(), rect.top())

        # --- 處理其餘八個邊位宮位 ---
        if row == 3: return QPointF(rect.center().x(), rect.top())  # 下排，取上邊中點
        if row == 0: return QPointF(rect.center().x(), rect.bottom())  # 上排，取下邊中點
        if col == 0: return QPointF(rect.right(), rect.center().y())  # 左排，取右邊中點
        if col == 3: return QPointF(rect.left(), rect.center().y())  # 右排，取左邊中點

        return rect.center()

    def _draw_empty_chart(self, painter, w, h):
        painter.setPen(QColor(200, 200, 200))
        for i in range(12):
            painter.drawRect(LayoutParams.get_cell_rect(w, h, i))
        painter.setPen(QColor(100, 100, 100))
        painter.drawRect(LayoutParams.get_center_rect(w, h))

    # BaseLayer 的 _draw_single_palace 只繪製本命星曜
    def _draw_single_palace(self, painter, rect, data, b_gan, d_gan, l_gan, table, index):

        school = self.full_data.get("config", {}).get("school", "北派")
        # --- 新增：來因宮/身宮標籤 ---
        label_text = ""
        if school == "北派" and index == self.laiyin_idx:
            label_text = "來因"
        elif school == "南派" and index == self.shen_idx:
            label_text = "身宮"

        # 繪製邊框
        painter.setPen(QPen(QColor(100, 100, 100), 1))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect)

        # 宮位名稱與干支 (維持原樣)
        font_name = QFont("Microsoft JhengHei", 12 + get_font_offset(), QFont.Bold)
        font_ganzhi = QFont("Microsoft JhengHei", 12 + get_font_offset())
        VerticalTextPainter.draw_text(painter, rect.right() - 15, rect.top() + 10, data.get("name", ""), font_name)
        VerticalTextPainter.draw_text(painter, rect.right() - 15, rect.bottom() - 40,
                                      f"{data.get('gan', '')}{data.get('zhi', '')}", font_ganzhi, QColor(80, 80, 80))

        # --- 新增：繪製長生十二神 (緊貼底部) ---
        changsheng = data.get("changsheng", "")
        if changsheng:
            font_cs = QFont("Microsoft JhengHei", 10 + get_font_offset())
            cs_spacing = 16
            # 動態計算起始 Y 座標，確保單字或雙字都能緊貼底部
            cs_start_y = rect.bottom() - 5 - (len(changsheng) * cs_spacing)
            VerticalTextPainter.draw_text(painter, rect.right() - 35, cs_start_y, changsheng, font_cs,
                                          QColor(120, 120, 120), spacing=cs_spacing)

        # 繪製來因宮/身宮
        if label_text:
            font_label = QFont("Microsoft JhengHei", 10+ get_font_offset(), QFont.Bold)
            painter.setFont(font_label)
            painter.setPen(QColor(100, 0, 150))  # 紫色
            painter.setBrush(QColor(240, 220, 255, 180))  # 淡紫色半透明背景
            # 計算文字大小
            fm = painter.fontMetrics()
            text_width = fm.horizontalAdvance(label_text) / 2
            text_height = fm.height() * 2
            # 座標: 擺在宮位名之下，高度一半
            label_x = rect.right() - 20
            label_y = (rect.bottom() + rect.top()) // 2 + get_font_offset()
            padding = 2  # 框的內邊距
            rounded_rect = QRect(
                int(label_x - padding - 2),
                int(label_y - text_height / 2 - padding),
                int(text_width + padding * 2),
                int(text_height - get_font_offset())
            )

            painter.drawRoundedRect(rounded_rect, 5, 5)  # 圓弧半徑 5
            painter.setBrush(Qt.NoBrush)  # 不填充文字背景
            VerticalTextPainter.draw_text(
                painter, label_x + text_width // 2 - 1, label_y - text_height // 2 - 2, label_text, font_label,
                QColor(100, 0, 150, 150), 15
            )

        # --- 星曜繪製核心邏輯 (只繪製本命星曜) ---
        natal_stars = []
        for star_obj in data.get("stars", []):
            if isinstance(star_obj, str):
                natal_stars.append({"name": star_obj, "type": "main", "brightness": ""})
            else:
                natal_stars.append(star_obj)

        colors = {"紫微": QColor(138, 43, 226), "天府": QColor(138, 43, 226), "七殺": QColor(200, 0, 0),
                  "破軍": QColor(200, 0, 0), "貪狼": QColor(200, 0, 0), "祿存": QColor(218, 165, 32)}

        # 定義字體
        font_main = QFont("Microsoft JhengHei", 12 + get_font_offset(), QFont.Bold)
        font_minor = QFont("Microsoft JhengHei", 11 + get_font_offset())  # 雜曜用 11 號字
        font_bright = QFont("Microsoft JhengHei", 9 + get_font_offset())  # 廟旺用 9 號字

        # 起始 X 座標 (從右往左排，避開宮位名稱)
        current_x = rect.right() - 45

        for star_obj in natal_stars:
            # 1. 解析資料 (相容舊格式)
            s_name = star_obj.get("name", "")
            s_type = star_obj.get("type", "main")
            s_bright = star_obj.get("brightness", "")

            # 2. 根據類型決定字體與間距
            if s_type == "minor":
                curr_font = font_minor
                col_step = 16+ get_font_offset()  # 雜曜佔用的寬度較窄
                spacing = 15  # 雜曜字與字的間距
            else:
                curr_font = font_main
                col_step = 18 + get_font_offset() # 主星/輔星維持原寬度
                spacing = 18

            # 3. 安全檢查：如果快要撞到左邊界，強制縮小
            if current_x < rect.left() + 15:
                curr_font.setPointSize(curr_font.pointSize() - 1)
                col_step -= 2
            # 上下文字間距
            spacing += get_font_offset()
            # 4. 繪製星曜文字
            c = colors.get(s_name, QColor(0, 0, 128))
            VerticalTextPainter.draw_text(painter, current_x, rect.top() + 10, s_name, curr_font, c, spacing=spacing)

            # 5. 繪製廟旺 (如果有)
            y_after_star = rect.top() + 10 + (len(s_name) * spacing)
            if s_bright and school == "南派":
                painter.setFont(font_bright)
                painter.setPen(QColor(120, 80, 40))
                painter.drawText(int(current_x - 10), int(y_after_star - 2), 20, 20, Qt.AlignCenter, s_bright)
                y_after_star += 12  # 有畫亮度才需要多往下推
            else:
                # 如果是北派，y_after_star 就維持在星曜正下方，四化標籤會緊貼星曜
                y_after_star += 2

            # 6. 繪製四化疊加 (傳入動態計算的 y 座標)
            # 生年四化無論南北派都顯示
            self._draw_sihua_stack(painter, current_x, y_after_star + 5, s_name, b_gan, d_gan, l_gan, table)

            # 7. 座標左移，準備畫下一顆星
            current_x -= col_step

    def _draw_sihua_stack(self, painter, x, start_y, star_name, b_gan, d_gan, l_gan, table):
        active_sh = []
        # 1. 生年 (紅) - 無論南北派都顯示
        sh_b = ZiweiCalculator.get_sihua(b_gan, star_name, table)
        if sh_b: active_sh.append({"val": sh_b, "color": QColor(220, 0, 0)})

        # 只有南派才顯示限流四化疊加
        school = self.full_data.get("config", {}).get("school", "北派")
        if school == "南派":
            if d_gan:
                sh_d = ZiweiCalculator.get_sihua(d_gan, star_name, table)
                if sh_d: active_sh.append({"val": sh_d, "color": QColor(0, 80, 220)})
            if l_gan:
                sh_l = ZiweiCalculator.get_sihua(l_gan, star_name, table)
                if sh_l: active_sh.append({"val": sh_l, "color": QColor(0, 150, 0)})

        for s_idx, sh in enumerate(active_sh):
            badge_y = start_y + (s_idx * 22)
            rect_badge = QRect(int(x - 10), int(badge_y), 20, 20)
            painter.setBrush(QBrush(sh["color"]))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect_badge, 4, 4)
            painter.setPen(Qt.white)
            painter.setFont(QFont("Microsoft JhengHei", 10+ get_font_offset(), QFont.Bold))
            painter.drawText(rect_badge, Qt.AlignCenter, sh["val"])
        painter.setBrush(Qt.NoBrush)

    def _draw_beipai_flying_sihua(self, painter, w, h, idx, table):
        """北派飛星標示"""
        palace_gan = self.full_data["palaces"][idx]["gan"]
        font_sihua = QFont("Microsoft JhengHei", 11+ get_font_offset(), QFont.Bold)
        painter.setFont(font_sihua)

        # --- 新增：定義四化顏色映射 ---
        sihua_colors = {
            "祿": QColor(0, 150, 0),  # 祿：綠色
            "權": QColor(0, 0, 200),  # 權：藍色
            "科": QColor(150, 0, 150),  # 科：紫色
            "忌": QColor(200, 0, 0)  # 忌：紅色
        }
        # -----------------------------

        # 遍歷所有宮位，找出飛入的星曜
        for i, p in enumerate(self.full_data["palaces"]):
            # 收集該宮位所有來自「選中宮位」的飛化
            flying_sihuas_in_this_palace = []
            for star_obj in p["stars"]:
                star_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                sh = ZiweiCalculator.get_sihua(palace_gan, star_name, table)
                if sh:
                    flying_sihuas_in_this_palace.append(sh)

            # 如果這個宮位有來自選中宮位的飛化，則繪製
            if flying_sihuas_in_this_palace:
                rect = LayoutParams.get_cell_rect(w, h, i)

                # 基準繪製點 (例如宮位左上角，稍微偏移)
                base_x = rect.left() + 5
                base_y = rect.top() + 18  # 初始Y座標

                # 每個標記的垂直間距
                line_height = painter.fontMetrics().height() + 2  # 字體高度 + 一點點間距

                # 垂直堆疊繪製
                for j, sh_val in enumerate(flying_sihuas_in_this_palace):
                    text_to_draw = f"飛{sh_val}"
                    current_y = base_y + (j * line_height)

                    # --- 根據四化值設定顏色 ---
                    painter.setPen(sihua_colors.get(sh_val, QColor(150, 0, 150)))  # 預設為紫色
                    # --------------------------

                    painter.drawText(base_x, current_y, text_to_draw)

    def _draw_nanpai_sanfang(self, painter, w, h, idx):
        """美化：南派三方四正虛線 (菱形連線)"""
        opp_idx = (idx + 6) % 12
        sf1_idx = (idx + 4) % 12
        sf2_idx = (idx + 8) % 12

        # 取得四個宮位的內側中點
        p_src = self._get_inner_midpoint(LayoutParams.get_cell_rect(w, h, idx), idx)
        p_opp = self._get_inner_midpoint(LayoutParams.get_cell_rect(w, h, opp_idx), opp_idx)
        p_sf1 = self._get_inner_midpoint(LayoutParams.get_cell_rect(w, h, sf1_idx), sf1_idx)
        p_sf2 = self._get_inner_midpoint(LayoutParams.get_cell_rect(w, h, sf2_idx), sf2_idx)

        pen = QPen(QColor(180, 180, 180), 1.5, Qt.DashLine)
        painter.setPen(pen)

        # 1. 主連線：本宮對沖、本宮至三方
        painter.drawLine(p_src, p_opp)
        painter.drawLine(p_src, p_sf1)
        painter.drawLine(p_src, p_sf2)

        # 2. 補全連線：三方互連
        painter.drawLine(p_sf2, p_sf1)

    def _draw_self_transformations(self, painter):
        palaces = self.full_data["palaces"]
        w, h = self.width(), self.height()
        arrow_pen = QPen(QColor(0, 0, 255), 1.5)
        font_sihua = QFont("Microsoft JhengHei", 11+ get_font_offset(), QFont.Bold)
        sihua_table = self.full_data.get("sihua_table")

        # 用來儲存中宮自化的任務清單
        center_tasks = []

        for i, p in enumerate(palaces):
            rect = LayoutParams.get_cell_rect(w, h, i)
            palace_gan = p["gan"]

            # 1. 處理向外的箭頭 (這部分通常不會重疊，維持原樣即可)
            direction = LayoutParams.get_outward_direction(i)
            out_sihuas = []
            for star_obj in p["stars"]:
                star_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                sihua = ZiweiCalculator.get_sihua(palace_gan, star_name, sihua_table)
                if sihua: out_sihuas.append(sihua)

            if out_sihuas:
                self._draw_arrow_out(painter, rect, direction, "".join(out_sihuas), arrow_pen, font_sihua, i)

            # 2. 處理中宮自化 (收集任務，不立刻畫)
            opp_idx = (i + 6) % 12
            in_sihuas = []
            for star_obj in palaces[opp_idx]["stars"]:
                star_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                sihua = ZiweiCalculator.get_sihua(palace_gan, star_name, sihua_table)
                if sihua: in_sihuas.append(sihua)

            if in_sihuas:
                # 儲存參數：(來源矩形, 目標矩形, 文字, 索引)
                center_tasks.append((LayoutParams.get_cell_rect(w, h, opp_idx), rect, "".join(in_sihuas), i))

        # --- 分層渲染核心 ---
        # 第一遍：只畫所有中宮的「線條」
        for task in center_tasks:
            self._draw_arrow_in_center_only(painter, *task, arrow_pen, font_sihua, draw_mode="line")

        # 第二遍：只畫所有中宮的「文字方塊」
        for task in center_tasks:
            self._draw_arrow_in_center_only(painter, *task, arrow_pen, font_sihua, draw_mode="text")

    def _draw_arrow_out(self, painter, rect, direction, text, pen, font, index):
        painter.save();
        painter.setPen(pen);
        painter.setFont(font)
        line_len, gap, margin = 25, 4, 2
        start_pt, end_pt = QPointF(), QPointF()
        if direction == "UP":
            start_pt = QPointF(float(rect.center().x()), float(rect.top()));
            end_pt = start_pt + QPointF(0, -line_len)
        elif direction == "DOWN":
            start_pt = QPointF(float(rect.center().x()), float(rect.bottom()));
            end_pt = start_pt + QPointF(0, line_len)
        elif direction == "LEFT":
            start_pt = QPointF(float(rect.left()), float(rect.center().y()));
            end_pt = start_pt + QPointF(-line_len, 0)
        elif direction == "RIGHT":
            start_pt = QPointF(float(rect.right()), float(rect.center().y()));
            end_pt = start_pt + QPointF(line_len, 0)
        path = QPainterPath();
        path.moveTo(start_pt);
        path.lineTo(end_pt);
        self._draw_arrow_head(path, start_pt, end_pt);
        painter.drawPath(path)
        fm = painter.fontMetrics();
        w_text, h_text = fm.horizontalAdvance(text), fm.height()
        tx, ty = end_pt.x(), end_pt.y()
        if index in [1, 2, 5, 6]:
            if direction == "UP":
                tx, ty = start_pt.x() - gap - w_text, start_pt.y() - margin - h_text
            elif direction == "DOWN":
                tx, ty = start_pt.x() - gap - w_text, start_pt.y() + margin
        elif index in [0, 11, 7, 8]:
            if direction == "UP":
                tx, ty = start_pt.x() + gap, start_pt.y() - margin - h_text
            elif direction == "DOWN":
                tx, ty = start_pt.x() + gap, start_pt.y() + margin
        elif index in [4, 9]:
            if direction == "LEFT":
                tx, ty = start_pt.x() - margin - w_text, start_pt.y() - gap - h_text
            elif direction == "RIGHT":
                tx, ty = start_pt.x() + margin, start_pt.y() - gap - h_text
        elif index in [3, 10]:
            if direction == "LEFT":
                tx, ty = start_pt.x() - margin - w_text, start_pt.y() + gap
            elif direction == "RIGHT":
                tx, ty = start_pt.x() + margin, start_pt.y() + gap
        painter.setPen(QColor(0, 0, 255));
        painter.drawText(int(tx), int(ty + fm.ascent()), text);
        painter.restore()

    def _draw_arrow_in_center_only(self, painter, from_rect, to_rect, text, index, pen, font, draw_mode="both"):
        painter.save()
        start_pt, end_pt = QPointF(from_rect.center()), QPointF(to_rect.center())
        w, h = from_rect.width() / 2, from_rect.height() / 2
        vec = end_pt - start_pt
        length = math.sqrt(vec.x() ** 2 + vec.y() ** 2)
        if length == 0: painter.restore(); return
        unit_vec = vec / length

        text_x_shift, text_y_shift = 0, 0
        # 你的座標修正邏輯 (index 已經正確傳入)
        if index in [2, 3, 4, 5]:
            start_pt -= QPointF(float(w), 0);
            end_pt += QPointF(float(w), 0);
            text_x_shift = -10 * len(text)
        if index in [8, 9, 10, 11]:
            start_pt += QPointF(float(w), 0);
            end_pt -= QPointF(float(w), 0);
            text_x_shift = 10 * len(text)
        if index in [11, 0, 1, 2]:
            start_pt += QPointF(0, float(h));
            end_pt -= QPointF(0, float(h));
            text_y_shift = 10
        if index in [5, 6, 7, 8]:
            start_pt -= QPointF(0, float(h));
            end_pt += QPointF(0, float(h));
            text_y_shift = -10

        # --- 繪製線條階段 ---
        if draw_mode in ["both", "line"]:
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(start_pt + unit_vec * 20)
            path.lineTo(end_pt)
            # 你的箭頭修正邏輯
            self._draw_arrow_head(path, end_pt, start_pt + unit_vec * 20)
            painter.drawPath(path)

        # --- 繪製文字階段 ---
        if draw_mode in ["both", "text"]:
            painter.setBrush(QColor(0, 0, 255))
            painter.setPen(Qt.NoPen)
            painter.setFont(font)  # 這裡現在會正確拿到 QFont 了
            txt_rect = QRect(0, 0, 20 * len(text), 20)
            txt_rect.moveCenter((start_pt + QPointF(text_x_shift, text_y_shift)).toPoint())
            painter.drawRoundedRect(txt_rect, 4, 4)
            painter.setPen(Qt.white)
            painter.drawText(txt_rect, Qt.AlignCenter, text)

        painter.restore()

    def _draw_arrow_head(self, path, start, end):
        angle = math.atan2(end.y() - start.y(), end.x() - start.x());
        arrow_size = 6
        p1 = end - QPointF(math.cos(angle - math.pi / 6) * arrow_size, math.sin(angle - math.pi / 6) * arrow_size)
        p2 = end - QPointF(math.cos(angle + math.pi / 6) * arrow_size, math.sin(angle + math.pi / 6) * arrow_size)
        path.moveTo(end);
        path.lineTo(p1);
        path.moveTo(end);
        path.lineTo(p2)


#  --- Layer 1: Info Layer (資訊層) ---
class InfoLayer(QWidget):
    """資訊層：負責中宮文字顯示、隱私遮蔽、大限流年宮位標籤及流曜"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.center_info = {}
        self.dx_gan = None
        self.ln_gan = None
        self.daxian_idx = None
        self.liunian_idx = None
        self.hide_name = self.hide_birth = self.hide_part = self.hide_all = False
        self.palace_names = ['命', '兄', '夫', '子', '財', '疾', '遷', '奴', '官', '田', '福', '父']
        self.setAttribute(Qt.WA_TransparentForMouseEvents)

        # --- 新增：儲存動態星曜資料 ---
        self.daxian_stars_data = {}
        self.liunian_stars_data = {}
        # -----------------------------

    def set_center_info(self, info):
        self.center_info = info
        self.update()

    def set_privacy(self, n, b, p, a):
        self.hide_name, self.hide_birth, self.hide_part, self.hide_all = n, b, p, a
        self.update()

    def set_highlight(self, d_idx, d_gan, l_idx, l_gan, daxian_stars_data=None, liunian_stars_data=None):
        """由 Main 層呼叫，更新當前選中的大限與流年狀態及流曜資料"""
        self.daxian_idx, self.dx_gan = d_idx, d_gan
        self.liunian_idx, self.ln_gan = l_idx, l_gan

        # --- 更新動態星曜資料 ---
        self.daxian_stars_data = daxian_stars_data if daxian_stars_data is not None else {}
        self.liunian_stars_data = liunian_stars_data if liunian_stars_data is not None else {}
        # --------------------------

        # 通知 BaseLayer 重繪 (BaseLayer 不再繪製動態星曜，但仍需更新以反映其他變化)
        self.parent().base_layer.update()
        self.update()  # InfoLayer 自身也需要更新來繪製流曜

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        w, h = self.width(), self.height()
        center_rect = LayoutParams.get_center_rect(w, h)

        # 1. 繪製中宮文字 (含 Halo 效果)
        if self.center_info and not self.hide_all:
            self._draw_center_text_with_halo(painter, center_rect)

        # 2. 繪製大限宮位標籤及流曜 (藍色，左下角)
        if self.daxian_idx is not None:
            # 傳遞該宮位的大限流曜資料
            self._draw_limit_labels_and_stars(painter, w, h, self.daxian_idx, "大", QColor(0, 80, 220), "bottom-left", self.daxian_stars_data)

        # 3. 繪製流年宮位標籤及流曜 (綠色，底部置中)
        if self.liunian_idx is not None:
            # 傳遞該宮位的流年流曜資料
            self._draw_limit_labels_and_stars(painter, w, h, self.liunian_idx, "流", QColor(0, 120, 0), "bottom-center", self.liunian_stars_data)

    # 新增函數：繪製宮位標籤及相關的動態星曜
    def _draw_limit_labels_and_stars(self, painter, w, h, highlight_idx, prefix, color, position,
                                     all_dynamic_stars_dict):
        font = QFont("Microsoft JhengHei", 11+ get_font_offset(), QFont.Bold)
        painter.setFont(font)
        painter.setPen(color)

        school = self.parent().base_layer.full_data.get("config", {}).get("school", "北派")

        for i, name_char in enumerate(self.palace_names):
            target_idx = (highlight_idx - i + 12) % 12
            rect = LayoutParams.get_cell_rect(w, h, target_idx)
            text = f"{prefix}{name_char}"

            # 1. 獲取該宮位的動態星曜
            dynamic_stars_for_this_palace = all_dynamic_stars_dict.get(target_idx, [])

            # 2. 計算標籤位置 (大命、流兄等)
            label_x, label_y = 0, 0
            if position == "bottom-left":
                label_x = int(rect.left() + 5)
                label_y = int(rect.bottom() - 5)
            elif position == "bottom-center":
                fw = painter.fontMetrics().horizontalAdvance(text)
                label_x = int(rect.left() + (rect.width() - fw) / 2)
                label_y = int(rect.bottom() - 5)

            # 繪製標籤
            painter.drawText(label_x, label_y, text)

            # 3. 繪製動態流曜 (南派)
            if dynamic_stars_for_this_palace and school == "南派":
                filtered_stars = [
                    s for s in dynamic_stars_for_this_palace
                    if "地空" not in s.get("name", "") and "地劫" not in s.get("name", "")
                ]

                if not filtered_stars:  # 如果過濾後沒星星了就跳過
                    continue

                star_font = QFont("Microsoft JhengHei", 10 + get_font_offset())
                painter.setFont(star_font)

                # 設定起始 X 座標 (標籤文字後方留 5 像素間距)
                base_star_x = label_x + painter.fontMetrics().horizontalAdvance(text) +10
                star_line_height = painter.fontMetrics().height()  # 稍微縮減行距讓排版緊湊
                column_width = 30  # 設定每一列的寬度 (足以容納兩個中文字)

                stars_per_col = get_stars_per_column()
                for idx, star_obj in enumerate(filtered_stars):
                    # --- 修改點 2：計算兩列排版座標 ---
                    col = idx // stars_per_col  # 每 stars_per_col 顆星換一列 (0,0,1,1,2,2...)
                    row = idx % stars_per_col  # 0 是下層, 1 是上層

                    draw_x = base_star_x + (col * column_width)
                    draw_y = label_y - (row * star_line_height)

                    star_name = star_obj.get("name", "")
                    display_star_name = star_name[1:] if star_name.startswith(('大', '年')) else star_name

                    # 繪製星曜名稱
                    painter.setPen(color)
                    painter.drawText(draw_x, draw_y, display_star_name)

                # 恢復字體以便繪製下一個宮位標籤
                painter.setFont(font)

    def _draw_center_text_with_halo(self, painter, rect):
        """保留原有的 Halo 文字繪製邏輯，確保視覺一致"""
        import re
        font, font_bold, num_font = QFont("Microsoft JhengHei", 12 + get_font_offset()), QFont("Microsoft JhengHei", 11+ get_font_offset(), QFont.Bold), QFont(
            "Microsoft JhengHei", 13+ get_font_offset())
        start_x, col_gap, top_y = rect.right() - 40, 40, rect.top() + 20

        if not self.hide_name:
            name = self.center_info.get("name", "")
            self._draw_text_path(painter, start_x, top_y, name, font_bold)

        if not self.hide_birth:
            raw_solar = self.center_info.get("solar_line", "")
            nums = re.findall(r'\d+', raw_solar)
            solar_text = f"{nums[0]} / {nums[1].zfill(2)} / {nums[2].zfill(2)}   {nums[3].zfill(2)}:{nums[4].zfill(2)}" if len(
                nums) >= 5 else raw_solar

            if not self.hide_part:
                # 繪製西元日期 (旋轉 90 度)
                self._draw_mixed_text(painter, start_x - col_gap, top_y, solar_text, num_font)

            self._draw_text_path(painter, start_x - col_gap * 2, top_y, self.center_info.get("lunar_line", ""), font)
            self._draw_text_path(painter, start_x - col_gap * 3, top_y, self.center_info.get("ming_line", ""),
                                 font_bold, QColor(138, 43, 226))

    def _draw_text_path(self, painter, x, y, text, font, color=Qt.black, spacing=18+get_font_offset()):
        painter.save()
        current_y, stroke_pen = y, QPen(Qt.white, 4)
        for char in text:
            if char.strip() == "": current_y += spacing / 2; continue
            path = QPainterPath()
            path.addText(x - 10, current_y + 15, font, char)
            painter.setPen(stroke_pen);
            painter.setBrush(Qt.NoBrush);
            painter.drawPath(path)
            painter.setPen(Qt.NoPen);
            painter.setBrush(color);
            painter.drawPath(path)
            current_y += spacing
        painter.restore()

    def _draw_mixed_text(self, painter, x, y, text, font, color=Qt.black):
        """繪製旋轉 90 度的數字/英文字串"""
        painter.save()
        small_font = QFont(font.family(), font.pointSize() - 1)
        transform = QTransform()
        transform.translate(x - 4, y + 1)
        transform.rotate(90)
        path = QPainterPath()
        path.addText(0, 0, small_font, text)
        rotated_path = transform.map(path)
        painter.strokePath(rotated_path, QPen(Qt.white, 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.fillPath(rotated_path, color)
        painter.restore()


class DrawingLayer(QWidget):
    tool_deactivated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.current_color, self.current_thickness = Qt.red, 2
        self.shapes, self.current_shape, self.selected_shape, self.active_handle = [], None, None, None
        self.is_drawing = self.is_moving = False
        self.last_pos, self.tool_type = QPointF(), None

        # 確保從 drawing_objects 匯入正確的類別
        from drawing_objects import PenShape, RectShape, CircleShape, ArrowShape, TextShape
        self.ShapeClasses = {
            "pen": PenShape,
            "rect": RectShape,
            "circle": CircleShape,
            "arrow": ArrowShape,
            "text": TextShape
        }

    def set_tool_type(self, t):
        self.tool_type = t
        if self.selected_shape:
            self.selected_shape.is_selected = False
            self.selected_shape = None
            self.update()

    def set_pen_color(self, c):
        self.current_color = c

    def set_thickness(self, t):
        self.current_thickness = t

    def undo(self):
        if self.shapes:
            if self.selected_shape == self.shapes[-1]: self.selected_shape = None
            self.shapes.pop()
            self.update()

    def clear(self):
        self.shapes, self.selected_shape = [], None
        self.update()

    def delete_selected(self):
        """從物件清單中移除目前被選中的物件"""
        # 修正：使用 self.selected_shape 而不是不存在的 selected_shape_idx
        if self.selected_shape is not None:
            try:
                # 從 shapes 清單中移除該物件
                self.shapes.remove(self.selected_shape)
                # 移除後將選取狀態重置
                self.selected_shape = None
                # 觸發重繪
                self.update()
            except ValueError:
                # 預防萬一物件不在清單中
                self.selected_shape = None

    def get_state(self):
        return list(self.shapes)

    def set_state(self, s):
        self.shapes, self.selected_shape = list(s) if s else [], None
        self.update()

    def mousePressEvent(self, event):
        pos = event.position()
        self.last_pos = pos

        # --- 新增：處理右鍵取消功能 ---
        if event.button() == Qt.RightButton:
            if self.tool_type is not None or self.selected_shape is not None or self.current_shape is not None:
                self.tool_type = None
                self.current_shape = None
                if self.selected_shape:
                    self.selected_shape.is_selected = False
                    self.selected_shape = None
                self.is_drawing = False
                self.is_moving = False
                self.active_handle = None
                self.tool_deactivated.emit()  # 發射 Signal
                self.update()
                return  # 右鍵事件處理完畢，不再執行後續邏輯

        if event.button() == Qt.LeftButton:
            # 1. 優先處理選中形狀的控制點 (Resize/Move handles)
            if self.selected_shape:
                handle = self.selected_shape.get_handle_at(pos)
                if handle:
                    self.active_handle = handle
                    return

            # 2. 偵測是否點擊到現有形狀
            clicked_shape = next((s for s in reversed(self.shapes) if s.contains(pos)), None)

            # --- 修正問題 1：點擊空白處先「取消選取/確認」，而不是立刻畫新的 ---
            if self.selected_shape and clicked_shape is None:
                self.selected_shape.is_selected = False
                self.selected_shape = None
                self.update()
                return  # 這次點擊只負責「確認/取消選取」，不觸發新繪圖

            # 3. 如果有點到形狀，則選取它
            if clicked_shape:
                if self.selected_shape: self.selected_shape.is_selected = False
                self.selected_shape = clicked_shape
                self.selected_shape.is_selected = True
                self.is_moving = True
                self.update()
                return

            # --- 修正問題 2：手動將事件導向底層的 BaseLayer ---
            if self.tool_type is None:
                # 這裡直接呼叫父組件中的 base_layer 處理函式
                if hasattr(self.parent(), 'base_layer'):
                    self.parent().base_layer.mousePressEvent(event)
                return

            # 4. 如果有選取工具，且目前沒有選中任何東西，才開始繪製新形狀
            if self.tool_type:
                if self.tool_type == "text":
                    self._handle_text_input(pos)
                    return

                self.is_drawing = True
                cls = self.ShapeClasses.get(self.tool_type)
                if self.tool_type == "pen":
                    self.current_shape = cls([pos], self.current_color, self.current_thickness)
                else:
                    self.current_shape = cls(pos, pos, self.current_color, self.current_thickness)
                self.update()

    def mouseMoveEvent(self, event):
        pos = event.position()
        delta = pos - self.last_pos
        self.last_pos = pos

        # 處理控制點拖曳 (包含 Arrow 的 cp1, cp2)
        if self.selected_shape and self.active_handle:
            if self.active_handle == "resize" and hasattr(self.selected_shape, "rect"):
                self.selected_shape.rect.setBottomRight(pos.toPoint())
            elif self.active_handle == "start":
                self.selected_shape.start_point = pos
            elif self.active_handle == "end":
                self.selected_shape.end_point = pos
            elif self.active_handle == "cp1":
                self.selected_shape.cp1 = pos
            elif self.active_handle == "cp2":
                self.selected_shape.cp2 = pos
            self.update()
            return

        # 處理整體移動
        if self.is_moving and self.selected_shape:
            self.selected_shape.move(delta)
            self.update()
            return

        # 處理正在繪製中的形狀
        if self.is_drawing and self.current_shape:
            if self.tool_type == "pen":
                self.current_shape.points.append(pos)
            elif hasattr(self.current_shape, "rect"):
                self.current_shape.rect.setBottomRight(pos.toPoint())
            elif self.tool_type == "arrow":
                # 繪製時更新終點
                self.current_shape.end_point = pos
                # 同步更新曲線控制點，使其初始看起來像直線
                if hasattr(self.current_shape, 'update_points'):
                    self.current_shape.update_points(self.current_shape.start_point, pos)
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self.active_handle:
                self.active_handle = None
                return
            if self.is_moving:
                self.is_moving = False
                return
            if self.is_drawing and self.current_shape:
                self.is_drawing = False
                # 繪製完成後，自動選中該形狀以便調整控制點 (特別是箭頭)
                if self.tool_type == "arrow":
                    self.current_shape.is_selected = True
                    self.selected_shape = self.current_shape
                self.shapes.append(self.current_shape)
                self.current_shape = None
                self.update()

    def _handle_text_input(self, pos, existing_shape=None):
        # ... (保留之前提供的強制樣式與多行支援的 _handle_text_input 邏輯) ...
        from PySide6.QtWidgets import QInputDialog
        dialog = QInputDialog(self)
        dialog.setWindowTitle("文字輸入")
        dialog.setLabelText("請輸入文字：")
        dialog.setInputMode(QInputDialog.TextInput)
        dialog.setOption(QInputDialog.UsePlainTextEditForTextInput, True)
        if existing_shape: dialog.setTextValue(existing_shape.text)
        dialog.setStyleSheet("""
            QDialog { background-color: #f0f0f0; }
            QLabel { color: black !important; }
            QPushButton { color: black !important; background-color: #e0e0e0; border: 1px solid #999; padding: 5px; }
            QLineEdit, QTextEdit, QPlainTextEdit { 
                background-color: white !important; 
                color: black !important; 
                border: 1px solid #777;
                font-family: "Microsoft JhengHei";
            }
        """)
        if dialog.exec() == QDialog.Accepted:
            text = dialog.textValue()
            if text.strip():
                if existing_shape:
                    existing_shape.text = text
                else:
                    from drawing_objects import TextShape
                    self.shapes.append(TextShape(pos, text, self.current_color, self.current_thickness))
            elif existing_shape:
                self.shapes.remove(existing_shape)
            self.update()
        self.setFocus()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        for shape in self.shapes:
            shape.draw(painter)
        if self.is_drawing and self.current_shape:
            self.current_shape.draw(painter)


class ZiweiChartWidget(QWidget):
    """命盤容器：整合所有圖層"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.base_layer = BaseLayer(self)
        self.info_layer = InfoLayer(self)
        self.drawing_layer = DrawingLayer(self)

        # 疊加圖層
        self.layout.addWidget(self.base_layer, 0, 0)
        self.layout.addWidget(self.info_layer, 0, 0)
        self.layout.addWidget(self.drawing_layer, 0, 0)

        # 確保手繪層在最上方接收事件
        self.drawing_layer.raise_()

    def set_data_directly(self, full_data):
        """由 Main 層呼叫，更新全盤資料"""
        self.base_layer.set_data(full_data)
        self.info_layer.set_center_info(full_data["center_info"])
        # 重置 InfoLayer 的動態星曜資料，因為是新的命盤
        self.info_layer.set_highlight(None, None, None, None, daxian_stars_data={}, liunian_stars_data={})


class BirthInfoDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("輸入生辰")
        self.setStyleSheet("background-color: #f0f0f0; color: black;")
        self.settings = QSettings("MyZiweiApp", "Settings")
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QFormLayout(self)

        # --- 新增：快速輸入欄位 ---
        self.quick_input = QLineEdit()
        self.quick_input.setPlaceholderText("輸入12位數字(如:197810030552)後按Enter")
        self.quick_input.setMaxLength(12)
        # 安裝事件過濾器，用來攔截 Enter 鍵
        self.quick_input.installEventFilter(self)
        layout.addRow("快速輸入:", self.quick_input)
        # -----------------------

        self.name_input = QLineEdit()
        layout.addRow("姓名:", self.name_input)

        type_layout = QHBoxLayout()
        self.radio_solar, self.radio_lunar = QRadioButton("國曆"), QRadioButton("農曆")
        self.radio_solar.setChecked(True)
        self.bg = QButtonGroup(self)
        self.bg.addButton(self.radio_solar)
        self.bg.addButton(self.radio_lunar)
        type_layout.addWidget(self.radio_solar)
        type_layout.addWidget(self.radio_lunar)
        layout.addRow("曆法:", type_layout)

        self.year_spin = QSpinBox()
        self.year_spin.setRange(1900, 2100)
        layout.addRow("年份:", self.year_spin)
        self.month_spin = QSpinBox()
        self.month_spin.setRange(1, 12)
        layout.addRow("月份:", self.month_spin)
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        layout.addRow("日期:", self.day_spin)

        time_layout = QHBoxLayout()
        self.hour_spin, self.minute_spin = QSpinBox(), QSpinBox()
        self.hour_spin.setRange(0, 23)
        self.minute_spin.setRange(0, 59)
        time_layout.addWidget(self.hour_spin)
        time_layout.addWidget(QLabel("時"))
        time_layout.addWidget(self.minute_spin)
        time_layout.addWidget(QLabel("分"))
        layout.addRow("時間:", time_layout)

        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["男", "女"])
        layout.addRow("性別:", self.gender_combo)

        self.category_combo = QComboBox()
        cats = self.settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])
        self.category_combo.addItems(cats if isinstance(cats, list) else ["其他"])
        layout.addRow("分類:", self.category_combo)

        self.note_input = QLineEdit()
        self.note_input.setPlaceholderText("備註")
        layout.addRow("備註:", self.note_input)

        self.cb_save_db = QCheckBox("儲存至資料庫")
        layout.addRow("", self.cb_save_db)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.save_settings)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def eventFilter(self, obj, event):
        # 如果是快速輸入欄位，且按下了鍵盤按鍵
        if obj is self.quick_input and event.type() == QEvent.KeyPress:
            # 如果按的是 Enter 或小鍵盤的 Enter
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.parse_quick_input()
                return True  # 回傳 True 代表我們已經處理了這個事件，不要再傳給對話框（就不會關閉視窗）
        return super().eventFilter(obj, event)

    def parse_quick_input(self):
        """解析 12 位數生辰字串 (YYYYMMDDHHmm)"""
        text = self.quick_input.text().strip()
        if len(text) == 12 and text.isdigit():
            try:
                year = int(text[0:4])
                month = int(text[4:6])
                day = int(text[6:8])
                hour = int(text[8:10])
                minute = int(text[10:12])

                # 更新下方的 SpinBox
                self.year_spin.setValue(year)
                self.month_spin.setValue(month)
                self.day_spin.setValue(day)
                self.hour_spin.setValue(hour)
                self.minute_spin.setValue(minute)

                # 解析成功後，將焦點移至姓名輸入框，方便繼續輸入
                self.name_input.setFocus()
                # 清空快速輸入欄位或給予視覺回饋
                self.quick_input.setStyleSheet("background-color: #e8f5e9;") # 淡淡的綠色表示成功
            except ValueError:
                # 如果數值不合法（例如月份 13），則不動作
                self.quick_input.setStyleSheet("background-color: #ffebee;") # 淡淡的紅色表示錯誤
        else:
            self.quick_input.setStyleSheet("background-color: #ffebee;")

    def load_settings(self):
        self.year_spin.setValue(int(self.settings.value("last_year", 1990)))
        self.month_spin.setValue(int(self.settings.value("last_month", 1)))
        self.day_spin.setValue(int(self.settings.value("last_day", 1)))
        self.hour_spin.setValue(int(self.settings.value("last_hour", 12)))
        self.gender_combo.setCurrentText(self.settings.value("last_gender", "男"))
        self.category_combo.setCurrentText(self.settings.value("last_category", "家人"))
        if self.settings.value("last_is_lunar", False, type=bool): self.radio_lunar.setChecked(True)

    def save_settings(self):
        self.settings.setValue("last_year", self.year_spin.value())
        self.settings.setValue("last_month", self.month_spin.value())
        self.settings.setValue("last_day", self.day_spin.value())
        self.settings.setValue("last_hour", self.hour_spin.value())
        self.settings.setValue("last_gender", self.gender_combo.currentText())
        self.settings.setValue("last_category", self.category_combo.currentText())
        self.settings.setValue("last_is_lunar", self.radio_lunar.isChecked())

    def get_birth_info(self):
        return {"name": self.name_input.text(), "year": self.year_spin.value(), "month": self.month_spin.value(),
                "day": self.day_spin.value(), "hour": self.hour_spin.value(), "minute": self.minute_spin.value(),
                "gender": self.gender_combo.currentText(), "is_lunar": self.radio_lunar.isChecked(),
                "note": self.note_input.text(), "category": self.category_combo.currentText(),
                "save_to_db": self.cb_save_db.isChecked()}

    def set_data(self, d):
        self.name_input.setText(d.get('name', ''))
        self.year_spin.setValue(d.get('year', 1990))
        self.month_spin.setValue(d.get('month', 1))
        self.day_spin.setValue(d.get('day', 1))
        self.hour_spin.setValue(d.get('hour', 12))
        self.gender_combo.setCurrentText(d.get('gender', '男'))
        self.note_input.setText(d.get('note', ''))
        self.cb_save_db.setVisible(False)
        if d.get('is_lunar'): self.radio_lunar.setChecked(True)


class DatabaseManagerDialog(QDialog):
    def __init__(self, db_helper, parent=None):
        super().__init__(parent)
        self.db = db_helper;
        self.selected_user = None
        self.settings = QSettings("MyZiweiApp", "Settings")
        self.setWindowTitle("資料庫管理");
        self.resize(800, 500);
        self.setStyleSheet("background-color: #f0f0f0; color: black;")
        self.init_ui();
        self.setup_shortcuts();

        #【新增】讀取上次開啟的分頁索引並切換
        last_idx = int(self.settings.value("last_db_tab_index", 0))
        if last_idx < self.tabs.count():
            self.tabs.setCurrentIndex(last_idx)

        # 【新增】當分頁切換時自動儲存索引
        self.tabs.currentChanged.connect(lambda idx: self.settings.setValue("last_db_tab_index", idx))

        self.load_data()

    def setup_shortcuts(self):
        from PySide6.QtGui import QShortcut, QKeySequence
        QShortcut(QKeySequence("D"), self, self.on_delete_clicked)
        QShortcut(QKeySequence("Delete"), self, self.on_delete_clicked)
        QShortcut(QKeySequence("M"), self, self.on_move_clicked)
        QShortcut(QKeySequence("E"), self, self.on_edit_clicked)

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget();
        self.tabs.setDocumentMode(True)
        settings = QSettings("MyZiweiApp", "Settings")
        cats = settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])
        if isinstance(cats, str):
            import ast
            try:
                cats = ast.literal_eval(cats)
            except:
                cats = ["家人", "朋友", "同事", "名人", "其他"]
        self.categories = ["全部"] + cats
        for c in self.categories: self.tabs.addTab(QWidget(), c)
        self.tabs.currentChanged.connect(self.load_data);
        self.tabs.setFixedHeight(self.tabs.tabBar().sizeHint().height() + 2);
        layout.addWidget(self.tabs)
        top = QHBoxLayout();
        self.search_input = QLineEdit();
        self.search_input.setPlaceholderText("搜尋姓名或備註...");
        self.search_input.textChanged.connect(self.load_data)
        top.addWidget(QLabel("關鍵字:"));
        top.addWidget(self.search_input);
        layout.addLayout(top)
        self.table = QTableWidget();
        self.table.setColumnCount(6);
        self.table.setHorizontalHeaderLabels(["ID", "姓名", "性別", "生辰 (西元)", "備註", "建立時間"])
        header = self.table.horizontalHeader();
        header.setSectionResizeMode(QHeaderView.Interactive);
        self.table.setColumnHidden(0, True);
        self.table.setColumnWidth(2, 35);
        self.table.setColumnWidth(3, 120);
        self.table.setColumnWidth(5, 120);
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows);
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection);
        self.table.doubleClicked.connect(self.on_load_clicked);
        layout.addWidget(self.table)
        privacy_group = QGroupBox("載入時隱私設定");
        privacy_layout = QHBoxLayout(privacy_group)
        self.cb_name, self.cb_birth, self.cb_part, self.cb_all = QCheckBox("隱藏姓名"), QCheckBox(
            "隱藏生辰"), QCheckBox("部分生辰"), QCheckBox("全部隱藏")
        privacy_layout.addWidget(self.cb_name);
        privacy_layout.addWidget(self.cb_birth);
        privacy_layout.addWidget(self.cb_part);
        privacy_layout.addWidget(self.cb_all);
        layout.addWidget(privacy_group)
        btn_layout = QHBoxLayout();
        b_del = QPushButton("刪除選取 (D)");
        b_del.setStyleSheet("background-color: #ffcccc; color: red;");
        b_del.clicked.connect(self.on_delete_clicked)
        b_edit = QPushButton("修改選取 (E)");
        b_edit.clicked.connect(self.on_edit_clicked);
        b_add = QPushButton("新增資料");
        b_add.clicked.connect(self.on_add_clicked)
        b_load = QPushButton("載入資料");
        b_load.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;");
        b_load.clicked.connect(self.on_load_clicked)
        b_cancel = QPushButton("取消");
        b_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(b_del);
        btn_layout.addWidget(b_edit);
        btn_layout.addWidget(b_add);
        btn_layout.addStretch();
        btn_layout.addWidget(b_load);
        btn_layout.addWidget(b_cancel);
        layout.addLayout(btn_layout)

    def load_data(self):
        keyword = self.search_input.text().strip();
        cat_idx = self.tabs.currentIndex();
        category = self.categories[cat_idx] if cat_idx > 0 else None
        users = self.db.get_all_users(keyword, category);
        self.table.setRowCount(0)
        for row, user in enumerate(users):
            self.table.insertRow(row);
            self.table.setItem(row, 0, QTableWidgetItem(str(user['id'])));
            self.table.setItem(row, 1, QTableWidgetItem(user['name']));
            self.table.setItem(row, 2, QTableWidgetItem(user['gender']))
            self.table.setItem(row, 3, QTableWidgetItem(
                f"{user['year']}/{user['month']:02d}/{user['day']:02d} {user['hour']:02d}:{user['minute']:02d}"));
            self.table.setItem(row, 4, QTableWidgetItem(user['note']));
            self.table.setItem(row, 5, QTableWidgetItem(str(user['created_at'])[:16]))
            self.table.item(row, 0).setData(Qt.UserRole, user)

    def on_delete_clicked(self):
        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())), reverse=True)
        if not selected_rows: return
        if QMessageBox.question(self, "確認", f"確定要刪除選中的 {len(selected_rows)} 筆資料嗎？") == QMessageBox.Yes:
            for row in selected_rows: self.db.delete_user(int(self.table.item(row, 0).text()))
            self.load_data()

    def on_edit_clicked(self):
        row = self.table.currentRow()
        if row < 0: return
        user_data = self.table.item(row, 0).data(Qt.UserRole);
        dialog = BirthInfoDialog(self);
        dialog.set_data(user_data)
        if dialog.exec() == QDialog.Accepted: self.db.update_user(user_data['id'],
                                                                  dialog.get_birth_info()); self.load_data()

    def on_add_clicked(self):
        dialog = BirthInfoDialog(self)
        if dialog.exec() == QDialog.Accepted: self.db.add_user(dialog.get_birth_info()); self.load_data()

    def on_move_clicked(self):
        selected_rows = list(set(index.row() for index in self.table.selectedIndexes()))
        if not selected_rows: return
        settings = QSettings("MyZiweiApp", "Settings");
        cats = settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])
        if isinstance(cats, str):
            import ast
            try:
                cats = ast.literal_eval(cats)
            except:
                cats = ["家人", "朋友", "同事", "名人", "其他"]
        cat, ok = QInputDialog.getItem(self, "移動群組", "請選擇目標群組：", cats, 0, False)
        if ok and cat:
            for row in selected_rows: self.db.update_user_category(int(self.table.item(row, 0).text()), cat)
            self.load_data()

    def on_load_clicked(self):
        row = self.table.currentRow()
        if row < 0: return
        self.selected_user = self.table.item(row, 0).data(Qt.UserRole);
        self.accept()

    def get_privacy_settings(self):
        return {"name": self.cb_name.isChecked(), "birth": self.cb_birth.isChecked(), "part": self.cb_part.isChecked(),
                "all": self.cb_all.isChecked()}

    def refresh_categories(self):
        settings = QSettings("MyZiweiApp", "Settings");
        cats = settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])
        if isinstance(cats, str):
            import ast
            try:
                cats = ast.literal_eval(cats)
            except:
                cats = ["家人", "朋友", "同事", "名人", "其他"]
        self.categories = ["全部"] + cats
        for i, cat in enumerate(self.categories):
            if i < self.tabs.count():
                self.tabs.setTabText(i, cat)
            else:
                self.tabs.addTab(QWidget(), cat)


class CategorySelectionDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent);
        self.setWindowTitle("選擇分類");
        layout = QVBoxLayout(self)
        self.combo = QComboBox();
        self.combo.addItems(["家人", "朋友", "同事", "名人", "其他"]);
        layout.addWidget(self.combo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel);
        btns.accepted.connect(self.accept);
        btns.rejected.connect(self.reject);
        layout.addWidget(btns)

    def get_category(self): return self.combo.currentText()


class SettingsDialog(QDialog):
    """系統設定對話框"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("系統設定")
        self.settings = QSettings("MyZiweiApp", "Settings")
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout(self)

        # 1. 子時與閏月設定
        group_basic = QGroupBox("基本排盤設定")
        layout_basic = QFormLayout(group_basic)

        self.combo_late_zi = QComboBox()
        self.combo_late_zi.addItems(["歸入當日 (00:00)", "併入隔日 (早子)"])
        layout_basic.addRow("晚子時處理:", self.combo_late_zi)

        self.combo_leap = QComboBox()
        self.combo_leap.addItems(["歸同月", "歸下月", "15日區分"])
        layout_basic.addRow("閏月處理:", self.combo_leap)
        # 新增字體縮放
        self.spin_font_offset = QSpinBox()
        self.spin_font_offset.setRange(-5, 10)  # 允許縮小5號或放大10號
        self.spin_font_offset.setSuffix(" pt")
        layout_basic.addRow("字體大小調整:", self.spin_font_offset)
        #group_display = QGroupBox("顯示設定")
        #layout_display = QFormLayout(group_display)

        self.spin_stars_col = QSpinBox()
        self.spin_stars_col.setRange(1, 5)  # 設定一列最多顯示1~5顆星
        layout_basic.addRow("限流星曜堆疊數:", self.spin_stars_col)
        self.cb_minimal = QCheckBox("北派星曜極簡化 (18星)")
        layout_basic.addRow(self.cb_minimal)
        #layout.addWidget(group_display)

        layout.addWidget(group_basic)

        # 2. 四化設定
        group_sihua = QGroupBox("十干四化設定")
        layout_sihua = QFormLayout(group_sihua)

        self.combo_wu = QComboBox()
        self.combo_wu.addItems(["貪陰右機", "貪陰陽機"])
        layout_sihua.addRow("戊干四化:", self.combo_wu)

        self.combo_geng = QComboBox()
        self.combo_geng.addItems(["陽武陰同", "陽武同陰", "陽武府同", "陽武同相"])
        layout_sihua.addRow("庚干四化:", self.combo_geng)

        self.combo_ren = QComboBox()
        self.combo_ren.addItems(["梁紫左武", "梁紫府武"])
        layout_sihua.addRow("壬干四化:", self.combo_ren)
        layout.addWidget(group_sihua)

        # 3. 群組名稱設定
        group_cat = QGroupBox("資料庫群組命名 (限4字)")
        layout_cat = QVBoxLayout(group_cat)
        self.cat_inputs = []
        default_cats = ["家人", "朋友", "同事", "名人", "其他"]
        for i in range(5):
            edit = QLineEdit()
            edit.setMaxLength(4)
            edit.setPlaceholderText(default_cats[i])
            layout_cat.addWidget(edit)
            self.cat_inputs.append(edit)
        layout.addWidget(group_cat)



        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.save_settings)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)


    def load_settings(self):
        self.combo_late_zi.setCurrentIndex(int(self.settings.value("late_zi_behavior", 0)))
        self.combo_leap.setCurrentIndex(int(self.settings.value("leap_month_behavior", 0)))
        # 讀取字體偏移，預設為 0
        self.spin_font_offset.setValue(int(self.settings.value("font_offset", 0)))
        self.spin_stars_col.setValue(int(self.settings.value("stars_per_column", 2)))

        wu = self.settings.value("sihua_wu", "貪陰右機")
        self.combo_wu.setCurrentText(wu)

        geng = self.settings.value("sihua_geng", "陽武陰同")
        self.combo_geng.setCurrentText(geng)

        ren = self.settings.value("sihua_ren", "梁紫左武")
        self.combo_ren.setCurrentText(ren)

        cats = self.settings.value("category_names", ["家人", "朋友", "同事", "名人", "其他"])
        if isinstance(cats, str):  # QSettings 有時會存成字串
            import ast
            try:
                cats = ast.literal_eval(cats)
            except:
                cats = ["家人", "朋友", "同事", "名人", "其他"]

        for i, name in enumerate(cats):
            if i < len(self.cat_inputs):
                self.cat_inputs[i].setText(name)

        self.cb_minimal.setChecked(self.settings.value("minimal_stars", True, type=bool))

    def save_settings(self):
        self.settings.setValue("late_zi_behavior", self.combo_late_zi.currentIndex())
        self.settings.setValue("leap_month_behavior", self.combo_leap.currentIndex())
        # 儲存字體偏移
        self.settings.setValue("font_offset", self.spin_font_offset.value())
        self.settings.setValue("stars_per_column", self.spin_stars_col.value())
        self.settings.setValue("sihua_wu", self.combo_wu.currentText())
        self.settings.setValue("sihua_geng", self.combo_geng.currentText())
        self.settings.setValue("sihua_ren", self.combo_ren.currentText())

        cats = [edit.text() if edit.text().strip() else edit.placeholderText() for edit in self.cat_inputs]
        self.settings.setValue("category_names", cats)
        self.settings.setValue("minimal_stars", self.cb_minimal.isChecked())