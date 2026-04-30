from PySide6.QtWidgets import *
from PySide6.QtGui import *
from PySide6.QtCore import *
import math

class BaseShape:
    def __init__(self, color=Qt.red, thickness=2):
        self.color = color
        self.thickness = thickness
        self.is_selected = False

    def draw(self, painter: QPainter):
        pass

    def contains(self, point: QPointF):
        return False

    def move(self, delta: QPointF):
        pass

    def get_handle_at(self, point: QPointF):
        return None

class PenShape(BaseShape):
    def __init__(self, points=None, color=Qt.red, thickness=2):
        super().__init__(color, thickness)
        self.points = points if points else []

    def draw(self, painter: QPainter):
        if len(self.points) < 2:
            return
        pen = QPen(self.color, self.thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        for i in range(len(self.points) - 1):
            painter.drawLine(self.points[i], self.points[i+1])
        
        if self.is_selected:
            painter.setPen(QPen(Qt.blue, 1, Qt.DashLine))
            painter.setBrush(Qt.NoBrush)
            path = QPainterPath()
            if self.points:
                path.moveTo(self.points[0])
                for pt in self.points[1:]:
                    path.lineTo(pt)
            painter.drawPath(path)

    def contains(self, point: QPointF):
        if not self.points: return False
        path = QPainterPath()
        path.moveTo(self.points[0])
        for pt in self.points[1:]:
            path.lineTo(pt)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(10, self.thickness + 5))
        stroke_path = stroker.createStroke(path)
        return stroke_path.contains(point)

    def move(self, delta: QPointF):
        self.points = [pt + delta for pt in self.points]

class RectShape(BaseShape):
    def __init__(self, start_point, end_point, color=Qt.red, thickness=2):
        super().__init__(color, thickness)
        self.rect = QRectF(start_point, end_point).normalized()

    def draw(self, painter: QPainter):
        painter.setBrush(Qt.NoBrush)
        pen = QPen(self.color, self.thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawRect(self.rect)
        if self.is_selected:
            painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.DashLine))
            painter.drawRect(self.rect.adjusted(-4, -4, 4, 4))
            
            # Draw resize handle at bottom-right
            painter.setPen(QPen(Qt.blue, 1))
            painter.setBrush(QBrush(Qt.white))
            handle_size = 8
            handle_rect = QRectF(self.rect.right() - handle_size/2, self.rect.bottom() - handle_size/2, handle_size, handle_size)
            painter.drawRect(handle_rect)

    def contains(self, point: QPointF):
        return self.rect.contains(point) or self.get_handle_at(point) is not None

    def move(self, delta: QPointF):
        self.rect.translate(delta)

    def get_handle_at(self, point: QPointF):
        handle_size = 12
        handle_rect = QRectF(self.rect.right() - handle_size/2, self.rect.bottom() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(point):
            return "resize"
        return None

class CircleShape(BaseShape):
    def __init__(self, start_point, end_point, color=Qt.red, thickness=2):
        super().__init__(color, thickness)
        self.rect = QRectF(start_point, end_point).normalized()

    def draw(self, painter: QPainter):
        painter.setBrush(Qt.NoBrush)
        pen = QPen(self.color, self.thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawEllipse(self.rect)
        if self.is_selected:
            painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.DashLine))
            painter.drawRect(self.rect.adjusted(-4, -4, 4, 4))
            
            # Draw resize handle at bottom-right
            painter.setPen(QPen(Qt.blue, 1))
            painter.setBrush(QBrush(Qt.white))
            handle_size = 8
            handle_rect = QRectF(self.rect.right() - handle_size/2, self.rect.bottom() - handle_size/2, handle_size, handle_size)
            painter.drawRect(handle_rect)

    def contains(self, point: QPointF):
        return self.rect.contains(point) or self.get_handle_at(point) is not None

    def move(self, delta: QPointF):
        self.rect.translate(delta)

    def get_handle_at(self, point: QPointF):
        handle_size = 12
        handle_rect = QRectF(self.rect.right() - handle_size/2, self.rect.bottom() - handle_size/2, handle_size, handle_size)
        if handle_rect.contains(point):
            return "resize"
        return None

class ArrowShape(BaseShape):
    def __init__(self, start_point, end_point, color=Qt.red, thickness=2):
        super().__init__(color, thickness)
        self.start_point = start_point
        self.end_point = end_point
        self.cp1 = start_point + (end_point - start_point) * 0.33
        self.cp2 = start_point + (end_point - start_point) * 0.66

    def update_points(self, start, end):
        self.start_point = start
        self.end_point = end
        self.cp1 = start + (end - start) * 0.33
        self.cp2 = start + (end - start) * 0.66

    def draw(self, painter: QPainter):
        painter.setBrush(Qt.NoBrush)
        pen = QPen(self.color, self.thickness, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        
        path = QPainterPath()
        path.moveTo(self.start_point)
        path.cubicTo(self.cp1, self.cp2, self.end_point)
        painter.drawPath(path)

        tangent = self.end_point - self.cp2
        angle = math.atan2(tangent.y(), tangent.x())
        
        arrow_size = 10 + self.thickness
        p1 = self.end_point + QPointF(math.cos(angle + math.radians(150)) * arrow_size,
                                    math.sin(angle + math.radians(150)) * arrow_size)
        p2 = self.end_point + QPointF(math.cos(angle - math.radians(150)) * arrow_size,
                                    math.sin(angle - math.radians(150)) * arrow_size)
        
        painter.setBrush(QBrush(self.color))
        painter.drawPolygon([self.end_point, p1, p2])

        if self.is_selected:
            painter.setBrush(Qt.NoBrush)
            # Draw control lines and handles
            painter.setPen(QPen(Qt.gray, 1, Qt.DashLine))
            painter.drawLine(self.start_point, self.cp1)
            painter.drawLine(self.end_point, self.cp2)
            
            painter.setPen(QPen(Qt.blue, 1))
            painter.setBrush(QBrush(Qt.white))
            handle_size = 6
            for pt in [self.start_point, self.end_point, self.cp1, self.cp2]:
                painter.drawEllipse(pt, handle_size/2, handle_size/2)

    def contains(self, point: QPointF):
        path = QPainterPath()
        path.moveTo(self.start_point)
        path.cubicTo(self.cp1, self.cp2, self.end_point)
        stroker = QPainterPathStroker()
        stroker.setWidth(max(10, self.thickness + 5))
        stroke_path = stroker.createStroke(path)
        return stroke_path.contains(point)

    def move(self, delta: QPointF):
        self.start_point += delta
        self.end_point += delta
        self.cp1 += delta
        self.cp2 += delta

    def get_handle_at(self, point: QPointF):
        handle_size = 10
        for name, pt in [("start", self.start_point), ("end", self.end_point), 
                         ("cp1", self.cp1), ("cp2", self.cp2)]:
            if (point - pt).manhattanLength() < handle_size:
                return name
        return None

class TextShape(BaseShape):
    def __init__(self, pos, text, color=Qt.red, thickness=2, font_size=14):
        super().__init__(color, thickness)
        self.pos = pos
        self.text = text
        self.font_size = font_size
        self._rect = QRectF()

    def draw(self, painter: QPainter):
        if not self.text:
            return

        painter.setBrush(Qt.NoBrush)

        # 1. 計算動態字體大小 (公式：基礎 12 + 粗細 * 2)
        # thickness 1 -> 14px, thickness 10 -> 52px
        dynamic_font_size = 12 + (self.thickness * 2)

        # 2. 設定字體與加粗
        font = QFont("Microsoft JhengHei", dynamic_font_size)
        if self.thickness > 3:
            font.setBold(True)
        painter.setFont(font)

        # 3. 設定畫筆 (文字顏色)
        # 注意：畫文字時，Pen 的粗細若太粗會導致字體模糊，建議固定為 1 或 2
        text_pen_thickness = 1 if self.thickness < 5 else 2
        painter.setPen(QPen(self.color, text_pen_thickness))

        # 4. 計算多行文字範圍
        fm = QFontMetrics(font)
        flags = Qt.AlignLeft | Qt.AlignTop | Qt.TextDontClip
        text_rect = fm.boundingRect(QRect(0, 0, 2000, 2000), flags, self.text)

        # 更新碰撞偵測用的矩形
        self._rect = QRectF(self.pos.x(), self.pos.y(), text_rect.width(), text_rect.height())

        # 5. 繪製文字
        painter.drawText(self._rect, flags, self.text)

        # 6. 選取框
        if self.is_selected:
            painter.setPen(QPen(QColor(128, 128, 128), 1, Qt.DashLine))
            painter.drawRect(self._rect.adjusted(-4, -4, 4, 4))

    def contains(self, point: QPointF):
        return self._rect.contains(point)

    def move(self, delta: QPointF):
        self.pos += delta
