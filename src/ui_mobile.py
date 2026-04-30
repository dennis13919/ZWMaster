import flet as ft


class PalaceCell(ft.Container):
    """單個宮位組件"""

    def __init__(self, index, palace_data=None, sihua_table=None, dynamic_stars=None,
                 is_shen=False, is_laiyin=False, school="北派", dx_label="", ln_label="",
                 palace_width=105, font_offset=0, star_wrap_offset=0, star_col_width_offset=0):  # 新增 font_offset
        super().__init__()
        self.star_wrap_offset = star_wrap_offset
        self.index = index
        self._palace_data = palace_data
        self.sihua_table = sihua_table or {}
        self.dynamic_stars = dynamic_stars or {"daxian": [], "liunian": []}
        self.is_shen = is_shen
        self.is_laiyin = is_laiyin
        self.school = school
        self.dx_label = dx_label
        self.ln_label = ln_label
        self.palace_width = palace_width
        self.font_offset = font_offset  # 儲存偏移量
        self.star_col_width_offset = star_col_width_offset  # 新增：儲存星曜間距偏移量

        self.expand = 1
        self.border = ft.border.all(0.5, "grey400")
        self.padding = 2
        self.bgcolor = "white"
        self.content = self.build_cell()

    def _build_star_column(self, star_dict, badges, cfg):
        if isinstance(star_dict, dict):
            star_name = star_dict.get('name', '')
            s_type = star_dict.get('type', 'minor')
            brightness = star_dict.get('brightness', '')
        else:
            star_name = str(star_dict)
            s_type = 'minor'
            brightness = ''

        is_main = (s_type == "main")
        is_major = s_type in ["main", "gaux", "baux"]

        chars = []
        for char in star_name:
            chars.append(
                ft.Text(
                    char,
                    size=cfg["size_main"] if is_main else cfg["size_major"] if is_major else cfg["size_minor"],
                    weight="bold" if (is_main or is_major or cfg["weight_minor"] == "bold") else "normal",
                    color="black" if self.school == "北派" else (
                        "purple" if "紫" in star_name else "red" if is_main else "blue800" if is_major else cfg[
                            "color_minor"]),
                    style=ft.TextStyle(height=cfg["line_height"])
                )
            )

        col = ft.Column(chars, spacing=cfg["spacing_char"], horizontal_alignment="center", tight=True)

        if brightness and self.school != "北派":
            col.controls.append(
                ft.Container(
                    content=ft.Text(brightness, size=cfg["size_bright"], color=cfg["color_bright"],
                                    weight=cfg["weight_bright"], style=ft.TextStyle(height=cfg["line_height"])),
                    margin=ft.margin.only(top=cfg["spacing_star_bright"], bottom=cfg["spacing_bright_sihua"])
                )
            )

        if badges and self.school == "北派":
            col.controls.append(ft.Container(height=cfg["spacing_sihua_north_extra"]))

        for badge in badges:
            col.controls.append(badge)

        return col

    def _get_sihua_badges(self, star_name, cfg):
        badges = []
        if not self.sihua_table: return badges
        # 本命四化 (南北派都顯示)
        b_gan = self._palace_data.get('b_gan')
        if b_gan:
            sh = self.sihua_table.get(b_gan, {}).get(star_name)
            if sh: badges.append(self._create_badge(sh, "red600", cfg))
        # 大限四化 (只在南派顯示)
        if self.school == "南派":
            d_gan = self._palace_data.get('d_gan')
            if d_gan:
                sh = self.sihua_table.get(d_gan, {}).get(star_name)
                if sh: badges.append(self._create_badge(sh, "blue600", cfg))
        # 流年四化 (只在南派顯示)
        if self.school == "南派":
            l_gan = self._palace_data.get('l_gan')
            if l_gan:
                sh = self.sihua_table.get(l_gan, {}).get(star_name)
                if sh: badges.append(self._create_badge(sh, "green600", cfg))

        return badges

    def _create_badge(self, text, color, cfg):
        return ft.Container(
            content=ft.Text(text, size=cfg["size_sihua"], color="white", weight="normal",
                            style=ft.TextStyle(height=1.0)),
            bgcolor=color,
            border_radius=2,
            padding=ft.padding.symmetric(horizontal=0, vertical=0),
            margin=ft.margin.only(top=cfg["spacing_sihua_gap"])
        )

    def build_cell(self):
        # 所有字體大小都加上 self.font_offset
        cfg = {
            "size_main": 13 + self.font_offset,
            "size_major": 13 + self.font_offset,
            "size_minor": 12 + self.font_offset,
            "size_bright": 10 + self.font_offset,
            "size_sihua": 12 + self.font_offset,
            "size_palace_natal": 12 + self.font_offset,
            "size_palace_dx": 11 + self.font_offset,
            "size_palace_ln": 11 + self.font_offset,
            "size_daliu": 11 + self.font_offset,
            "weight_minor": "normal",       # 小星粗細 (bold 或 normal)
            "weight_bright": "normal",      # 亮度粗細 (bold 或 normal)
            "color_minor": "#1A237E",       # 小星顏色 (深藍色)
            "color_bright": "grey500",      # 亮度顏色 (灰色)
            "line_height": 1.0,         # 文字行高 (1.0 為最緊湊)
            "spacing_char": 0.1,        # 星曜直排時，字與字之間的上下間距
            "spacing_star_bright": 0.1, # 星曜與「亮度」之間的上下間距
            "spacing_bright_sihua": 1,  # 「亮度」與「四化標籤」之間的上下間距
            "spacing_sihua_gap": 1,     # 多個四化標籤疊加時，標籤之間的上下間距
            "spacing_sihua_north_extra": 3,
            "spacing_dynamic_star_palace": 4,
            # 每顆星之間的左右間距 (數值越小越緊湊)
            "star_col_width": (15 + (self.font_offset * 0.5) + self.star_col_width_offset) if self.school == "北派" else (
                        12 + (self.font_offset * 0.5) + self.star_col_width_offset),
            "star_row_height": 40 + (self.font_offset * 2),  # # 換行後，上下排的垂直間距
            "margin_right_stars": 0,    # 第一顆星距離右側的邊距
            "margin_top_stars": 2,      # 第一排星距離頂部的邊距
            "liunian_left_offset": 28 + (self.font_offset * 1.5),   # 流年標籤距離「左側」的距離
            "reserved_left_space": 40 + (self.font_offset * 2), # 左側預留給大限流年標籤的空間
            "row2_max_stars": 4,    # 第二排(偶數排)的最大星曜數量限制
            "margin_right_info": 2, # 干支的右側邊界
        }

        # 修改可用寬度計算，加入偏移量
        available_width = (self.palace_width
                           - cfg["margin_right_stars"]
                           - cfg["reserved_left_space"]
                           + self.star_wrap_offset)  # 這裡加入偏移

        W = max(1, int((available_width - 4) // cfg["star_col_width"]))
        L = min(W, cfg["row2_max_stars"])

        if not self._palace_data:
            return ft.Text(str(self.index), color="grey300")

        stack_controls = []

        right_bottom_items = []
        tag_text = ""
        if self.school == "北派" and self.is_laiyin:
            tag_text = "來因"
        elif self.school == "南派" and self.is_shen:
            tag_text = "身宮"

        if tag_text:
            right_bottom_items.append(
                ft.Container(
                    content=ft.Text(tag_text, size=10 + self.font_offset, color="purple700",
                                    style=ft.TextStyle(height=1.0)),
                    bgcolor="purple50",
                    border=ft.border.all(1, "purple200"),
                    border_radius=4,
                    padding=ft.padding.symmetric(horizontal=1, vertical=0),
                    margin=ft.margin.only(bottom=1)
                )
            )

        right_bottom_items.extend([
            ft.Container(
                content=ft.Text(f"{self._palace_data.get('gan', '')}{self._palace_data.get('zhi', '')}",
                                size=11 + self.font_offset,
                                color="grey700", style=ft.TextStyle(height=1.5)),
                padding=ft.padding.only(right=1)
            ),
            ft.Text(self._palace_data.get('name', ''), size=cfg["size_palace_natal"], weight="bold", color="black",
                    style=ft.TextStyle(height=1.0)),
        ])

        info_col = ft.Column(right_bottom_items, spacing=0, horizontal_alignment="end", tight=True)

        changsheng_str = self._palace_data.get("changsheng", "")
        if changsheng_str:
            cs_chars = [ft.Text(c, size=10 + self.font_offset, color="grey600", style=ft.TextStyle(height=1.1)) for c in
                        changsheng_str]
            cs_col = ft.Column(cs_chars, spacing=0, horizontal_alignment="center", tight=True)
            bottom_right_row = ft.Row(
                controls=[cs_col, info_col],
                spacing=0,
                vertical_alignment="end",
                tight=True
            )
            stack_controls.append(ft.Container(bottom_right_row, right=cfg["margin_right_info"], bottom=2))
        else:
            stack_controls.append(ft.Container(info_col, right=cfg["margin_right_info"], bottom=2))

        stars = self._palace_data.get('stars', [])
        for i in reversed(range(len(stars))):
            s = stars[i]
            s_name = s.get('name', '') if isinstance(s, dict) else s
            badges = self._get_sihua_badges(s_name, cfg)
            star_col = self._build_star_column(s, badges, cfg)

            cycle = i // (W + L)
            rem = i % (W + L)

            if rem < W:
                r = 2 * cycle
                c = rem
                right_pos = cfg["margin_right_stars"] + c * cfg["star_col_width"]
            else:
                r = 2 * cycle + 1
                c = rem - W
                right_pos = cfg["margin_right_stars"] + (W - 1 - c) * cfg["star_col_width"]

            top_pos = cfg["margin_top_stars"] + r * cfg["star_row_height"]
            stack_controls.append(ft.Container(star_col, right=right_pos, top=top_pos))

        dx_controls = []
        ln_controls = []

        def is_valid_dynamic(star_name):
            clean_name = star_name.replace("大", "").replace("年", "")
            return clean_name not in ["地空", "地劫"]

        if self.school == "南派":
            for s in self.dynamic_stars.get("daxian", []):
                if is_valid_dynamic(s['name']):
                    name = s['name'].replace("大", "")
                    dx_controls.append(
                        ft.Text(name, size=11 + self.font_offset, color="blue700", style=ft.TextStyle(height=1.0)))
            for s in self.dynamic_stars.get("liunian", []):
                if is_valid_dynamic(s['name']):
                    name = s['name'].replace("年", "")
                    ln_controls.append(
                        ft.Text(name, size=11 + self.font_offset, color="green700", style=ft.TextStyle(height=1.0)))

        if dx_controls and self.dx_label:
            dx_controls.append(ft.Container(height=cfg["spacing_dynamic_star_palace"]))
        if ln_controls and self.ln_label:
            ln_controls.append(ft.Container(height=cfg["spacing_dynamic_star_palace"]))

        if self.dx_label:
            dx_controls.append(
                ft.Text(self.dx_label, size=cfg["size_palace_dx"], color="blue700", weight="bold",
                        style=ft.TextStyle(height=1.0)))
        if self.ln_label:
            ln_controls.append(
                ft.Text(self.ln_label, size=cfg["size_palace_ln"], color="green700", weight="bold",
                        style=ft.TextStyle(height=1.0)))

        dx_col = ft.Column(dx_controls, spacing=0, horizontal_alignment="center", tight=True)
        ln_col = ft.Column(ln_controls, spacing=0, horizontal_alignment="center", tight=True)

        stack_controls.append(ft.Container(dx_col, left=2, bottom=2))
        stack_controls.append(ft.Container(ln_col, left=cfg["liunian_left_offset"], bottom=2))

        return ft.Stack(stack_controls, expand=True)