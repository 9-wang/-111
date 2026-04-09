import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'app.db')

def add_missing_columns():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 获取现有列名
    cursor.execute("PRAGMA table_info(models)")
    existing_columns = [row[1] for row in cursor.fetchall()]
    
    columns_to_add = [
        ("analysis_status", "TEXT"),
        ("max_displacement", "REAL"),
        ("max_stress", "REAL"),
        ("safety_factor", "REAL"),
    ]
    
    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE models ADD COLUMN {col_name} {col_type}")
                print(f"列 '{col_name}' 添加成功")
            except sqlite3.OperationalError as e:
                print(f"添加列 '{col_name}' 失败: {e}")
        else:
            print(f"列 '{col_name}' 已存在，跳过")
    
    conn.commit()
    conn.close()
    print("数据库修复完成！")

if __name__ == "__main__":
    add_missing_columns()