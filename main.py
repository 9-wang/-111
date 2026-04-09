from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, send_file
from flask_compress import Compress
from flask_session import Session
from flask_cors import CORS
import sqlite3
import os
import json
from datetime import datetime
from werkzeug.utils import secure_filename

import analysis_manager
import models_manager
from models_manager import get_model, get_user_models, get_user_analyses
import truss_template
from cache import cache
from config import APP_DB_PATH, UPLOAD_FOLDER

# 创建Flask应用实例
app = Flask(__name__)
CORS(app)
Compress(app)

# 配置
app.config.update({
    'SECRET_KEY': os.environ.get('SECRET_KEY', 'hard-to-guess-secret-key-for-development-only'),
    'SESSION_TYPE': 'filesystem',
    'SESSION_PERMANENT': True,
    'PERMANENT_SESSION_LIFETIME': 3600 * 24 * 7,
    'SESSION_FILE_DIR': os.path.join(os.getcwd(), '.flask_session'),
    'SESSION_FILE_THRESHOLD': 500,
    'SESSION_FILE_MODE': 0o600,
    'SESSION_COOKIE_SECURE': False,
    'SESSION_COOKIE_HTTPONLY': True,
    'SESSION_COOKIE_SAMESITE': 'Lax',
    'SEND_FILE_MAX_AGE_DEFAULT': 3600 * 24 * 7,
    'COMPRESS_ALGORITHM': ['gzip', 'br', 'zstd'],
    'COMPRESS_LEVEL': 9,
    'COMPRESS_MIN_SIZE': 500,
    'COMPRESS_VARY_HEADER': True,
    'MAX_CONTENT_LENGTH': 100 * 1024 * 1024,
    'UPLOAD_FOLDER': UPLOAD_FOLDER
})

Session(app)

# 确保目录存在
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['SESSION_FILE_DIR'], exist_ok=True)

DATABASE = APP_DB_PATH

# ---------- 辅助函数 ----------
def get_current_user_id():
    return 0

def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    print(f"初始化数据库 - 路径: {DATABASE}")
    try:
        models_manager.init_models_table()
        analysis_manager.init_analysis_table()
        print("数据库表初始化成功")
    except Exception as e:
        print(f"初始化数据库表时出错：{e}")

# ---------- 参数化建模辅助函数 ----------
def validate_parametric_params(truss_type, model_name, span, height, node_spacing, top_span=None):
    if not model_name:
        return False, '请输入模型名称'
    if not truss_type:
        return False, '请选择桁架类型'
    if span <= 0 or height <= 0 or node_spacing <= 0:
        return False, '跨度、高度和节点间距必须大于0'
    if node_spacing > span:
        return False, '节点间距不能大于跨度'
    if truss_type == 'trapezoid' and (top_span is None or top_span <= 0):
        return False, '梯形桁架需要设置顶部跨度'
    return True, ''

def create_truss_model(truss_type, span, height, node_spacing, section_type, top_span=None):
    if truss_type == 'triangle':
        return truss_template.TriangleTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing)
    elif truss_type == 'trapezoid':
        return truss_template.TrapezoidTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing, top_span=top_span)
    elif truss_type == 'parallel':
        return truss_template.ParallelTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing)
    elif truss_type == 'warren':
        return truss_template.WarrenTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing)
    elif truss_type == 'howe':
        return truss_template.HoweTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing)
    elif truss_type == 'pratt':
        return truss_template.PrattTruss(span=span, height=height, section_type=section_type, node_spacing=node_spacing)
    else:
        return None

# ---------- 路由 ----------
@app.route('/')
def index():
    return redirect(url_for('home'))

@app.route('/home')
def home():
    return render_template('home.html', username='Guest', active_menu='home')

