"""
vCenter vMon Service Checker - Flask Web 应用
用于分析和展示 vCenter 服务状态和依赖关系的 Web 界面
"""

from flask import Flask, render_template, request, redirect, url_for, jsonify, send_from_directory
import yaml
import os
from datetime import datetime
from werkzeug.utils import secure_filename
import subprocess
import sys
import stat
import requests
import tempfile
import traceback
from jinja2 import TemplateNotFound
from werkzeug.exceptions import NotFound

# 首先创建 Flask 应用
app = Flask(__name__)

# 获取当前文件所在目录的绝对路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOADS_FOLDER = os.path.join(BASE_DIR, 'uploads')
OUTPUT_FOLDER = os.path.join(BASE_DIR, 'output')

# 确保目录存在
os.makedirs(UPLOADS_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# 添加安全配置
app.config.update(
    MAX_CONTENT_LENGTH=50 * 1024 * 1024,  # 增加到 50MB
    UPLOAD_FOLDER=UPLOADS_FOLDER,
    SECRET_KEY=os.urandom(24)
)

ALLOWED_EXTENSIONS = {'log'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def check_directories():
    """检查并创建必要的目录
    
    功能：
    - 检查上传和输出目录是否存在
    - 创建缺失的目录
    - 设置适当的目录权限
    - 确保目录可写
    
    权限设置：
    - 默认权限：755 (rwxr-xr-x)
    - 如果需要，升级到 777 以支持容器环境
    """
    directories = [UPLOADS_FOLDER, OUTPUT_FOLDER]
    for directory in directories:
        try:
            # 确保目录存在
            os.makedirs(directory, exist_ok=True)
            # 设置目录权限为 755 (rwxr-xr-x)
            os.chmod(directory, 0o755)
            # 确保目录可写
            if not os.access(directory, os.W_OK):
                print(f"Warning: Directory not writable: {directory}", file=sys.stderr)
                # 在容器环境中可能需要更宽松的权限
                os.chmod(directory, 0o777)
        except Exception as e:
            print(f"Error creating/checking directory {directory}: {e}", file=sys.stderr)
            sys.exit(1)

def check_directory_permissions():
    """检查目录权限
    
    检查以下目录的权限：
    - uploads: 文件上传目录
    - output: 分析结果输出目录
    - configs: 配置文件目录
    - utils: 工具脚本目录
    - templates: 模板文件目录
    
    Returns:
        list: 权限问题列表，如果没有问题则为空
    """
    directories = {
        'uploads': UPLOADS_FOLDER,
        'output': OUTPUT_FOLDER,
        'configs': os.path.join(BASE_DIR, 'configs'),
        'utils': os.path.join(BASE_DIR, 'utils'),
        'templates': os.path.join(BASE_DIR, 'templates')
    }
    
    issues = []
    for name, path in directories.items():
        if not os.path.exists(path):
            issues.append(f"{name} directory does not exist: {path}")
            continue
            
        # 检查目录权限
        try:
            mode = os.stat(path).st_mode
            if not mode & stat.S_IRWXU:  # 检查用户读写执行权限
                issues.append(f"{name} directory lacks proper permissions: {path}")
        except Exception as e:
            issues.append(f"Error checking {name} directory: {str(e)}")
    
    return issues

# 检查权限
permission_issues = check_directory_permissions()
if permission_issues:
    print("Permission issues found:", file=sys.stderr)
    for issue in permission_issues:
        print(f"  - {issue}", file=sys.stderr)

class ServiceConfig:
    """服务配置管理类
    
    负责加载和处理服务配置信息，包括：
    - 加载服务配置文件
    - 处理服务状态数据
    - 计算服务依赖关系
    - 生成服务矩阵数据
    """
    
    def __init__(self, config_path=None, vcenter_version='8'):
        """初始化服务配置
        
        Args:
            config_path: 配置文件路径，如果为 None 则根据版本自动选择
            vcenter_version: vCenter 版本 ('7' 或 '8')
        """
        if config_path is None:
            # 根据版本选择正确的配置文件
            config_file = 'vcsa8u3-all-services.yaml' if vcenter_version == '8' else 'vcsa7u3-all-services.yaml'
            config_path = os.path.join(BASE_DIR, 'configs', config_file)
        print(f"Using config file: {config_path}")  # 添加这行调试信息
        self.config_path = config_path
        self.config_data = None
        self.status_data = None
        self.dependencies = None
        self.reverse_dependencies = None
        self.vcenter_version = vcenter_version
    
    def load_configs(self):
        """加载配置和状态数据
        
        - 加载服务配置文件
        - 加载最新的分析结果
        - 验证 system-control 服务
        - 计算依赖关系
        """
        try:
            print(f"\nLoading config from: {self.config_path}")
            print(f"vCenter version: {self.vcenter_version}")
            
            # 读取服务配置
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
                print("Config data loaded successfully")
                print(f"Found {len(self.config_data.get('services', {}))} services in config")
            
            # 验证 system-control 服务的 ID
            print("\nVerifying system-control services:")
            for service_name, info in self.config_data['services'].items():
                if info.get('type') == 'system-control':
                    service_id = info.get('id')
                    print(f"Service: {service_name}, ID: {service_id}, Type: system-control")
                    # 对于 vCenter 7，验证高 ID 服务
                    if self.vcenter_version == '7' and service_id > 50:
                        print(f"Warning: Found high ID ({service_id}) for service {service_name}")
            
            # 获取最新的分析结果文件
            analysis_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('-vmon-analysis.yaml')]
            if not analysis_files:
                raise FileNotFoundError("No analysis files found")
            
            latest_file = sorted(analysis_files)[-1]
            print(f"\nLatest analysis file: {latest_file}")
            
            # 读取服务状态
            status_file = os.path.join(OUTPUT_FOLDER, latest_file)
            print(f"Loading status from: {status_file}")
            with open(status_file, 'r') as f:
                self.status_data = yaml.safe_load(f)
                print(f"Status data loaded successfully with {len(self.status_data.get('services', {}))} services")
            
            # 打印状态数据中的服务
            print("\nServices in status data:")
            for service_name in self.status_data.get('services', {}):
                print(f"Status found for service: {service_name}")
            
            self._calculate_dependencies()
            
        except Exception as e:
            print(f"Error loading configs: {str(e)}")
            traceback.print_exc()
            raise
    
    def _calculate_dependencies(self):
        """计算服务间的依赖关系
        
        建立正向和反向依赖关系映射：
        - dependencies: 服务依赖的其他服务
        - reverse_dependencies: 依赖该服务的其他服务
        """
        self.dependencies = {}
        self.reverse_dependencies = {}
        
        for service_name, info in self.config_data['services'].items():
            # 获取该服务依赖的其他服务
            dp_services = info.get('dp_service', [])
            self.dependencies[service_name] = dp_services
            
            # 建立反向依赖关系
            for dp in dp_services:
                if dp not in self.reverse_dependencies:
                    self.reverse_dependencies[dp] = []
                self.reverse_dependencies[dp].append(service_name)
    
    def get_service_color(self, service_status, service_info):
        """确定服务的显示颜色"""
        try:
            service_type = service_info.get('type', '')
            
            if service_type == 'system-control':
                return 'blue'
            
            if service_type == 'vmon-control':
                status = service_status.get('service_status', '')
                if status == 'running':
                    return 'green'
                elif status == 'failed to start':
                    return 'red'
                elif status == 'stopped':
                    return 'yellow'
            
            return 'gray'
        except Exception as e:
            print(f"Error getting color for service: {str(e)}")
            return 'gray'
    
    def get_service_color_vcenter7(self, service_status, service_info):
        """确定 vCenter 7 服务的显示颜色"""
        try:
            service_type = service_info.get('type', '')
            
            if service_type == 'system-control':
                return 'blue'
            
            if service_type == 'vmon-control':
                status = service_status.get('service_status', '')
                if status == 'running':
                    return 'green'
                elif status == 'failed to start':
                    return 'red'
                elif status == 'stopped':
                    return 'yellow'
            
            return 'gray'
        except Exception as e:
            print(f"Error getting color for vCenter 7 service: {str(e)}")
            return 'gray'
    
    def get_matrix_data(self):
        """生成矩阵数据
        
        生成用于 Web 界面显示的服务矩阵数据，包括：
        - 服务位置排列
        - 服务状态颜色
        - 依赖关系信息
        
        Returns:
            list: 二维矩阵数据
        """
        all_services = []
        system_control_services = []  # 专门存储 system-control 类型的服务
        other_services = []  # 存储其他类型的服务
        
        # 首先分类所有服务
        for name, info in self.config_data['services'].items():
            service_id = info.get('id')
            if service_id is not None:
                if info.get('type') == 'system-control':
                    system_control_services.append((service_id, name, info))
                else:
                    other_services.append((service_id, name, info))
        
        # 按 ID 排序
        system_control_services.sort()
        other_services.sort()
        
        # 获取所有服务 ID 并打印详细信息
        print("\nSystem Control Services:")
        for sid, name, _ in system_control_services:
            print(f"ID: {sid}, Name: {name}")
        
        # 根据 vCenter 版本调整矩阵的行数
        if self.vcenter_version == '7':
            rows = 6  # vCenter 7 使用 6 行
        else:
            rows = 7  # vCenter 8 保持 7 行
        
        cols = 10  # 列数保持不变
        print(f"\nMatrix dimensions: {rows}x{cols}")
        
        # 创建矩阵
        matrix = []
        
        # 合并所有服务，确保 system-control 服务在其实际 ID 位置
        all_services = system_control_services + other_services
        
        # 使用实际的服务 ID 而不是位置计数
        for row in range(rows):
            matrix_row = []
            for col in range(cols):
                position = row * cols + col + 1
                
                # 查找该位置是否有对应 ID 的服务
                service_info = None
                for sid, name, info in all_services:
                    if sid == position:
                        service_info = (sid, name, info)
                        break
                
                if service_info:
                    cell_data = self._get_cell_data(service_info[0], all_services)
                else:
                    cell_data = {
                        'name': '',
                        'color': 'white',
                        'id': position,
                        'type': 'empty',
                        'status': 'none',
                        'dp_services': [],
                        'rdp_services': [],
                        'prestart_logs': [],
                        'service_logs': [],
                        'config_logs': []
                    }
                
                matrix_row.append(cell_data)
            matrix.append(matrix_row)
        
        return matrix
    
    def _get_cell_data(self, current_id, all_services):
        """获取单个单元格的数据"""
        # 添加调试信息
        print(f"Getting cell data for ID: {current_id}")
        print(f"Available service IDs: {[sid for sid, _, _ in all_services]}")
        
        service_info = None
        for sid, name, info in all_services:
            if sid == current_id:
                service_info = (name, info)
                print(f"Found service for ID {current_id}: {name}")
                break
        
        if service_info:
            service_name, info = service_info
            status_info = self.status_data['services'].get(service_name, {})
            
            # 根据 vCenter 版本调整颜色和状态
            if self.vcenter_version == '7':
                # vCenter 7 的状态处理逻辑
                cell_data = {
                    'name': service_name,
                    'color': self.get_service_color_vcenter7(status_info, info),
                    'id': current_id,
                    'type': info.get('type', 'unknown'),
                    'status': status_info.get('service_status', 'unknown'),
                    'dp_services': self.dependencies.get(service_name, []),
                    'rdp_services': self.reverse_dependencies.get(service_name, []),
                    'prestart_logs': status_info.get('prestart_logs', []),
                    'service_logs': status_info.get('service_logs', []),
                    'config_logs': info.get('log', [])
                }
                print(f"Created cell data for service {service_name}: {cell_data}")
                return cell_data
            else:
                # vCenter 8 的状态处理逻辑
                return {
                    'name': service_name,
                    'color': self.get_service_color(status_info, info),
                    'id': current_id,
                    'type': info.get('type', 'unknown'),
                    'status': status_info.get('service_status', 'unknown'),
                    'dp_services': self.dependencies.get(service_name, []),
                    'rdp_services': self.reverse_dependencies.get(service_name, []),
                    'prestart_logs': status_info.get('prestart_logs', []),
                    'service_logs': status_info.get('service_logs', []),
                    'config_logs': info.get('log', [])
                }
        else:
            print(f"No service found for ID {current_id}")
            return {
                'name': '',
                'color': 'white',
                'id': current_id,
                'type': 'empty',
                'status': 'none',
                'dp_services': [],
                'rdp_services': [],
                'prestart_logs': [],
                'service_logs': [],
                'config_logs': []
            }

# 添加CORS支持
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE')
    return response

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    """处理文件上传
    
    - GET: 显示上传页面
    - POST: 处理文件上传并分析
    """
    try:
        print("Upload route accessed")
        if request.method == 'POST':
            if 'file' not in request.files:
                return 'No file part', 400
            
            file = request.files['file']
            vcenter_version = request.form.get('vcenter_version')
            
            # 检查是否选择了版本
            if not vcenter_version:
                return 'Please select vCenter version', 400
            
            if file.filename == '':
                return 'No selected file', 400
            
            if file and allowed_file(file.filename):
                try:
                    # 添加时间戳到文件名
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    original_filename = secure_filename(file.filename)
                    filename = f"{timestamp}_{original_filename}"
                    
                    # 保存文件
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(filepath)
                    print(f"File saved to: {filepath}")
                    
                    # 根据版本选择配置文件
                    config_file = 'vcsa8u3-all-services.yaml' if vcenter_version == '8' else 'vcsa7u3-all-services.yaml'
                    config_path = os.path.join(BASE_DIR, 'configs', config_file)
                    
                    # 执行分析脚本时传入版本信息
                    script_path = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
                    result = subprocess.run(
                        ['python3', script_path, '--log-file', filepath, '--vcenter-version', vcenter_version],
                        capture_output=True,
                        text=True,
                        check=False
                    )
                    print("Analysis output:", result.stdout)
                    print("Analysis error output:", result.stderr)  # 打印错误输出
                    
                    if result.returncode != 0:
                        return f'Error processing log file: {result.stderr}', 500
                    
                    # 检查是否生成了分析文件
                    analysis_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('-vmon-analysis.yaml')]
                    if not analysis_files:
                        return 'Analysis completed but no output file generated', 500
                    
                    # 重定向到矩阵页面显示结果
                    return redirect(url_for('matrix', vcenter_version=vcenter_version))
                except Exception as e:
                    error_msg = f"Error processing upload: {str(e)}"
                    print(error_msg, file=sys.stderr)
                    traceback.print_exc(file=sys.stderr)
                    return error_msg, 500
            
            return 'Invalid file type', 400
        
        return render_template('upload.html')
    except Exception as e:
        error_msg = f"Error in upload route: {str(e)}"
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return error_msg, 500

