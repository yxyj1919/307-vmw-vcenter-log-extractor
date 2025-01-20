import pandas as pd
import json
import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional

@dataclass
class ServicePreStartStatus:
    """服务pre-start状态的数据类"""
    service_name: str                # 服务名称
    prestart_name: str              # prestart服务名称
    constructed_command: str = ''    # 构造的命令
    status: str = 'Not Found'       # 状态：Success, Failed, Not Found
    status_log: str = ''            # 状态相关的日志行

class VMonPreStartAnalyzer:
    """vMon Pre-Start服务分析器"""
    
    def __init__(self, profiles_path: str = 'configs/vmon-8-profiles.json',
                 services_path: str = 'configs/vmon-8-control-services.json'):
        """
        初始化分析器
        
        Args:
            profiles_path: profile配置文件路径
            services_path: 服务配置文件路径
        """
        # 加载配置文件
        with open(profiles_path, 'r') as f:
            self.profiles = json.load(f)
        with open(services_path, 'r') as f:
            self.services = json.load(f)
    
    def get_profile_name(self, df: pd.DataFrame) -> str:
        """
        从日志中获取profile名称
        
        Args:
            df: 日志DataFrame
        
        Returns:
            str: profile名称，如果未找到则返回'ALL'
        """
        profile_pattern = r"Starting vMon with profile '(\w+)'"
        profile_logs = df[df['CompleteLog'].str.contains("Starting vMon with profile", na=False)]
        
        if not profile_logs.empty:
            for log in profile_logs['CompleteLog']:
                match = re.search(profile_pattern, log)
                if match:
                    profile_name = match.group(1)
                    print(f"找到Profile: {profile_name}")
                    return profile_name
        
        print("未找到Profile信息，使用默认Profile: ALL")
        return 'ALL'
    
    def get_services_for_profile(self, profile_name: str) -> List[str]:
        """
        获取指定profile下的服务列表
        
        Args:
            profile_name: profile名称
        
        Returns:
            List[str]: 服务列表
        """
        return self.profiles.get(profile_name, [])
    
    def analyze_prestart_status(self, df: pd.DataFrame, service: str) -> ServicePreStartStatus:
        """分析单个服务的pre-start状态"""
        result = ServicePreStartStatus(
            service_name=service,
            prestart_name=f"{service}-prestart"
        )
        
        print(f"\n=== 分析服务 {service} ===")
        
        # 检查服务是否有prestart命令
        if result.prestart_name not in self.services.get(service, []):
            print(f"状态: Not Found - 原因: 服务 {service} 不需要prestart命令")
            return result
        
        # 首先在整个DataFrame中搜索成功状态
        success_pattern = 'Service pre-start command completed successfully.'
        success_logs = df[
            df['Log'].str.contains(success_pattern, regex=False, na=False) &
            df['Service'].str.contains(f"<{service}>", regex=False, na=False)
        ]
        
        # 如果找到成功状态，直接标记为成功
        if not success_logs.empty:
            result.status = 'Success'
            result.status_log = success_logs.iloc[0]['CompleteLog']
            print(f"状态: Success - 找到成功日志: {result.status_log}")
            return result
        
        # 搜索失败状态
        fail_pattern = 'Service pre-start command failed with exit'
        fail_logs = df[
            df['Log'].str.contains(fail_pattern, regex=False, na=False) &
            df['Service'].str.contains(f"<{service}>", regex=False, na=False)
        ]
        
        # 如果找到失败状态，标记为失败
        if not fail_logs.empty:
            result.status = 'Failed'
            result.status_log = fail_logs.iloc[0]['CompleteLog']
            print(f"状态: Failed - 找到失败日志: {result.status_log}")
            return result
        
        # 获取所有相关的服务日志
        service_logs = df[
            df['Service'].str.contains(f"<{service}>", regex=False, na=False)
        ]
        
        # 如果有服务日志但没有状态信息
        if not service_logs.empty:
            print(f"状态: Not Found - 原因: 找到服务日志但未包含成功或失败状态")
            print(f"找到 {len(service_logs)} 条相关日志:")
            for _, row in service_logs.iterrows():
                print(f"- {row['CompleteLog']}")
            
            # 查找构造的命令
            command_logs = service_logs[
                service_logs['Log'].str.contains("Constructed command", regex=False, na=False)
            ]
            if not command_logs.empty:
                result.constructed_command = command_logs.iloc[0]['Log']
                print(f"找到构造命令: {result.constructed_command}")
        else:
            print(f"状态: Not Found - 原因: 在日志中未找到任何与服务相关的记录")
        
        return result
    
    def analyze_logs(self, log_file: str) -> pd.DataFrame:
        """
        分析日志文件
        
        Args:
            log_file: 日志文件路径
        
        Returns:
            pd.DataFrame: 分析结果DataFrame
        """
        try:
            # 读取CSV文件
            df = pd.read_csv(log_file)
            
            # 获取profile名称
            profile_name = self.get_profile_name(df)
            
            # 获取服务列表
            services = self.get_services_for_profile(profile_name)
            print(f"Profile {profile_name} 包含 {len(services)} 个服务")
            
            # 分析每个服务的pre-start状态
            results = []
            for service in services:
                status = self.analyze_prestart_status(df, service)
                results.append(vars(status))  # 转换dataclass为dict
            
            # 创建结果DataFrame
            results_df = pd.DataFrame(results)
            
            # 保存分析结果
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = f'output/{timestamp}-vmon-prestart-analysis.csv'
            results_df.to_csv(output_file, index=False)
            print(f"\n分析结果已保存到: {output_file}")
            
            # 打印统计信息
            print("\nPre-start状态统计:")
            print(results_df['status'].value_counts())
            
            return results_df
            
        except Exception as e:
            print(f"分析过程中发生错误: {str(e)}")
            raise

def main():
    """主函数"""
    analyzer = VMonPreStartAnalyzer()
    # 使用最新的过滤日志文件
    output_files = glob.glob('output/*-vmon-2-filtered.csv')
    if output_files:
        latest_file = max(output_files, key=os.path.getctime)
        print(f"使用日志文件: {latest_file}")
        analyzer.analyze_logs(latest_file)
    else:
        print("未找到过滤后的日志文件！")

if __name__ == "__main__":
    import glob
    import os
    main() 