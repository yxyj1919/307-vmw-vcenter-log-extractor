import pandas as pd
from vmon_log_processor import VMonLogProcessor
from vmon_yaml_reader import YamlReader
import os

def analyze_service_prestarts(yaml_reader, profile_services, filtered_df):
    """Analyze the prestart status of services in the specified profile"""
    service_prestarts = []
    
    # Get prestart related logs
    prestart_logs = filtered_df[
        filtered_df['Log'].str.contains('Service pre-start command completed successfully|Service pre-start command failed with exit', na=False)
    ]
    print(f"\nFound {len(prestart_logs)} prestart logs")
    print("\nPrestart log samples:")
    print(prestart_logs['CompleteLog'].head())
    
    for service in sorted(profile_services):
        # 获取服务配置
        service_info = yaml_reader.get_service_info(service)
        service_id = service_info.get('id', 'N/A')
        serviceprestart = service_info.get('serviceprestart', '')
        
        # 查找服务相关的日志
        service_logs = filtered_df[filtered_df['Service'] == service]
        
        # 分析prestart状态
        prestart_logs = []
        error_logs = []
        prestart_status = 'not executed'  # 默认状态
        
        if not service_logs.empty:
            for _, log in service_logs.iterrows():
                log_content = log['Log']
                log_entry = {
                    'timestamp': log['Time'],
                    'level': log['Level'],
                    'service': log['Service'],
                    'content': log_content
                }
                
                if 'Service pre-start command completed successfully' in log_content:
                    prestart_logs.append(log_entry)
                    prestart_status = 'success'
                elif 'Service pre-start command failed with exit' in log_content:
                    prestart_logs.append(log_entry)
                    prestart_status = 'failed'
                elif "Service pre-start command's stderr:" in log_content:
                    error_logs.append(log_entry)
        
        service_prestarts.append({
            'service': service,
            'id': service_id,
            'description': service_info.get('description', 'N/A'),
            'level': service_info.get('level', 'N/A'),
            'serviceprestart': serviceprestart,
            'prestart_logs': prestart_logs,
            'error_logs': error_logs,
            'prestart_status': prestart_status
        })
    
    return service_prestarts

def print_service_info(service, show_logs=True):
    """Print service information
    
    Args:
        service: Service information dictionary
        show_logs: Whether to show logs, defaults to True
    """
    print(f"\nService: {service['service']}")
    print(f"ID: {service['id']}")
    print(f"Description: {service['description']}")
    print(f"Level: {service['level']}")
    print(f"ServicePrestart: {service['serviceprestart']}")
    print(f"Status: {service['prestart_status']}")
    if show_logs and service['prestart_logs']:
        print("Prestart Logs:")
        for log in service['prestart_logs']:
            print_log_entry(log)

def print_log_entry(log_entry):
    """格式化打印日志条目"""
    print(f"  [{log_entry['timestamp']}] [{log_entry['level']}] [{log_entry['service']}] {log_entry['content']}")

def analyze_vmon_logs():
    """Analyze service prestart status in VMON logs"""
    # 1. Read and process log file
    log_file = 'logs/vmon-803-24022515-reboot.log'
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
    
    # 4. Analyze service prestart status
    service_prestarts = analyze_service_prestarts(yaml_reader, profile_services, filtered_df)
    
    # 5. Group and display results by status
    success_services = [s for s in service_prestarts if s['prestart_status'] == 'success']
    failed_services = [s for s in service_prestarts if s['prestart_status'] == 'failed']
    not_executed_services = [s for s in service_prestarts if s['prestart_status'] == 'not executed']
    
    # Display successful services
    print(f"\nSuccessful Prestart Services (Total: {len(success_services)}):")
    for service in success_services:
        print_service_info(service)
    
    # Display failed services
    print(f"\nFailed Prestart Services (Total: {len(failed_services)}):")
    for service in failed_services:
        print_service_info(service)
    
    # Display not executed services
    print(f"\nNot Executed Prestart Services (Total: {len(not_executed_services)}):")
    for service in not_executed_services:
        print_service_info(service, show_logs=False)
    
    return {
        'filtered_df': filtered_df,
        'profile_name': profile_name,
        'profile_services': profile_services,
        'service_prestarts': service_prestarts
    }

if __name__ == "__main__":
    results = analyze_vmon_logs() 