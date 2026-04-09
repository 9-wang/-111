import sqlite3
import os
from werkzeug.security import generate_password_hash
from config import APP_DB_PATH

def init_database():
    """
    初始化数据库，创建所有必要的表结构
    """
    # 初始化app.db数据库
    print("初始化app.db数据库...")
    conn = sqlite3.connect(APP_DB_PATH)
    cursor = conn.cursor()
    
    # 创建users表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT DEFAULT 'user',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP,
        name TEXT,
        phone TEXT
    )
    ''')
    print("创建了users表")
    
    # 创建models表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        model_name TEXT NOT NULL,
        truss_type TEXT NOT NULL,
        file_path TEXT,
        apdl_script_path TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        span REAL NOT NULL,
        height REAL NOT NULL,
        node_spacing REAL NOT NULL,
        section_type TEXT NOT NULL,
        boundary_condition TEXT DEFAULT 'simply_supported',
        top_span REAL,
        filename TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')
    print("创建了models表")
    
    # 创建analyses表
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id TEXT UNIQUE,
        user_id INTEGER,
        model_id INTEGER,
        model_name TEXT,
        analysis_type TEXT,
        status TEXT,
        elastic_modulus REAL,
        poisson_ratio REAL,
        density REAL,
        mesh_size REAL,
        started_at TEXT,
        completed_at TEXT,
        results TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (model_id) REFERENCES models(id)
    )
    ''')
    print("创建了analyses表")
    
    # 检查是否已有admin用户，如果没有则创建
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        # 创建管理员用户
        admin_password = generate_password_hash('admin123', method='pbkdf2:sha256')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, name) VALUES (?, ?, ?, ?, ?)",
            ('admin', 'admin@example.com', admin_password, 'admin', '系统管理员')
        )
        print("已创建管理员用户: admin/admin123")
        
        # 创建测试用户
        test_password = generate_password_hash('user123', method='pbkdf2:sha256')
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, role, name) VALUES (?, ?, ?, ?, ?)",
            ('user1', 'user1@example.com', test_password, 'user', '测试用户')
        )
        print("已创建测试用户: user1/user123")
    
    # 提交并关闭连接
    conn.commit()
    conn.close()
    
    print("数据库初始化完成！")
    print(f"数据库文件位置：")
    print(f"  - app.db: {APP_DB_PATH}")

def create_upload_directories():
    """
    创建必要的上传目录
    """
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 创建uploads目录
    uploads_dir = os.path.join(base_dir, 'uploads')
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
        print(f"创建上传目录: {uploads_dir}")
    
    # 创建apdl_scripts目录
    apdl_scripts_dir = os.path.join(base_dir, 'apdl_scripts')
    if not os.path.exists(apdl_scripts_dir):
        os.makedirs(apdl_scripts_dir)
        print(f"创建APDL脚本目录: {apdl_scripts_dir}")
    
    # 创建analysis_results目录
    results_dir = os.path.join(base_dir, 'analysis_results')
    if not os.path.exists(results_dir):
        os.makedirs(results_dir)
        print(f"创建分析结果目录: {results_dir}")

if __name__ == "__main__":
    print("开始数据库和目录初始化...")
    create_upload_directories()
    init_database()
    print("初始化全部完成！")