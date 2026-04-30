import flet as ft
import flet.canvas as cv
import datetime
import traceback
import csv
import time
import json
import os
from logic import ZiweiCalculator
from database import ZiweiDatabase
from ui_mobile import PalaceCell
from chart_overlay import draw_chart_overlay

ABOUT_TEXT = """
**版本：** V6.0 (行動裝置版)  
**開發者：** Dennis19319  
**技術核心：** Google Gemini 3 Flash Preview  
**版權所有：** © 2026 Dennis19319. All Rights Reserved.  

本系統提供專業的南北派紫微斗數排盤功能。
設定選單並提供多種繪圖自定義參數，以完美符合各比例行動裝置。
V6.0 強化資料庫匯入匯出功能。

** 三方四正 或 北派自化線 錯置: 請旋轉螢幕方向，會自動重抓位置。

【授權與使用條款】

免費原則：本軟體免費提供予大眾個人學習與研究使用。

禁止營利：未經作者授權，禁止將本軟體用於商業營利行為。

禁止更動：禁止對本軟體進行反編譯、修改、或修改開發資訊後重新發佈。

若有授權需求，請聯繫 https://bit.ly/AuthZWM  
"""


# ==========================================
# 改用 Flet 原生的 client_storage，完美解決手機端儲存問題
# ==========================================
class SettingsManager:
    def __init__(self, page: ft.Page):
        self.page = page

    def get(self, key, default=None):
        if self.page.client_storage.contains_key(key):
            return self.page.client_storage.get(key)
        return default

    def set(self, key, value):
        self.page.client_storage.set(key, value)


UI_CFG = {
    "appbar_title": 16,
    "appbar_height": 45,
    "db_list_font": 12,
    "db_list_height": 45,
    "setting_font": 13,
    "setting_title": 14,
    "input_label": 12,
    "btn_font": 12,
    "chart_padding": 20,
}