@app.route('/models')
def models():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    search_term = request.args.get('search', '')
    user_id = get_current_user_id()
    try:
        if search_term:
            pagination = models_manager.search_user_models(user_id, search_term, page, per_page)
        else:
            pagination = models_manager.get_user_models(user_id, page, per_page)
    except Exception as e:
        print(f"获取模型列表时出错: {str(e)}")
        flash('获取模型列表失败', 'error')
        pagination = {'models': [], 'total': 0, 'page': 1, 'per_page': per_page, 'pages': 0}
    return render_template('models.html',
                           username='Guest',
                           active_menu='models',
                           models=pagination['models'],
                           pagination=pagination,
                           search_term=search_term)

@app.route('/model_list')
def model_list():
    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM models ORDER BY id DESC').fetchall()
    conn.close()
    
    models = []
    for row in rows:
        model_dict = dict(row)
        if model_dict.get('parameters'):
            try:
                model_dict['parameters'] = json.loads(model_dict['parameters'])
            except:
                model_dict['parameters'] = {}
        else:
            model_dict['parameters'] = {}
        models.append(model_dict)
    
    print(f"从数据库查询到 {len(models)} 条模型记录")
    return render_template('model_list.html', username='Guest', models=models)

@app.route('/upload_model', methods=['POST'])
def upload_model():
    try:
        model_file = request.files.get('model_file')
        model_name = request.form.get('model_name', '').strip()
        model_description = request.form.get('model_description', '').strip()
        user_id = get_current_user_id()
        model_id, filename = models_manager.save_model_file(
            model_file, user_id, model_name, model_description
        )
        flash('模型上传成功！', 'success')
        return redirect(url_for('models'))
    except ValueError as e:
        flash(str(e), 'error')
        return redirect(url_for('models'))
    except Exception as e:
        print(f"上传模型时出错: {str(e)}")
        flash(f'上传失败: {str(e)}', 'error')
        return redirect(url_for('models'))

@app.route('/test_save_truss')
def test_save_truss():
    try:
        model_id = models_manager.save_truss_model(
            user_id=0,
            model_name="测试桁架_" + datetime.now().strftime("%H%M%S"),
            truss_type="triangle",
            parameters={"span": 10.0, "height": 2.0, "node_spacing": 1.0, "section_type": "HN150×75"},
            nodes=[[0,0,0], [5,0,0], [2.5,2,0]],
            elements=[[0,1], [0,2], [1,2]]
        )
        return jsonify({"success": True, "model_id": model_id})
    except Exception as e:
        import traceback
        return jsonify({"success": False, "error": str(e), "trace": traceback.format_exc()})
    
@app.route('/analysis')
def analysis():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    user_id = get_current_user_id()
    user_models_data = models_manager.get_user_models(user_id, page=1, per_page=100)
    user_models = user_models_data['models'] if isinstance(user_models_data, dict) else []
    analysis_history = analysis_manager.get_user_analysis_history(user_id, page=page, per_page=per_page)
    return render_template('analysis.html',
                           username='Guest',
                           active_menu='analysis',
                           user_models=user_models,
                           analyses=analysis_history.get('analyses', []),
                           pagination=analysis_history.get('pagination', {}))

