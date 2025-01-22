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

def check_directory_permissions():
    """检查目录权限"""
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
    """服务配置管理类"""
    def __init__(self, config_path=None):
        if config_path is None:
            config_path = os.path.join(BASE_DIR, 'configs', 'vcsa8u3-all-services-20250120.yaml')
        self.config_path = config_path
        self.config_data = None
        self.status_data = None
        self.dependencies = None
        self.reverse_dependencies = None
    
    def load_configs(self):
        """加载配置和状态数据"""
        try:
            print(f"\nLoading config from: {self.config_path}")
            # 读取服务配置
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
                print("Config data loaded successfully")
                print(f"Found {len(self.config_data.get('services', {}))} services in config")
            
            # 获取最新的分析结果文件
            analysis_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('-vmon-analysis.yaml')]
            if not analysis_files:
                raise FileNotFoundError("No analysis files found")
            
            latest_file = sorted(analysis_files)[-1]
            print(f"Latest analysis file: {latest_file}")
            
            # 读取服务状态
            status_file = os.path.join(OUTPUT_FOLDER, latest_file)
            print(f"Loading status from: {status_file}")
            with open(status_file, 'r') as f:
                self.status_data = yaml.safe_load(f)
                print(f"Status data loaded successfully with {len(self.status_data.get('services', {}))} services")
            
            self._calculate_dependencies()
            
        except Exception as e:
            print(f"Error loading configs: {str(e)}")
            import traceback
            traceback.print_exc()
            raise
    
    def _calculate_dependencies(self):
        """计算服务间的依赖关系"""
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
    
    def get_matrix_data(self):
        """生成矩阵数据"""
        # 获取所有服务并按ID排序
        all_services = []
        for name, info in self.config_data['services'].items():
            service_id = info.get('id')
            if service_id is not None:
                all_services.append((service_id, name, info))
        all_services.sort()
        
        # 创建7x10矩阵
        matrix = []
        service_count = 0
        
        for row in range(7):
            matrix_row = []
            for col in range(10):
                service_count += 1
                cell_data = self._get_cell_data(service_count, all_services)
                matrix_row.append(cell_data)
            matrix.append(matrix_row)
        
        return matrix
    
    def _get_cell_data(self, current_id, all_services):
        """获取单个单元格的数据"""
        # 查找当前ID对应的服务
        service_info = None
        for sid, name, info in all_services:
            if sid == current_id:
                service_info = (name, info)
                break
        
        if service_info:
            service_name, info = service_info
            status_info = self.status_data['services'].get(service_name, {})
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
    """文件上传处理"""
    try:
        # 检查目录权限
        if not os.access(UPLOADS_FOLDER, os.W_OK):
            error_msg = f"Upload directory is not writable: {UPLOADS_FOLDER}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
            
        if request.method == 'POST':
            if 'file' not in request.files:
                return 'No file part', 400
            
            file = request.files['file']
            vcenter_version = request.form.get('vcenter_version', '8')  # 默认为 8.x
            
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
                    config_file = 'vcsa8u3-all-services.yaml' if vcenter_version == '8' else 'vcsa7-all-services.yaml'
                    config_path = os.path.join(BASE_DIR, 'configs', config_file)
                    
                    # 执行分析脚本时传入版本信息
                    script_path = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
                    result = subprocess.run(
                        ['python', script_path, '--log-file', filepath, '--vcenter-version', vcenter_version],
                        capture_output=True,
                        text=True,
                        check=True
                    )
                    print("Analysis output:", result.stdout)
                    
                    # 检查是否生成了分析文件
                    analysis_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('-vmon-analysis.yaml')]
                    if not analysis_files:
                        return 'Analysis completed but no output file generated', 500
                    
                    # 重定向到矩阵页面显示结果
                    return redirect(url_for('matrix'))
                except subprocess.CalledProcessError as e:
                    print(f"Error running analysis: {e.stdout}\n{e.stderr}")
                    return f'Error processing log file: {str(e)}', 500
                except Exception as e:
                    error_msg = f"Error processing upload: {str(e)}"
                    print(error_msg, file=sys.stderr)
                    import traceback
                    traceback.print_exc(file=sys.stderr)
                    return error_msg, 500
            
            return 'Invalid file type', 400
        
        return render_template('upload.html')
    except Exception as e:
        error_msg = f"Error in upload route: {str(e)}"
        print(error_msg, file=sys.stderr)
        import traceback
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
        import traceback
        traceback.print_exc(file=sys.stderr)
        return error_msg, 500

