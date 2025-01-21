import pandas as pd
from vmon_log_processor import VMonLogProcessor
from vmon_yaml_reader import YamlReader
import os

def analyze_service_status(yaml_reader, profile_services, filtered_df):
    """Analyze the startup status of services in the specified profile"""
    service_status = []
    
    # Get status related logs
    status_logs = filtered_df[
        filtered_df['Log'].str.contains('Service STARTED successfully|Service exited. Exit code', na=False)
    ]
    print(f"\nFound {len(status_logs)} status logs")
    print("\nStatus log samples:")
    print(status_logs['CompleteLog'].head())
    
    for service in sorted(profile_services):
        # 获取服务配置
        service_info = yaml_reader.get_service_info(service)
        service_id = service_info.get('id', 'N/A')
        parent_id = service_info.get('parent_id', 'N/A')
        dp_services = service_info.get('dp_service', [])  # 获取依赖服务列表
        
        # 查找服务相关的日志
        service_logs = filtered_df[filtered_df['Service'] == service]
        
        # 分析服务启动状态
        start_logs = []
        start_status = 'stopped'  # 默认状态为stopped
        
        if not service_logs.empty:
            for _, log in service_logs.iterrows():
                log_content = log['Log']
                log_entry = {
                    'timestamp': log['Time'],
                    'level': log['Level'],
                    'service': log['Service'],
                    'content': log_content
                }
                
                # 检查服务状态
                if 'Service STARTED successfully' in log_content:
                    start_logs.append(log_entry)
                    start_status = 'running'
                elif 'Service exited. Exit code' in log_content:
                    start_logs.append(log_entry)
                    start_status = 'failed to start'
        
        service_status.append({
            'service': service,
            'id': service_id,
            'parent_id': parent_id,
            'description': service_info.get('description', 'N/A'),
            'level': service_info.get('level', 'N/A'),
            'type': service_info.get('type', 'N/A'),  # 添加服务类型
            'dp_services': dp_services,  # 添加依赖服务列表
            'start_logs': start_logs,
            'start_status': start_status
        })
    
    return service_status

def print_log_entry(log_entry):
    """格式化打印日志条目"""
    print(f"  [{log_entry['timestamp']}] [{log_entry['level']}] [{log_entry['service']}] {log_entry['content']}")

def print_service_info(service, show_logs=True):
    """Print service information
    
    Args:
        service: Service information dictionary
        show_logs: Whether to show logs, defaults to True
    """
    print(f"\nService: {service['service']}")
    print(f"ID: {service['id']}")
    print(f"Parent ID: {service['parent_id']}")
    print(f"Description: {service['description']}")
    print(f"Level: {service['level']}")
    print(f"Type: {service['type']}")
    print(f"Status: {service['start_status']}")
    
    # 显示依赖服务
    if service['dp_services']:
        print("Dependencies:")
        for dp in service['dp_services']:
            print(f"  • {dp}")
    else:
        print("Dependencies: None")
    
    if show_logs and service['start_logs']:
        print("Startup Logs:")
        for log in service['start_logs']:
            print_log_entry(log)

def analyze_vmon_logs():
    """Analyze service startup status in VMON logs"""
    # 1. Read and process log file
    log_file = 'logs/vmon-803-24322028-unhealthy.log'
    processor = VMonLogProcessor()
    processed_df = processor.process_log_file(log_file)
    filtered_df = processor.filter_logs(processed_df)
    print(f"Total log entries: {len(filtered_df)}")
    
    # 2. Get profile name
    profile_logs = filtered_df[filtered_df['Log'].str.contains('Starting vMon with profile', na=False)]
    if not profile_logs.empty:
        profile_name = profile_logs.iloc[-1]['Log'].split("'")[-2]
        print(f"\nCurrent profile: {profile_name}")
    else:
        profile_name = 'NONE'
        print("\nProfile information not found")
    
    # 3. Get services associated with the profile
    yaml_reader = YamlReader('configs/vcsa8u3-all-services-20250120.yaml')
    profile_services = yaml_reader.get_services_by_profile(profile_name)
    print(f"\nServices in profile '{profile_name}' (Total: {len(profile_services)})")
    
    # 4. Analyze service startup status
    service_status = analyze_service_status(yaml_reader, profile_services, filtered_df)
    
    # 5. Group and display results by status
    running_services = [s for s in service_status if s['start_status'] == 'running']
    failed_services = [s for s in service_status if s['start_status'] == 'failed to start']
    stopped_services = [s for s in service_status if s['start_status'] == 'stopped']
    
    # Display running services
    print(f"\nRunning Services (Total: {len(running_services)}):")
    for service in running_services:
        print_service_info(service)
    
    # Display failed services
    print(f"\nFailed Services (Total: {len(failed_services)}):")
    for service in failed_services:
        print_service_info(service)
    
    # Display stopped services
    print(f"\nStopped Services (Total: {len(stopped_services)}):")
    for service in stopped_services:
        print_service_info(service, show_logs=False)
    
    return {
        'filtered_df': filtered_df,
        'profile_name': profile_name,
        'profile_services': profile_services,
        'service_status': service_status
    }

if __name__ == "__main__":
    results = analyze_vmon_logs() 