def main(page: ft.Page):
    page.title = "ZWMaster Mobile"
    page.theme_mode = ft.ThemeMode.LIGHT
    page.padding = 0
    if page.platform in [ft.PagePlatform.WINDOWS, ft.PagePlatform.MACOS, ft.PagePlatform.LINUX]:
        page.window.width = 420
        page.window.height = 850
        page.update()
    time.sleep(0.1)  # 讓 Flet 有時間完成視窗初始化

    # 初始化設定管理器 (綁定當前 page)
    settings = SettingsManager(page)
    db = ZiweiDatabase()
    calculator = ZiweiCalculator()

    def get_categories():
        return [
            settings.get("cat_1") or "家人",
            settings.get("cat_2") or "朋友",
            settings.get("cat_3") or "同事",
            settings.get("cat_4") or "名人",
            settings.get("cat_5") or "其他"
        ]

    locked_w = settings.get("locked_width")
    locked_h = settings.get("locked_height")

    app_state = {
        "full_data": None,
        "birth_info": None,
        "daxian_idx": None,
        "liunian_year": None,
        "daxian_pos": None,
        "liunian_pos": None,
        "current_d_gan": None,
        "current_l_gan": None,
        "start_age": 2,
        "dynamic_stars_data": {"daxian_stars": {}, "liunian_stars": {}},
        "school": settings.get("school") or "北派",
        "page_width": locked_w or (page.width if page.width > 0 else 420),
        "page_height": locked_h or (page.height if page.height > 0 else 850),
        "selected_palace_idx": None,
        "chart_w": 0,
        "chart_h": 0,
        "x_offset": settings.get("x_offset", 0),
        "y_offset": settings.get("y_offset", 0),
        "font_offset": int(settings.get("font_offset", 0)),  # 新增：讀取字體偏移
        "star_wrap_offset": int(settings.get("star_wrap_offset", 0)),  # 新增
        "star_col_width_offset": int(settings.get("star_col_width_offset", 0)),  # 新增：讀取星曜間距偏移
        "drawing_mode": False,
        "draw_tool": "pen",  # pen, arrow, circle, rect, eraser
        "stroke_width": 2,
        "draw_history": [],  # 儲存已完成的形狀
        "temp_path": None,  # 正在畫的形狀
    }

    drawing_canvas = cv.Canvas(expand=True)

    app_state["last_update"] = 0

    def refresh_drawing_canvas():
        # 1. 建立全新的列表引用
        new_shapes = list(app_state["draw_history"])
        if app_state["temp_path"]:
            new_shapes.append(app_state["temp_path"])

        # 2. 賦值給畫布
        drawing_canvas.shapes = new_shapes

        # 3. 使用 page.update([control]) 只更新畫布，這比 page.update() 快得多
        # 並且不會觸發整個頁面的重繪
        try:
            page.update([drawing_canvas])
        except Exception:
            # 如果畫布還沒掛載，就先用 page.update() 兜底
            page.update()

    def on_pan_update(e: ft.DragUpdateEvent):
        if not app_state["drawing_mode"]: return
        x, y = e.local_x, e.local_y

        # 取得當前工具設定
        is_eraser = (app_state["draw_tool"] == "eraser")
        color = "white" if is_eraser else "red700"
        sw = 20 if is_eraser else app_state["stroke_width"]

        if app_state["draw_tool"] in ["pen", "eraser"]:
            if app_state["temp_path"]:
                # 持續增加線段
                app_state["temp_path"].elements.append(cv.Path.LineTo(x, y))

        elif app_state["draw_tool"] == "rect":
            sx, sy = app_state["temp_start"]
            app_state["temp_path"] = cv.Rect(
                sx, sy, x - sx, y - sy,
                paint=ft.Paint(color=color, stroke_width=sw, style=ft.PaintingStyle.STROKE)
            )

        elif app_state["draw_tool"] == "circle":
            sx, sy = app_state["temp_start"]
            radius = ((x - sx) ** 2 + (y - sy) ** 2) ** 0.5
            app_state["temp_path"] = cv.Circle(
                sx, sy, radius,
                paint=ft.Paint(color=color, stroke_width=sw, style=ft.PaintingStyle.STROKE)
            )

        elif app_state["draw_tool"] == "arrow":
            sx, sy = app_state["temp_start"]
            import math
            angle = math.atan2(y - sy, x - sx)
            arrow_len = 15 + sw
            x1 = x - arrow_len * math.cos(angle - math.pi / 6)
            y1 = y - arrow_len * math.sin(angle - math.pi / 6)
            x2 = x - arrow_len * math.cos(angle + math.pi / 6)
            y2 = y - arrow_len * math.sin(angle + math.pi / 6)

            app_state["temp_path"] = cv.Path([
                cv.Path.MoveTo(sx, sy), cv.Path.LineTo(x, y),
                cv.Path.MoveTo(x, y), cv.Path.LineTo(x1, y1),
                cv.Path.MoveTo(x, y), cv.Path.LineTo(x2, y2),
            ], paint=ft.Paint(color=color, stroke_width=sw, style=ft.PaintingStyle.STROKE))

        # 執行更新
        refresh_drawing_canvas()

    def on_pan_end(e: ft.DragEndEvent):
        if app_state["temp_path"]:
            app_state["draw_history"].append(app_state["temp_path"])
            app_state["temp_path"] = None
        refresh_drawing_canvas()



    def add_text_to_canvas(e):
        x, y = app_state.get("last_click_pos", (50, 50))

        # 動態大小：基礎 14 + 筆觸粗細 * 2 + 全域偏移
        dynamic_size = 14 + (app_state["stroke_width"] * 2) + app_state["font_offset"]

        new_text = cv.Text(
            x=x,
            y=y,
            text=text_input_field.value,
            style=ft.TextStyle(
                size=dynamic_size,
                color="red700",
                weight="bold"
            )
        )

        app_state["draw_history"].append(new_text)
        page.close(text_dialog)
        refresh_drawing_canvas()

    # 修改輸入框設定，加入 on_submit
    text_input_field = ft.TextField(
        label="輸入文字",
        autofocus=True,
        on_submit=add_text_to_canvas  # 按 Enter 直接觸發確定
    )

    text_dialog = ft.AlertDialog(
        title=ft.Text("輸入文字"),
        content=text_input_field,
        actions=[
            ft.TextButton("取消", on_click=lambda e: page.close(text_dialog)),
            ft.TextButton("確定", on_click=add_text_to_canvas)
        ]
    )

    def on_pan_start(e: ft.DragStartEvent):
        if not app_state["drawing_mode"]: return
        x, y = e.local_x, e.local_y

        if app_state["draw_tool"] == "text":
            app_state["last_click_pos"] = (x, y)
            text_input_field.value = ""  # 每次打開都清空
            page.open(text_dialog)
            return

        # 畫筆邏輯
        color = "red700"
        sw = app_state["stroke_width"]

        if app_state["draw_tool"] == "pen":
            app_state["temp_path"] = cv.Path([cv.Path.MoveTo(x, y)],
                                             paint=ft.Paint(color=color, stroke_width=sw,
                                                            style=ft.PaintingStyle.STROKE))
        else:
            app_state["temp_start"] = (x, y)
            app_state["temp_path"] = cv.Path([], paint=ft.Paint(color=color, stroke_width=sw,
                                                                style=ft.PaintingStyle.STROKE))
        refresh_drawing_canvas()

    # --- 3. 最後才定義 GestureDetector ---
    drawing_gesture = ft.GestureDetector(
        # 這裡不要放 content=drawing_canvas，改由 Container 包裹
        on_pan_start=on_pan_start,
        on_pan_update=on_pan_update,
        on_pan_end=on_pan_end,
        expand=True,
        visible=False,
        drag_interval=10,
    )

    # 使用 Container 來提供背景色，並包裹 GestureDetector 與 Canvas
    drawing_layer = ft.Container(
        content=ft.Stack([
            drawing_canvas,
            drawing_gesture,
        ]),
        expand=True,
        visible=False,
        bgcolor=ft.Colors.with_opacity(0.01, "white"),  # 必須有背景色才能攔截事件
    )

    def show_snack(msg, color="black"):
        try:
            snack = ft.SnackBar(ft.Text(msg, color="white", size=UI_CFG["setting_font"]), bgcolor=color, duration=2000)
            page.open(snack)
        except Exception:
            pass

    def page_resize(e):
        w = float(page.width)
        h = float(page.height)

        # 取得之前存好的直立鎖定值
        locked_w = settings.get("locked_width")
        locked_h = settings.get("locked_height")

        if w > h:
            # --- 橫向模式 (平板或手機橫放) ---
            # 橫向時不使用鎖定值，直接自適應
            app_state["page_width"] = w
            app_state["page_height"] = h
        else:
            # --- 直向模式 ---
            # 1. 如果還沒存過鎖定值，且現在看起來是正常的直向尺寸，就存起來
            if not locked_w and w > 300:
                settings.set("locked_width", w)
                settings.set("locked_height", h)
                app_state["page_width"] = w
                app_state["page_height"] = h
            # 2. 如果已經有鎖定值，就強制使用鎖定值 (解決縮水 Bug)
            elif locked_w:
                app_state["page_width"] = locked_w
                app_state["page_height"] = locked_h
            # 3. 萬一都還沒存過，就先用當前的
            else:
                app_state["page_width"] = w
                app_state["page_height"] = h

        # 更新畫布與 UI
        if app_state["full_data"]:
            draw_chart()


    page.on_resized = page_resize

    def quick_parse(e):
        val = e.control.value
        if len(val) == 12 and val.isdigit():
            input_year.value = val[:4]
            input_month.value = val[4:6]
            input_day.value = val[6:8]
            input_hour.value = val[8:10]
            input_minute.value = val[10:12]
            input_name.focus()
            page.update()

    def do_calculate_logic(birth_data):
        late_zi_str = settings.get("late_zi") or "併入隔日 (早子)"
        late_zi_val = 1 if late_zi_str == "併入隔日 (早子)" else 0

        leap_str = settings.get("leap_month") or "15日區分"
        leap_val = 2 if leap_str == "15日區分" else (1 if leap_str == "歸下月" else 0)

        config = {
            "school": app_state["school"],
            "minimal_stars": settings.get("minimal_stars", False),
            "late_zi_behavior": late_zi_val,
            "leap_month_behavior": leap_val,
            "sihua_wu": settings.get("wu_sihua") or "貪陰右機",
            "sihua_geng": settings.get("geng_sihua") or "陽武陰同",
            "sihua_ren": settings.get("ren_sihua") or "梁紫左武"
        }

        res = calculator.calculate_birth_info(
            birth_data["year"], birth_data["month"], birth_data["day"],
            birth_data["hour"], minute=birth_data["minute"], is_lunar=birth_data["is_lunar"], config=config
        )
        res['name'] = birth_data["name"]
        res['gender'] = birth_data["gender"]
        res['is_lunar'] = birth_data.get("is_lunar", False)
        res['minute'] = birth_data.get("minute", 0)
        res['note'] = birth_data.get("note", "")
        res['category'] = birth_data.get("category", "")

        full_data = calculator.calculate_chart(res, config=config)

        app_state["full_data"] = full_data
        app_state["birth_info"] = res
        app_state["daxian_idx"] = None
        app_state["liunian_year"] = None
        app_state["daxian_pos"] = None
        app_state["liunian_pos"] = None
        app_state["current_d_gan"] = None
        app_state["current_l_gan"] = None
        app_state["dynamic_stars_data"] = {"daxian_stars": {}, "liunian_stars": {}}
        app_state["selected_palace_idx"] = None

        update_limit_buttons(full_data)
        draw_chart()
        draw_overlay()

        app_state["draw_history"] = []  # 重新排盤時清空繪圖
        refresh_drawing_canvas()

    def on_dialog_submit(e):
        page.close(dialog)

        try:
            birth_data = {
                "name": input_name.value if input_name.value else "匿名",
                "year": int(input_year.value) if input_year.value else 1990,
                "month": int(input_month.value) if input_month.value else 1,
                "day": int(input_day.value) if input_day.value else 1,
                "hour": int(input_hour.value) if input_hour.value else 0,
                "minute": int(input_minute.value) if input_minute.value else 0,
                "gender": gender_radio.value,
                "is_lunar": calendar_radio.value == "農曆",
                "category": input_category.value,
                "note": input_note.value
            }

            if app_state.get("edit_uid") is not None:
                db.update_user(app_state["edit_uid"], birth_data)
                show_snack("已更新資料", "green700")
                refresh_db_list()
            else:
                # 新增：按下排盤或儲存時，記憶當前選取的分類
                settings.set("last_input_category", input_category.value)
                if save_db_cb.value:
                    db.add_user(birth_data)
                    show_snack("已儲存至資料庫", "green700")
                    save_db_cb.value = False

                do_calculate_logic(birth_data)
                if page.route != "/":
                    page.go("/")

        except Exception as ex:
            traceback.print_exc()
            show_snack(f"發生錯誤: {str(ex)}", color="red800")

    def toggle_school(selected_school):
        app_state["school"] = selected_school
        settings.set("school", selected_school)

        # 更新按鈕樣式
        btn_nan.bgcolor = "blue700" if selected_school == "南派" else "transparent"
        btn_nan.content.color = "white" if selected_school == "南派" else "blue700"
        btn_bei.bgcolor = "blue700" if selected_school == "北派" else "transparent"
        btn_bei.content.color = "white" if selected_school == "北派" else "blue700"

        if app_state["full_data"]:
            app_state["selected_palace_idx"] = None
            # 重新計算邏輯
            do_calculate_logic(app_state["birth_info"])


    def on_daxian_click(idx):
        if app_state["daxian_idx"] == idx:
            app_state["daxian_idx"] = None
            app_state["liunian_year"] = None
            liunian_row.controls.clear()
            for i in range(10):
                liunian_row.controls.append(ft.Container(expand=1, height=25, border=ft.border.all(0.5, "grey300")))
        else:
            app_state["daxian_idx"] = idx
            app_state["liunian_year"] = None
            current_age = app_state["start_age"] + idx * 10
            birth_year = app_state["birth_info"]["year"]

            liunian_row.controls.clear()
            for i in range(10):
                y = birth_year + (current_age + i) - 1
                btn = ft.Container(
                    data=y,
                    content=ft.Text(str(y), size=11, color="grey700", text_align="center"),
                    expand=1, height=25, border=ft.border.all(0.5, "grey300"),
                    alignment=ft.alignment.center,
                    on_click=lambda e, year=y: on_liunian_click(year)
                )
                liunian_row.controls.append(btn)

        for i, btn in enumerate(daxian_row.controls):
            is_sel = (i == app_state["daxian_idx"])
            btn.bgcolor = "blue200" if is_sel else "transparent"
            btn.content.color = "black" if is_sel else "grey700"
            btn.content.weight = "bold" if is_sel else "normal"

        calculate_dynamic()
        page.update()

    def on_liunian_click(year):
        if app_state["liunian_year"] == year:
            app_state["liunian_year"] = None
        else:
            app_state["liunian_year"] = year

        for btn in liunian_row.controls:
            if hasattr(btn, 'data') and btn.data:
                is_sel = (btn.data == app_state["liunian_year"])
                btn.bgcolor = "green200" if is_sel else "transparent"
                btn.content.color = "black" if is_sel else "grey700"
                btn.content.weight = "bold" if is_sel else "normal"

        calculate_dynamic()
        page.update()

    def calculate_dynamic():
        if not app_state["full_data"]: return
        fd = app_state["full_data"]
        bi = app_state["birth_info"]
        d_idx = app_state["daxian_idx"]
        l_year = app_state["liunian_year"]

        d_gan, d_zhi, l_gan, l_zhi = None, None, None, None
        d_pos, lz_idx = None, None

        if d_idx is not None:
            birth_ming_idx = fd.get("ming_index", 2)
            info = fd["center_info"]
            is_cw = (info.get("gender") == "男" and info.get("yinyang") == "陽") or \
                    (info.get("gender") == "女" and info.get("yinyang") == "陰")
            d_pos = (birth_ming_idx + d_idx) % 12 if is_cw else (birth_ming_idx - d_idx + 12) % 12
            d_gan = fd["palaces"][d_pos]["gan"]
            d_zhi = fd["palaces"][d_pos]["zhi"]

        if l_year is not None:
            lz_idx = (l_year - 4) % 12
            l_zhi = ZiweiCalculator.DIZHI[lz_idx]
            l_gan = ZiweiCalculator.TIANGAN[(l_year - 4) % 10]

        app_state["current_d_gan"] = d_gan
        app_state["current_l_gan"] = l_gan
        app_state["daxian_pos"] = d_pos
        app_state["liunian_pos"] = lz_idx

        hr_idx = (bi["calc_hour"] + 1) // 2 % 12
        dyn_stars = ZiweiCalculator.calculate_dynamic_stars(
            fd["palaces"], daxian_gan=d_gan, daxian_zhi=d_zhi,
            liunian_gan=l_gan, liunian_zhi=l_zhi,
            natal_month=bi["lunar_month"], natal_day=bi["lunar_day"], natal_hour_idx=hr_idx
        )
        app_state["dynamic_stars_data"] = dyn_stars
        draw_chart()

    def on_chart_resize(e):
        pass

    overlay_canvas = cv.Canvas(expand=True, on_resize=on_chart_resize)

    def on_palace_click(idx):
        if app_state["selected_palace_idx"] == idx:
            app_state["selected_palace_idx"] = None
        else:
            app_state["selected_palace_idx"] = idx
        draw_chart()
        #draw_overlay()

    def draw_overlay():
        # 增加保護：確保畫布存在且已掛載
        if overlay_canvas:
            draw_chart_overlay(overlay_canvas, app_state, UI_CFG,
                               app_state["page_width"], app_state["page_height"],
                               app_state["font_offset"])

    def draw_chart():
        data = app_state["full_data"]
        if not data:
            chart_grid.controls.clear()
            page.update()
            return

        palaces = data['palaces']
        info = data['center_info']
        b_gan = info.get("birth_year_gan")
        sihua_table = data.get("sihua_table", {})
        school = data.get("config", {}).get("school", "北派")
        f_off = app_state["font_offset"]  # 取得偏移量
        scw_off = app_state["star_col_width_offset"]  # 取得星曜間距偏移量

        laiyin_idx = data.get("laiyin_idx", -1)
        shen_idx = data.get("shen_idx", -1)
        dyn_data = app_state["dynamic_stars_data"]
        d_pos = app_state.get("daxian_pos")
        l_pos = app_state.get("liunian_pos")

        PALACE_NAMES = ["命宮", "兄弟", "夫妻", "子女", "財帛", "疾厄", "遷移", "交友", "官祿", "田宅", "福德", "父母"]
        current_chart_padding = UI_CFG["chart_padding"] if school == "北派" else 0
        chart_container.padding = current_chart_padding
        # 【重要修復】：使用保護好的 app_state["page_width"]，不要再抓 page.width
        current_width = app_state["page_width"] if app_state["page_width"] > 0 else 420
        palace_width = (current_width - (current_chart_padding * 2)) * .345

        def get_p(idx):
            cell_dyn = {
                "daxian": dyn_data.get("daxian_stars", {}).get(idx, []),
                "liunian": dyn_data.get("liunian_stars", {}).get(idx, [])
            }
            p_data = palaces[idx].copy()
            p_data['b_gan'] = b_gan
            p_data['d_gan'] = app_state.get("current_d_gan")
            p_data['l_gan'] = app_state.get("current_l_gan")

            dx_label = ""
            if d_pos is not None:
                name = PALACE_NAMES[(idx - d_pos + 12) % 12]
                dx_label = f"大{name[0]}" if name != "交友" else "大奴"

            ln_label = ""
            if l_pos is not None:
                name = PALACE_NAMES[(idx - l_pos + 12) % 12]
                ln_label = f"流{name[0]}" if name != "交友" else "流奴"

            # 傳入 font_offset
            cell = PalaceCell(
                idx, palace_data=p_data, sihua_table=sihua_table,
                dynamic_stars=cell_dyn, is_shen=(idx == shen_idx),
                is_laiyin=(idx == laiyin_idx), school=school,
                dx_label=dx_label, ln_label=ln_label,
                palace_width=palace_width, font_offset=f_off,
                star_wrap_offset=app_state["star_wrap_offset"],
                star_col_width_offset=scw_off  # 新增：傳遞星曜間距偏移
            )

            if app_state["selected_palace_idx"] == idx:
                cell.bgcolor = "yellow50"

            cell.on_click = lambda e, i=idx: on_palace_click(i)
            return cell

        display_name = "匿名" if hide_name_cb.value else app_state.get("birth_info", {}).get('name',
                                                                                             info.get('name', '未命名'))
        # 處理隱藏生辰的文字邏輯
        solar_text = info['solar_line'].replace("西元 ", "")
        lunar_text = info['lunar_line'].replace("農曆 ", "")

        if hide_birth_cb.value:
            solar_text = ""  # 西元完全隱藏
            # 農曆只保留年份與時辰 (例如: 壬辰年 子時)
            parts = lunar_text.split(" ")
            if len(parts) >= 2:
                lunar_text = f"{parts[0]} {parts[-1]}"
            else:
                lunar_text = ""

        middle_info = ft.Container(
            content=ft.Column([
                ft.Text(display_name, weight="bold", size=13 + f_off, color="black"),
                ft.Text(solar_text, size=12 + f_off, color="grey700") if solar_text else ft.Container(),
                ft.Text(lunar_text, size=12 + f_off, color="grey700"),
                ft.Text(info['ming_line'], color="purple700", size=12 + f_off, weight="bold"),
            ], alignment="center", horizontal_alignment="center", spacing=2),
            expand=2,
            alignment=ft.alignment.center
        )

        chart_grid.controls.clear()
        chart_grid.controls.extend([
            ft.Row([get_p(5), get_p(6), get_p(7), get_p(8)], expand=1, spacing=0),
            ft.Row([get_p(4), middle_info, get_p(9)], expand=1, spacing=0),
            ft.Row([get_p(3), ft.Container(expand=2), get_p(10)], expand=1, spacing=0),
            ft.Row([get_p(2), get_p(1), get_p(0), get_p(11)], expand=1, spacing=0),
        ])
        draw_overlay()
        page.update()


    daxian_row = ft.Row(spacing=0)
    liunian_row = ft.Row(spacing=0)

    def update_limit_buttons(data):
        ming_line = data['center_info']['ming_line']
        start_age = 2
        for age_str, val in [("二", 2), ("三", 3), ("四", 4), ("五", 5), ("六", 6)]:
            if age_str in ming_line:
                start_age = val
                break
        app_state["start_age"] = start_age

        daxian_row.controls.clear()
        liunian_row.controls.clear()

        for i in range(10):
            age = start_age + i * 10
            btn = ft.Container(  #大限區字體
                content=ft.Text(f"{age}-{age + 9}", size=10, color="grey700", text_align="center"),
                expand=1, height=25, border=ft.border.all(0.5, "grey300"),
                alignment=ft.alignment.center,
                on_click=lambda e, idx=i: on_daxian_click(idx)
            )
            daxian_row.controls.append(btn)

            empty_btn = ft.Container(expand=1, height=25, border=ft.border.all(0.5, "grey300"))
            liunian_row.controls.append(empty_btn)

    def on_export_result(e: ft.FilePickerResultEvent):
        if e.path:
            try:
                now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M")
                filename = f"zw_export_{now_str}.csv"
                filepath = os.path.join(e.path, filename)

                users = db.get_all_users()
                with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    # 增加群組欄位
                    writer.writerow(["姓名", "性別", "生辰", "備註", "群組"])
                    for u in users:
                        birth_str = f"{u['year']}{u['month']:02d}{u['day']:02d}{u['hour']:02d}{u['minute']:02d}"
                        # 寫入群組，若無則預設為 "其他"
                        writer.writerow([u['name'], u['gender'], birth_str, u.get('note', ''), u.get('category', '其他')])
                show_snack(f"匯出成功: {filename}", "green700")
            except Exception as ex:
                show_snack(f"匯出失敗: {str(ex)}", "red800")

    def on_import_result(e: ft.FilePickerResultEvent):
        if e.files and len(e.files) > 0:
            try:
                # 取得當前設定的群組清單
                valid_categories = get_categories()
                # 預設歸類為最後一個群組
                default_cat = valid_categories[-1]

                count = 0
                with open(e.files[0].path, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    next(reader, None)  # 跳過標題
                    for row in reader:
                        if len(row) >= 3:
                            name, gender, birth_str = row[0], row[1], row[2]
                            note = row[3] if len(row) > 3 else ""
                            # 讀取 CSV 中的群組，若不在設定清單內，則強制歸類到 default_cat
                            csv_cat = row[4].strip() if len(row) > 4 else ""
                            final_cat = csv_cat if csv_cat in valid_categories else default_cat

                            if len(birth_str) == 12 and birth_str.isdigit():
                                data = {
                                    "name": name, "gender": gender,
                                    "year": int(birth_str[:4]),
                                    "month": int(birth_str[4:6]),
                                    "day": int(birth_str[6:8]),
                                    "hour": int(birth_str[8:10]),
                                    "minute": int(birth_str[10:12]),
                                    "is_lunar": False, "category": final_cat, "note": note
                                }
                                db.add_user(data)
                                count += 1
                show_snack(f"成功匯入 {count} 筆資料", "green700")
                if len(page.views) > 1 and page.views[-1].route == "/db":
                    refresh_db_list()
            except Exception as ex:
                show_snack(f"匯入失敗: {str(ex)}", "red800")

    export_picker = ft.FilePicker(on_result=on_export_result)
    import_picker = ft.FilePicker(on_result=on_import_result)
    page.overlay.extend([export_picker, import_picker])

    db_state = {"category": "全部", "keyword": "", "selected_ids": set(), "is_select_mode": False, "auto_anon": False }
    db_list_view = ft.ListView(expand=True, spacing=4, padding=4)
    db_appbar = ft.AppBar(toolbar_height=UI_CFG["appbar_height"])

    def refresh_db_list():
        cat = None if db_state["category"] == "全部" else db_state["category"]
        users = db.get_all_users(keyword=db_state["keyword"], category=cat)
        db_list_view.controls.clear()

        if not users:
            db_list_view.controls.append(
                ft.Container(content=ft.Text("沒有符合的資料", color="grey", size=UI_CFG["db_list_font"]), padding=20,
                             alignment=ft.alignment.center))
        else:
            for u in users:
                uid = u['id']
                is_sel = uid in db_state["selected_ids"]
                name_str = u['name'][:8]
                birth_str = f"{u['year']}/{u['month']:02d}/{u['day']:02d} {u['hour']:02d}:{u['minute']:02d}"
                row_content = ft.Row([
                    ft.Text(name_str, width=65, size=UI_CFG["db_list_font"], weight="bold",
                            color="blue700" if u['gender'] == "男" else "pink700", text_align="right"),
                    ft.Text(u['gender'], width=25, size=UI_CFG["db_list_font"], color="grey800", text_align="center"),
                    ft.Text(birth_str, width=100, size=UI_CFG["db_list_font"], color="grey800", text_align="left"),
                    ft.Text(u['note'], expand=True, size=UI_CFG["db_list_font"], color="grey600", no_wrap=True,
                            overflow="ellipsis", text_align="left")
                ], alignment="start", vertical_alignment="center", spacing=5)

                if db_state["is_select_mode"]:
                    row_content.controls.insert(0, ft.Icon(
                        ft.Icons.CHECK_CIRCLE, color="blue" if is_sel else "grey", size=16))

                container = ft.Container(
                    content=row_content, height=UI_CFG["db_list_height"],
                    padding=ft.padding.symmetric(horizontal=8), border=ft.border.all(1, "grey300"),
                    border_radius=6, bgcolor="blue50" if is_sel else "white",
                    on_long_press=lambda e, id=uid: on_db_long_press(id),
                    on_click=lambda e, user=u: on_db_click(user)
                )
                db_list_view.controls.append(container)
        update_db_appbar()
        page.update()

    def on_db_long_press(uid):
        if not db_state["is_select_mode"]:
            db_state["is_select_mode"] = True
            db_state["selected_ids"].add(uid)
            refresh_db_list()

    def on_db_click(user):
        if db_state["is_select_mode"]:
            uid = user['id']
            if uid in db_state["selected_ids"]:
                db_state["selected_ids"].remove(uid)
            else:
                db_state["selected_ids"].add(uid)
            if not db_state["selected_ids"]:
                db_state["is_select_mode"] = False
            refresh_db_list()
        else:
            load_user(user)

    def exit_select_mode(e=None):
        db_state["is_select_mode"] = False
        db_state["selected_ids"].clear()
        refresh_db_list()

    def delete_selected(e):
        def confirm_delete(e):
            for uid in db_state["selected_ids"]:
                db.delete_user(uid)
            show_snack(f"已刪除 {len(db_state['selected_ids'])} 筆資料")
            page.close(confirm_dlg)
            exit_select_mode()

        confirm_dlg = ft.AlertDialog(
            modal=True, title=ft.Text("確認刪除", size=UI_CFG["setting_title"]),
            content=ft.Text(f"確定要刪除選取的 {len(db_state['selected_ids'])} 筆資料嗎？", size=UI_CFG["setting_font"]),
            actions=[
                ft.TextButton("取消", on_click=lambda e: page.close(confirm_dlg)),
                ft.ElevatedButton("刪除", on_click=confirm_delete, bgcolor="red700", color="white")
            ], actions_padding=10
        )
        page.open(confirm_dlg)

    def move_selected(e):
        move_dd = ft.Dropdown(
            options=[ft.dropdown.Option(c) for c in get_categories()], value=get_categories()[0],
            dense=True, text_size=UI_CFG["setting_font"],
            content_padding=ft.padding.symmetric(vertical=8, horizontal=10)
        )

        def confirm_move(e):
            for uid in db_state["selected_ids"]:
                db.update_user_category(uid, move_dd.value)
            show_snack(f"已移動至 {move_dd.value}")
            page.close(move_dlg)
            exit_select_mode()

        move_dlg = ft.AlertDialog(
            modal=True, title=ft.Text("移動至群組", size=UI_CFG["setting_title"]), content=move_dd,
            actions=[
                ft.TextButton("取消", on_click=lambda e: page.close(move_dlg)),
                ft.TextButton("確定", on_click=confirm_move)
            ]
        )
        page.open(move_dlg)

    def edit_selected(e):
        if len(db_state["selected_ids"]) == 1:
            uid = list(db_state["selected_ids"])[0]
            users = db.get_all_users()
            for u in users:
                if u['id'] == uid:
                    load_user(u, auto_calc=False)
                    app_state["edit_uid"] = uid
                    dialog_title.value = "編輯生辰"
                    submit_btn.text = "儲存"
                    save_db_cb.visible = False
                    hide_name_cb.visible = False
                    page.open(dialog)
                    exit_select_mode()
                    break

    def update_db_appbar():
        if db_state["is_select_mode"]:
            db_appbar.title = ft.Text(f"已選取 {len(db_state['selected_ids'])} 筆", size=UI_CFG["appbar_title"])
            db_appbar.leading = ft.IconButton(ft.Icons.CLOSE, on_click=exit_select_mode)
            actions = [
                ft.IconButton(ft.Icons.DRIVE_FILE_MOVE_OUTLINE, tooltip="移動", on_click=move_selected),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, tooltip="刪除", icon_color="red", on_click=delete_selected)
            ]
            if len(db_state["selected_ids"]) == 1:
                actions.insert(0, ft.IconButton(ft.Icons.EDIT, tooltip="編輯", on_click=edit_selected))
            db_appbar.actions = actions
        else:
            db_appbar.title = ft.Text("資料庫管理", size=UI_CFG["appbar_title"])
            db_appbar.leading = ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: page.go("/"))
            db_appbar.actions = [
                ft.IconButton(ft.Icons.FILE_DOWNLOAD, tooltip="匯入 CSV",
                              on_click=lambda _: import_picker.pick_files(allow_multiple=False,
                                                                          allowed_extensions=["csv"])),
                ft.IconButton(ft.Icons.FILE_UPLOAD, tooltip="匯出 CSV",
                              on_click=lambda _: export_picker.get_directory_path())
            ]

    def open_db_view():
        # 修改：從設定讀取上次的分類，預設為 "全部"
        last_db_cat = settings.get("last_db_category") or "全部"
        db_state["category"] = last_db_cat
        db_state["keyword"] = ""
        exit_select_mode()
        cats = ["全部"] + get_categories()
        # 找出上次選取的分類在 Tabs 中的索引位置
        initial_tab_index = cats.index(last_db_cat) if last_db_cat in cats else 0

        def on_tab_change(e):
            selected_cat = cats[e.control.selected_index]
            db_state["category"] = selected_cat
            # 新增：切換分頁時立即記憶
            settings.set("last_db_category", selected_cat)
            exit_select_mode()

        def on_search(e):
            db_state["keyword"] = e.control.value
            refresh_db_list()

        search_field = ft.TextField(
            hint_text="搜尋姓名或備註...", prefix_icon=ft.Icons.SEARCH, on_change=on_search, dense=True,
            content_padding=ft.padding.symmetric(vertical=8, horizontal=10),
            border_radius=20, text_size=UI_CFG["setting_font"],
            color="black", bgcolor="white", hint_style=ft.TextStyle(color="grey500")
        )
        tabs = ft.Tabs(
            selected_index=initial_tab_index,  # 修改：使用計算出的索引
            on_change=on_tab_change, scrollable=True, height=40,
            label_color="black", unselected_label_color="grey",
            tabs=[ft.Tab(text=c) for c in cats]
        )
        auto_anon_cb = ft.Checkbox(
            label="匿名排盤",
            value=db_state["auto_anon"],
            label_style=ft.TextStyle(size=12),
            on_change=lambda e: db_state.update({"auto_anon": e.control.value})
        )
        return ft.View(
            "/db", [
                db_appbar, tabs,
                ft.Container(
                    ft.Row([search_field, auto_anon_cb], alignment="spaceBetween"),  # 讓搜尋跟勾選並排
                    padding=ft.padding.symmetric(horizontal=10, vertical=5)
                ),
                db_list_view
            ],
            padding=0, bgcolor="white"
        )

    def open_settings_view():
        def save_settings(e):
            settings.set("late_zi", late_zi_dd.value)
            settings.set("leap_month", leap_month_dd.value)
            settings.set("wu_sihua", wu_sihua_dd.value)
            settings.set("geng_sihua", geng_sihua_dd.value)
            settings.set("ren_sihua", ren_sihua_dd.value)
            settings.set("cat_1", cat1_tf.value)
            settings.set("cat_2", cat2_tf.value)
            settings.set("cat_3", cat3_tf.value)
            settings.set("cat_4", cat4_tf.value)
            settings.set("cat_5", cat5_tf.value)
            settings.set("minimal_stars", minimal_stars_cb.value)


            try:
                x_val = int(x_offset_tf.value)
                settings.set("x_offset", x_val)
                app_state["x_offset"] = x_val
            except:
                settings.set("x_offset", 0)
                app_state["x_offset"] = 0

            try:
                y_val = int(y_offset_tf.value)
                settings.set("y_offset", y_val)
                app_state["y_offset"] = y_val
            except:
                settings.set("y_offset", 0)
                app_state["y_offset"] = 0

            # 新增：儲存字體偏移
            try:
                f_val = int(font_offset_tf.value)
                settings.set("font_offset", f_val)
                app_state["font_offset"] = f_val
            except:
                settings.set("font_offset", 0)
                app_state["font_offset"] = 0
            # 修正：在這裡儲存星曜偏移
            try:
                sw_val = int(star_wrap_offset_tf.value)
                settings.set("star_wrap_offset", sw_val)
                app_state["star_wrap_offset"] = sw_val
            except:
                pass

            # 新增：儲存星曜間距偏移
            try:
                scw_val = int(star_col_width_offset_tf.value)
                settings.set("star_col_width_offset", scw_val)
                app_state["star_col_width_offset"] = scw_val
            except:
                settings.set("star_col_width_offset", 0)
                app_state["star_col_width_offset"] = 0
            # --- 關鍵：如果已經有排盤資料，立即重新計算並重繪 ---
            if app_state["full_data"]:
                # 重新執行計算邏輯，這會自動呼叫 draw_chart()
                do_calculate_logic(app_state["birth_info"])

            input_category.options = [ft.dropdown.Option(c) for c in get_categories()]
            show_snack("設定已儲存", "green700")
            page.go("/")

        dd_style = {"dense": True, "text_size": UI_CFG["setting_font"],
                    "label_style": ft.TextStyle(size=UI_CFG["input_label"]),
                    "content_padding": ft.padding.symmetric(vertical=8, horizontal=10),
                    "color": "black",   "bgcolor" :  "white"}
        tf_style = {"dense": True, "text_size": UI_CFG["setting_font"],
                    "label_style": ft.TextStyle(size=UI_CFG["input_label"]),
                    "content_padding": ft.padding.symmetric(vertical=8, horizontal=10),
                    "color": "black",   "bgcolor" : "white"}

        # 將下拉選單加上 expand=1 以便並排
        late_zi_dd = ft.Dropdown(label="晚子時", options=[ft.dropdown.Option("併入隔日 (早子)"),
                                                          ft.dropdown.Option("歸入當日 (00:00)")],
                                 value=settings.get("late_zi") or "併入隔日 (早子)", expand=1, **dd_style)
        leap_month_dd = ft.Dropdown(label="閏月", options=[ft.dropdown.Option("15日區分"), ft.dropdown.Option("歸同月"),
                                                           ft.dropdown.Option("歸下月")],
                                    value=settings.get("leap_month") or "15日區分", expand=1, **dd_style)
        wu_sihua_dd = ft.Dropdown(label="戊干",
                                  options=[ft.dropdown.Option("貪陰右機"), ft.dropdown.Option("貪陰陽機")],
                                  value=settings.get("wu_sihua") or "貪陰右機", expand=1, **dd_style)
        geng_sihua_dd = ft.Dropdown(label="庚干",
                                    options=[ft.dropdown.Option("陽武陰同"), ft.dropdown.Option("陽武同陰"),
                                             ft.dropdown.Option("陽武府同"), ft.dropdown.Option("陽武同相")],
                                    value=settings.get("geng_sihua") or "陽武陰同", expand=1, **dd_style)
        ren_sihua_dd = ft.Dropdown(label="壬干",
                                   options=[ft.dropdown.Option("梁紫左武"), ft.dropdown.Option("梁紫府武")],
                                   value=settings.get("ren_sihua") or "梁紫左武", expand=1, **dd_style)

        cats = get_categories()
        cat1_tf = ft.TextField(label="分類 1", value=cats[0], expand=1, **tf_style)
        cat2_tf = ft.TextField(label="分類 2", value=cats[1], expand=1, **tf_style)
        cat3_tf = ft.TextField(label="分類 3", value=cats[2], expand=1, **tf_style)
        cat4_tf = ft.TextField(label="分類 4", value=cats[3], expand=1, **tf_style)
        cat5_tf = ft.TextField(label="分類 5", value=cats[4], expand=1, **tf_style)

        x_offset_tf = ft.TextField(label="X軸偏移量 (+/-)", value=str(settings.get("x_offset", 0)),
                                   keyboard_type="number", expand=1, **tf_style)
        y_offset_tf = ft.TextField(label="Y軸偏移量 (+/-)", value=str(settings.get("y_offset", 0)),
                                   keyboard_type="number", expand=1, **tf_style)


        font_offset_tf = ft.TextField(label="全域字體縮放 (+/-)", value=str(settings.get("font_offset", 0)),
                                      keyboard_type="number", expand=1, **tf_style)
        star_wrap_offset_tf = ft.TextField(label="星曜換行偏移 (+/-)", value=str(settings.get("star_wrap_offset", 0)),
                                           keyboard_type="number", expand=1, **tf_style)
        # 新增：星曜間距偏移輸入框
        star_col_width_offset_tf = ft.TextField(label="星曜左右間距 (+/-)",
                                                value=str(settings.get("star_col_width_offset", 0)),
                                                keyboard_type="number", expand=1, **tf_style)

        minimal_stars_cb = ft.Checkbox(
            label="北派星曜極簡化",
            value=settings.get("minimal_stars", True)
        )

        return ft.View(
            "/settings", [
                ft.AppBar(title=ft.Text("系統設定", size=UI_CFG["appbar_title"], color="black"),
                          toolbar_height=UI_CFG["appbar_height"], bgcolor="surfaceVariant",
                          leading=ft.IconButton(ft.Icons.ARROW_BACK, icon_color="black",
                                                on_click=lambda e: page.go("/"))),
                # 加上 expand=True 讓 ListView 佔滿剩餘空間並可捲動
                ft.ListView([
                    ft.Text("基本排盤設定", weight="bold", color="blue700", size=UI_CFG["setting_title"]),
                    ft.Row([late_zi_dd, leap_month_dd]), ft.Divider(height=10),
                    ft.Text("十干四化設定", weight="bold", color="blue700", size=UI_CFG["setting_title"]),
                    ft.Row([wu_sihua_dd, geng_sihua_dd]),
                    ft.Row([ren_sihua_dd, ft.Container(expand=1)]), ft.Divider(height=10),
                    ft.Text("資料庫群組命名 (限4字)", weight="bold", color="blue700", size=UI_CFG["setting_title"]),
                    ft.Row([cat1_tf, cat2_tf]),
                    ft.Row([cat3_tf, cat4_tf]),
                    ft.Row([cat5_tf, ft.Container(expand=1)]), ft.Divider(height=10),
                    ft.Text("畫布與字體微調", weight="bold", color="blue700", size=UI_CFG["setting_title"]),
                    ft.Row([x_offset_tf, y_offset_tf]),
                    ft.Row([font_offset_tf, star_wrap_offset_tf]),  # 修正：將兩個偏移並排
                    ft.Row([star_col_width_offset_tf, ft.Container(expand=1)]),  # 新增：將星曜間距偏移單獨一行或與其他設定並排
                    ft.Row([minimal_stars_cb]), ft.Divider(height=10),

                    ft.Container(height=10),
                    ft.ElevatedButton(content=ft.Text("儲存設定", size=UI_CFG["btn_font"], color="white"),
                                      on_click=save_settings, bgcolor="blue700", height=40),
                    ft.TextButton(
                        "重置螢幕偵測(測試中)",
                        icon=ft.Icons.REFRESH,
                        on_click=lambda _: [
                            settings.set("locked_width", None),
                            settings.set("locked_height", None),
                            show_snack("已重置", "blue700")
                        ]
                    )
                ], padding=15, spacing=10, expand=True)
            ], padding=0, bgcolor="white"
        )

    def load_user(u, auto_calc=True):
        try:
            if db_state["auto_anon"]:
                hide_name_cb.value = True
            input_name.value = u['name']
            input_year.value = str(u['year'])
            input_month.value = str(u['month'])
            input_day.value = str(u['day'])
            input_hour.value = str(u['hour'])
            input_minute.value = str(u['minute'])
            gender_radio.value = u['gender']
            calendar_radio.value = "農曆" if u['is_lunar'] else "國曆"
            input_category.value = u.get('category', get_categories()[0])
            input_note.value = u.get('note', '')
            if auto_calc:
                birth_data = {
                    "name": input_name.value, "year": int(input_year.value),
                    "month": int(input_month.value), "day": int(input_day.value),
                    "hour": int(input_hour.value), "minute": int(input_minute.value),
                    "gender": gender_radio.value, "is_lunar": calendar_radio.value == "農曆",
                    "category": input_category.value, "note": input_note.value
                }
                do_calculate_logic(birth_data)
                page.go("/")
        except Exception as ex:
            traceback.print_exc()

    tf_style = {"dense": True, "text_size": UI_CFG["setting_font"],
                "label_style": ft.TextStyle(size=UI_CFG["input_label"]),
                "content_padding": ft.padding.symmetric(vertical=8, horizontal=10),
                "color": "black",   "bgcolor" :  "white"}

    input_name = ft.TextField(label="姓名", **tf_style)
    input_year = ft.TextField(label="年", expand=1, keyboard_type="number", **tf_style)
    input_month = ft.TextField(label="月", expand=1, keyboard_type="number", **tf_style)
    input_day = ft.TextField(label="日", expand=1, keyboard_type="number", **tf_style)
    input_hour = ft.TextField(label="時", expand=1, keyboard_type="number", **tf_style)
    input_minute = ft.TextField(label="分", expand=1, keyboard_type="number", value="0", **tf_style)

    gender_radio = ft.RadioGroup(
        content=ft.Row([ft.Radio(value="男", label="男"), ft.Radio(value="女", label="女")], spacing=0), value="男")
    calendar_radio = ft.RadioGroup(
        content=ft.Row([ft.Radio(value="國曆", label="國曆"), ft.Radio(value="農曆", label="農曆")], spacing=0),
        value="國曆")

    last_input_cat = settings.get("last_input_category") or get_categories()[0]
    input_category = ft.Dropdown(label="分類", expand=2, options=[ft.dropdown.Option(c) for c in get_categories()],
                                 value=get_categories()[0], **tf_style)
    input_note = ft.TextField(label="備註", **tf_style)
    save_db_cb = ft.Checkbox(label="儲存至資料庫", value=False)
    hide_name_cb = ft.Checkbox(label="隱藏姓名", value=False, on_change=lambda e: draw_chart())
    hide_birth_cb = ft.Checkbox(label="隱藏生辰", value=False, on_change=lambda e: draw_chart())

    chart_grid = ft.Column(expand=True, spacing=0)

    bg_image = ft.Container(
        content=ft.Image(
            src="bg.png",
            fit=ft.ImageFit.CONTAIN,  # 改用 CONTAIN 確保正方形圖片完整顯示不被裁切
            opacity=0.075,
        ),
        alignment=ft.alignment.center,  # 這裡控制圖片在 Stack 中垂直水平置中
        expand=True,
    )

    chart_stack = ft.Stack([bg_image, chart_grid, overlay_canvas, drawing_layer], expand=True)
    chart_container = ft.Container(content=chart_stack, expand=True, bgcolor="white")

    dialog_title = ft.Text("輸入生辰", size=UI_CFG["appbar_title"], weight="bold")
    submit_btn = ft.ElevatedButton("排盤", on_click=on_dialog_submit, bgcolor="blue700", color="white")

    dialog = ft.AlertDialog(
        modal=True, title=dialog_title,
        content=ft.Column([
            ft.TextField(label="快速輸入(12位數)", hint_text="例:199001011230", on_change=quick_parse,
                         keyboard_type="number", **tf_style),
            input_name,
            calendar_radio,  # 國曆/農曆 獨立一排
            gender_radio,  # 性別 獨立一排
            ft.Row([input_year, input_month, input_day], spacing=5),
            ft.Row([input_hour, input_minute, input_category], spacing=5),
            input_note,
            ft.Column([
                ft.Row([save_db_cb], alignment="start"),
                ft.Row([hide_name_cb, hide_birth_cb], alignment="start")
            ], spacing=0)
        ], tight=True, width=300, scroll="always", spacing=5),
        actions=[
            ft.TextButton("取消", on_click=lambda e: page.close(dialog)),
            submit_btn
        ], actions_padding=5
    )

    btn_nan = ft.Container(
        content=ft.Text("南派", size=UI_CFG["btn_font"], weight="bold"),
        alignment=ft.alignment.center, width=60, height=32,
        border_radius=ft.border_radius.only(top_left=8, bottom_left=8),
        on_click=lambda e: toggle_school("南派")
    )
    btn_bei = ft.Container(
        content=ft.Text("北派", size=UI_CFG["btn_font"], weight="bold"),
        alignment=ft.alignment.center, width=60, height=32,
        border_radius=ft.border_radius.only(top_right=8, bottom_right=8),
        on_click=lambda e: toggle_school("北派")
    )
    toggle_school(app_state["school"])

    school_toggle_row = ft.Container(
        content=ft.Row([btn_nan, btn_bei], spacing=0),
        border=ft.border.all(1, "blue700"), border_radius=8, width=122
    )

    def open_dialog(e):
        app_state["edit_uid"] = None
        dialog_title.value = "輸入生辰"
        submit_btn.text = "排盤"
        save_db_cb.visible = True
        hide_name_cb.visible = True
        input_name.value = ""
        page.open(dialog)

    def show_about_dialog(e):
        about_dlg = ft.AlertDialog(
            title=ft.Text("關於系統", weight="bold", size=UI_CFG["setting_title"]),
            content=ft.Column([
                ft.Container(
                    content=ft.Image(src="ZWMaster.png", width=80, height=80),
                    border_radius=15,
                    clip_behavior=ft.ClipBehavior.ANTI_ALIAS
                ),
                #ft.Image(src="ZWMaster.png", width=80, height=80, fit=ft.ImageFit.CONTAIN),
                ft.Container(height=10),
                ft.Markdown(ABOUT_TEXT, selectable=True, extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED)
            ], tight=True, horizontal_alignment="center", scroll="auto"),
            actions=[
                ft.TextButton("關閉", on_click=lambda e: page.close(about_dlg))
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        page.open(about_dlg)

    def route_change(route):
        page.views.clear()
        if page.route == "/db":
            page.views.append(open_db_view())
        elif page.route == "/settings":
            page.views.append(open_settings_view())
        else:
            # --- 根據模式決定 UI 元件 ---
            if app_state["drawing_mode"]:
                # 繪圖模式的頂部
                current_appbar = ft.AppBar(
                    leading=ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda _: toggle_drawing_mode(False)),
                    title=ft.Row([
                        ft.IconButton(ft.Icons.EDIT, tooltip="畫筆", on_click=lambda _: set_tool("pen")),
                        ft.IconButton(ft.Icons.NORTH_EAST, tooltip="箭頭", on_click=lambda _: set_tool("arrow")),
                        # 修正：CIRCLE_OUTLINE 改為 CIRCLE_OUTLINED
                        ft.IconButton(ft.Icons.CIRCLE_OUTLINED, tooltip="圓圈", on_click=lambda _: set_tool("circle")),
                        # 修正：RECTANGLE_OUTLINE 改為 RECTANGLE_OUTLINED (或用 SQUARE_OUTLINED)
                        ft.IconButton(ft.Icons.RECTANGLE_OUTLINED, tooltip="方形", on_click=lambda _: set_tool("rect")),
                        ft.IconButton(ft.Icons.TEXT_FIELDS, tooltip="文字", on_click=lambda _: set_tool("text")),
                    ], alignment="center", spacing=5),
                    bgcolor="blueGrey50", toolbar_height=UI_CFG["appbar_height"]
                )
                # 繪圖模式的底部
                current_bottombar = ft.BottomAppBar(
                    bgcolor="blueGrey50", height=60,
                    content=ft.Row([
                        ft.Row([
                            ft.Text("粗細", size=12, weight="bold"),
                            ft.Slider(min=1, max=10, value=app_state["stroke_width"], width=150,
                                      on_change=change_stroke),
                        ], alignment="center", spacing=5),
                        # 右側：清除與復原
                        ft.IconButton(ft.Icons.DELETE_FOREVER, tooltip="清除全部", icon_color="red",
                                      on_click=clear_draw_history),
                        ft.IconButton(ft.Icons.UNDO, tooltip="復原", on_click=undo_draw),
                    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
                )
                drawing_gesture.visible = True # 開啟繪圖層
            else:
                # 原本的 AppBar
                current_appbar = ft.AppBar(
                    title=ft.Row([
                        ft.Container(content=ft.Image(src="ZWMaster.png", width=28, height=28), border_radius=8, clip_behavior=ft.ClipBehavior.ANTI_ALIAS),
                        ft.Text("ZWMaster Mobile", weight="bold", size=UI_CFG["appbar_title"])
                    ], spacing=8),
                    toolbar_height=UI_CFG["appbar_height"], bgcolor="surfaceVariant",
                    leading=ft.IconButton(ft.Icons.STORAGE, tooltip="資料庫", on_click=lambda e: page.go("/db")),
                    actions=[
                        # 在這裡增加進入繪圖模式的按鈕
                        ft.IconButton(ft.Icons.DRAW, tooltip="進入繪圖模式", on_click=lambda _: toggle_drawing_mode(True)),
                        ft.IconButton(ft.Icons.INFO_OUTLINE, tooltip="關於", on_click=show_about_dialog),
                        ft.IconButton(ft.Icons.SETTINGS, tooltip="設定", on_click=lambda e: page.go("/settings"))
                    ]
                )
                # 原本的 BottomAppBar
                current_bottombar = ft.BottomAppBar(
                    bgcolor="surfaceVariant", height=60,
                    padding=ft.padding.only(bottom=10),
                    content=ft.Row([
                        ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, tooltip="輸入排盤", icon_color="blue700", icon_size=28, on_click=open_dialog),
                        school_toggle_row,
                        ft.IconButton(ft.Icons.CALENDAR_MONTH, icon_color="blue700" if hide_birth_cb.value else "grey500",
                                      on_click=lambda e: toggle_hide_birth(e)),
                    ], alignment=ft.MainAxisAlignment.SPACE_EVENLY)
                )
                drawing_gesture.visible = False # 關閉繪圖層

            # 組裝 View
            page.views.append(ft.View(
                route="/",
                bgcolor="white",
                appbar=current_appbar,
                bottom_appbar=current_bottombar,
                controls=[chart_container, ft.Container(ft.Column([daxian_row, liunian_row], spacing=0), padding=5, bgcolor="white")],
                padding=0
            ))
        page.update()

    def toggle_drawing_mode(enabled):
        app_state["drawing_mode"] = enabled
        # 控制整個繪圖層的可見性
        drawing_layer.visible = enabled

        if enabled:
            app_state["selected_palace_idx"] = None
            draw_chart()

        route_change(page.route)
        page.update()

    def set_tool(tool):
        app_state["draw_tool"] = tool
        show_snack(f"當前工具: {tool}")
        route_change(None)

    def change_stroke(e):
        app_state["stroke_width"] = int(e.control.value)
        page.update()

    def undo_draw(e):
        if app_state["draw_history"]:
            app_state["draw_history"].pop()
            refresh_drawing_canvas()

    def clear_draw_history(e):
        app_state["draw_history"] = []
        refresh_drawing_canvas()

    def toggle_hide_birth(e):
        hide_birth_cb.value = not hide_birth_cb.value
        e.control.icon_color = "blue700" if hide_birth_cb.value else "grey500"
        draw_chart()
        page.update()

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    now = datetime.datetime.now()
    input_year.value = str(now.year)
    input_month.value = str(now.month)
    input_day.value = str(now.day)
    input_hour.value = str(now.hour)
    input_minute.value = str(now.minute)
    input_name.value = "當下時辰"

    page.go(page.route)

    initial_birth_data = {
        "name": input_name.value, "year": int(input_year.value),
        "month": int(input_month.value), "day": int(input_day.value),
        "hour": int(input_hour.value), "minute": int(input_minute.value),
        "gender": gender_radio.value, "is_lunar": calendar_radio.value == "農曆",
        "category": input_category.value, "note": input_note.value
    }
    do_calculate_logic(initial_birth_data)


if __name__ == "__main__":
    ft.app(target=main)