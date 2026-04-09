import os

# 获取项目根目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 文件上传相关配置
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
APDL_SCRIPTS_DIR = os.path.join(BASE_DIR, 'apdl_scripts')
ANALYSIS_RESULTS_DIR = os.path.join(BASE_DIR, 'analysis_results')

# 数据库配置
APP_DB_PATH = os.path.join(BASE_DIR, 'app.db')

# 支持的文件扩展名
ALLOWED_EXTENSIONS = {'obj', 'fbx', 'gltf', 'glb', 'stl'}

# ANSYS配置
ANSYS_EXECUTABLE = r"C:\Program Files\ANSYS Inc\v222\ansys\bin\winx64\ANSYS222.exe"
# 尝试其他常见的ANSYS版本
ANSYS_VERSIONS = ["v222", "v212", "v202", "v195"]

# Flask配置
SECRET_KEY = 'your-secret-key-here-change-in-production'
SESSION_TYPE = 'filesystem'
SESSION_PERMANENT = True
PERMANENT_SESSION_LIFETIME = 3600 * 24 * 7  # 7天

# 应用配置
APP_NAME = "建筑与受力分析系统"
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB