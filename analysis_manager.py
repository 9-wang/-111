import os
import json
import time
import threading
from datetime import datetime
from config import ANALYSIS_RESULTS_DIR, APP_DB_PATH

# 导入anastruct库
from anastruct import SystemElements

# 确保分析结果目录存在
def ensure_results_directory():
    """确保分析结果目录存在，如果不存在则创建"""
    if not os.path.exists(ANALYSIS_RESULTS_DIR):
        os.makedirs(ANALYSIS_RESULTS_DIR)
    return ANALYSIS_RESULTS_DIR

# 创建数据库连接
def get_db_connection():
    import sqlite3
    conn = sqlite3.connect(APP_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# 初始化分析表
def init_analysis_table():
    """初始化分析表"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS analyses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        analysis_id TEXT,
        user_id INTEGER DEFAULT 0,
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
        results TEXT
    )
    ''')
    conn.commit()
    conn.close()

# 创建分析记录
def create_analysis_record(params):
    """创建新的分析记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 生成分析ID
    cursor.execute('SELECT MAX(CAST(analysis_id AS INTEGER)) FROM analyses')
    max_id = cursor.fetchone()
    max_id = max_id[0] if max_id is not None else None
    analysis_id = str(max_id + 1) if max_id is not None else '1'
    
    # 插入分析记录
    cursor.execute('''
    INSERT INTO analyses (analysis_id, user_id, model_id, model_name, analysis_type, 
                         status, elastic_modulus, poisson_ratio, density, mesh_size, started_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        analysis_id,
        params.get('user_id', 0),
        params.get('model_id', 1),
        params.get('model_name', ''),
        params.get('analysis_type', 'static'),
        'running',
        params.get('elastic_modulus', 210000.0),
        params.get('poisson_ratio', 0.3),
        params.get('density', 7850.0),
        params.get('mesh_size', 10.0),
        datetime.now().isoformat()
    ))
    
    conn.commit()
    conn.close()
    return analysis_id

# 更新分析状态
def update_analysis_status(analysis_id, status, completed_at=None, results=None):
    """更新分析状态"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status == 'completed' and completed_at:
            if results:
                # 尝试序列化结果
                try:
                    results_json = json.dumps(results)
                except Exception as e:
                    print(f"序列化结果失败: {e}")
                    results_json = json.dumps({'status': 'completed', 'message': '分析成功完成'})
                
                cursor.execute('''
                UPDATE analyses SET status = ?, completed_at = ?, results = ? WHERE analysis_id = ?
                ''', (status, completed_at, results_json, analysis_id))
            else:
                cursor.execute('''
                UPDATE analyses SET status = ?, completed_at = ? WHERE analysis_id = ?
                ''', (status, completed_at, analysis_id))
        else:
            cursor.execute('''
            UPDATE analyses SET status = ? WHERE analysis_id = ?
            ''', (status, analysis_id))
        
        conn.commit()
        conn.close()
        print(f"分析状态更新成功: {analysis_id} -> {status}")
    except Exception as e:
        print(f"更新分析状态失败: {e}")
        # 即使出现异常，也要确保连接关闭
        try:
            conn.close()
        except:
            pass

# 获取分析记录
def get_analysis_record(analysis_id):
    """获取分析记录"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT * FROM analyses WHERE analysis_id = ?
    ''', (analysis_id,))
    
    record = cursor.fetchone()
    conn.close()
    
    if record:
        return dict(record)
    return None

# 获取用户的分析历史
def get_user_analysis_history(user_id, page=1, per_page=10):
    """获取用户的分析历史"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 获取总数
    if user_id == 0:
        cursor.execute('SELECT COUNT(*) FROM analyses')
    else:
        cursor.execute('SELECT COUNT(*) FROM analyses WHERE user_id = ?', (user_id,))
    total = cursor.fetchone()[0]
    
    # 计算偏移量
    offset = (page - 1) * per_page
    
    # 获取分页数据
    if user_id == 0:
        cursor.execute('''
        SELECT * FROM analyses 
        ORDER BY started_at DESC 
        LIMIT ? OFFSET ?
        ''', (per_page, offset))
    else:
        cursor.execute('''
        SELECT * FROM analyses WHERE user_id = ? 
        ORDER BY started_at DESC 
        LIMIT ? OFFSET ?
        ''', (user_id, per_page, offset))
    
    analyses = []
    for row in cursor.fetchall():
        analyses.append(dict(row))
    
    conn.close()
    
    # 计算总页数
    pages = (total + per_page - 1) // per_page
    
    return {
        'analyses': analyses,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'pages': pages,
            'total': total
        }
    }

# 解析模型文件，提取模型信息
def parse_model_file(model_path):
    """解析模型文件，提取模型信息"""
    try:
        import os
        filename = os.path.basename(model_path)
        
        # 读取文件内容
        with open(model_path, 'r') as f:
            content = f.read()
        
        # 根据文件扩展名判断文件类型
        ext = os.path.splitext(filename)[1].lower()
        
        vertices = []
        edges = []
        
        if ext == '.obj':
            # 解析OBJ文件
            for line in content.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if parts[0] == 'v':
                    # 顶点: v x y z
                    x = float(parts[1])
                    y = float(parts[2])
                    z = float(parts[3])
                    vertices.append((x, y, z))
                elif parts[0] == 'l':
                    # 边: l vertex1 vertex2
                    v1 = int(parts[1]) - 1  # OBJ文件中的顶点索引从1开始
                    v2 = int(parts[2]) - 1
                    edges.append((v1, v2))
        elif ext == '.inp' or 'truss' in filename.lower():
            # 解析APDL脚本文件
            node_lines = []
            element_lines = []
            
            for line in content.strip().split('\n'):
                line = line.strip()
                if not line or line.startswith('!') or line.startswith('/'):
                    continue
                
                parts = line.split(',')
                if parts[0].upper() == 'N':
                    # 节点: N,node_id,x,y,z
                    if len(parts) >= 5:
                        node_id = int(parts[1])
                        x = float(parts[2])
                        y = float(parts[3])
                        z = float(parts[4])
                        node_lines.append((node_id, x, y, z))
                elif parts[0].upper() == 'E':
                    # 单元: E,element_id,node1,node2
                    if len(parts) >= 4:
                        element_id = int(parts[1])
                        node1 = int(parts[2])
                        node2 = int(parts[3])
                        element_lines.append((element_id, node1, node2))
            
            # 排序节点，确保顺序正确
            node_lines.sort(key=lambda x: x[0])
            # 构建顶点列表
            for node_id, x, y, z in node_lines:
                vertices.append((x, y, z))
            
            # 构建边列表（需要将节点ID转换为索引）
            node_id_to_index = {node_id: i for i, (node_id, _, _, _) in enumerate(node_lines)}
            for _, node1, node2 in element_lines:
                if node1 in node_id_to_index and node2 in node_id_to_index:
                    v1 = node_id_to_index[node1]
                    v2 = node_id_to_index[node2]
                    edges.append((v1, v2))
        
        # 计算模型参数
        if vertices:
            # 计算跨度（x方向的最大距离）
            x_coords = [v[0] for v in vertices]
            span = max(x_coords) - min(x_coords)
            
            # 计算高度（y方向的最大距离）
            y_coords = [v[1] for v in vertices]
            height = max(y_coords) - min(y_coords)
            
            # 检查长度单位，如果跨度小于1，可能是米，需要转换为毫米
            if span < 1:
                # 转换为毫米
                for i, vertex in enumerate(vertices):
                    vertices[i] = (vertex[0] * 1000, vertex[1] * 1000, vertex[2] * 1000)
                # 重新计算跨度和高度
                x_coords = [v[0] for v in vertices]
                span = max(x_coords) - min(x_coords)
                y_coords = [v[1] for v in vertices]
                height = max(y_coords) - min(y_coords)
                print(f"长度单位转换：将米转换为毫米，新的跨度: {span} mm, 新的高度: {height} mm")
            
            # 根据顶点和边的数量判断桁架类型
            node_count = len(vertices)
            element_count = len(edges)
            
            # 简单的桁架类型判断
            if node_count == 3 and element_count == 3:
                truss_type = 'triangle'
            elif node_count == 4 and element_count == 4:
                truss_type = 'rectangle'
            elif 'pratt' in filename.lower():
                truss_type = 'pratt'
            elif 'warren' in filename.lower():
                truss_type = 'warren'
            elif 'howe' in filename.lower():
                truss_type = 'howe'
            elif 'trapezoid' in filename.lower():
                truss_type = 'trapezoid'
            elif 'parallel' in filename.lower():
                truss_type = 'parallel'
            else:
                truss_type = 'custom'
            
            # 计算节点间距
            node_spacing = span / (node_count - 1) if node_count > 1 else 1.0
        else:
            # 默认值
            truss_type = 'pratt'
            span = 10.0
            height = 3.0
            node_spacing = 1.0
        
        print(f"解析模型文件 {filename} 成功:")
        print(f"  桁架类型: {truss_type}")
        print(f"  跨度: {span}")
        print(f"  高度: {height}")
        print(f"  节点数: {len(vertices)}")
        print(f"  元素数: {len(edges)}")
        print(f"  节点间距: {node_spacing}")
        
        return {
            'truss_type': truss_type,
            'span': span,
            'height': height,
            'node_count': len(vertices),
            'element_count': len(edges),
            'node_spacing': node_spacing,
            'vertices': vertices,
            'edges': edges
        }
    except Exception as e:
        print(f"解析模型文件失败: {e}")
        import traceback
        traceback.print_exc()
        return {
            'truss_type': 'pratt',
            'span': 10.0,
            'height': 3.0,
            'node_count': 0,
            'element_count': 0,
            'node_spacing': 1.0,
            'vertices': [],
            'edges': []
        }

# 使用PyNite库进行3D有限元分析
def run_truss_analysis(model_info, analysis_params, analysis_id):
    """使用PyNite库进行3D有限元分析"""
    try:
        # 导入必要的库
        import numpy as np
        from PyNite import FEModel3D
        
        # 获取模型参数
        span = model_info.get('span', 10.0)
        height = model_info.get('height', 3.0)
        truss_type = model_info.get('truss_type', 'pratt')
        node_count = model_info.get('node_count', 3)
        element_count = model_info.get('element_count', 3)
        vertices = model_info.get('vertices', [])
        edges = model_info.get('edges', [])
        
        # 材料属性
        E = analysis_params.get('elastic_modulus', 210000.0)  # MPa
        density = analysis_params.get('density', 7850.0)  # kg/m³
        area = 5000  # 5000 mm²
        
        # 截面属性（mm^4）
        Iy = 1e8  # 绕y轴惯性矩，示例值
        Iz = 1e8  # 绕z轴惯性矩，示例值
        J = 1e7  # 极惯性矩，示例值
        
        # 荷载信息
        print(f"analysis_params: {analysis_params}")
        concentrated_load = analysis_params.get('concentrated_load', 0)
        print(f"concentrated_load: {concentrated_load}, type: {type(concentrated_load)}")
        if concentrated_load == 0:
            concentrated_load = 1000  # 默认荷载
            print("使用默认荷载1000N")
        
        print(f"模型信息:")
        print(f"  桁架类型: {truss_type}")
        print(f"  跨度: {span}")
        print(f"  高度: {height}")
        print(f"  节点数: {node_count}")
        print(f"  元素数: {element_count}")
        print(f"  顶点数: {len(vertices)}")
        print(f"  边数: {len(edges)}")
        
        # 创建FEModel3D实例
        model = FEModel3D()
        
        # 添加材料
        model.add_material('Steel', E, 0.3, density)
        
        # 创建几何模型
        # 为每个顶点添加节点
        node_map = {}
        for i, vertex in enumerate(vertices):
            node_id = i + 1  # 节点ID从1开始
            # 添加3D节点（z坐标设为0）
            model.add_node(f'N{i+1}', vertex[0], vertex[1], 0.0)
            node_map[i] = node_id
        
        # 添加元素
        for i, edge in enumerate(edges):
            v1, v2 = edge
            if v1 in node_map and v2 in node_map:
                # 添加梁单元
                model.add_member(f'M{i+1}', node_map[v1], node_map[v2], 'Steel', area, Iy, Iz, J)
        
        # 添加边界条件（支座）
        # 假设第一个节点为固定铰支座，最后一个节点为滑动铰支座
        if node_map:
            # 左端为固定铰支座（限制x,y,z方向位移）
            model.def_support(node_map[0], True, True, True, False, False, False)
            # 右端为滑动铰支座（限制y,z方向位移）
            model.def_support(node_map[len(node_map)-1], False, True, True, False, False, False)
        
        # 施加荷载
        # 在顶部节点施加集中力
        if node_map:
            # 找到顶部节点（y坐标最大的节点）
            top_node = max(vertices, key=lambda v: v[1])
            top_node_index = vertices.index(top_node)
            if top_node_index in node_map:
                # 施加向下的集中力（y方向）
                model.add_node_load(node_map[top_node_index], 'FY', -concentrated_load)
        
        # 执行求解
        print("开始求解...")
        model.solve()
        print("求解完成")
        
        # 获取结果
        # 获取最大位移
        max_global_displacement = 0.0
        max_node_displacement = {'node_id': None, 'ux': 0, 'uy': 0, 'uz': 0, 'total': 0}
        
        for node in model.nodes.values():
            # 计算总位移
            total_disp = np.sqrt(node.Ux**2 + node.Uy**2 + node.Uz**2)
            if total_disp > max_global_displacement:
                max_global_displacement = total_disp
                max_node_displacement = {
                    'node_id': node.name,
                    'ux': node.Ux,
                    'uy': node.Uy,
                    'uz': node.Uz,
                    'total': total_disp
                }
        
        # 获取最大内力
        max_forces = {
            'axial': -np.inf,  # 轴力
            'shear_y': -np.inf,  # y方向剪力
            'shear_z': -np.inf,  # z方向剪力
            'moment_y': -np.inf,  # y方向弯矩
            'moment_z': -np.inf,  # z方向弯矩
            'torsion': -np.inf  # 扭矩
        }
        
        for member in model.members.values():
            # 获取单元内力
            max_axial = max(abs(member.MaxAxial), abs(member.MinAxial))
            max_shear_y = max(abs(member.MaxShearVy), abs(member.MinShearVy))
            max_shear_z = max(abs(member.MaxShearVz), abs(member.MinShearVz))
            max_moment_y = max(abs(member.MaxMomentMy), abs(member.MinMomentMy))
            max_moment_z = max(abs(member.MaxMomentMz), abs(member.MinMomentMz))
            max_torsion = max(abs(member.MaxTorsion), abs(member.MinTorsion))
            
            # 更新最大值
            max_forces['axial'] = max(max_forces['axial'], max_axial)
            max_forces['shear_y'] = max(max_forces['shear_y'], max_shear_y)
            max_forces['shear_z'] = max(max_forces['shear_z'], max_shear_z)
            max_forces['moment_y'] = max(max_forces['moment_y'], max_moment_y)
            max_forces['moment_z'] = max(max_forces['moment_z'], max_moment_z)
            max_forces['torsion'] = max(max_forces['torsion'], max_torsion)
        
        # 计算最大应力
        def calculate_max_stress(A, Iy, Iz, max_forces, y_max, z_max):
            """
            计算结构最大应力。
            :param y_max: 截面中性轴到y方向最远点的距离 (mm)
            :param z_max: 截面中性轴到z方向最远点的距离 (mm)
            """
            # 轴向应力: σ_axial = N / A (N/mm² = MPa)
            sigma_axial = max_forces['axial'] / A if A > 0 else 0
            # 弯曲应力: σ_bending = M * y / I (N*mm / mm^4 = N/mm² = MPa)
            sigma_bending_y = max_forces['moment_y'] * z_max / Iz if Iz > 0 else 0
            sigma_bending_z = max_forces['moment_z'] * y_max / Iy if Iy > 0 else 0
            # 总应力为两者之和（取最不利组合）
            max_sigma = sigma_axial + max(sigma_bending_y, sigma_bending_z)
            return max_sigma, sigma_axial, sigma_bending_y, sigma_bending_z
        
        y_max = 100  # 截面中性轴到y方向最远点的距离，示例值 (mm)
        z_max = 100  # 截面中性轴到z方向最远点的距离，示例值 (mm)
        max_sigma, sigma_axial, sigma_bending_y, sigma_bending_z = calculate_max_stress(
            area, Iy, Iz, max_forces, y_max, z_max
        )
        
        # 计算安全系数
        # 定义材料许用应力 [σ] (Pa)
        allowable_sigma = 235e6  # 235 MPa
        
        def calculate_safety_factor(max_sigma, allowable_sigma):
            """计算安全系数"""
            if max_sigma == 0:
                return 1000000  # 使用一个大数字代替无穷大
            return allowable_sigma / abs(max_sigma)
        
        safety_factor = calculate_safety_factor(max_sigma, allowable_sigma)
        
        # 输出结果
        print("========== 分析结果 ==========")
        print(f"最大位移: {max_global_displacement:.6f} m")
        if max_node_displacement['node_id']:
            print(f"最大节点位移: 节点 {max_node_displacement['node_id']}")
            print(f"   水平位移 (ux): {max_node_displacement['ux']:.6f} m")
            print(f"   竖直位移 (uy): {max_node_displacement['uy']:.6f} m")
            print(f"   垂直位移 (uz): {max_node_displacement['uz']:.6f} m")
            print(f"   总位移: {max_node_displacement['total']:.6f} m")
        print("\n最大内力:")
        print(f"   轴力 (N): {max_forces['axial']:.2f} N")
        print(f"   y方向剪力 (Qy): {max_forces['shear_y']:.2f} N")
        print(f"   z方向剪力 (Qz): {max_forces['shear_z']:.2f} N")
        print(f"   y方向弯矩 (My): {max_forces['moment_y']:.2f} N·m")
        print(f"   z方向弯矩 (Mz): {max_forces['moment_z']:.2f} N·m")
        print(f"   扭矩 (T): {max_forces['torsion']:.2f} N·m")
        print("\n应力计算:")
        print(f"   最大轴向应力 (σ_axial): {sigma_axial/1e6:.2f} MPa")
        print(f"   y方向弯曲应力 (σ_bending_y): {sigma_bending_y/1e6:.2f} MPa")
        print(f"   z方向弯曲应力 (σ_bending_z): {sigma_bending_z/1e6:.2f} MPa")
        print(f"   最大组合应力 (σ_max): {max_sigma/1e6:.2f} MPa")
        print(f"\n安全系数 (基于 {allowable_sigma/1e6:.0f} MPa 许用应力): {safety_factor:.2f}")
        
        # 构建结果
        results = {
            'status': 'completed',
            'truss_type': truss_type,
            'span': span,
            'height': height,
            'node_count': node_count,
            'element_count': element_count,
            'max_displacement': max_global_displacement,
            'max_stress': max_sigma / 1e6,  # 转换为MPa
            'safety_factor': safety_factor,
            'elements_count': element_count,
            'nodes_count': node_count,
            'analysis_method': 'pynite',
            'message': '分析成功完成',
            'max_forces': max_forces,
            'sigma_axial': sigma_axial / 1e6,
            'sigma_bending_y': sigma_bending_y / 1e6,
            'sigma_bending_z': sigma_bending_z / 1e6,
            'max_node_displacement': max_node_displacement
        }
        
        # 生成3D可视化结果
        generate_3d_visualization(model, model_info, analysis_params, analysis_id)
        
        return results
    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()
        return {'status': 'failed', 'error': str(e), 'message': '分析失败，请检查模型参数'}

# 生成3D可视化结果
def generate_3d_visualization(model, model_info, analysis_params, analysis_id):
    """生成3D可视化结果"""
    try:
        import pyvista as pv
        import numpy as np
        import os
        
        print("开始生成3D可视化结果...")
        
        # 创建PyVista网格
        points = []
        lines = []
        line_count = 0
        
        # 添加节点
        node_id_map = {}
        for i, node in enumerate(model.nodes.values()):
            points.append([node.X, node.Y, node.Z])
            node_id_map[node.name] = i
        
        # 添加单元
        for member in model.members.values():
            start_node = node_id_map[member.i_node.name]
            end_node = node_id_map[member.j_node.name]
            lines.extend([2, start_node, end_node])
            line_count += 1
        
        # 创建PolyData
        points_array = np.array(points)
        lines_array = np.array(lines, dtype=np.int32)
        
        mesh = pv.PolyData(points_array, lines=lines_array)
        
        # 添加位移数据
        displacements = []
        for node in model.nodes.values():
            total_disp = np.sqrt(node.Ux**2 + node.Uy**2 + node.Uz**2)
            displacements.append(total_disp)
        
        mesh['Displacement'] = np.array(displacements)
        
        # 计算变形后的网格
        deformed_points = points_array.copy()
        for i, node in enumerate(model.nodes.values()):
            deformed_points[i] += [node.Ux, node.Uy, node.Uz]
        
        deformed_mesh = pv.PolyData(deformed_points, lines=lines_array)
        deformed_mesh['Displacement'] = np.array(displacements)
        
        # 创建可视化场景
        plotter = pv.Plotter()
        
        # 添加原始结构（半透明）
        plotter.add_mesh(mesh, color='gray', opacity=0.5, line_width=2, label='Original')
        
        # 添加变形结构（彩色，根据位移）
        plotter.add_mesh(
            deformed_mesh, 
            scalars='Displacement', 
            cmap='jet', 
            line_width=3, 
            label='Deformed',
            colorbar_args={'title': 'Displacement (m)'}
        )
        
        # 添加节点
        plotter.add_mesh(
            pv.PolyData(points_array),
            color='black',
            point_size=5,
            label='Nodes'
        )
        
        # 设置场景
        plotter.add_axes()
        plotter.set_title(f"3D Truss Analysis - {model_info.get('truss_type', 'Custom')}")
        plotter.add_legend()
        
        # 保存可视化结果
        analysis_dir = os.path.join(ANALYSIS_RESULTS_DIR, analysis_id)
        os.makedirs(analysis_dir, exist_ok=True)
        
        # 保存为VTK文件
        vtk_file = os.path.join(analysis_dir, 'visualization.vtk')
        deformed_mesh.save(vtk_file)
        print(f"3D可视化结果已保存为: {vtk_file}")
        
        # 保存为PNG图片
        png_file = os.path.join(analysis_dir, 'visualization.png')
        plotter.screenshot(png_file)
        print(f"3D可视化截图已保存为: {png_file}")
        
        # 关闭plotter
        plotter.close()
        
        print("3D可视化结果生成完成")
        
    except Exception as e:
        print(f"生成3D可视化结果失败: {e}")
        import traceback
        traceback.print_exc()

# 运行分析
def run_analysis(analysis_id, params):
    """运行分析"""
    try:
        # 确保结果目录存在
        ensure_results_directory()
        
        # 创建分析工作目录
        analysis_dir = os.path.join(ANALYSIS_RESULTS_DIR, analysis_id)
        os.makedirs(analysis_dir, exist_ok=True)
        
        # 创建日志文件和结果文件路径
        results_json = os.path.join(analysis_dir, 'results.json')
        
        # 解析模型文件，提取模型信息
        model_path = params.get('model_path')
        if not model_path:
            # 如果没有模型路径，使用默认参数
            model_info = {
                'truss_type': 'pratt',
                'span': 10.0,
                'height': 3.0,
                'node_spacing': 1.0
            }
        else:
            # 构建完整的模型文件路径
            import os
            upload_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
            full_model_path = os.path.join(upload_dir, model_path)
            model_info = parse_model_file(full_model_path)
        
        # 调用run_truss_analysis函数执行实际分析
        print(f"开始分析: {analysis_id}")
        results = run_truss_analysis(model_info, params, analysis_id)
        print(f"run_truss_analysis返回的结果: {results}")
        
        if results.get('status') == 'completed':
            # 保存结果
            print(f"准备保存结果到文件: {results_json}")
            print(f"结果内容: {results}")
            with open(results_json, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"结果保存成功: {results_json}")
            # 验证文件内容
            with open(results_json, 'r') as f:
                saved_results = json.load(f)
            print(f"文件中保存的结果: {saved_results}")
            
            # 更新分析状态
            update_analysis_status(analysis_id, 'completed', datetime.now().isoformat(), results)
            print(f"分析成功完成: {analysis_id}")
        else:
            # 分析失败
            with open(results_json, 'w') as f:
                json.dump(results, f, indent=2)
            
            # 更新分析状态为失败
            update_analysis_status(analysis_id, 'failed')
            print(f"分析失败: {analysis_id}")
    except Exception as e:
        print(f"分析执行失败: {e}")
        # 更新分析状态为失败
        update_analysis_status(analysis_id, 'failed')

# 获取分析结果
def get_analysis_result(analysis_id):
    """获取分析结果"""
    # 直接从文件系统获取
    analysis_dir = os.path.join(ANALYSIS_RESULTS_DIR, analysis_id)
    results_json = os.path.join(analysis_dir, 'results.json')
    
    if os.path.exists(results_json):
        try:
            with open(results_json, 'r') as f:
                return json.load(f)
        except:
            pass
    
    # 如果文件系统中没有结果，再尝试从数据库获取
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
    SELECT results FROM analyses WHERE analysis_id = ?
    ''', (analysis_id,))
    
    record = cursor.fetchone()
    conn.close()
    
    if record and record['results']:
        try:
            return json.loads(record['results'])
        except:
            pass
    
    return None

# 删除分析记录
def delete_analysis(analysis_id, user_id):
    """删除分析记录"""
    import shutil
    
    # 删除数据库记录
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if user_id == 0:
        cursor.execute('DELETE FROM analyses WHERE analysis_id = ?', (analysis_id,))
    else:
        cursor.execute('DELETE FROM analyses WHERE analysis_id = ? AND user_id = ?', (analysis_id, user_id))
    
    conn.commit()
    conn.close()
    
    # 删除分析目录
    analysis_dir = os.path.join(ANALYSIS_RESULTS_DIR, analysis_id)
    if os.path.exists(analysis_dir):
        try:
            shutil.rmtree(analysis_dir)
        except:
            pass
    
    return True

# 初始化分析表
init_analysis_table()