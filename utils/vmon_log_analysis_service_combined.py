import pandas as pd
import yaml
from datetime import datetime
from vmon_log_processor import VMonLogProcessor
from vmon_yaml_reader import YamlReader
from vmon_log_analysis_service_prestart import analyze_service_prestarts
from vmon_log_analysis_service_status import analyze_service_status
import argparse
import os
import sys

def print_combined_service_info(service_prestart, service_status, show_logs=True):
    """打印服务的综合信息，包括prestart和运行状态
    
    Args:
        service_prestart: 服务prestart相关信息
        service_status: 服务运行状态相关信息
        show_logs: 是否显示日志，默认为True
    """
    print(f"\nService: {service_status['service']}")
    print(f"ID: {service_status['id']}")
    print(f"Parent ID: {service_status['parent_id']}")
    print(f"Description: {service_status['description']}")
    print(f"Level: {service_status['level']}")
    print(f"Type: {service_status['type']}")
    print(f"ServicePrestart: {service_prestart['serviceprestart']}")
    print(f"Prestart Status: {service_prestart['prestart_status']}")
    print(f"Service Status: {service_status['start_status']}")
    
    # 显示依赖服务
    if service_status['dp_services']:
        print("Dependencies:")
        for dp in service_status['dp_services']:
            print(f"  • {dp}")
    else:
        print("Dependencies: None")
    
    if show_logs:
        # 显示prestart相关日志
        if service_prestart['prestart_logs']:
            print("Prestart Logs:")
            for log in service_prestart['prestart_logs']:
                print_log_entry(log)
        # 显示服务启动相关日志
        if service_status['start_logs']:
            print("Service Logs:")
            for log in service_status['start_logs']:
                print_log_entry(log)

def print_log_entry(log_entry):
    """格式化打印日志条目"""
    print(f"  [{log_entry['timestamp']}] [{log_entry['level']}] [{log_entry['service']}] {log_entry['content']}")

def export_to_yaml(services_by_status, profile_name, output_dir='output'):
    """将分析结果导出为YAML文件
    
    Args:
        services_by_status: 包含服务状态信息的列表
        profile_name: 配置文件名称
        output_dir: 输出目录，默认为'output'
    """
    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)
    
    # 生成时间戳
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # 准备YAML数据结构
    yaml_data = {
        'profile': profile_name,
        'services': {}
    }
    
    # 按服务ID排序
    sorted_services = sorted(services_by_status, key=lambda x: (x['status']['level'], x['combined_status']))
    
    # 处理每个服务的信息
    for service_info in sorted_services:
        service_name = service_info['service']
        prestart_info = service_info['prestart']
        status_info = service_info['status']
        
        # 格式化prestart日志
        prestart_logs = [
            {
                'timestamp': log['timestamp'],
                'level': log['level'],
                'content': log['content']
            } for log in prestart_info['prestart_logs']
        ]
        
        # 格式化服务状态日志
        status_logs = [
            {
                'timestamp': log['timestamp'],
                'level': log['level'],
                'content': log['content']
            } for log in status_info['start_logs']
        ]
        
        # 创建服务条目
        yaml_data['services'][service_name] = {
            'id': status_info['id'],
            'parent_id': status_info['parent_id'],
            'description': status_info['description'],
            'level': status_info['level'],
            'type': status_info['type'],
            'serviceprestart': prestart_info['serviceprestart'],
            'prestart_status': prestart_info['prestart_status'],
            'service_status': status_info['start_status'],
            'combined_status': service_info['combined_status'],
            'dp_services': status_info['dp_services'],
            'prestart_logs': prestart_logs,
            'service_logs': status_logs
        }
    
    # 生成输出文件名（时间戳在前）
    output_file = f"{output_dir}/{timestamp}-vmon-analysis.yaml"
    
    # 导出到YAML文件
    with open(output_file, 'w') as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
    
    print(f"\nAnalysis results exported to: {output_file}")
    return output_file

def analyze_vmon_logs(log_file, config_path):
    """分析vmon日志文件
    
    Args:
        log_file: vmon日志文件路径
        config_path: 服务配置文件路径
    """
    try:
        # 1. 读取并处理日志文件
        processor = VMonLogProcessor()
        processed_df = processor.process_log_file(log_file)
        filtered_df = processor.filter_logs(processed_df)
        print(f"Total log entries: {len(filtered_df)}")
        
        # 2. 获取配置文件名称
        profile_logs = filtered_df[filtered_df['Log'].str.contains('Starting vMon with profile', na=False)]
        if not profile_logs.empty:
            profile_name = profile_logs.iloc[-1]['Log'].split("'")[-2]
            print(f"\nCurrent profile: {profile_name}")
        else:
            profile_name = 'NONE'
            print("\nProfile information not found")
        
        # 3. 获取配置文件关联的服务
        yaml_reader = YamlReader(config_path)
        profile_services = yaml_reader.get_services_by_profile(profile_name)
        print(f"\nServices in profile '{profile_name}' (Total: {len(profile_services)})")
        
        # 4. 分析服务的prestart和运行状态
        service_prestarts = analyze_service_prestarts(yaml_reader, profile_services, filtered_df)
        service_status = analyze_service_status(yaml_reader, profile_services, filtered_df)
        
        # 创建查找字典，方便访问
        prestart_dict = {s['service']: s for s in service_prestarts}
        status_dict = {s['service']: s for s in service_status}
        
        # 5. 按组合状态对服务分组
        services_by_status = []
        for service in profile_services:
            prestart_info = prestart_dict[service]
            status_info = status_dict[service]
            
            services_by_status.append({
                'service': service,
                'prestart': prestart_info,
                'status': status_info,
                'combined_status': f"{prestart_info['prestart_status']}/{status_info['start_status']}"
            })
        
        # 按级别和状态排序
        services_by_status.sort(key=lambda x: (x['status']['level'], x['combined_status']))
        
        # 显示服务状态摘要
        print("\nService Status Summary:")
        for service_info in services_by_status:
            print_combined_service_info(
                service_info['prestart'],
                service_info['status'],
                show_logs=True
            )
        
        # 导出结果到YAML文件
        output_file = export_to_yaml(services_by_status, profile_name)
        
        return {
            'filtered_df': filtered_df,
            'profile_name': profile_name,
            'profile_services': profile_services,
            'service_prestarts': service_prestarts,
            'service_status': service_status,
            'output_file': output_file
        }
    except Exception as e:
        print(f"Error analyzing log file: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)

def main():
    parser = argparse.ArgumentParser(description='Analyze vmon log file')
    parser.add_argument('--log-file', required=True, help='Path to the vmon log file')
    parser.add_argument('--vcenter-version', choices=['7', '8'], default='8', 
                      help='vCenter version (7 or 8)')
    args = parser.parse_args()
    
    try:
        # 检查文件是否存在
        if not os.path.exists(args.log_file):
            print(f"Error: Log file not found: {args.log_file}")
            sys.exit(1)
        
        # 根据版本选择配置文件
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if args.vcenter_version == '8':
            config_file = 'vcsa8u3-all-services.yaml'
        else:
            config_file = 'vcsa7-all-services.yaml'
            
        config_path = os.path.join(base_dir, 'configs', config_file)
        
        if not os.path.exists(config_path):
            print(f"Error: Config file not found: {config_path}")
            sys.exit(1)
            
        # 分析日志文件
        results = analyze_vmon_logs(args.log_file, config_path)
        print(f"\nAnalysis completed successfully")
        print(f"Output file: {results['output_file']}")
        
    except Exception as e:
        print(f"Error analyzing log file: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(2)

if __name__ == '__main__':
    main()