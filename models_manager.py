import os
import uuid
import sqlite3
import json
from datetime import datetime

# 导入配置
from config import APP_DB_PATH, ALLOWED_EXTENSIONS, UPLOAD_FOLDER
# 导入数据库连接池（假设 db.py 中的 get_db_connection 返回 sqlite3.Connection 并设置 row_factory）
from db import get_db_connection
# 导入缓存
from cache import cache


def ensure_upload_directory():
    """确保上传目录存在，如果不存在则创建"""
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
    return UPLOAD_FOLDER


def allowed_file(filename):
    """检查文件扩展名是否在允许的列表中"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_model_file(model_file, user_id, model_name, model_description=""):
    """保存模型文件并将信息存储到数据库（用于文件上传）"""
    try:
        if not model_file or not model_name:
            raise ValueError("请选择文件并输入模型名称")

        file_ext = model_file.filename.rsplit('.', 1)[1].lower() if '.' in model_file.filename else ''
        if not allowed_file(model_file.filename):
            raise ValueError("不支持的文件格式，请上传.obj, .fbx, .gltf, .glb或.stl文件")

        upload_dir = ensure_upload_directory()
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(UPLOAD_FOLDER, unique_filename)

        model_file.save(file_path)
        file_size = os.path.getsize(file_path)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO models 
               (user_id, model_name, model_description, file_path, file_size, file_type, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, model_name, model_description, unique_filename, file_size, file_ext, datetime.now())
        )
        model_id = cursor.lastrowid
        conn.commit()
        conn.close()

        # 清除相关缓存
        cache.delete(f"get_user_models:{user_id}:1:10")
        return model_id, unique_filename

    except Exception as e:
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise e


def save_truss_model(user_id, model_name, truss_type, parameters, nodes, elements):
    """
    保存参数化桁架模型到数据库。
    :param user_id: 用户ID
    :param model_name: 模型名称
    :param truss_type: 桁架类型字符串
    :param parameters: 参数字典（包含 span, height 等）
    :param nodes: 节点坐标列表，如 [[x,y,z], ...]
    :param elements: 杆件连接关系列表，如 [[start_idx, end_idx], ...]
    :return: 新模型的 ID
    """
    print("===== save_truss_model 开始执行 =====")
    try:
        if not model_name:
            raise ValueError("模型名称不能为空")
        print(f"模型名称: {model_name}")

        # 构建完整的参数数据（包含 nodes 和 elements）
        full_parameters = dict(parameters)
        full_parameters['nodes'] = nodes
        full_parameters['elements'] = elements
        full_parameters['truss_type'] = truss_type
        print("参数合并完成")

        # 将参数序列化为 JSON 字符串
        parameters_json = json.dumps(full_parameters, ensure_ascii=False)
        print("JSON 序列化完成")

        # 生成一个唯一的文件名，用于存储模型数据（JSON 格式）
        upload_dir = ensure_upload_directory()
        unique_filename = f"truss_{uuid.uuid4().hex}.json"
        file_path = os.path.join(upload_dir, unique_filename)
        print(f"文件路径: {file_path}")

        # 将模型数据保存为 JSON 文件，便于后续查看或调试
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(full_parameters, f, ensure_ascii=False, indent=2)
        print("JSON 文件写入成功")

        file_size = os.path.getsize(file_path)

        # 插入数据库记录
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO models 
               (user_id, model_name, model_description, file_path, file_size, file_type, 
                model_type, parameters, created_at, analysis_status)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                user_id,
                model_name,
                f'{truss_type}桁架 - 跨度{parameters.get("span", "?")}m',
                unique_filename,          # file_path 存相对路径
                file_size,
                'json',
                'truss',                  # model_type 标记为桁架
                parameters_json,
                datetime.now(),
                'pending'                 # 初始分析状态
            )
        )
        model_id = cursor.lastrowid
        conn.commit()
        conn.close()
        print(f"数据库插入成功，model_id = {model_id}")

        # 清除相关缓存
        cache.delete(f"get_user_models:{user_id}:1:10")
        print("缓存已清除")
        return model_id

    except Exception as e:
        print(f"!!!!! 发生异常: {e} !!!!!")
        import traceback
        traceback.print_exc()
        # 若保存失败，清理可能已创建的文件
        if 'file_path' in locals() and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except:
                pass
        raise e


@cache.cache_decorator(expiry=60)
def get_user_models(user_id, page=1, per_page=10):
    """获取用户的模型，支持分页"""
    conn = get_db_connection()
    if user_id == 0:
        total = conn.execute('SELECT COUNT(*) FROM models').fetchone()[0]
        offset = (page - 1) * per_page
        models = conn.execute(
            'SELECT * FROM models ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (per_page, offset)
        ).fetchall()
    else:
        total = conn.execute(
            'SELECT COUNT(*) FROM models WHERE user_id = ?', (user_id,)
        ).fetchone()[0]
        offset = (page - 1) * per_page
        models = conn.execute(
            'SELECT * FROM models WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?',
            (user_id, per_page, offset)
        ).fetchall()
    conn.close()

    return {
        'models': models,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }


@cache.cache_decorator(expiry=300)
def get_model(model_id, user_id=None):
    """获取指定ID的模型，如果提供了user_id则验证所有权"""
    conn = get_db_connection()
    if user_id is not None:
        model = conn.execute(
            'SELECT * FROM models WHERE id = ? AND user_id = ?', (model_id, user_id)
        ).fetchone()
    else:
        model = conn.execute(
            'SELECT * FROM models WHERE id = ?', (model_id,)
        ).fetchone()
    conn.close()

    if not model:
        return None

    # 将 sqlite3.Row 转换为字典
    model_dict = dict(model)
    # 解析 parameters JSON 字段
    if model_dict.get('parameters'):
        try:
            model_dict['parameters'] = json.loads(model_dict['parameters'])
        except:
            model_dict['parameters'] = {}
    else:
        model_dict['parameters'] = {}

    return model_dict


def delete_model(model_id, user_id):
    """删除指定的模型文件和数据库记录"""
    try:
        model = get_model(model_id, user_id)
        if not model:
            raise ValueError("模型不存在或无权访问")

        # 删除关联的文件
        upload_dir = ensure_upload_directory()
        file_path = os.path.join(upload_dir, model['file_path'])
        if os.path.exists(file_path):
            os.remove(file_path)

        conn = get_db_connection()
        conn.execute('DELETE FROM models WHERE id = ? AND user_id = ?', (model_id, user_id))
        conn.commit()
        conn.close()

        # 清除缓存
        cache.delete(f"get_model:{model_id}:{user_id}")
        cache.delete(f"get_user_models:{user_id}:1:10")
        return True
    except Exception as e:
        raise e


def update_model(model_id, user_id, model_name=None, model_description=None):
    """更新模型的元信息"""
    try:
        existing = get_model(model_id, user_id)
        if not existing:
            raise ValueError("模型不存在或无权访问")

        update_fields = []
        params = []
        if model_name is not None:
            update_fields.append("model_name = ?")
            params.append(model_name)
        if model_description is not None:
            update_fields.append("model_description = ?")
            params.append(model_description)

        update_fields.append("last_modified = ?")
        params.append(datetime.now())
        params.append(model_id)
        params.append(user_id)

        conn = get_db_connection()
        conn.execute(
            f"UPDATE models SET {', '.join(update_fields)} WHERE id = ? AND user_id = ?",
            params
        )
        conn.commit()
        conn.close()

        cache.delete(f"get_model:{model_id}:{user_id}")
        cache.delete(f"get_user_models:{user_id}:1:10")
        return True
    except Exception as e:
        raise e


# ---------- 分析相关函数（代理到 analysis_manager） ----------
def create_analysis_record(params):
    from analysis_manager import create_analysis_record as _create
    return _create(params)


def run_analysis(analysis_id, params):
    from analysis_manager import run_analysis as _run
    model = get_model(params.get('model_id'))
    if model:
        model_file_path = get_model_file_path(model['file_path'])
        _run(model_file_path, params.get('user_id'), params)


def get_analysis_result(analysis_id):
    from analysis_manager import get_analysis_result as _get
    return _get(analysis_id)


def get_analysis_record(analysis_id):
    from analysis_manager import get_analysis_record as _get
    return _get(analysis_id)


def delete_analysis_record(analysis_id):
    from analysis_manager import delete_analysis as _del
    return _del(analysis_id)


def delete_analysis(analysis_id, user_id):
    from analysis_manager import delete_analysis as _del
    return _del(analysis_id, user_id)


def get_user_analyses(user_id, page=1, per_page=10):
    from analysis_manager import get_user_analysis_history
    return get_user_analysis_history(user_id, page, per_page)


@cache.cache_decorator(expiry=30)
def search_user_models(user_id, search_term, page=1, per_page=10):
    """搜索用户的模型，支持分页"""
    conn = get_db_connection()
    if user_id == 0:
        total = conn.execute(
            '''SELECT COUNT(*) FROM models 
               WHERE model_name LIKE ? OR model_description LIKE ?''',
            (f"%{search_term}%", f"%{search_term}%")
        ).fetchone()[0]
        offset = (page - 1) * per_page
        models = conn.execute(
            '''SELECT * FROM models 
               WHERE model_name LIKE ? OR model_description LIKE ?
               ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            (f"%{search_term}%", f"%{search_term}%", per_page, offset)
        ).fetchall()
    else:
        total = conn.execute(
            '''SELECT COUNT(*) FROM models 
               WHERE user_id = ? AND (model_name LIKE ? OR model_description LIKE ?)''',
            (user_id, f"%{search_term}%", f"%{search_term}%")
        ).fetchone()[0]
        offset = (page - 1) * per_page
        models = conn.execute(
            '''SELECT * FROM models 
               WHERE user_id = ? AND (model_name LIKE ? OR model_description LIKE ?)
               ORDER BY created_at DESC LIMIT ? OFFSET ?''',
            (user_id, f"%{search_term}%", f"%{search_term}%", per_page, offset)
        ).fetchall()
    conn.close()

    return {
        'models': models,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page
    }


def get_model_file_path(filename):
    """获取模型文件的完整路径"""
    upload_dir = ensure_upload_directory()
    return os.path.join(upload_dir, filename)


def init_models_table():
    """初始化模型表（支持普通上传和参数化桁架模型）"""
    conn = get_db_connection()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER DEFAULT 0,
            model_name TEXT NOT NULL,
            model_description TEXT,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            file_type TEXT,
            model_type TEXT,
            parameters TEXT,
            apdl_script TEXT,
            created_at TIMESTAMP,
            last_modified TIMESTAMP,
            max_displacement REAL,
            max_stress REAL,
            safety_factor REAL,
            analysis_status TEXT
        )
    ''')
    conn.commit()
    conn.close()