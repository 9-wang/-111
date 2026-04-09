import plotly.graph_objects as go
from plotly.subplots import make_subplots


class TrussVisualizer:
    def __init__(self, model_data):
        self.model_data = model_data
        self._validate_data()
        
    def _validate_data(self):
        """验证模型数据格式"""
        if 'nodes' not in self.model_data or 'elements' not in self.model_data:
            raise ValueError("模型数据缺少必要字段: nodes, elements")
            
        # 验证节点坐标（2D/3D）
        for node in self.model_data['nodes']:
            if len(node) not in [2, 3]:
                raise ValueError(f"节点坐标格式错误: {node}")

    def create_3d_plot(self, title="Truss Structure", show_displacements=False, show_stresses=False):
        """创建Plotly 3D可视化"""
        # 创建坐标轴
        x = [node[0] for node in self.model_data['nodes']]
        y = [node[1] for node in self.model_data['nodes']]
        z = [node[2] if len(node) == 3 else 0 for node in self.model_data['nodes']]
        
        # 创建杆件坐标
        lines_x = []
        lines_y = []
        lines_z = []
        
        for elem in self.model_data['elements']:
            node1 = self.model_data['nodes'][elem[0]]
            node2 = self.model_data['nodes'][elem[1]]
            
            lines_x.extend([node1[0], node2[0], None])
            lines_y.extend([node1[1], node2[1], None])
            lines_z.extend([node1[2] if len(node1) == 3 else 0,
                           node2[2] if len(node2) == 3 else 0, None])
        
        # 创建节点散点图
        nodes_trace = go.Scatter3d(
            x=x, y=y, z=z,
            mode='markers',
            marker=dict(size=4, color='blue'),
            name='Nodes'
        )
        
        # 创建杆件线图
        elements_trace = go.Scatter3d(
            x=lines_x, y=lines_y, z=lines_z,
            mode='lines',
            line=dict(color='black', width=2),
            name='Elements'
        )
        
        traces = [nodes_trace, elements_trace]

        # 添加位移可视化（修复版）
        if show_displacements and 'displacements' in self.model_data:
            displacements = self.model_data['displacements']
            # 检查 displacements 是否为列表且长度匹配
            if isinstance(displacements, list) and len(displacements) == len(x):
                disp_x = []
                disp_y = []
                disp_z = []
                for i, disp in enumerate(displacements):
                    # 处理 disp 可能是 dict、list 或 None
                    if isinstance(disp, dict):
                        dx = disp.get('dx', 0)
                        dy = disp.get('dy', 0)
                        dz = disp.get('dz', 0)
                    elif isinstance(disp, (list, tuple)) and len(disp) >= 3:
                        dx, dy, dz = disp[0], disp[1], disp[2]
                    else:
                        dx = dy = dz = 0
                    disp_x.append(x[i] + dx)
                    disp_y.append(y[i] + dy)
                    disp_z.append(z[i] + dz)
                
                disp_trace = go.Scatter3d(
                    x=disp_x, y=disp_y, z=disp_z,
                    mode='markers',
                    marker=dict(size=3, color='red'),
                    name='Displaced Nodes'
                )
                traces.append(disp_trace)
        
        # 添加应力可视化（修复版）
        if show_stresses and 'stresses' in self.model_data:
            stresses = self.model_data['stresses']
            # 应力可以基于单元，也可以基于节点。此处假设 stresses 长度等于单元数，并在单元中点处显示颜色
            # 为简化，在节点上显示应力（取相邻单元平均），或使用线段颜色映射
            # 这里采用更简单的方式：在节点上显示应力（如果 stresses 长度等于节点数）
            if isinstance(stresses, list) and len(stresses) == len(x):
                stress_colors = self._get_stress_colors(stresses)
                stress_trace = go.Scatter3d(
                    x=x, y=y, z=z,
                    mode='markers',
                    marker=dict(
                        size=4,
                        color=stress_colors,
                        colorscale='RdBu',
                        colorbar=dict(title='Stress (Pa)')
                    ),
                    name='Stress'
                )
                traces.append(stress_trace)
            else:
                # 如果应力长度与单元数相同，可以将应力显示为杆件颜色（使用线段分段颜色较复杂，暂不实现）
                print("Warning: stresses length does not match nodes, skipping stress visualization")
        
        # 创建布局
        layout = go.Layout(
            title=title,
            scene=dict(
                xaxis=dict(title='X (m)'),
                yaxis=dict(title='Y (m)'),
                zaxis=dict(title='Z (m)')
            ),
            margin=dict(l=0, r=0, b=0, t=40)
        )
        
        # 创建3D图
        fig = go.Figure(data=traces, layout=layout)
        return fig
    
    def _get_stress_colors(self, stresses):
        """将应力值映射为颜色（范围 -1 到 1）"""
        if not stresses:
            return []
        max_abs = max(abs(s) for s in stresses)
        if max_abs == 0:
            return [0] * len(stresses)
        # 归一化到 [-1, 1]
        norm_stress = [s / max_abs for s in stresses]
        return norm_stress
    
    def save_plot(self, filename, format='html'):
        """保存可视化结果"""
        fig = self.create_3d_plot()
        if format == 'html':
            fig.write_html(filename)
        elif format == 'png':
            fig.write_image(filename, width=1200, height=800)
        else:
            raise ValueError("Unsupported format. Use 'html' or 'png'")


