import pandas as pd
import re
from datetime import datetime
import os

class VMonLogProcessor:
    def __init__(self):
        # 定义日志格式的正则表达式
        self.log_pattern = r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)\s+([A-Za-z]+\(\d+\))\s+(host-\d+)\s+<([^>]+)>\s+(.+)$'
        
        # 添加单独的模式用于更灵活的匹配
        self.time_pattern = r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)'
        self.level_pattern = r'([A-Za-z]+\(\d+\))'
        self.host_pattern = r'(host-\d+)'
        self.service_pattern = r'<([^>]+)>'
    
    def process_log_line(self, line):
        """处理单行日志"""
        match = re.match(self.log_pattern, line.strip())
        
        if match:
            # 如果匹配标准格式
            time, level, host, service, log = match.groups()
            service_value = service.strip() if service and service.strip() != 'unknown' else ''
            return {
                'Time': time,
                'Level': level,
                'Host': host,
                'Service': service_value,
                'Log': log,
                'CompleteLog': line.strip()
            }
        else:
            # 如果不匹配完整格式，尝试分别匹配各个部分
            line_str = line.strip()
            result = {
                'Time': '',
                'Level': '',
                'Host': '',
                'Service': '',  # 确保未匹配时为空字符串
                'Log': line_str,
                'CompleteLog': line_str
            }
            
            # 尝试匹配时间戳
            time_match = re.match(self.time_pattern, line_str)
            if time_match:
                result['Time'] = time_match.group(1)
                remaining = line_str[len(time_match.group(1)):].strip()
                
                # 尝试匹配Level
                level_match = re.search(self.level_pattern, remaining)
                if level_match:
                    result['Level'] = level_match.group(1)
                
                # 尝试匹配Host
                host_match = re.search(self.host_pattern, remaining)
                if host_match:
                    result['Host'] = host_match.group(1)
                
                # 尝试匹配Service
                service_match = re.search(self.service_pattern, remaining)
                if service_match:
                    service_value = service_match.group(1).strip()
                    result['Service'] = '' if service_value == 'unknown' else service_value
                
                # 更新Log字段（移除已匹配的部分）
                result['Log'] = remaining
            
            return result
    
    def process_log_file(self, file_path):
        """处理日志文件并返回DataFrame"""
        log_entries = []
        
        try:
            with open(file_path, 'r') as file:
                for line in file:
                    if line.strip():  # 跳过空行
                        log_entry = self.process_log_line(line)
                        log_entries.append(log_entry)
            
            # 创建DataFrame
            df = pd.DataFrame(log_entries)
            
            # 确保所有必需的列都存在
            required_columns = ['Time', 'Level', 'Host', 'Service', 'Log', 'CompleteLog']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = ''
            
            # 按照指定顺序排列列
            df = df[required_columns]
            
            # 将Service列中的'unknown'替换为空字符串
            df['Service'] = df['Service'].replace('unknown', '')
            
            # 生成带时间戳的CSV文件名
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = 'output'
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 构建输出文件路径
            output_file = os.path.join(output_dir, f'{timestamp}-vmon-1-processed.csv')
            
            # 保存为CSV文件
            df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"日志已保存到: {output_file}")
            
            return df
            
        except Exception as e:
            print(f"处理日志文件时发生错误: {str(e)}")
            return pd.DataFrame(columns=['Time', 'Level', 'Host', 'Service', 'Log', 'CompleteLog'])

    def filter_logs(self, df, output_suffix='filtered'):
        """
        过滤掉包含特定关键词的日志，并保存为新的CSV文件
        
        参数:
            df: 原始DataFrame
            output_suffix: 输出文件的后缀名，默认为'filtered'
        
        返回:
            过滤后的DataFrame
        """
        try:
            # 创建DataFrame的副本以避免修改原始数据
            filtered_df = df.copy()
            
            # 过滤掉包含指定关键词的行
            filter_keywords = [
                '<event-pub> Constructed command',
                'Client info Uid'
            ]
            
            for keyword in filter_keywords:
                filtered_df = filtered_df[~filtered_df['Log'].str.contains(keyword, na=False)]
            
            # 生成新的CSV文件名（使用原始时间戳-vmon-filtered.csv格式）
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_dir = 'output'
            output_file = os.path.join(output_dir, f'{timestamp}-vmon-2-{output_suffix}.csv')
            
            # 保存为新的CSV文件
            filtered_df.to_csv(output_file, index=False, encoding='utf-8')
            print(f"过滤后的日志已保存到: {output_file}")
            
            # 打印过滤统计信息
            total_rows = len(df)
            filtered_rows = len(filtered_df)
            removed_rows = total_rows - filtered_rows
            print(f"\n过滤统计:")
            print(f"原始行数: {total_rows}")
            print(f"过滤后行数: {filtered_rows}")
            print(f"移除行数: {removed_rows}")
            
            return filtered_df
            
        except Exception as e:
            print(f"过滤日志时发生错误: {str(e)}")
            return df
