import os
import json
import subprocess
import tempfile
from typing import Dict, List, Tuple, Optional, Union
from config import APDL_SCRIPTS_DIR, ANSYS_EXECUTABLE, ANSYS_VERSIONS

# 常用H型钢规格（截面尺寸）
H_SECTIONS = {
    # HN系列（窄翼缘H型钢）
    "HN100×50": {"area": 14.9, "iy": 198.0, "iz": 8.3, "weight": 11.7},
    "HN100×100": {"area": 21.9, "iy": 310.0, "iz": 31.0, "weight": 17.2},
    "HN125×60": {"area": 21.3, "iy": 443.0, "iz": 12.4, "weight": 16.7},
    "HN150×75": {"area": 27.4, "iy": 838.0, "iz": 18.7, "weight": 21.5},
    "HN175×90": {"area": 35.2, "iy": 1510.0, "iz": 29.0, "weight": 27.7},
    "HN200×100": {"area": 39.6, "iy": 1880.0, "iz": 35.5, "weight": 31.1},
    "HN200×150": {"area": 50.5, "iy": 2370.0, "iz": 88.2, "weight": 39.7},
    "HN250×125": {"area": 54.5, "iy": 3950.0, "iz": 62.9, "weight": 42.7},
    "HN300×150": {"area": 71.1, "iy": 7350.0, "iz": 104.0, "weight": 55.8},
    "HN350×175": {"area": 84.9, "iy": 12200.0, "iz": 149.0, "weight": 66.7},
    "HN400×150": {"area": 83.3, "iy": 15600.0, "iz": 104.0, "weight": 65.5},
    "HN400×200": {"area": 106.0, "iy": 17500.0, "iz": 223.0, "weight": 83.0},
    "HN450×150": {"area": 94.7, "iy": 21000.0, "iz": 111.0, "weight": 74.3},
    "HN450×200": {"area": 118.0, "iy": 23700.0, "iz": 239.0, "weight": 92.9},
    "HN500×150": {"area": 101.0, "iy": 26200.0, "iz": 106.0, "weight": 79.5},
    "HN500×200": {"area": 129.0, "iy": 31000.0, "iz": 255.0, "weight": 101.0},
    "HN500×250": {"area": 151.0, "iy": 35200.0, "iz": 402.0, "weight": 119.0},
    "HN600×200": {"area": 147.0, "iy": 46400.0, "iz": 272.0, "weight": 115.0},
    "HN600×250": {"area": 173.0, "iy": 52900.0, "iz": 436.0, "weight": 136.0},
    "HN700×300": {"area": 222.0, "iy": 88500.0, "iz": 657.0, "weight": 174.0},
    "HN800×300": {"area": 243.0, "iy": 127000.0, "iz": 678.0, "weight": 191.0},
    "HN900×300": {"area": 267.0, "iy": 172000.0, "iz": 695.0, "weight": 210.0},
    "HN1000×300": {"area": 289.0, "iy": 225000.0, "iz": 709.0, "weight": 227.0},
    
    # HW系列（宽翼缘H型钢）
    "HW100×100": {"area": 21.9, "iy": 310.0, "iz": 31.0, "weight": 17.2},
    "HW125×125": {"area": 31.2, "iy": 591.0, "iz": 59.0, "weight": 24.5},
    "HW150×150": {"area": 42.4, "iy": 1080.0, "iz": 108.0, "weight": 33.3},
    "HW175×175": {"area": 54.5, "iy": 1660.0, "iz": 165.0, "weight": 42.8},
    "HW200×200": {"area": 67.5, "iy": 2500.0, "iz": 250.0, "weight": 53.1},
    "HW250×250": {"area": 92.1, "iy": 5280.0, "iz": 524.0, "weight": 72.4},
    "HW300×300": {"area": 121.0, "iy": 9400.0, "iz": 940.0, "weight": 95.0},
    "HW350×350": {"area": 178.0, "iy": 17000.0, "iz": 1730.0, "weight": 140.0},
    "HW400×400": {"area": 219.0, "iy": 26600.0, "iz": 2670.0, "weight": 172.0},
    "HW450×450": {"area": 337.0, "iy": 47200.0, "iz": 4740.0, "weight": 265.0},
    "HW500×500": {"area": 411.0, "iy": 69200.0, "iz": 6930.0, "weight": 323.0},
    
    # HM系列（中翼缘H型钢）
    "HM148×100": {"area": 31.5, "iy": 811.0, "iz": 49.1, "weight": 24.7},
    "HM194×150": {"area": 56.7, "iy": 1880.0, "iz": 116.0, "weight": 44.5},
    "HM244×175": {"area": 72.4, "iy": 3450.0, "iz": 183.0, "weight": 56.9},
    "HM294×200": {"area": 87.8, "iy": 5920.0, "iz": 245.0, "weight": 69.0},
    "HM340×250": {"area": 119.0, "iy": 11400.0, "iz": 428.0, "weight": 93.6},
    "HM390×300": {"area": 156.0, "iy": 18900.0, "iz": 674.0, "weight": 122.0},
    "HM440×300": {"area": 174.0, "iy": 25900.0, "iz": 690.0, "weight": 137.0},
    "HM482×300": {"area": 189.0, "iy": 32700.0, "iz": 692.0, "weight": 149.0},
    "HM582×300": {"area": 215.0, "iy": 51400.0, "iz": 702.0, "weight": 169.0},
    "HM588×300": {"area": 219.0, "iy": 54900.0, "iz": 693.0, "weight": 172.0}
}

