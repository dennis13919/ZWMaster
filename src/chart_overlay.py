import flet as ft
import flet.canvas as cv
import math
from logic import ZiweiCalculator


def draw_chart_overlay(overlay_canvas, app_state, ui_cfg, page_width, page_height, font_offset=0):
    overlay_canvas.shapes.clear()
    data = app_state["full_data"]
    if not data:
        if overlay_canvas.page:
            overlay_canvas.update()
        return

    school = data.get("config", {}).get("school", "北派")
    palaces = data["palaces"]
    sihua_table = data.get("sihua_table", {})
    sel_idx = app_state["selected_palace_idx"]

    current_padding = ui_cfg["chart_padding"] if school == "北派" else 0

    # 取得使用者自定義的 X/Y 軸偏移量
    x_offset = app_state.get("x_offset", 0)
    y_offset = app_state.get("y_offset", 0)

    # 【重要修復】：直接強制使用鎖定後的 page_width / page_height 進行計算
    # 徹底棄用 app_state["chart_w"] 和 chart_h，避免吃到熱重啟時的縮水數據
    W = page_width - (current_padding * 2)
    H = page_height - ui_cfg.get("appbar_height", 45) - 150 - (current_padding * 2)

    # 加上自定義偏移量
    W = W + x_offset
    H = H + y_offset

    pw = W / 4
    ph = H / 4

    COORDS = [(3, 2), (3, 1), (3, 0), (2, 0), (1, 0), (0, 0), (0, 1), (0, 2), (0, 3), (1, 3), (2, 3), (3, 3)]

    # ==========================================
    # 座標微調參數區
    # ==========================================
    TWEAK_CENTER_BOX_X = 0
    TWEAK_CENTER_BOX_Y = -8
    TWEAK_OUT_TEXT_X = 15
    TWEAK_OUT_TEXT_Y = -10

    def get_center(idx):
        r, c = COORDS[idx]
        return (c * pw + pw / 2, r * ph + ph / 2)

    def get_inner_edge(idx):
        r, c = COORDS[idx]
        cx, cy = get_center(idx)
        if idx == 2: return (cx + pw / 2, cy - ph / 2)
        if idx == 5: return (cx + pw / 2, cy + ph / 2)
        if idx == 8: return (cx - pw / 2, cy + ph / 2)
        if idx == 11: return (cx - pw / 2, cy - ph / 2)

        if r == 0: return (cx, cy + ph / 2)
        if r == 3: return (cx, cy - ph / 2)
        if c == 0: return (cx + pw / 2, cy)
        if c == 3: return (cx - pw / 2, cy)
        return (cx, cy)

    draw_queue_lines = []
    draw_queue_boxes = []
    draw_queue_texts = []

    def queue_arrow(x1, y1, x2, y2, color=ft.colors.BLUE_600):
        paint = ft.Paint(color=color, stroke_width=1.2, style=ft.PaintingStyle.STROKE)
        angle = math.atan2(y2 - y1, x2 - x1)
        arrow_len = 5
        p1_x = x2 - arrow_len * math.cos(angle - math.pi / 6)
        p1_y = y2 - arrow_len * math.sin(angle - math.pi / 6)
        p2_x = x2 - arrow_len * math.cos(angle + math.pi / 6)
        p2_y = y2 - arrow_len * math.sin(angle + math.pi / 6)

        path = cv.Path(
            elements=[
                cv.Path.MoveTo(x1, y1), cv.Path.LineTo(x2, y2),
                cv.Path.MoveTo(x2, y2), cv.Path.LineTo(p1_x, p1_y),
                cv.Path.MoveTo(x2, y2), cv.Path.LineTo(p2_x, p2_y),
            ],
            paint=paint
        )
        draw_queue_lines.append(path)

    def queue_sihua_box(x, y, text, is_vertical=False):
        char_w = 13 + font_offset
        char_h = 15 + font_offset

        if not is_vertical:
            # 原本的橫向邏輯
            box_w = (char_w * len(text)) + 2
            box_h = char_h
            draw_queue_boxes.append(
                cv.Rect(x, y, box_w, box_h, paint=ft.Paint(color=ft.colors.BLUE_600, style=ft.PaintingStyle.FILL),
                        border_radius=3))
            draw_queue_texts.append(cv.Text(x + 1, y - 2, text,
                                            style=ft.TextStyle(size=13 + font_offset, color=ft.colors.WHITE,
                                                               weight="bold")))
        else:
            # 垂直排列邏輯
            box_w = char_h  # 寬度變成原本的高度
            box_h = (char_h * len(text)) + 2
            draw_queue_boxes.append(
                cv.Rect(x, y, box_w, box_h, paint=ft.Paint(color=ft.colors.BLUE_600, style=ft.PaintingStyle.FILL),
                        border_radius=3))
            for i, char in enumerate(text):
                draw_queue_texts.append(cv.Text(x + 2, y + (i * char_h), char,
                                                style=ft.TextStyle(size=13 + font_offset, color=ft.colors.WHITE,
                                                                   weight="bold")))

    def queue_plain_text(x, y, text, is_vertical=False):
        s = 13 + font_offset
        if is_vertical:
            for idx, char in enumerate(text):
                draw_queue_texts.append(cv.Text(x, y + (idx * (s + 1)), char,
                                                style=ft.TextStyle(size=s, color=ft.colors.BLUE_600, weight="bold")))
        else:
            draw_queue_texts.append(
                cv.Text(x, y, text, style=ft.TextStyle(size=s, color=ft.colors.BLUE_600, weight="bold")))

    if school == "北派":
        for i, p in enumerate(palaces):
            p_gan = p["gan"]
            r, c = COORDS[i]
            cx, cy = get_center(i)

            out_sihuas = []
            for star_obj in p["stars"]:
                s_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                sh = ZiweiCalculator.get_sihua(p_gan, s_name, sihua_table)
                if sh: out_sihuas.append(sh)

            if out_sihuas:
                text = "".join(out_sihuas)
                arr_len = 18
                start_x, start_y, end_x, end_y = cx, cy, cx, cy
                tx, ty = 0, 0
                is_vert = False

                if c < 2:
                    start_x -= 10
                    end_x -= 10

                if r == 0:  # 上方化出
                    start_y = cy - ph / 2;
                    end_y = start_y - arr_len
                    tx = end_x - 10 + TWEAK_OUT_TEXT_X
                    ty = end_y
                elif r == 3: # 下方化出
                    start_y = cy + ph / 2;
                    end_y = start_y + arr_len
                    tx = end_x - 10 + TWEAK_OUT_TEXT_X
                    ty = end_y - 14
                elif c == 0: # 左邊化出
                    start_x = cx - pw / 2;
                    end_x = start_x - arr_len
                    tx = end_x - 12 + TWEAK_OUT_TEXT_X
                    ty = end_y + TWEAK_OUT_TEXT_Y
                    start_y -= 12; end_y -=12
                    is_vert = True
                elif c == 3: # 右邊化出
                    start_x = cx + pw / 2;
                    end_x = start_x + arr_len
                    tx = end_x + 0 - TWEAK_OUT_TEXT_X
                    ty = end_y + TWEAK_OUT_TEXT_Y
                    start_y -= 12; end_y -= 12
                    is_vert = True

                queue_arrow(start_x, start_y, end_x, end_y)
                queue_plain_text(tx, ty, text, is_vertical=is_vert)

            opp_idx = (i + 6) % 12
            in_sihuas = []
            for star_obj in palaces[opp_idx]["stars"]:
                s_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                sh = ZiweiCalculator.get_sihua(p_gan, s_name, sihua_table)
                if sh: in_sihuas.append(sh)

            if in_sihuas:
                text = "".join(in_sihuas)
                sx, sy = get_inner_edge(i)
                ex, ey = get_inner_edge(opp_idx)

                # --- 1. 提前計算文字方塊尺寸 (與 queue_sihua_box 邏輯一致) ---
                #char_w = 13 + font_offset
                #box_w = (char_w * len(text)) + 2  # padding_left + padding_right = 2
                box_w = 15 + font_offset
                box_h = 15 + font_offset

                # --- 2. 計算向量並調整箭頭終點 ---
                dx = ex - sx
                dy = ey - sy

                # 設定一個緩衝距離，讓箭頭不要貼得太死
                buffer = -1

                #new_ex, new_ey = ex, ey

                if abs(dx) > abs(dy):
                    # 水平為主：X軸退回方塊寬度，Y軸依比例調整
                    # 箭頭方向向量 (dx, dy)，我們想退回 box_w + buffer
                    move_x = (box_w + buffer) if dx > 0 else -(box_w + buffer)
                    move_y = (dy / dx) * move_x if dx != 0 else 0
                    new_ex = ex - move_x
                    new_ey = ey - move_y
                else:
                    # 垂直為主：Y軸退回方塊高度，X軸依比例調整
                    move_y = (box_h + buffer) if dy > 0 else -(box_h + buffer)
                    move_x = (dx / dy) * move_y if dy != 0 else 0
                    new_ex = ex - move_x
                    new_ey = ey - move_y

                # --- 3. 繪製調整後的箭頭 ---
                queue_arrow(sx, sy, new_ex, new_ey)

                # --- 4. 繪製文字方塊 (使用原始 ex, ey 確保位置正確) ---
                # 這裡沿用你原本的對齊邏輯
                if dx > 0:  # 箭頭向右
                    box_x = ex - box_w + 1
                else:  # 箭頭向左
                    box_x = ex

                if dy > 0:  # 箭頭向下
                    box_y = ey - box_h / 2 + 1
                else:  # 箭頭向上
                    box_y = ey + box_h / 2

                box_x += TWEAK_CENTER_BOX_X
                box_y += TWEAK_CENTER_BOX_Y

                # 判斷是否為右側宮位 (申酉戌亥對應索引 8, 9,10,11)
                # 這裡我們判斷終點位置是否在右側，或者直接判斷 opp_idx
                is_right_side = opp_idx in [8, 9, 10, 11]
                if opp_idx in [10, 11] and len(text)>1:
                    box_y -= box_h

                queue_sihua_box(box_x, box_y, text, is_vertical=is_right_side)

        if sel_idx is not None:
            sel_gan = palaces[sel_idx]["gan"]
            color_map = {"祿": ft.colors.GREEN_700, "權": ft.colors.RED_700, "科": ft.colors.BROWN_500,
                         "忌": ft.colors.BLACK}

            for i, p in enumerate(palaces):
                flying = []
                for star_obj in p["stars"]:
                    s_name = star_obj.get("name") if isinstance(star_obj, dict) else star_obj
                    sh = ZiweiCalculator.get_sihua(sel_gan, s_name, sihua_table)
                    if sh: flying.append(sh)

                if flying:
                    px = COORDS[i][1] * pw + 2
                    py = COORDS[i][0] * ph + 2
                    for j, sh_val in enumerate(flying):
                        c = color_map.get(sh_val, ft.colors.PURPLE_700)
                        draw_queue_texts.append(cv.Text(px, py + (j * (16 + font_offset)), f"飛{sh_val}",
                                                        style=ft.TextStyle(size=12 + font_offset, color=c,
                                                                           weight="bold")))

    elif school == "南派" and sel_idx is not None:
        opp_idx = (sel_idx + 6) % 12
        sf1_idx = (sel_idx + 4) % 12
        sf2_idx = (sel_idx + 8) % 12

        p_src = get_inner_edge(sel_idx)
        p_opp = get_inner_edge(opp_idx)
        p_sf1 = get_inner_edge(sf1_idx)
        p_sf2 = get_inner_edge(sf2_idx)

        paint_sf = ft.Paint(color=ft.colors.with_opacity(0.6, ft.colors.GREY_400), stroke_width=1.0,
                            style=ft.PaintingStyle.STROKE)

        def queue_line(p1, p2):
            path = cv.Path(elements=[cv.Path.MoveTo(p1[0], p1[1]), cv.Path.LineTo(p2[0], p2[1])], paint=paint_sf)
            draw_queue_lines.append(path)

        queue_line(p_src, p_opp)
        queue_line(p_src, p_sf1)
        queue_line(p_src, p_sf2)
        queue_line(p_sf1, p_sf2)

    overlay_canvas.shapes.extend(draw_queue_lines)
    overlay_canvas.shapes.extend(draw_queue_boxes)
    overlay_canvas.shapes.extend(draw_queue_texts)

    if overlay_canvas.page:
        overlay_canvas.update()