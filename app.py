from flask import Flask, render_template
import yaml
import os

app = Flask(__name__)

class ServiceConfig:
    """服务配置管理类"""
    def __init__(self, config_path='configs/vcsa8u3-all-services-20250120.yaml'):
        self.config_path = config_path
        self.config_data = None
        self.status_data = None
        self.dependencies = None
        self.reverse_dependencies = None
    
    def load_configs(self):
        """加载配置和状态数据"""
        try:
            # 读取服务配置
            with open(self.config_path, 'r') as f:
                self.config_data = yaml.safe_load(f)
                print("Config data loaded successfully")
            
            # 获取最新的分析结果文件
            output_dir = 'output'
            analysis_files = [f for f in os.listdir(output_dir) if f.endswith('-vmon-analysis.yaml')]
            if not analysis_files:
                raise FileNotFoundError("No analysis files found")
            
            latest_file = sorted(analysis_files)[-1]
            print(f"Latest analysis file: {latest_file}")
            
            # 读取服务状态
            with open(os.path.join(output_dir, latest_file), 'r') as f:
                self.status_data = yaml.safe_load(f)
                print("Status data loaded successfully")
            
            # 计算依赖关系
            self._calculate_dependencies()
            
        except Exception as e:
            print(f"Error loading configs: {str(e)}")
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

@app.route('/')
def index():
    """主页路由"""
    try:
        service_config = ServiceConfig()
        service_config.load_configs()
        matrix = service_config.get_matrix_data()
        return render_template('index.html', matrix=matrix)
    except Exception as e:
        print(f"Error in index route: {str(e)}")
        return f"Error: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)