# 默认材料属性（Q235钢）
DEFAULT_MATERIAL = {
    "youngs_modulus": 206000.0,  # MPa
    "poisson_ratio": 0.3,
    "density": 7850.0  # kg/m³
}

class TrussTemplate:
    """
    平面桁架模板基类
    """
    def __init__(self, span: float, height: float, section_type: str, elastic_modulus: float = None, node_spacing: float = None):
        """
        初始化桁架模板
        
        Args:
            span: 跨度 (m)
            height: 高度 (m)
            section_type: 截面类型 (H型钢规格)
            elastic_modulus: 弹性模量 (MPa)，可选
            node_spacing: 节点间距 (m)，可选，默认根据跨度自动计算
        """
        self.span = span
        self.height = height
        # 如果未提供节点间距，根据跨度自动计算合理值
        self.node_spacing = node_spacing if node_spacing is not None else max(0.5, min(span / 5, 2.0))
        self.section_type = section_type
        # 如果提供了弹性模量，则更新默认材料属性
        self.elastic_modulus = elastic_modulus if elastic_modulus is not None else DEFAULT_MATERIAL['youngs_modulus']
        # 保存桁架类型
        self.truss_type = self.__class__.__name__.replace('Truss', '').lower()
        
        # 验证参数
        self._validate_parameters()
        
        # 存储节点和单元信息
        self.nodes = []  # [(node_id, x, y, z), ...]
        self.elements = []  # [(element_id, node1, node2), ...]
        
        # 创建节点和单元
        self._generate_nodes()
        self._generate_elements()
    
    def get_model_data(self) -> dict:
        """
        获取模型数据，用于前端可视化
        
        Returns:
            包含nodes和elements的字典
        """
        # 转换节点格式
        nodes = []
        for node_id, x, y, z in self.nodes:
            nodes.append({
                'id': node_id,
                'x': x,
                'y': y,
                'z': z
            })
        
        # 转换单元格式
        elements = []
        for element_id, node1, node2 in self.elements:
            elements.append({
                'id': element_id,
                'node1': node1,
                'node2': node2
            })
        
        return {
            'nodes': nodes,
            'elements': elements,
            'span': self.span,
            'height': self.height,
            'node_spacing': self.node_spacing,
            'section_type': self.section_type
        }
    
    def _validate_parameters(self) -> None:
        """
        验证参数合法性
        """
        # 跨度验证
        if not (0.5 <= self.span <= 100.0):
            raise ValueError(f"跨度必须在0.5m-100m之间，当前值: {self.span}m")
        
        # 高度验证
        if not (0.1 <= self.height <= 50.0):
            raise ValueError(f"高度必须在0.1m-50m之间，当前值: {self.height}m")
        
        # 节点间距验证
        if not (0.1 <= self.node_spacing <= 5.0):
            raise ValueError(f"节点间距必须在0.1m-5m之间，当前值: {self.node_spacing}m")
        
        # 截面类型验证
        if self.section_type not in H_SECTIONS:
            raise ValueError(f"不支持的截面类型: {self.section_type}，支持的类型: {list(H_SECTIONS.keys())}")
        
        # 节点间距合理性验证
        if self.node_spacing > self.span / 2:
            raise ValueError(f"节点间距过大，建议≤跨度/2以保证稳定性，当前节点间距: {self.node_spacing}m, 跨度/2: {self.span/2}m")
        
        # 移除 span <= height 的强制错误，改为警告
        if self.span <= self.height:
            print(f"警告：跨度({self.span}m)不大于高度({self.height}m)，结构可能不稳定")
    
    def _generate_nodes(self) -> None:
        """
        生成节点坐标，由子类实现
        """
        raise NotImplementedError("子类必须实现_generate_nodes方法")
    
    def _generate_elements(self) -> None:
        """
        生成单元连接，由子类实现
        """
        raise NotImplementedError("子类必须实现_generate_elements方法")
    
    def generate_apdl_script(self, filename, boundary_condition='simply_supported'):
        """生成APDL脚本"""
        with open(filename, 'w') as f:
            f.write(f"! APDL Script for {self.truss_type} Truss\n")
            f.write(f"! Span: {self.span}m, Height: {self.height}m\n")
            f.write(f"! Node spacing: {self.node_spacing}m\n")
            f.write(f"! Section: {self.section_type}\n\n")
            
            # 添加节点
            for i, node in enumerate(self.nodes):
                f.write(f"N,{i+1},{node[1]},{node[2]}\n")
            
            # 添加单元
            for i, elem in enumerate(self.elements):
                f.write(f"E,{i+1},{elem[1]},{elem[2]}\n")
            
            # 添加边界条件
            if boundary_condition == 'simply_supported':
                f.write("\nD,1,UX,0\n")
                f.write("D,1,UY,0\n")
                f.write(f"D,{len(self.nodes)},UY,0\n")
            elif boundary_condition == 'fixed':
                f.write("\nD,1,UX,0\n")
                f.write("D,1,UY,0\n")
                f.write("D,1,UZ,0\n")
                f.write(f"D,{len(self.nodes)},UX,0\n")
                f.write(f"D,{len(self.nodes)},UY,0\n")
                f.write(f"D,{len(self.nodes)},UZ,0\n")
            
            # 添加载荷
            f.write("\nF,100,FY,-10000\n")
            
            # 求解
            f.write("\nSOLVE\n")
        
        return True
    
    def validate_script(self, script_path):
        """验证生成的APDL脚本文件是否存在且非空"""
        if not os.path.exists(script_path):
            return False, f"脚本文件不存在: {script_path}"
        if os.path.getsize(script_path) == 0:
            return False, "脚本文件为空"
        return True, "脚本有效"