# ---------- 参数化建模 ----------
@app.route('/parametric_modeling', methods=['GET', 'POST'])
def parametric_modeling():
    if request.method == 'POST':
        print("\n===== 接收到参数化建模 POST 请求 =====")
        try:
            truss_type = request.form.get('truss_type')
            span = float(request.form.get('span'))
            height = float(request.form.get('height'))
            node_spacing = float(request.form.get('node_spacing'))
            section_type = request.form.get('section_type', '').replace('x', '×').replace('*', '×')
            model_name = request.form.get('model_name', '').strip()
            top_span = float(request.form.get('top_span')) if truss_type == 'trapezoid' and request.form.get('top_span') else None

            print(f"模型名称: {model_name}, 类型: {truss_type}, 跨度: {span}, 高度: {height}")

            valid, error_msg = validate_parametric_params(truss_type, model_name, span, height, node_spacing, top_span)
            if not valid:
                print(f"参数验证失败: {error_msg}")
                flash(error_msg, 'error')
                return render_template('parametric_modeling_new.html', username='Guest', active_menu='parametric_modeling')

            truss = create_truss_model(truss_type, span, height, node_spacing, section_type, top_span)
            if not truss:
                print("桁架创建失败")
                flash('不支持的桁架类型', 'error')
                return render_template('parametric_modeling_new.html', username='Guest', active_menu='parametric_modeling')

            print("桁架对象创建成功，正在获取模型数据...")
            model_data = truss.get_model_data()
            print(f"节点数量: {len(model_data['nodes'])}, 杆件数量: {len(model_data['elements'])}")

            user_id = get_current_user_id()

            parameters = {
                'truss_type': truss_type,
                'span': span,
                'height': height,
                'node_spacing': node_spacing,
                'section_type': section_type,
                'top_span': top_span
            }

            print("准备调用 save_truss_model...")
            model_id = models_manager.save_truss_model(
                user_id=user_id,
                model_name=model_name,
                truss_type=truss_type,
                parameters=parameters,
                nodes=model_data['nodes'],
                elements=model_data['elements']
            )
            print(f"save_truss_model 返回 model_id = {model_id}")

            flash('模型生成成功！', 'success')
            return redirect(url_for('view_3d_model', model_id=model_id))

        except Exception as e:
            print(f"!!!!! 参数化建模异常: {e} !!!!!")
            import traceback
            traceback.print_exc()
            flash(f'生成模型失败: {str(e)}', 'error')
            return render_template('parametric_modeling_new.html', username='Guest', active_menu='parametric_modeling')

    return render_template('parametric_modeling_new.html', username='Guest', active_menu='parametric_modeling')

# ---------- 查看模型 ----------
@app.route('/view_3d_model/<int:model_id>')
def view_3d_model(model_id):
    # 直接通过数据库获取模型，忽略 user_id 限制
    conn = get_db_connection()
    model_row = conn.execute('SELECT * FROM models WHERE id = ?', (model_id,)).fetchone()
    conn.close()
    if not model_row:
        flash('模型不存在', 'error')
        return redirect(url_for('models'))
    # 转换为字典并解析 parameters
    model = dict(model_row)
    if model.get('parameters'):
        try:
            model['parameters'] = json.loads(model['parameters'])
        except:
            model['parameters'] = {}
    else:
        model['parameters'] = {}
    return render_template('view_3d_model.html', model=model, username='Guest')

@app.route('/view_model/<int:model_id>')
def view_model(model_id):
    return redirect(url_for('view_3d_model', model_id=model_id))

# ---------- 分析 ----------
@app.route('/run_analysis', methods=['POST'])
def run_analysis():
    return redirect(url_for('analyze'), code=307)

@app.route('/analyze', methods=['POST'])
def analyze():
    model_id = request.form.get('model_id')
    if not model_id:
        flash('模型ID缺失', 'error')
        return redirect(url_for('analysis'))

    user_id = get_current_user_id()
    model = models_manager.get_model(model_id, user_id=None)
    if not model:
        flash('模型不存在', 'error')
        return redirect(url_for('analysis'))

    try:
        from truss_analyzer import analyze_with_anastruct
        model_data = model.get('parameters', {})
        if not model_data:
            flash('模型参数为空，请重新生成模型', 'error')
            return redirect(url_for('analysis'))

        analysis_id = analysis_manager.create_analysis_record({
            'user_id': user_id,
            'model_id': model_id,
            'model_name': model['model_name'],
            'analysis_type': 'static'
        })

        analysis_result = analyze_with_anastruct(model_data)

        with get_db_connection() as conn:
            conn.execute(
                '''UPDATE models 
                   SET max_displacement = ?, max_stress = ?, safety_factor = ?, analysis_status = ? 
                   WHERE id = ?''',
                (analysis_result.get('max_displacement', 0),
                 analysis_result.get('max_stress', 0),
                 analysis_result.get('safety_factor', 0),
                 'completed',
                 model_id)
            )
            conn.commit()

        analysis_manager.update_analysis_status(
            analysis_id, 
            'completed', 
            datetime.now().isoformat(), 
            analysis_result
        )

        display_results = {
            'span': model_data.get('span', 0),
            'height': model_data.get('height', 0),
            'node_spacing': model_data.get('node_spacing', 0),
            'max_stress': analysis_result.get('max_stress', 0),
            'max_displacement': analysis_result.get('max_displacement', 0),
            'safety_factor': analysis_result.get('safety_factor', 0),
            'nodes': model_data.get('nodes', []),
            'elements': model_data.get('elements', [])
        }

        return render_template('analysis_results.html',
                               results=display_results,
                               model_name=model['model_name'])

    except Exception as e:
        print(f"分析失败: {str(e)}")
        flash(f'分析失败: {str(e)}', 'error')
        return redirect(url_for('analysis'))

