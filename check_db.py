#!/usr/bin/env python3
"""
检查数据库中的模型记录
"""

import sqlite3
import os

# 数据库路径
DB_PATH = os.path.join(os.getcwd(), 'app.db')

def check_database():
    """检查数据库中的模型记录"""
    print(f"数据库路径: {DB_PATH}")
    print(f"数据库文件存在: {os.path.exists(DB_PATH)}")
    
    try:
        # 连接数据库
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 检查模型表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='models';")
        table_exists = cursor.fetchone() is not None
        print(f"模型表存在: {table_exists}")
        
        if table_exists:
            # 检查记录数量
            cursor.execute("SELECT COUNT(*) FROM models;")
            count = cursor.fetchone()[0]
            print(f"模型记录数量: {count}")
            
            # 查看最新的3条记录
            if count > 0:
                print("\n最新的3条模型记录:")
                cursor.execute("SELECT id, model_name, created_at FROM models ORDER BY id DESC LIMIT 3;")
                records = cursor.fetchall()
                for record in records:
                    print(f"ID: {record[0]}, 名称: {record[1]}, 创建时间: {record[2]}")
        
        # 关闭连接
        conn.close()
        
    except Exception as e:
        print(f"错误: {e}")

if __name__ == "__main__":
    check_database()