class TriangleTruss(TrussTemplate):
    """
    三角形桁架模板（下弦均匀节点，上弦一个顶点）
    """
    def _generate_nodes(self):
        """生成三角形桁架节点：下弦均匀节点 + 一个顶点"""
        num_bottom = int(self.span / self.node_spacing) + 1
        # 下弦节点
        for i in range(num_bottom):
            x = i * self.node_spacing
            self.nodes.append((i+1, x, 0.0, 0.0))
        # 顶点（位于跨中）
        self.nodes.append((num_bottom+1, self.span/2, self.height, 0.0))
    
    def _generate_elements(self):
        """生成三角形桁架单元：下弦杆 + 腹杆（顶点连接每个下弦节点）"""
        num_bottom = int(self.span / self.node_spacing) + 1
        elem_id = 1
        # 下弦杆
        for i in range(num_bottom - 1):
            self.elements.append((elem_id, i+1, i+2))
            elem_id += 1
        # 腹杆（顶点与每个下弦节点相连）
        for i in range(num_bottom):
            self.elements.append((elem_id, i+1, num_bottom+1))
            elem_id += 1


class TrapezoidTruss(TrussTemplate):
    """
    梯形桁架模板（下弦均匀节点，上弦等间距且短于下弦）
    """
    def __init__(self, span: float, height: float, section_type: str, elastic_modulus: float = None, 
                 node_spacing: float = None, top_span: float = None):
        """
        初始化梯形桁架模板
        
        Args:
            span: 下弦跨度 (m)
            height: 高度 (m)
            section_type: 截面类型
            elastic_modulus: 弹性模量 (MPa)
            node_spacing: 节点间距 (m)
            top_span: 上弦跨度 (m)，默认下跨度的80%
        """
        self.top_span = top_span if top_span is not None else span * 0.8
        # 验证上弦跨度必须小于下弦跨度
        if self.top_span >= span:
            raise ValueError(f"上弦跨度必须小于下弦跨度，当前上弦跨度: {self.top_span}m, 下弦跨度: {span}m")
        super().__init__(span, height, section_type, elastic_modulus, node_spacing)
    
    def _generate_nodes(self):
        """生成梯形桁架节点：下弦均匀节点，上弦等间距节点"""
        num_nodes = int(self.span / self.node_spacing) + 1
        # 下弦节点
        for i in range(num_nodes):
            x = i * self.node_spacing
            self.nodes.append((i+1, x, 0.0, 0.0))
        # 上弦节点（等间距，范围从 indent 到 indent+top_span）
        indent = (self.span - self.top_span) / 2
        for i in range(num_nodes):
            x = indent + i * (self.top_span / (num_nodes - 1))
            self.nodes.append((num_nodes + i + 1, x, self.height, 0.0))
    
    def _generate_elements(self):
        """生成梯形桁架单元：下弦、上弦、竖杆、斜杆"""
        num_nodes = int(self.span / self.node_spacing) + 1
        elem_id = 1
        
        # 下弦杆
        for i in range(num_nodes - 1):
            self.elements.append((elem_id, i+1, i+2))
            elem_id += 1
        
        # 上弦杆
        for i in range(num_nodes - 1):
            self.elements.append((elem_id, num_nodes+1+i, num_nodes+2+i))
            elem_id += 1
        
        # 竖杆（垂直连接上下弦对应节点）
        for i in range(num_nodes):
            self.elements.append((elem_id, i+1, num_nodes+1+i))
            elem_id += 1
        
        # 斜杆（仅两端倾斜部分，此处简化：所有跨中竖杆两侧都加斜杆）
        # 更精确的做法：两端各1/4节点区域加斜杆，此处为通用性，添加交叉斜杆（可选）
        # 为避免单元过多，只添加简单的斜杆模式：连接下弦i与上弦i+1
        for i in range(num_nodes - 1):
            self.elements.append((elem_id, i+1, num_nodes+2+i))
            elem_id += 1