@app.route('/')
def index():
    """主页路由 - 重定向到上传页面"""
    try:
        # 检查目录权限
        if not os.access(UPLOADS_FOLDER, os.W_OK):
            error_msg = f"Upload directory is not writable: {UPLOADS_FOLDER}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
            
        if not os.access(OUTPUT_FOLDER, os.W_OK):
            error_msg = f"Output directory is not writable: {OUTPUT_FOLDER}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
            
        return redirect(url_for('upload'))
    except Exception as e:
        error_msg = f"Error in index route: {str(e)}"
        print(error_msg, file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return error_msg, 500

@app.route('/matrix')
def matrix():
    """显示服务矩阵页面
    
    生成并显示服务状态矩阵，包括：
    - 服务位置和状态
    - 统计信息
    - 依赖关系
    """
    try:
        # 从请求中获取 vcenter_version 参数
        vcenter_version = request.args.get('vcenter_version')
        if not vcenter_version:
            return redirect(url_for('upload'))
        
        print(f"vCenter version received: {vcenter_version}")
        
        # 创建 ServiceConfig 实例时传递 vcenter_version
        service_config = ServiceConfig(vcenter_version=vcenter_version)
        service_config.load_configs()
        
        # 生成矩阵数据
        matrix = service_config.get_matrix_data()
        print(f"Matrix size: {len(matrix)}x{len(matrix[0])}")
        
        # 计算统计信息
        stats = {
            'system_control': 0,
            'vmon_control': 0,
            'running': 0,
            'failed': 0,
            'stopped': 0,
            'profile': service_config.status_data.get('profile', 'Unknown')
        }
        
        # 遍历所有服务统计数量
        for service_name, info in service_config.config_data['services'].items():
            if info.get('type') == 'system-control':
                stats['system_control'] += 1
            elif info.get('type') == 'vmon-control':
                stats['vmon_control'] += 1
            
            # 获取服务状态
            status = service_config.status_data['services'].get(service_name, {}).get('service_status', '')
            if status == 'running':
                stats['running'] += 1
            elif status == 'failed to start':
                stats['failed'] += 1
            elif status == 'stopped':
                stats['stopped'] += 1
        
        last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 添加更多调试信息
        print("Template context:", {
            'matrix': matrix,
            'last_updated': last_updated,
            'stats': stats
        })
        
        response = render_template('index.html', 
                                 matrix=matrix,
                                 last_updated=last_updated,
                                 stats=stats,
                                 vcenter_version=vcenter_version)
        print("Template rendered successfully")
        return response
        
    except Exception as e:
        print(f"Error in matrix route: {str(e)}")
        traceback.print_exc()
        return f"Server error: {str(e)}", 500

@app.route('/test')
def test():
    """测试路由"""
    try:
        # 检查目录
        dirs = {
            'base': str(BASE_DIR),
            'uploads': str(UPLOADS_FOLDER),
            'output': str(OUTPUT_FOLDER),
            'configs': str(os.path.join(BASE_DIR, 'configs'))
        }
        
        # 检查文件
        config_file = os.path.join(BASE_DIR, 'configs', 'vcsa8u3-all-services-20250120.yaml')
        script_file = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
        
        files = {
            'config': {
                'path': str(config_file),
                'exists': os.path.exists(config_file)
            },
            'script': {
                'path': str(script_file),
                'exists': os.path.exists(script_file)
            }
        }
        
        # 检查输出目录内容
        output_files = os.listdir(OUTPUT_FOLDER) if os.path.exists(OUTPUT_FOLDER) else []
        
        result = {
            'directories': dirs,
            'files': files,
            'output_files': output_files,
            'directory_exists': {
                'uploads': os.path.exists(UPLOADS_FOLDER),
                'output': os.path.exists(OUTPUT_FOLDER),
                'configs': os.path.exists(os.path.join(BASE_DIR, 'configs'))
            }
        }
        
        response = jsonify(result)
        return response
    except Exception as e:
        print(f"Error in test route: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 添加静态文件路由
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# 添加 favicon 路由
@app.route('/favicon.ico')
def favicon():
    try:
        return send_from_directory('static', 'favicon.ico', mimetype='image/vnd.microsoft.icon')
    except (FileNotFoundError, NotFound):  # 添加 NotFound 异常的处理
        # 如果找不到 favicon.ico，直接返回 204 No Content，不使用模板
        return '', 204
    except Exception as e:
        print(f"Error serving favicon: {str(e)}")
        return '', 204  # 对于任何错误都返回 204

# 修改日志文件路由
@app.route('/uploads/<path:filename>')  # 改为 uploads
def serve_uploads(filename):  # 改名为更合适的名称
    return send_from_directory(UPLOADS_FOLDER, filename)

# 添加输出文件路由
@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# 添加一个简单的错误处理器
@app.errorhandler(404)
def not_found_error(error):
    print(f"404 Error: {request.url}")
    try:
        return render_template('404.html'), 404
    except TemplateNotFound:
        # 如果模板不存在，返回简单的错误信息
        return "404 Not Found", 404

@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {str(e)}")
    traceback.print_exc()
    return f"Server error: {str(e)}", 500

# 检查并创建必要的目录
check_directories()

@app.route('/upload_url', methods=['POST'])
def upload_url():
    """处理 URL 上传请求
    
    功能：
    - 接收 vmon.log 文件的 URL
    - 下载日志文件
    - 根据选择的 vCenter 版本进行分析
    - 生成分析报告
    
    Returns:
        JSON 响应，包含处理结果和重定向 URL
    """
    try:
        data = request.get_json()
        if not data or 'file_url' not in data:
            return jsonify({'error': 'No URL provided'}), 400
        
        url = data['file_url']
        vcenter_version = data.get('vcenter_version')
        
        # 检查是否选择了版本
        if not vcenter_version:
            return jsonify({'error': 'Please select vCenter version'}), 400
            
        # 下载文件
        response = requests.get(url, stream=True)
        if not response.ok:
            return jsonify({'error': 'Failed to download file'}), 400
            
        # 创建临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_downloaded.log"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 保存文件
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        # 执行分析脚本
        script_path = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
        result = subprocess.run(
            ['python3', script_path, '--log-file', filepath, '--vcenter-version', vcenter_version],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            return jsonify({'error': f'Error processing log file: {result.stderr}'}), 500
        
        # 返回成功响应，包含重定向 URL
        return jsonify({
            'success': True,
            'redirect_url': url_for('matrix', vcenter_version=vcenter_version)
        })
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Error downloading file: {str(e)}'}), 400
    except Exception as e:
        print(f"Error processing URL upload: {str(e)}")
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

if __name__ == '__main__':
    # 本地开发时监听 127.0.0.1
    host = '127.0.0.1'
    port = 5000
    
    # 如果在容器环境中运行，则监听所有接口
    if os.environ.get('DOCKER_ENV') == 'true':
        host = '0.0.0.0'
    
    app.run(host=host, port=port, debug=False)