import sqlite3
from config import APP_DB_PATH
import os

# 确保数据库文件所在目录存在
db_dir = os.path.dirname(APP_DB_PATH)
if db_dir:
    os.makedirs(db_dir, exist_ok=True)

# 获取SQLite连接（兼容旧代码）
def get_db_connection():
    """获取数据库连接，支持通过列名访问"""
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 兼容性别名
engine = None
SessionLocal = None

def get_db():
    """数据库依赖函数"""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()