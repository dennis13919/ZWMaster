import sqlite3
import os
import sys
from datetime import datetime


class ZiweiDatabase:
    def __init__(self, db_name="ziwei_data.db"):
        # 【重要修復】：解決 APK 更新時資料庫被清空的 Bug
        # Flet 預設的 os.getcwd() 在手機上通常是 /data/.../files/app
        # 每次覆蓋安裝 APK，這個 "app" 資料夾會被整包刪除重建！
        # 因此我們要退回上一層的 "files" 目錄，這裡是安全且持久的。
        cwd = os.getcwd()
        if os.path.basename(cwd) == "app":
            safe_dir = os.path.dirname(cwd)
        else:
            safe_dir = os.environ.get("HOME", cwd)

        # 組合出完整的絕對路徑
        self.db_path = os.path.join(safe_dir, db_name)

        self.init_db()

    def get_connection(self):
        # 統一使用 self.db_path，並加上 check_same_thread=False 增加穩定性
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def init_db(self):
        """初始化資料庫與資料表"""
        conn = self.get_connection()
        cursor = conn.cursor()
        # 建立 User 表
        # id: 主鍵
        # name: 姓名
        # gender: 性別
        # year, month, day, hour, minute: 生辰
        # is_lunar: 農曆標記 (1=True, 0=False)
        # note: 備註 (限30字)
        # category: 分類 (家人, 朋友, 同事, 名人, 其他)
        # created_at: 建立時間
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                gender TEXT NOT NULL,
                birth_year INTEGER,
                birth_month INTEGER,
                birth_day INTEGER,
                birth_hour INTEGER,
                birth_minute INTEGER,
                is_lunar INTEGER,
                note TEXT,
                category TEXT DEFAULT '其他',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # 檢查是否需要新增 category 欄位 (針對舊資料庫)
        cursor.execute("PRAGMA table_info(users)")
        columns = [info[1] for info in cursor.fetchall()]
        if 'category' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN category TEXT DEFAULT '其他'")

        conn.commit()
        conn.close()

    def check_duplicate(self, name, gender, year, month, day, hour):
        """
        檢查重複：姓名、性別、年、月、日、時 (不含分)
        回傳: (is_duplicate, duplicate_count)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM users 
            WHERE name=? AND gender=? AND birth_year=? 
            AND birth_month=? AND birth_day=? AND birth_hour=?
        ''', (name, gender, year, month, day, hour))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0, count

    def check_duplicate_full(self, name, gender, year, month, day, hour, minute):
        """
        檢查重複：姓名、性別、年、月、日、時、分
        回傳: (is_duplicate, duplicate_count)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT COUNT(*) FROM users
            WHERE name=? AND gender=? AND birth_year=?
            AND birth_month=? AND birth_day=? AND birth_hour=? AND birth_minute=?
        ''', (name, gender, year, month, day, hour, minute))
        count = cursor.fetchone()[0]
        conn.close()
        return count > 0, count

    def add_user(self, data):
        """新增使用者"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO users (name, gender, birth_year, birth_month, birth_day, birth_hour, birth_minute, is_lunar, note, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['name'], data['gender'],
            data['year'], data['month'], data['day'],
            data['hour'], data['minute'],
            1 if data['is_lunar'] else 0,
            data.get('note', ''),
            data.get('category', '其他')
        ))
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id

    def delete_user(self, user_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        conn.close()

    def update_user(self, user_id, data):
        """更新使用者資料"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE users
            SET name=?, gender=?, birth_year=?, birth_month=?, birth_day=?,
                birth_hour=?, birth_minute=?, is_lunar=?, note=?, category=?, created_at=CURRENT_TIMESTAMP
            WHERE id=?
        ''', (
            data['name'], data['gender'],
            data['year'], data['month'], data['day'],
            data['hour'], data['minute'],
            1 if data['is_lunar'] else 0,
            data.get('note', ''),
            data.get('category', '其他'),
            user_id
        ))
        conn.commit()
        conn.close()

    def update_user_category(self, user_id, category):
        """更新使用者分類"""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute('UPDATE users SET category = ? WHERE id = ?', (category, user_id))
        conn.commit()
        conn.close()

    def get_all_users(self, keyword="", category=None):
        """取得所有使用者，支援關鍵字搜尋 (姓名或備註) 與分類過濾"""
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = """
            SELECT id, name, gender, birth_year, birth_month, birth_day,
                   birth_hour, birth_minute, is_lunar, note, category, created_at
            FROM users WHERE 1=1
        """
        params = []

        if category:
            sql += " AND category = ?"
            params.append(category)

        if keyword:
            sql += " AND (name LIKE ? OR note LIKE ?)"
            wildcard = f"%{keyword}%"
            params.extend([wildcard, wildcard])

        sql += " ORDER BY created_at DESC"

        cursor.execute(sql, params)
        rows = cursor.fetchall()

        # 轉換為字典列表以便前端使用
        result = []
        for row in rows:
            result.append({
                "id": row[0],
                "name": row[1],
                "gender": row[2],
                "year": row[3],
                "month": row[4],
                "day": row[5],
                "hour": row[6],
                "minute": row[7],
                "is_lunar": bool(row[8]),
                "note": row[9],
                "category": row[10],
                "created_at": row[11]
            })

        conn.close()
        return result