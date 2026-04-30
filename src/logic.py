#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ZWM紫微斗數排盤計算核心 (Logic Core) - 動態查詢版
"""

from datetime import datetime

from lunar_python import Lunar, Solar

class ZiweiCalculator:
    TIANGAN = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
    DIZHI = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

    NAYIN_TABLE = {
        "甲子": 4, "乙丑": 4, "丙寅": 6, "丁卯": 6, "戊辰": 3, "己巳": 3,
        "庚午": 5, "辛未": 5, "壬申": 4, "癸酉": 4, "甲戌": 6, "乙亥": 6,
        "丙子": 2, "丁丑": 2, "戊寅": 5, "己卯": 5, "庚辰": 4, "辛巳": 4,
        "壬午": 3, "癸未": 3, "甲申": 2, "乙酉": 2, "丙戌": 5, "丁亥": 5,
        "戊子": 6, "己丑": 6, "庚寅": 3, "辛卯": 3, "壬辰": 2, "癸巳": 2,
        "甲午": 4, "乙未": 4, "丙申": 6, "丁酉": 6, "戊戌": 3, "己亥": 3,
        "庚子": 5, "辛丑": 5, "壬寅": 4, "癸卯": 4, "甲辰": 6, "乙巳": 6,
        "丙午": 2, "丁未": 2, "戊申": 5, "己酉": 5, "庚戌": 4, "辛亥": 4,
        "壬子": 3, "癸丑": 3, "甲寅": 2, "乙卯": 2, "丙辰": 5, "丁巳": 5,
        "戊午": 6, "己未": 6, "庚申": 3, "辛酉": 3, "壬戌": 2, "癸亥": 2
    }

    @staticmethod
    def get_dizhi_index(char):
        return ZiweiCalculator.DIZHI.index(char)

    @staticmethod
    def get_tiangan_index(char):
        return ZiweiCalculator.TIANGAN.index(char)

    @staticmethod
    def calculate_birth_info(year, month, day, hour, minute=0, is_lunar=False, config=None):
        if config is None: config = {"late_zi_behavior": 0, "leap_month_behavior": 0}
        calc_year, calc_month, calc_day, calc_hour = year, month, day, hour
        if hour == 23 and config.get("late_zi_behavior") == 1:
            temp_solar = Solar.fromYmdHms(year, month, day, hour, minute, 0)
            next_solar = temp_solar.next(1)
            calc_year, calc_month, calc_day, calc_hour = next_solar.getYear(), next_solar.getMonth(), next_solar.getDay(), 0

        if is_lunar:
            lunar = Lunar.fromYmdHms(calc_year, calc_month, calc_day, calc_hour, minute, 0)
            solar = lunar.getSolar()
        else:
            solar = Solar.fromYmdHms(calc_year, calc_month, calc_day, calc_hour, minute, 0)
            lunar = solar.getLunar()

        lunar_month, lunar_day = lunar.getMonth(), lunar.getDay()
        if lunar.getMonth() < 0:
            actual_month = abs(lunar_month)
            behavior = config.get("leap_month_behavior", 0)
            if behavior == 1 or (behavior == 2 and lunar_day > 15):
                lunar_month = actual_month + 1
            else:
                lunar_month = actual_month
        if lunar_month > 12: lunar_month = 1

        return {
            "year": solar.getYear(), "month": solar.getMonth(), "day": solar.getDay(),
            "hour": hour, "calc_hour": calc_hour, "minute": minute,  # calc_hour 是處理晚子時後的時辰
            "lunar_year": lunar.getYear(), "lunar_month": lunar_month, "lunar_day": lunar_day,
            "year_gan": lunar.getYearGan(), "year_zhi": lunar.getYearZhi(),
            "lunar_month_str": f"{abs(lunar.getMonth())}月" if lunar.getMonth() < 0 else lunar.getMonthInChinese() + "月",
            "lunar_day_str": lunar.getDayInChinese(), "lunar_hour_str": lunar.getTimeZhi() + "時",
            "solar_date_str": f"{year}年{month}月{day}日 {hour}時{minute}分",
            "is_leap": lunar.getMonth() < 0
        }

    # 計算中宮的資訊
    @classmethod
    def calculate_chart(cls, birth_info, config=None):
        if config is None: config = {}
        school = config.get('school', '北派')  # 預設北派

        sihua_table = cls.generate_sihua_table(config)
        palaces = cls._init_palaces(birth_info["year_gan"])
        # 使用 calc_hour 來決定時辰索引
        ming_pos, hour_idx = cls._setup_palace_names(palaces, birth_info["lunar_month"], birth_info["calc_hour"])
        wuxing_jum, wuxing_str = cls._get_wuxing_jum(palaces[ming_pos])

        gan, zhi, mon, day = birth_info["year_gan"], birth_info["year_zhi"], birth_info["lunar_month"], birth_info[
            "lunar_day"]

        # 來因宮
        laiyin_idx, sen_idx = -1, -1
        for i, p in enumerate(palaces):  # 遍歷所有宮位，從子宮開始 (index 0)
            if p["gan"] == gan:  # gan 是 birth_info["year_gan"]
                laiyin_idx = i
                break

        # 基礎星曜 (南北派共有)
        cls._add_main_stars(palaces, wuxing_jum, day)
        # 使用 calc_hour 來排文昌文曲
        cls._add_aux_stars(palaces, mon, hour_idx)

        gender = birth_info.get("gender", "男")
        yinyang = {"甲": "陽", "丙": "陽", "戊": "陽", "庚": "陽", "壬": "陽"}.get(gan, "陰")

        # 根據流派增加星曜
        if school == "南派":
            # 使用 calc_hour 來排南派輔星
            cls._add_southern_stars(palaces, gan, zhi, hour_idx)
            sen_idx = cls._add_minor_stars(palaces, gan, zhi, mon, day, hour_idx, yinyang + gender)
            # --- 新增：計算長生十二神 ---
            changsheng_start = {2: 8, 3: 11, 4: 5, 5: 8, 6: 2}[wuxing_jum]  # 申=8, 亥=11, 巳=5, 寅=2
            changsheng_names = ["長生", "沐浴", "冠帶", "臨官", "帝旺", "衰", "病", "死", "墓", "絕", "胎", "養"]
            is_forward = (yinyang == "陽" and gender == "男") or (yinyang == "陰" and gender == "女")

            for i in range(12):
                idx = (changsheng_start + i) % 12 if is_forward else (changsheng_start - i + 12) % 12
                palaces[idx]["changsheng"] = changsheng_names[i]

        return {
            "palaces": palaces,
            "center_info": {
                "name": birth_info.get("name", "匿名"),
                "solar_line": f"西元 {birth_info['solar_date_str']}",
                "lunar_line": f"農曆 {gan}{zhi}年 {birth_info['lunar_month_str']} {birth_info['lunar_day_str']} {birth_info['lunar_hour_str']}",
                "ming_line": f"{yinyang}{gender}{wuxing_str}",
                "gender": gender, "yinyang": yinyang, "birth_year_gan": gan
            },
            "ming_index": ming_pos,
            "sihua_table": sihua_table,
            "config": config,  # 確保 config 被傳回給 UI 層
            "shen_idx": sen_idx,
            "laiyin_idx": laiyin_idx
        }

    # 回傳宮位的干支
    @staticmethod
    def _init_palaces(year_gan):
        # 寅宮地支索引是 2
        # 根據年干決定寅宮天干
        yin_gan_map = {
            "甲": "丙", "己": "丙",
            "乙": "戊", "庚": "戊",
            "丙": "庚", "辛": "庚",
            "丁": "壬", "壬": "壬",
            "戊": "甲", "癸": "甲"
        }
        yin_gan_char = yin_gan_map.get(year_gan, "甲")  # 預設為甲，以防萬一
        yin_gan_actual_idx = ZiweiCalculator.get_tiangan_index(yin_gan_char)

        palaces = [None] * 12
        for i in range(12):
            # 地支從子 (0) 到亥 (11)
            zhi_char = ZiweiCalculator.DIZHI[(i+2)%12]

            # 計算該宮位的天干
            # 從寅宮 (index 2) 的天干開始，順排十二宮天干
            gan_idx = (yin_gan_actual_idx + (i - 2 + 12)) % 10
            gan_char = ZiweiCalculator.TIANGAN[gan_idx]

            palaces[(i+2)%12] = {"gan": gan_char, "zhi": zhi_char, "name": "", "stars": []}

        return palaces

    # 傳回命宮位置，時辰。填好宮位名稱
    @staticmethod
    def _setup_palace_names(palaces, month, calc_hour):
        # 時辰索引 (子時 0, 丑時 1, ..., 亥時 11)
        # calc_hour 是 0-23，所以需要轉換
        # 子時 (23-01) -> 0
        # 丑時 (01-03) -> 1
        # ...
        # 亥時 (21-23) -> 11
        hour_idx = (calc_hour + 1) // 2 % 12  # 這是原來的邏輯，保持不變

        # 命宮位置：寅宮起正月，順數到生月，再從生月逆數到生時
        # 寅宮地支索引是 2
        # 命宮起始點：寅宮 (2) + (生月 - 1)
        # 然後從這個點逆數到生時 (hour_idx)
        ming_pos = (2 + (month - 1) - hour_idx + 12) % 12  # 確保結果為正

        names = ["命宮", "兄弟", "夫妻", "子女", "財帛", "疾厄", "遷移", "奴僕", "官祿", "田宅", "福德", "父母"]
        for i in range(12):
            # 從命宮開始逆數，填入宮位名稱
            palaces[(ming_pos - i + 12) % 12]["name"] = names[i]
        return ming_pos, hour_idx

    @staticmethod
    def _get_wuxing_jum(ming_palace):
        nk = ming_palace["gan"] + ming_palace["zhi"]
        jum = ZiweiCalculator.NAYIN_TABLE.get(nk, 2)
        name = {2: "水二局", 3: "木三局", 4: "金四局", 5: "土五局", 6: "火六局"}[jum]
        return jum, name

    # 放入主星
    @staticmethod
    def _add_main_stars(palaces, wuxing_jum, day):
        # 紫微星系起點
        x = 0
        while (day + x) % wuxing_jum != 0: x += 1
        bp = (2 + ((day + x) // wuxing_jum - 1)) % 12  # 寅宮起初一，順數到生月，再從生月逆數到生時
        zp = (bp + x) % 12 if x % 2 == 0 else (bp - x + 12) % 12  # 確保結果為正

        for n, o in [("紫微", 0), ("天機", -1), ("太陽", -3), ("武曲", -4), ("天同", -5), ("廉貞", -8)]:
            pos = (zp + o + 12) % 12  # 確保結果為正
            zhi = palaces[pos]["zhi"]
            palaces[pos]["stars"].append({
                "name": n,
                "type": "main",
                "brightness": ZiweiCalculator.get_brightness(n, zhi)
            })

        # 天府星系起點
        # 天府與紫微相對，紫微在寅申巳亥，天府在申寅亥巳
        # 紫微在子午卯酉，天府在午子酉卯
        # 紫微在辰戌丑未，天府在戌辰未丑
        # 簡化為：天府與紫微的宮位關係是固定的
        # 天府星系起點與紫微星系起點的關係
        # 這裡的 tp 應該是天府星的起始宮位，而不是簡單的 (4 - zp) % 12
        # 根據紫微斗數排盤規則，天府星的排法是從寅宮起天府，然後順數到紫微星的宮位，再從該宮位逆數到天府星的宮位
        # 這裡沿用原始代碼的 tp 計算方式，但需要注意其準確性
        tp = (4 - zp + 12) % 12  # 確保結果為正

        for n, o in [("天府", 0), ("太陰", 1), ("貪狼", 2), ("巨門", 3), ("天相", 4), ("天梁", 5), ("七殺", 6),
                     ("破軍", 10)]:
            pos = (tp + o + 12) % 12  # 確保結果為正
            zhi = palaces[pos]["zhi"]
            palaces[pos]["stars"].append({
                "name": n,
                "type": "main",
                "brightness": ZiweiCalculator.get_brightness(n, zhi)
            })

    @staticmethod
    def _add_aux_stars(palaces, month, hour_idx):
        # 左輔 (辰宮順數到生月)
        zao_pos = (4 + month - 1) % 12
        palaces[zao_pos]["stars"].append({"name": "左輔", "type": "gaux",
                                          "brightness": ZiweiCalculator.get_brightness("左輔",
                                                                                       palaces[zao_pos]["zhi"])})

        # 右弼 (戌宮逆數到生月)
        you_pos = (10 - (month - 1) + 12) % 12
        palaces[you_pos]["stars"].append({"name": "右弼", "type": "gaux",
                                          "brightness": ZiweiCalculator.get_brightness("右弼",
                                                                                       palaces[you_pos]["zhi"])})

        # 文昌 (戌宮逆數到生時)
        chang_pos = (10 - hour_idx + 12) % 12
        palaces[chang_pos]["stars"].append({"name": "文昌", "type": "gaux",
                                            "brightness": ZiweiCalculator.get_brightness("文昌",
                                                                                         palaces[chang_pos]["zhi"])})

        # 文曲 (辰宮順數到生時)
        qu_pos = (4 + hour_idx) % 12
        palaces[qu_pos]["stars"].append({"name": "文曲", "type": "gaux",
                                         "brightness": ZiweiCalculator.get_brightness("文曲", palaces[qu_pos]["zhi"])})

    @staticmethod
    def _calculate_gan_aux_stars(gan_char, hour_idx):
        """
        計算基於天干的輔星：祿存、擎羊、陀羅、天魁、天鉞。
        返回一個字典，鍵為宮位索引，值為星曜列表。
        """
        stars_to_place = {}

        # 定義天干與宮位索引的對應表 (0=子, 1=丑...)
        # 格式: 天干: (天魁宮位索引, 天鉞宮位索引, 祿存宮位索引)
        GAN_STAR_CONFIG = {
            "甲": (1, 7, 2),  # 魁丑, 鉞未, 祿寅
            "乙": (0, 8, 3),  # 魁子, 鉞申, 祿卯
            "丙": (11, 9, 5),  # 魁亥, 鉞酉, 祿巳
            "丁": (11, 9, 6),  # 魁亥, 鉞酉, 祿午
            "戊": (1, 7, 5),  # 魁丑, 鉞未, 祿巳
            "己": (0, 8, 6),  # 魁子, 鉞申, 祿午
            "庚": (1, 7, 8),  # 魁丑, 鉞未, 祿申
            "辛": (6, 2, 9),  # 魁午, 鉞寅, 祿酉
            "壬": (3, 5, 11),  # 魁卯, 鉞巳, 祿亥
            "癸": (3, 5, 0),  # 魁卯, 鉞巳, 祿子
        }

        kui_idx, yue_idx, lu_idx = GAN_STAR_CONFIG[gan_char]

        # 祿存
        stars_to_place.setdefault(lu_idx, []).append({"name": "祿存", "type": "gaux"})
        # 擎羊、陀羅
        yang_idx = (lu_idx + 1) % 12
        tuo_idx = (lu_idx + 11) % 12
        stars_to_place.setdefault(yang_idx, []).append({"name": "擎羊", "type": "baux"})
        stars_to_place.setdefault(tuo_idx, []).append({"name": "陀羅", "type": "baux"})
        # 天魁、天鉞
        stars_to_place.setdefault(kui_idx, []).append({"name": "天魁", "type": "gaux"})
        stars_to_place.setdefault(yue_idx, []).append({"name": "天鉞", "type": "gaux"})

        return stars_to_place

    @staticmethod
    def _calculate_zhi_aux_stars(zhi_char, hour_idx):
        """
        計算基於地支的輔星：火星、鈴星、天馬、地空、地劫。
        返回一個字典，鍵為宮位索引，值為星曜列表。
        """
        stars_to_place = {}
        huolin = {
            "申": (2, 10),
            "子": (2, 10),
            "辰": (2, 10),
            "寅": (1, 3),
            "午": (1, 3),
            "戌": (1, 3),
            "巳": (3, 10),
            "酉": (3, 10),
            "丑": (3, 10),
            "亥": (9, 10),
            "卯": (9, 10),
            "未": (9, 10),
        }
        huo_start_idx, lin_start_idx = huolin[zhi_char]

        # 火星、鈴星 (根據時辰順數/逆數)
        huo_idx = (huo_start_idx + hour_idx) % 12
        lin_idx = (lin_start_idx + hour_idx) % 12
        stars_to_place.setdefault(huo_idx, []).append({"name": "火星", "type": "baux"})
        stars_to_place.setdefault(lin_idx, []).append({"name": "鈴星", "type": "baux"})

        # 天馬
        ma_idx = -1
        if zhi_char in ["寅", "午", "戌"]:
            ma_idx = 8  # 申
        elif zhi_char in ["申", "子", "辰"]:
            ma_idx = 2  # 寅
        elif zhi_char in ["巳", "酉", "丑"]:
            ma_idx = 11  # 亥
        elif zhi_char in ["亥", "卯", "未"]:
            ma_idx = 5  # 巳
        if ma_idx != -1:
            stars_to_place.setdefault(ma_idx, []).append({"name": "天馬", "type": "gaux"})

        # 地空、地劫 (地空從亥宮逆數到生時，地劫從亥宮順數到生時)
        kong_idx = (11 - hour_idx + 12) % 12  # 亥宮地支索引 11
        jie_idx = (11 + hour_idx) % 12
        stars_to_place.setdefault(kong_idx, []).append({"name": "地空", "type": "baux"})
        stars_to_place.setdefault(jie_idx, []).append({"name": "地劫", "type": "baux"})

        return stars_to_place

    @staticmethod
    def _calculate_changqu_stars(month, hour_idx):
        """
        計算文昌、文曲。
        返回一個字典，鍵為宮位索引，值為星曜列表。
        """
        stars_to_place = {}
        # 文昌 (從戌宮逆數到生時)
        chang_idx = (10 - hour_idx + 12) % 12
        stars_to_place.setdefault(chang_idx, []).append({"name": "文昌", "type": "gaux"})
        # 文曲 (從辰宮順數到生時)
        qu_idx = (4 + hour_idx) % 12
        stars_to_place.setdefault(qu_idx, []).append({"name": "文曲", "type": "gaux"})
        return stars_to_place

    @staticmethod
    def _calculate_luanxi_stars(zhi_char):
        """
        計算紅鸞、天喜。
        返回一個字典，鍵為宮位索引，值為星曜列表。
        """
        stars_to_place = {}
        zhi_idx = ZiweiCalculator.get_dizhi_index(zhi_char)
        # 紅鸞 (從卯宮逆數到生年地支)
        luan_idx = (3 - zhi_idx + 12) % 12  # 卯宮地支索引 3
        stars_to_place.setdefault(luan_idx, []).append({"name": "紅鸞", "type": "minor"})
        # 天喜 (紅鸞對宮)
        xi_idx = (luan_idx + 6) % 12
        stars_to_place.setdefault(xi_idx, []).append({"name": "天喜", "type": "minor"})
        return stars_to_place

    @staticmethod
    def _add_southern_stars(palaces, gan, zhi, hr_idx):
        # 祿存、羊陀、魁鉞
        gan_aux_stars_map = ZiweiCalculator._calculate_gan_aux_stars(gan, hr_idx)
        for pos, stars in gan_aux_stars_map.items():
            for star in stars:
                star_copy = star.copy()
                star_copy["brightness"] = ZiweiCalculator.get_brightness(star["name"], palaces[pos]["zhi"])
                palaces[pos]["stars"].append(star_copy)

        # 火星、鈴星、天馬、地空、地劫
        zhi_aux_stars_map = ZiweiCalculator._calculate_zhi_aux_stars(zhi, hr_idx)
        for pos, stars in zhi_aux_stars_map.items():
            for star in stars:
                star_copy = star.copy()
                star_copy["brightness"] = ZiweiCalculator.get_brightness(star["name"], palaces[pos]["zhi"])
                palaces[pos]["stars"].append(star_copy)

        # 文昌、文曲 (本命文昌文曲在 _add_aux_stars 已經處理，這裡不再重複添加)
        # 如果南派有不同的文昌文曲排法，則需要在這裡實現。
        # 南派的昌曲排法與北派相同，都是依據生時。
        # 所以這裡不需要再呼叫 _calculate_changqu_stars。

        # 紅鸞、天喜
        luanxi_stars_map = ZiweiCalculator._calculate_luanxi_stars(zhi)
        for pos, stars in luanxi_stars_map.items():
            for star in stars:
                star_copy = star.copy()
                star_copy["brightness"] = ZiweiCalculator.get_brightness(star["name"], palaces[pos]["zhi"])
                palaces[pos]["stars"].append(star_copy)

        # ... (其他雜曜，如果需要，可以繼續拆解或直接保留在 _add_minor_stars 中)
        # _add_minor_stars 處理的是本命雜曜，與大限流年流曜不同。

    @staticmethod
    def _add_minor_stars(palaces, gan, zhi, mon, day, hr_idx, yinyangender):
        # 天才天壽需要命宮身宮, 天傷天使在遷移宮前後, 三台八座天貴恩光
        zhi_idx = ZiweiCalculator.get_dizhi_index(zhi)
        gan_idx = ZiweiCalculator.get_tiangan_index(gan)

        # 命宮身宮位置 (需要從 palaces 中獲取，因為 _setup_palace_names 已經填好了)
        ming_pos = -1
        sen_pos = -1
        for i, p in enumerate(palaces):
            if p["name"] == "命宮":
                ming_pos = i
            sen_pos = (2 + (mon - 1) + hr_idx) % 12  # 確保結果為正

        # 天傷天使
        if yinyangender in ["陽男", "陰女"]:
            shang_pos = ming_pos + 5;  shi_pos = ming_pos + 7
        else:
            shang_pos = ming_pos + 7;  shi_pos = ming_pos + 5

        # 三台八座
        santai_pos = (2 + mon + day) % 12  # 原始代碼
        eightzuo_pos = (48 - mon - day + 12) % 12  # 原始代碼，確保結果為正

        # 天貴恩光
        tenguai_pos = 2 + hr_idx + day   # 原始代碼
        enguan_pos = 20 - hr_idx + day   # 原始代碼，確保結果為正

        # 0天哭、1天虛、2紅鸞、3天喜、4天空、5孤辰、6寡宿、7劫殺、8大耗、9蜚廉、10破碎、11華蓋、12咸池、13龍德、14月德、15天德、16年解、17龍池、18鳳閣
        # 這裡的 ZHI_STAR_CONFIG 已經在 _calculate_luanxi_stars 和 _calculate_zhi_aux_stars 中處理了部分
        # 這裡只處理剩餘的雜曜
        ZHI_STAR_CONFIG_MINOR = {
            "子": (6, 6, 3, 9, 1, 2, 10, 5, 7, 8, 5, 4, 9, 7, 5, 9, 10, 4, 10),  # 這裡的索引需要對應到具體的星曜
            "丑": (5, 7, 2, 8, 2, 2, 10, 2, 6, 9, 1, 2, 6, 8, 6, 10, 9, 5, 9),
            "寅": (4, 8, 1, 7, 3, 5, 1, 11, 9, 10, 9, 10, 3, 9, 7, 11, 8, 6, 8),
            "卯": (3, 9, 0, 6, 4, 5, 1, 8, 8, 5, 5, 7, 0, 10, 8, 0, 7, 7, 7),
            "辰": (2, 10, 11, 5, 5, 5, 1, 5, 11, 6, 1, 4, 9, 11, 9, 1, 6, 8, 6),
            "巳": (1, 11, 10, 4, 6, 8, 4, 2, 10, 7, 9, 2, 6, 0, 10, 2, 5, 9, 5),
            "午": (0, 0, 9, 3, 7, 8, 4, 11, 1, 2, 5, 10, 3, 1, 11, 3, 4, 10, 4),
            "未": (11, 1, 8, 2, 8, 8, 4, 8, 0, 3, 1, 7, 0, 2, 0, 4, 3, 11, 3),
            "申": (10, 2, 7, 1, 9, 11, 7, 5, 3, 4, 9, 4, 9, 3, 1, 5, 2, 0, 2),
            "酉": (9, 3, 6, 0, 10, 11, 7, 2, 2, 11, 5, 2, 6, 4, 2, 6, 1, 1, 1),
            "戌": (8, 4, 5, 11, 11, 11, 7, 11, 5, 0, 1, 10, 3, 5, 3, 7, 0, 2, 0),
            "亥": (7, 5, 4, 10, 0, 2, 10, 8, 4, 1, 9, 7, 0, 6, 4, 8, 11, 3, 11),
        }
        # 0天巫, 1天月 字典查找
        temp_dic_wu = {1: 5, 2: 8, 3: 2, 0: 11}  # 這裡的 0 應該是 12，代表子月
        tenwu_pos = temp_dic_wu[mon % 4] if mon % 4 != 0 else temp_dic_wu[0]  # 修正：處理月份為 12 的情況

        temp_dic_yue = {1: 10, 2: 5, 3: 4, 4: 2, 5: 7, 6: 3, 7: 11, 8: 7, 9: 2, 10: 6, 11: 10, 12: 2}
        tenua_pos = temp_dic_yue[mon]

        # 0天官 1天福 2天廚 3截空
        GAN_STAR_CONFIG_MINOR = {
            "甲": (7, 9, 5, 8),  # 天官午, 天福辰, 天廚巳, 截空申
            "乙": (4, 8, 6, 6),  # 天官卯, 天福丑, 天廚午, 截空午
            "丙": (5, 0, 0, 4),  # 天官辰, 天福子, 天廚戌, 截空辰
            "丁": (2, 11, 5, 2),  # 天官丑, 天福亥, 天廚巳, 截空寅
            "戊": (3, 3, 6, 0),  # 天官寅, 天福子, 天廚午, 截空子
            "己": (9, 2, 8, 8),  # 天官申, 天福亥, 天廚申, 截空申
            "庚": (11, 6, 2, 6),  # 天官戌, 天福卯, 天廚寅, 截空午
            "辛": (9, 5, 6, 4),  # 天官申, 天福寅, 天廚午, 截空辰
            "壬": (10, 6, 9, 2),  # 天官酉, 天福卯, 天廚酉, 截空寅
            "癸": (6, 5, 11, 0),  # 天官巳, 天福寅, 天廚亥, 截空子
        }

        star_definitions = [
            ("天刑", lambda: (8 + mon) % 12, "minor"),  # 卯宮起正月，順數到生月
            ("天姚", lambda: mon % 12, "minor"),  # 丑宮起正月，順數到生月
            ("天官", lambda: GAN_STAR_CONFIG_MINOR[gan][0], "minor"),
            ("天福", lambda: GAN_STAR_CONFIG_MINOR[gan][1], "minor"),
            ("龍池", lambda: ZHI_STAR_CONFIG_MINOR[zhi][17], "minor"),
            ("鳳閣", lambda: ZHI_STAR_CONFIG_MINOR[zhi][18], "minor"),
            # 紅鸞天喜已在 _calculate_luanxi_stars 處理
            ("天哭", lambda: ZHI_STAR_CONFIG_MINOR[zhi][0], "minor"),
            ("天虛", lambda: ZHI_STAR_CONFIG_MINOR[zhi][1], "minor"),
            ("台輔", lambda: (hr_idx + 6) % 12, "minor"),  # 酉宮起子時，順數到生時
            ("封誥", lambda: (hr_idx + 2) % 12, "minor"),  # 巳宮起子時，順數到生時
            ("三台", lambda: santai_pos % 12, "minor"),
            ("八座", lambda: eightzuo_pos % 12, "minor"),
            ("天貴", lambda: tenguai_pos % 12, "minor"),
            ("恩光", lambda: enguan_pos % 12, "minor"),
            ("天月", lambda: tenua_pos % 12, "minor"),
            ("天廚", lambda: GAN_STAR_CONFIG_MINOR[gan][2], "minor"),
            ("截空", lambda: GAN_STAR_CONFIG_MINOR[gan][3], "minor"),
            ("截空", lambda: (GAN_STAR_CONFIG_MINOR[gan][3] + 1) % 12, "minor"),  # 截空有兩個宮位
            ("天空", lambda: ZHI_STAR_CONFIG_MINOR[zhi][4], "minor"),
            ("孤辰", lambda: ZHI_STAR_CONFIG_MINOR[zhi][5], "minor"),
            ("寡宿", lambda: ZHI_STAR_CONFIG_MINOR[zhi][6], "minor"),
            ("劫殺", lambda: ZHI_STAR_CONFIG_MINOR[zhi][7], "minor"),
            ("大耗", lambda: ZHI_STAR_CONFIG_MINOR[zhi][8], "minor"),
            ("蜚廉", lambda: ZHI_STAR_CONFIG_MINOR[zhi][9], "minor"),
            ("破碎", lambda: ZHI_STAR_CONFIG_MINOR[zhi][10], "minor"),
            ("華蓋", lambda: ZHI_STAR_CONFIG_MINOR[zhi][11], "minor"),
            ("咸池", lambda: ZHI_STAR_CONFIG_MINOR[zhi][12], "minor"),
            ("龍德", lambda: ZHI_STAR_CONFIG_MINOR[zhi][13], "minor"),
            ("月德", lambda: ZHI_STAR_CONFIG_MINOR[zhi][14], "minor"),
            ("天德", lambda: ZHI_STAR_CONFIG_MINOR[zhi][15], "minor"),
            ("年解", lambda: ZHI_STAR_CONFIG_MINOR[zhi][16], "minor"),
            ("解神", lambda: (((mon + 1) // 2) * 2 + 6) % 12, "minor"),  # 這裡的邏輯需要確認
            ("陰煞", lambda: (28 - mon * 2 + 12) % 12, "minor"),  # 這裡的邏輯需要確認
            ("天巫", lambda: tenwu_pos % 12, "minor"),
            ("天才", lambda: (ming_pos + zhi_idx) % 12, "minor"),  # 命宮順數到生年地支
            ("天壽", lambda: (sen_pos + zhi_idx) % 12, "minor"),  # 身宮順數到生年地支
            ("天傷", lambda: shang_pos % 12, "minor"),
            ("天使", lambda: shi_pos % 12, "minor"),
            ("旬空", lambda: (zhi_idx + 22 - gan_idx + 12) % 12, "minor"),  # 旬空有兩個宮位
            ("旬空", lambda: (zhi_idx + 23 - gan_idx + 12) % 12, "minor"),
        ]

        for name, get_pos, s_type in star_definitions:
            p_idx = get_pos()  # 執行 lambda 取得宮位 index
            # 建立星曜物件
            star_obj = {"name": name, "type": s_type}
            # 如果是特定類型，則計算亮度 (brightness)
            # 這裡可以根據你的需求判斷哪些星要算亮度
            needs_brightness = ["紅鸞", "天喜", "龍池", "鳳閣", "天刑", "天姚"]  # 這裡的紅鸞天喜已經在 _calculate_luanxi_stars 處理
            if name in needs_brightness:
                star_obj["brightness"] = ZiweiCalculator.get_brightness(name, palaces[p_idx]["zhi"])
            palaces[p_idx]["stars"].append(star_obj)
        return sen_pos  # 返回身宮索引

    @classmethod
    def calculate_dynamic_stars(cls, current_palaces, daxian_gan=None, daxian_zhi=None,
                                liunian_gan=None, liunian_zhi=None,
                                natal_month=None, natal_day=None, natal_hour_idx=None):
        dynamic_stars_data = {"daxian_stars": {}, "liunian_stars": {}}

        def process_stars(gan, zhi, prefix, star_type):
            results = {}
            # 1. 天干系列 (祿羊陀魁鉞) - 依天干
            s1 = cls._calculate_gan_aux_stars(gan, natal_hour_idx)

            # 2. 地支系列 (火鈴馬) - 依地支
            # 註：空劫在動態盤中各派見解不同，目前維持依本命時辰
            s2 = cls._calculate_zhi_aux_stars(zhi, natal_hour_idx)

            # 3. 鸞喜系列 (紅鸞天喜) - 依地支
            s3 = cls._calculate_luanxi_stars(zhi)

            # 4. 【修正】動態昌曲系列 - 依天干 (不再傳入 natal_month)
            s4 = cls._calculate_dynamic_changqu_stars(gan)

            for s_map in [s1, s2, s3, s4]:
                for pos, stars in s_map.items():
                    for star in stars:
                        s_copy = star.copy()
                        s_copy.update({"name": f"{prefix}{star['name']}", "type": star_type})
                        s_copy["brightness"] = cls.get_brightness(star["name"], current_palaces[pos]["zhi"])
                        results.setdefault(pos, []).append(s_copy)
            return results

        if daxian_gan and daxian_zhi:
            dynamic_stars_data["daxian_stars"] = process_stars(daxian_gan, daxian_zhi, "大", "daxian_star")

        if liunian_gan and liunian_zhi:
            dynamic_stars_data["liunian_stars"] = process_stars(liunian_gan, liunian_zhi, "年", "liunian_star")

        return dynamic_stars_data

    @staticmethod
    def generate_sihua_table(config):
        table = {
            "甲": {"廉貞": "祿", "破軍": "權", "武曲": "科", "太陽": "忌"},
            "乙": {"天機": "祿", "天梁": "權", "紫微": "科", "太陰": "忌"},
            "丙": {"天同": "祿", "天機": "權", "文昌": "科", "廉貞": "忌"},
            "丁": {"太陰": "祿", "天同": "權", "天機": "科", "巨門": "忌"},
            "戊": {"貪狼": "祿", "太陰": "權", "右弼": "科", "天機": "忌"},
            "己": {"武曲": "祿", "貪狼": "權", "天梁": "科", "文曲": "忌"},
            "庚": {"太陽": "祿", "武曲": "權", "太陰": "科", "天同": "忌"},
            "辛": {"巨門": "祿", "太陽": "權", "文曲": "科", "文昌": "忌"},
            "壬": {"天梁": "祿", "紫微": "權", "左輔": "科", "武曲": "忌"},
            "癸": {"破軍": "祿", "巨門": "權", "太陰": "科", "貪狼": "忌"}
        }
        if config.get("sihua_wu") == "貪陰陽機": table["戊"] = {"貪狼": "祿", "太陰": "權", "太陽": "科", "天機": "忌"}
        geng = config.get("sihua_geng")
        if geng == "陽武同陰":
            table["庚"] = {"太陽": "祿", "武曲": "權", "天同": "科", "太陰": "忌"}
        elif geng == "陽武府同":
            table["庚"] = {"太陽": "祿", "武曲": "權", "天府": "科", "天同": "忌"}
        if config.get("sihua_ren") == "梁紫府武": table["壬"] = {"天梁": "祿", "紫微": "權", "天府": "科", "武曲": "忌"}
        return table

    @staticmethod
    def get_sihua(tiangan, star_name, sihua_table):
        if not tiangan or not star_name: return None
        return sihua_table.get(tiangan, {}).get(star_name)

    BRIGHTNESS_MAP = {
        "紫微": {"子": "平", "丑": "廟", "寅": "旺", "卯": "旺", "辰": "得", "巳": "旺", "午": "廟", "未": "廟",
                 "申": "旺", "酉": "旺", "戌": "得", "亥": "旺"},
        "天機": {"子": "廟", "丑": "陷", "寅": "得", "卯": "旺", "辰": "利", "巳": "平", "午": "廟", "未": "陷",
                 "申": "得", "酉": "旺", "戌": "利", "亥": "平"},
        "太陽": {"子": "陷", "丑": "不", "寅": "旺", "卯": "廟", "辰": "旺", "巳": "旺", "午": "旺", "未": "得",
                 "申": "得", "酉": "陷", "戌": "不", "亥": "陷"},
        "武曲": {"子": "旺", "丑": "廟", "寅": "得", "卯": "利", "辰": "廟", "巳": "平", "午": "旺", "未": "廟",
                 "申": "得", "酉": "利", "戌": "廟", "亥": "平"},
        "天同": {"子": "旺", "丑": "不", "寅": "利", "卯": "平", "辰": "平", "巳": "廟", "午": "陷", "未": "不",
                 "申": "旺", "酉": "平", "戌": "平", "亥": "廟"},
        "廉貞": {"子": "平", "丑": "利", "寅": "廟", "卯": "平", "辰": "利", "巳": "陷", "午": "平", "未": "利",
                 "申": "廟", "酉": "平", "戌": "利", "亥": "陷"},
        "天府": {"子": "廟", "丑": "廟", "寅": "廟", "卯": "得", "辰": "廟", "巳": "得", "午": "旺", "未": "廟",
                 "申": "得", "酉": "旺", "戌": "廟", "亥": "得"},
        "太陰": {"子": "廟", "丑": "廟", "寅": "旺", "卯": "陷", "辰": "陷", "巳": "陷", "午": "不", "未": "不",
                 "申": "利", "酉": "不", "戌": "旺", "亥": "廟"},
        "貪狼": {"子": "旺", "丑": "廟", "寅": "平", "卯": "利", "辰": "廟", "巳": "陷", "午": "旺", "未": "廟",
                 "申": "平", "酉": "利", "戌": "廟", "亥": "陷"},
        "巨門": {"子": "旺", "丑": "不", "寅": "廟", "卯": "廟", "辰": "陷", "巳": "旺", "午": "旺", "未": "不",
                 "申": "廟", "酉": "廟", "戌": "陷", "亥": "旺"},
        "天相": {"子": "廟", "丑": "廟", "寅": "廟", "卯": "陷", "辰": "得", "巳": "得", "午": "廟", "未": "得",
                 "申": "廟", "酉": "陷", "戌": "得", "亥": "得"},
        "天梁": {"子": "廟", "丑": "旺", "寅": "廟", "卯": "廟", "辰": "廟", "巳": "陷", "午": "廟", "未": "旺",
                 "申": "陷", "酉": "得", "戌": "廟", "亥": "陷"},
        "七殺": {"子": "旺", "丑": "廟", "寅": "廟", "卯": "旺", "辰": "廟", "巳": "平", "午": "旺", "未": "廟",
                 "申": "廟", "酉": "廟", "戌": "廟", "亥": "平"},
        "破軍": {"子": "廟", "丑": "旺", "寅": "得", "卯": "陷", "辰": "旺", "巳": "平", "午": "廟", "未": "旺",
                 "申": "得", "酉": "陷", "戌": "旺", "亥": "平"},
        "文昌": {"子": "得", "丑": "廟", "寅": "陷", "卯": "利", "辰": "得", "巳": "廟", "午": "陷", "未": "利",
                 "申": "得", "酉": "廟", "戌": "陷", "亥": "利"},
        "文曲": {"子": "得", "丑": "廟", "寅": "平", "卯": "旺", "辰": "得", "巳": "廟", "午": "陷", "未": "旺",
                 "申": "得", "酉": "廟", "戌": "陷", "亥": "旺"},
        "火星": {"子": "陷", "丑": "得", "寅": "廟", "卯": "利", "辰": "陷", "巳": "得", "午": "廟", "未": "利",
                 "申": "陷", "酉": "得", "戌": "廟", "亥": "利"},
        "鈴星": {"子": "陷", "丑": "得", "寅": "廟", "卯": "利", "辰": "陷", "巳": "得", "午": "廟", "未": "利",
                 "申": "陷", "酉": "得", "戌": "廟", "亥": "利"},
        "擎羊": {"子": "陷", "丑": "廟", "寅": "", "卯": "陷", "辰": "廟", "巳": "", "午": "陷", "未": "廟", "申": "",
                 "酉": "陷", "戌": "廟", "亥": ""},
        "陀羅": {"子": "", "丑": "廟", "寅": "陷", "卯": "", "辰": "廟", "巳": "陷", "午": "", "未": "廟", "申": "陷",
                 "酉": "", "戌": "廟", "亥": "陷"},
        "天魁": {"子": "旺", "丑": "旺", "寅": "", "卯": "廟", "辰": "", "巳": "", "午": "廟", "未": "", "申": "",
                 "酉": "", "戌": "", "亥": "旺"},
        "天鉞": {"子": "", "丑": "", "寅": "旺", "卯": "", "辰": "", "巳": "旺", "午": "", "未": "旺", "申": "廟",
                 "酉": "廟", "戌": "", "亥": ""},
        "祿存": {"子": "旺", "丑": "", "寅": "廟", "卯": "旺", "辰": "", "巳": "廟", "午": "旺", "未": "", "申": "廟",
                 "酉": "旺", "戌": "", "亥": "廟"},
        "左輔": {"子": "旺", "丑": "廟", "寅": "廟", "卯": "陷", "辰": "廟", "巳": "平", "午": "旺", "未": "廟",
                 "申": "平", "酉": "陷", "戌": "廟", "亥": "閑"},
        "右弼": {"子": "廟", "丑": "廟", "寅": "旺", "卯": "陷", "辰": "廟", "巳": "平", "午": "旺", "未": "廟",
                 "申": "閑", "酉": "陷", "戌": "廟", "亥": "平"},
        "地空": {"子": "平", "丑": "陷", "寅": "陷", "卯": "平", "辰": "陷", "巳": "廟", "午": "廟", "未": "平",
                 "申": "廟", "酉": "廟", "戌": "陷", "亥": "陷"},
        "地劫": {"子": "陷", "丑": "陷", "寅": "平", "卯": "平", "辰": "陷", "巳": "閑", "午": "廟", "未": "平",
                 "申": "廟", "酉": "平", "戌": "平", "亥": "旺"},
        "紅鸞": {"子": "廟", "丑": "陷", "寅": "旺", "卯": "廟", "辰": "陷", "巳": "旺", "午": "旺", "未": "陷",
                 "申": "廟", "酉": "旺", "戌": "陷", "亥": "廟"},
        "天喜": {"子": "旺", "丑": "陷", "寅": "廟", "卯": "旺", "辰": "陷", "巳": "廟", "午": "廟", "未": "陷",
                 "申": "旺", "酉": "廟", "戌": "陷", "亥": "旺"},
        "天馬": {"子": "", "丑": "", "寅": "旺", "卯": "", "辰": "", "巳": "平", "午": "", "未": "", "申": "旺",
                 "酉": "", "戌": "", "亥": "平"},
        "天刑": {"子": "平", "丑": "陷", "寅": "廟", "卯": "廟", "辰": "平", "巳": "陷", "午": "平", "未": "陷",
                 "申": "陷", "酉": "廟", "戌": "廟", "亥": "陷"},
        "天姚": {"子": "陷", "丑": "平", "寅": "旺", "卯": "廟", "辰": "陷", "巳": "平", "午": "平", "未": "旺",
                 "申": "閑", "酉": "廟", "戌": "廟", "亥": "陷"},
    }
    # 流昌曲天干對應表 (昌, 曲) 的地支索引
    # 甲: 巳(11), 酉(9) -> 這裡索引需對應 子0, 丑1, 寅2...
    DYNAMIC_CHANGQU_MAP = {
        "甲": (5, 9),  # 昌巳, 曲酉
        "乙": (6, 8),  # 昌午, 曲申
        "丙": (8, 6),  # 昌申, 曲午
        "丁": (9, 5),  # 昌酉, 曲巳
        "戊": (8, 6),  # 昌申, 曲午 (同丙)
        "己": (9, 5),  # 昌酉, 曲巳 (同丁)
        "庚": (11, 3),  # 昌亥, 曲卯 (同甲)
        "辛": (0, 2),  # 昌子, 曲寅 (同乙)
        "壬": (2, 0),  # 昌寅, 曲子
        "癸": (3, 11),  # 昌卯, 曲亥
    }

    @staticmethod
    def _calculate_dynamic_changqu_stars(gan_char):
        """
        計算流年/大限昌曲 (依天干排)
        """
        stars_to_place = {}
        if gan_char in ZiweiCalculator.DYNAMIC_CHANGQU_MAP:
            chang_idx, qu_idx = ZiweiCalculator.DYNAMIC_CHANGQU_MAP[gan_char]
            stars_to_place.setdefault(chang_idx, []).append({"name": "文昌", "type": "gaux"})
            stars_to_place.setdefault(qu_idx, []).append({"name": "文曲", "type": "gaux"})
        return stars_to_place

    @staticmethod
    def get_brightness(star_name, zhi):
        return ZiweiCalculator.BRIGHTNESS_MAP.get(star_name, {}).get(zhi, "")