class ParallelTruss(TrussTemplate):
    """
    平行弦桁架实现（上下弦平行，腹杆为竖杆加斜杆）
    """
    def _generate_nodes(self) -> None:
        """
        生成平行弦桁架节点（以跨度中心对称）
        """
        node_count = int(self.span / self.node_spacing) + 1
        # 下弦节点 (y=0)
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((i + 1, x, 0.0, 0.0))
        # 上弦节点 (y=height)
        top_node_start_idx = node_count + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((top_node_start_idx + i, x, self.height, 0.0))
    
    def _generate_elements(self) -> None:
        """
        生成平行弦桁架单元：上下弦、竖杆、斜杆
        """
        node_count = int(self.span / self.node_spacing) + 1
        top_node_start_idx = node_count + 1
        elem_id = 1
        
        # 下弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, i + 1, i + 2))
            elem_id += 1
        
        # 上弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, top_node_start_idx + i, top_node_start_idx + i + 1))
            elem_id += 1
        
        # 竖杆
        for i in range(node_count):
            self.elements.append((elem_id, i + 1, top_node_start_idx + i))
            elem_id += 1
        
        # 斜杆（下弦i到上弦i+1，以及上弦i到下弦i+1）
        for i in range(node_count - 1):
            self.elements.append((elem_id, i + 1, top_node_start_idx + i + 1))
            elem_id += 1
            self.elements.append((elem_id, top_node_start_idx + i, i + 2))
            elem_id += 1


class WarrenTruss(TrussTemplate):
    """
    斜拉桁架（Warren Truss）实现（无竖杆，仅斜腹杆）
    """
    def _generate_nodes(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((i + 1, x, 0.0, 0.0))
        top_node_start_idx = node_count + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((top_node_start_idx + i, x, self.height, 0.0))
    
    def _generate_elements(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        top_node_start_idx = node_count + 1
        elem_id = 1
        
        # 下弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, i + 1, i + 2))
            elem_id += 1
        
        # 上弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, top_node_start_idx + i, top_node_start_idx + i + 1))
            elem_id += 1
        
        # 斜腹杆（形成V形或倒V形）
        for i in range(node_count - 1):
            if i % 2 == 0:  # 偶数节点：下弦i -> 上弦i+1
                self.elements.append((elem_id, i + 1, top_node_start_idx + i + 1))
            else:           # 奇数节点：上弦i -> 下弦i+1
                self.elements.append((elem_id, top_node_start_idx + i, i + 2))
            elem_id += 1


class HoweTruss(TrussTemplate):
    """
    豪式桁架（Howe Truss）实现（竖杆受压，斜杆受拉）
    """
    def _generate_nodes(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((i + 1, x, 0.0, 0.0))
        top_node_start_idx = node_count + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((top_node_start_idx + i, x, self.height, 0.0))
    
    def _generate_elements(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        top_node_start_idx = node_count + 1
        elem_id = 1
        
        # 下弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, i + 1, i + 2))
            elem_id += 1
        
        # 上弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, top_node_start_idx + i, top_node_start_idx + i + 1))
            elem_id += 1
        
        # 竖杆
        for i in range(node_count):
            self.elements.append((elem_id, i + 1, top_node_start_idx + i))
            elem_id += 1
        
        # 斜杆（从下弦节点连接到上弦节点，形成下斜腹杆）
        for i in range(node_count - 2):
            self.elements.append((elem_id, i + 1, top_node_start_idx + i + 2))
            elem_id += 1


class PrattTruss(TrussTemplate):
    """
    普拉特桁架（Pratt Truss）实现（竖杆受拉，斜杆受压）
    """
    def _generate_nodes(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((i + 1, x, 0.0, 0.0))
        top_node_start_idx = node_count + 1
        for i in range(node_count):
            x = -self.span / 2 + i * self.node_spacing
            self.nodes.append((top_node_start_idx + i, x, self.height, 0.0))
    
    def _generate_elements(self) -> None:
        node_count = int(self.span / self.node_spacing) + 1
        top_node_start_idx = node_count + 1
        elem_id = 1
        
        # 下弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, i + 1, i + 2))
            elem_id += 1
        
        # 上弦杆
        for i in range(node_count - 1):
            self.elements.append((elem_id, top_node_start_idx + i, top_node_start_idx + i + 1))
            elem_id += 1
        
        # 竖杆
        for i in range(node_count):
            self.elements.append((elem_id, i + 1, top_node_start_idx + i))
            elem_id += 1
        
        # 斜杆（从上弦节点连接到下弦节点，形成上斜腹杆）
        for i in range(node_count - 2):
            self.elements.append((elem_id, i + 3, top_node_start_idx + i))
            elem_id += 1


# 注册可用的桁架模板
TRUSS_TEMPLATES = {
    "triangle": TriangleTruss,
    "trapezoid": TrapezoidTruss,
    "parallel": ParallelTruss,
    "warren": WarrenTruss,
    "howe": HoweTruss,
    "pratt": PrattTruss
}


def create_truss_template(truss_type: str, **params) -> TrussTemplate:
    """
    创建桁架模板实例
    
    Args:
        truss_type: 桁架类型
        **params: 模板参数
        
    Returns:
        桁架模板实例
    """
    if truss_type not in TRUSS_TEMPLATES:
        raise ValueError(f"不支持的桁架类型: {truss_type}，支持的类型: {list(TRUSS_TEMPLATES.keys())}")
    
    template_class = TRUSS_TEMPLATES[truss_type]
    return template_class(**params)


def register_truss_template(truss_type: str, template_class: type) -> None:
    """
    注册新的桁架模板类型
    
    Args:
        truss_type: 桁架类型名称
        template_class: 模板类，必须继承自TrussTemplate
    """
    if not issubclass(template_class, TrussTemplate):
        raise ValueError("模板类必须继承自TrussTemplate")
    
    TRUSS_TEMPLATES[truss_type] = template_class
    print(f"已注册新的桁架模板: {truss_type}")


def get_available_sections() -> List[str]:
    """
    获取可用的截面类型列表
    """
    return list(H_SECTIONS.keys())


def get_section_properties(section_type: str) -> Dict:
    """
    获取截面属性
    
    Args:
        section_type: 截面类型
        
    Returns:
        截面属性字典
    """
    if section_type not in H_SECTIONS:
        raise ValueError(f"不支持的截面类型: {section_type}")
    
    return H_SECTIONS[section_type].copy()


if __name__ == "__main__":
    # 示例用法
    try:
        # 创建三角形桁架
        triangle_truss = create_truss_template(
            "triangle",
            span=10.0,
            height=2.0,
            node_spacing=1.0,
            section_type="HN150×75"
        )
        
        # 生成APDL脚本
        script_path = "triangle_truss_simply_supported.inp"
        triangle_truss.generate_apdl_script(script_path)
        print(f"三角形桁架APDL脚本已生成: {script_path}")
        
        # 验证脚本
        success, message = triangle_truss.validate_script(script_path)
        print(f"脚本验证: {success}")
        print(f"验证结果: {message}")
        
        # 创建梯形桁架
        trapezoid_truss = create_truss_template(
            "trapezoid",
            span=12.0,
            height=3.0,
            node_spacing=1.0,
            section_type="HN200×100"
        )
        
        # 生成APDL脚本
        script_path = "trapezoid_truss_fixed.inp"
        trapezoid_truss.generate_apdl_script(script_path, boundary_condition="fixed")
        print(f"梯形桁架APDL脚本已生成: {script_path}")
        
    except ValueError as e:
        print(f"参数错误: {e}")
    except Exception as e:
        print(f"发生错误: {e}")