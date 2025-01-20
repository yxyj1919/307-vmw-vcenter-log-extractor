import pandas as pd
from utils.vmon_log_processor import VMonLogProcessor
from utils.vmon_yaml_reader import YamlReader
import os

def analyze_vmon_logs():
    """分析VMON日志和服务配置"""
    # 1. 读取并处理日志文件
    log_file = 'logs/vmon-803-24022515-healthy.log'
    processor = VMonLogProcessor()
    
    # 处理日志并保存为CSV
    processed_df = processor.process_log_file(log_file)
    processed_csv = 'logs/processed_vmon.csv'
    processed_df.to_csv(processed_csv, index=False)
    print(f"\n处理后的日志已保存到: {processed_csv}")
    print(f"总日志条数: {len(processed_df)}")
    
    # 2. 查找启动配置文件
    profile_logs = processed_df[processed_df['Log'].str.contains('Starting vMon with profile', na=False)]
    if not profile_logs.empty:
        profile_log = profile_logs.iloc[-1]['Log']
        profile_name = profile_log.split("'")[-2]  # 获取引号中的配置文件名
        print(f"\n当前使用的配置文件: {profile_name}")
    else:
        profile_name = 'NONE'  # 默认值
        print("\n未找到配置文件信息")
    
    # 3. 读取YAML文件并查找相关服务
    yaml_file = 'configs/vcsa8u3-all-services-20250120.yaml'
    yaml_reader = YamlReader(yaml_file)
    
    # 使用YamlReader类中的方法查找使用该配置文件的服务
    profile_services = yaml_reader.get_services_by_profile(profile_name)
    
    print(f"\n配置文件 '{profile_name}' 相关的服务 (共 {len(profile_services)} 个):")
    for service in sorted(profile_services):
        service_info = yaml_reader.get_service_info(service)
        print(f"- {service}: {service_info.get('description', 'N/A')}")
    
    return {
        'processed_df': processed_df,
        'profile_name': profile_name,
        'profile_services': profile_services
    }

if __name__ == "__main__":
    results = analyze_vmon_logs() 