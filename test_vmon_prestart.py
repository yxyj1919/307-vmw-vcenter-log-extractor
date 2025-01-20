from analyze_vmon_prestart import VMonPreStartAnalyzer, ServicePreStartStatus
import pandas as pd
import glob
import os

def test_prestart_analysis():
    """测试vMon Pre-Start分析功能"""
    
    try:
        print("\n=== 开始测试 vMon Pre-Start 分析 ===")
        
        # 第一步：获取最新的过滤日志文件
        output_files = glob.glob('output/*-vmon-2-filtered.csv')
        if not output_files:
            print("错误：未找到过滤后的日志文件！")
            return
        
        latest_file = max(output_files, key=os.path.getctime)
        print(f"\n使用日志文件: {latest_file}")
        
        # 第二步：读取日志文件并显示基本信息
        df = pd.read_csv(latest_file)
        print(f"\n日志文件基本信息:")
        print(f"总行数: {len(df)}")
        print(f"列名: {', '.join(df.columns)}")
        
        # 第三步：显示包含profile信息的日志
        print("\n=== Profile信息 ===")
        profile_logs = df[df['CompleteLog'].str.contains("Starting vMon with profile", na=False)]
        if not profile_logs.empty:
            print("\n找到的Profile信息:")
            for _, row in profile_logs.iterrows():
                print(row['CompleteLog'])
        
        # 显示所有唯一的Service值
        print("\n=== Service列表 ===")
        services = sorted(df['Service'].dropna().astype(str).unique())
        print("所有出现的Service:")
        for service in services:
            print(f"- {service}")
            
        # 显示每个Service的相关日志
        print("\n=== 每个Service的日志搜索 ===")
        for service in services:
            print(f"\n检查Service: {service}")
            
            # 搜索prestart成功的日志
            success_logs = df[
                df['Log'].str.contains('Service pre-start command completed successfully.', regex=False, na=False) &
                df['Service'].str.contains(service, regex=False, na=False)
            ]
            if not success_logs.empty:
                print("找到prestart成功日志:")
                print(success_logs['CompleteLog'].iloc[0])
            
            # 搜索prestart失败的日志
            fail_logs = df[
                df['Log'].str.contains('Service pre-start command failed with exit', regex=False, na=False) &
                df['Service'].str.contains(service, regex=False, na=False)
            ]
            if not fail_logs.empty:
                print("找到prestart失败日志:")
                print(fail_logs['CompleteLog'].iloc[0])
            
            # 搜索命令构造的日志
            command_logs = df[
                df['Log'].str.contains('Constructed command', regex=False, na=False) &
                df['Service'].str.contains(service, regex=False, na=False)
            ]
            if not command_logs.empty:
                print("找到命令构造日志:")
                print(command_logs['CompleteLog'].iloc[0])
        
        # 继续原有的分析
        print("\n=== 开始分析器分析 ===")
        analyzer = VMonPreStartAnalyzer()
        results_df = analyzer.analyze_logs(latest_file)
        
        # 第五步：显示详细的分析结果
        if results_df is not None:
            print("\n=== 详细分析结果 ===")
            
            # 显示成功的服务
            success_services = results_df[results_df['status'] == 'Success']
            if not success_services.empty:
                print("\n成功启动的服务:")
                for _, row in success_services.iterrows():
                    print(f"\n服务: {row['service_name']}")
                    print(f"状态日志: {row['status_log']}")
            
            # 显示失败的服务
            failed_services = results_df[results_df['status'] == 'Failed']
            if not failed_services.empty:
                print("\n启动失败的服务:")
                for _, row in failed_services.iterrows():
                    print(f"\n服务: {row['service_name']}")
                    print(f"状态日志: {row['status_log']}")
            
            # 显示未找到状态的服务
            not_found_services = results_df[results_df['status'] == 'Not Found']
            if not not_found_services.empty:
                print(f"\n未找到状态的服务数量: {len(not_found_services)}")
                print("服务列表:", ', '.join(not_found_services['service_name']))
        
        print("\n=== 测试完成 ===")
        
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")
        raise e

if __name__ == "__main__":
    test_prestart_analysis() 