@app.route('/matrix')
def matrix():
    """矩阵显示页面"""
    try:
        print("\n=== Starting matrix route ===")
        
        # 检查配置文件
        config_file = os.path.join(BASE_DIR, 'configs', 'vcsa8u3-all-services-20250120.yaml')
        if not os.path.exists(config_file):
            error_msg = f"Configuration file not found: {config_file}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
        
        # 检查分析脚本
        script_file = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
        if not os.path.exists(script_file):
            error_msg = f"Analysis script not found: {script_file}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
            
        # 检查模板文件
        template_file = os.path.join(BASE_DIR, 'templates', 'index.html')
        if not os.path.exists(template_file):
            error_msg = f"Template file not found: {template_file}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
        
        # 检查目录权限
        permission_issues = check_directory_permissions()
        if permission_issues:
            error_msg = "Directory permission issues: " + "; ".join(permission_issues)
            print(error_msg, file=sys.stderr)
            return error_msg, 500
        
        # 检查是否有分析结果
        print(f"Checking OUTPUT_FOLDER: {OUTPUT_FOLDER}")
        try:
            analysis_files = [f for f in os.listdir(OUTPUT_FOLDER) if f.endswith('-vmon-analysis.yaml')]
            print(f"Found analysis files: {analysis_files}")
        except PermissionError as e:
            error_msg = f"Permission denied accessing output directory: {str(e)}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
        except Exception as e:
            error_msg = f"Error accessing output directory: {str(e)}"
            print(error_msg, file=sys.stderr)
            return error_msg, 500
        
        if not analysis_files:
            print("No analysis files found, redirecting to upload")
            return redirect(url_for('upload'))
        
        print("Loading service config...")
        # 有分析结果，显示矩阵
        service_config = ServiceConfig()
        service_config.load_configs()
        matrix = service_config.get_matrix_data()
        print(f"Matrix size: {len(matrix)}x{len(matrix[0])}")
        
        last_updated = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 计算统计信息
        stats = {
            'system_control': 0,
            'vmon_control': 0,
            'running': 0,
            'failed': 0,
            'stopped': 0,
            'profile': service_config.status_data.get('profile', 'Unknown')
        }
        
        print("Calculating stats...")
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
        
        print(f"Stats calculated: {stats}")
        print("Rendering template...")
        
        return render_template('index.html', 
                             matrix=matrix,
                             last_updated=last_updated,
                             stats=stats)
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        print(error_msg, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return error_msg, 500

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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# 添加静态文件路由
@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory('static', filename)

# 修改日志文件路由
@app.route('/uploads/<path:filename>')  # 改为 uploads
def serve_uploads(filename):  # 改名为更合适的名称
    return send_from_directory(UPLOADS_FOLDER, filename)

# 添加输出文件路由
@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_FOLDER, filename)

# 添加一个简单的错误处理器
@app.errorhandler(Exception)
def handle_error(e):
    print(f"Unhandled error: {str(e)}")
    import traceback
    traceback.print_exc()
    return f"Server error: {str(e)}", 500

# 检查并创建必要的目录
def check_directories():
    """检查并创建必要的目录"""
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

# 初始化时检查目录
check_directories()

@app.route('/upload_url', methods=['POST'])
def upload_url():
    """处理URL上传"""
    try:
        data = request.get_json()
        if not data or 'file_url' not in data:
            return 'No URL provided', 400
            
        url = data['file_url']
        vcenter_version = data.get('vcenter_version', '8')  # 默认为 8.x
        
        # 下载文件
        response = requests.get(url, stream=True)
        if not response.ok:
            return 'Failed to download file', 400
            
        # 创建临时文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_downloaded.log"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        
        # 保存文件
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    
        # 根据版本选择配置文件
        config_file = 'vcsa8u3-all-services.yaml' if vcenter_version == '8' else 'vcsa7-all-services.yaml'
        config_path = os.path.join(BASE_DIR, 'configs', config_file)
        
        # 执行分析脚本时传入版本信息
        script_path = os.path.join(BASE_DIR, 'utils', 'vmon_log_analysis_service_combined.py')
        result = subprocess.run(
            ['python', script_path, '--log-file', filepath, '--vcenter-version', vcenter_version],
            capture_output=True,
            text=True,
            check=True
        )
        
        return jsonify({'success': True})
        
    except requests.exceptions.RequestException as e:
        return f'Error downloading file: {str(e)}', 400
    except Exception as e:
        print(f"Error processing URL upload: {str(e)}")
        return f'Error processing file: {str(e)}', 500

if __name__ == '__main__':
    # 本地开发时监听 127.0.0.1
    host = '127.0.0.1'
    port = 5000
    
    # 如果在容器环境中运行，则监听所有接口
    if os.environ.get('DOCKER_ENV') == 'true':
        host = '0.0.0.0'
    
    app.run(host=host, port=port, debug=False)