def export_model_json(model_id, show_displacements=False, show_stresses=False):
    """导出模型数据为JSON，包含Plotly所需格式"""
    import json
    import os
    from db import get_db_connection
    from truss_analyzer import analyze_with_anastruct
    
    # 从数据库获取模型信息
    conn = get_db_connection()
    model = conn.execute('SELECT * FROM models WHERE id = ?', (model_id,)).fetchone()
    conn.close()
    
    if not model:
        return {"error": "Model not found"}
    
    # 解析参数
    parameters = {}
    if model['parameters']:
        try:
            parameters = json.loads(model['parameters'])
        except:
            pass
    
    # 从数据库获取存储的模型数据
    model_data = {}
    if model['file_path']:
        try:
            from main import UPLOAD_FOLDER
            with open(os.path.join(UPLOAD_FOLDER, model['file_path']), 'r') as f:
                model_data = json.load(f)
        except Exception as e:
            print(f"Error loading model data: {str(e)}")
    
    # 如果没有存储的模型数据，使用参数重新生成（修复：使用正确的节点和单元生成逻辑）
    if not model_data.get('nodes') or not model_data.get('elements'):
        truss_type = parameters.get('truss_type', 'triangle')
        length = float(parameters.get('span', 5.0))
        height = float(parameters.get('height', 2.0))
        node_spacing = float(parameters.get('node_spacing', 1.0))
        
        n_segments = max(2, int(length / node_spacing))
        segment_length = length / n_segments
        
        nodes = []
        # 下弦节点
        for i in range(n_segments + 1):
            nodes.append([i * segment_length, 0, 0])
        # 上弦节点
        top_start = len(nodes)
        for i in range(n_segments + 1):
            nodes.append([i * segment_length, -height, 0])
        
        elements = []
        # 下弦单元
        for i in range(n_segments):
            elements.append([i, i+1])
        # 上弦单元
        for i in range(n_segments):
            elements.append([top_start + i, top_start + i + 1])
        # 竖杆
        for i in range(n_segments + 1):
            elements.append([i, top_start + i])
        
        model_data = {
            "nodes": nodes,
            "elements": elements
        }
    
    # 构建分析所需数据
    truss_data = {
        "nodes": model_data["nodes"],
        "elements": model_data["elements"],
        "section_type": parameters.get('section_type', 'HN150×75'),
        "boundary_condition": parameters.get('boundary_condition', 'simply_supported')
    }
    # 如果存在载荷信息，也可以加入
    analysis_result = analyze_with_anastruct(truss_data)
    
    # 生成位移数据（格式兼容可视化）
    displacements = []
    for i in range(len(model_data["nodes"])):
        displacements.append({'dx': 0, 'dy': 0, 'dz': 0})
    
    if analysis_result.get('status') == 'completed':
        for node_id_str, disp_dict in analysis_result.get('displacements', {}).items():
            try:
                idx = int(node_id_str) - 1  # 假设节点编号从1开始
                if 0 <= idx < len(displacements):
                    displacements[idx] = {
                        'dx': disp_dict.get('dx', 0),
                        'dy': disp_dict.get('dy', 0),
                        'dz': disp_dict.get('dz', 0)
                    }
            except (ValueError, TypeError):
                continue
    
    # 生成应力数据（基于单元，可视化中可能需要基于节点，此处先保留单元应力）
    stresses = []  # 单元应力列表
    element_forces = analysis_result.get('element_forces', [])
    for elem in element_forces:
        stresses.append(elem.get('stress', 0))
    
    # 构建最终输出
    result = {
        "nodes": model_data["nodes"],
        "elements": model_data["elements"],
        "metadata": {
            "truss_type": parameters.get('truss_type', 'triangle'),
            "span": parameters.get('span', 5.0),
            "height": parameters.get('height', 2.0),
            "section_type": parameters.get('section_type', ''),
            "max_displacement": analysis_result.get('max_displacement', 0),
            "max_stress": analysis_result.get('max_stress', 0),
            "safety_factor": analysis_result.get('safety_factor', 1.5)
        }
    }
    
    if show_displacements:
        result['displacements'] = displacements
    if show_stresses:
        # 注意：stresses 长度等于单元数，若要在节点上显示，需做单元->节点平均，此处简单传递
        result['stresses'] = stresses
    
    return result