@app.route('/analysis_results')
def view_analysis_results_page():
    model_id = request.args.get('model_id')
    if not model_id:
        flash('缺少模型ID', 'error')
        return redirect(url_for('analysis'))

    user_id = get_current_user_id()
    model = models_manager.get_model(model_id, user_id=None)
    if not model:
        flash('模型不存在', 'error')
        return redirect(url_for('analysis'))

    model_data = model.get('parameters', {})
    if not model_data:
        flash('模型参数为空', 'error')
        return redirect(url_for('analysis'))

    display_results = {
        'span': model_data.get('span', 0),
        'height': model_data.get('height', 0),
        'node_spacing': model_data.get('node_spacing', 0),
        'max_stress': model.get('max_stress', 0),
        'max_displacement': model.get('max_displacement', 0),
        'safety_factor': model.get('safety_factor', 0),
        'nodes': model_data.get('nodes', []),
        'elements': model_data.get('elements', [])
    }

    return render_template('analysis_results.html',
                           results=display_results,
                           model_name=model['model_name'])

@app.route('/view_analysis/<analysis_id>')
def view_analysis(analysis_id):
    user_id = get_current_user_id()
    record = analysis_manager.get_analysis_record(analysis_id)
    if not record:
        flash('分析记录不存在', 'error')
        return redirect(url_for('analysis'))

    results = analysis_manager.get_analysis_result(analysis_id)
    if not results:
        flash('分析结果不存在', 'error')
        return redirect(url_for('analysis'))

    model = models_manager.get_model(record['model_id'], user_id=None)
    model_data = model.get('parameters', {}) if model else {}

    display_results = {
        'span': model_data.get('span', 0),
        'height': model_data.get('height', 0),
        'node_spacing': model_data.get('node_spacing', 0),
        'max_stress': results.get('max_stress', 0),
        'max_displacement': results.get('max_displacement', 0),
        'safety_factor': results.get('safety_factor', 0),
        'nodes': model_data.get('nodes', []),
        'elements': model_data.get('elements', [])
    }

    return render_template('analysis_results.html',
                           results=display_results,
                           model_name=record['model_name'])

@app.route('/delete_analysis/<analysis_id>')
def delete_analysis_route(analysis_id):
    user_id = get_current_user_id()
    try:
        analysis_manager.delete_analysis(analysis_id, user_id)
        flash('分析记录已删除', 'success')
    except Exception as e:
        flash(f'删除失败: {str(e)}', 'error')
    return redirect(url_for('analysis'))

# ---------- 3D 可视化 API ----------
@app.route('/api/model/<int:model_id>.json')
def get_model_data_api(model_id):
    """返回模型 JSON 数据，供前端 Plotly 使用（修复字段读取错误）"""
    conn = get_db_connection()
    model_row = conn.execute('SELECT * FROM models WHERE id = ?', (model_id,)).fetchone()
    conn.close()
    
    if not model_row:
        return jsonify({"error": "Model not found"}), 404
    
    model = dict(model_row)
    # 解析 parameters
    params = {}
    if model.get('parameters'):
        try:
            params = json.loads(model['parameters'])
        except:
            pass
    
    # 👇 修复：优先从数据库独立列读取 nodes/elements，兼容旧数据
    nodes = model.get('nodes', [])  # 先读独立列
    elements = model.get('elements', [])
    # 如果独立列为空，再尝试从 parameters 里读（兼容旧版本的模型）
    if not nodes:
        nodes = params.get('nodes', [])
    if not elements:
        elements = params.get('elements', [])
    
    # 兜底：如果还是空，尝试根据参数重建模型
    if not nodes or not elements:
        truss_type = params.get('truss_type', 'triangle')
        span = params.get('span', 10.0)
        height = params.get('height', 3.0)
        node_spacing = params.get('node_spacing', 1.0)
        section_type = params.get('section_type', 'HN150×75')
        top_span = params.get('top_span', None)
        try:
            truss = create_truss_model(truss_type, span, height, node_spacing, section_type, top_span)
            if truss:
                model_data = truss.get_model_data()
                nodes = model_data['nodes']
                elements = model_data['elements']
        except Exception as e:
            print(f"重建模型数据失败: {e}")
    
    # 分析结果字段（同样优先读独立列）
    max_displacement = model.get('max_displacement') or 0
    max_stress = model.get('max_stress') or 0
    safety_factor = model.get('safety_factor') or 1.5
    
    # 位移/应力数据
    displacements = model.get('displacements', [])
    stresses = model.get('stresses', [])
    if not displacements:
        displacements = params.get('displacements', [])
    if not stresses:
        stresses = params.get('stresses', [])
    
    result = {
        "nodes": nodes,
        "elements": elements,
        "max_displacement": max_displacement,
        "max_stress": max_stress,
        "safety_factor": safety_factor,
        "displacements": displacements,
        "stresses": stresses,
        "name": model['model_name'],
        "is_mock_data": False
    }
    return jsonify(result)

# 保留旧版兼容路由（支持字符串参数，但建议使用整数 ID）
@app.route('/api/model/<string:filename_or_id>.json')
def export_model_json_compat(filename_or_id):
    # 如果传入的是数字字符串，重定向到整数版本
    if filename_or_id.isdigit():
        return redirect(url_for('get_model_data_api', model_id=int(filename_or_id)))
    # 否则按旧逻辑尝试查找（保留原有功能）
    conn = get_db_connection()
    model = conn.execute('SELECT * FROM models WHERE file_path LIKE ?', (f'%{filename_or_id}%',)).fetchone()
    conn.close()
    if not model:
        return jsonify({"error": "模型不存在"}), 404
    return redirect(url_for('get_model_data_api', model_id=model['id']))

# ---------- 删除模型 ----------
@app.route('/delete_model/<int:model_id>', methods=['POST'])
def delete_model_route(model_id):
    user_id = get_current_user_id()
    try:
        models_manager.delete_model(model_id, user_id)
        flash('模型已成功删除', 'success')
    except Exception as e:
        flash(str(e), 'error')
    return redirect(url_for('model_list'))

# ---------- 其他路由 ----------
@app.route('/download_script/<int:file_id>')
def download_script(file_id):
    user_id = get_current_user_id()
    with get_db_connection() as conn:
        model = conn.execute(
            'SELECT file_path, model_name FROM models WHERE id = ? AND user_id = ?',
            (file_id, user_id)
        ).fetchone()
    if not model or not os.path.exists(model['file_path']):
        flash('文件不存在或无权访问', 'error')
        return redirect(url_for('model_list'))
    return send_file(model['file_path'], as_attachment=True, download_name=os.path.basename(model['file_path']))

@app.route('/test_session')
def test_session():
    if 'user_id' in session:
        return jsonify({'status': 'logged_in', 'user_id': session['user_id']})
    session['test'] = 'ok'
    return jsonify({'status': 'not_logged_in'})

# ---------- 启动 ----------
if __name__ == '__main__':
    init_db()
    app.run(debug=False, use_reloader=False)