import yaml
import re
from typing import Dict, Any

def fix_yaml_format(input_file: str, output_file: str):
    """修复YAML文件格式"""
    
    def fix_value(value: Any) -> Any:
        """修复单个值的格式"""
        if value is None:
            return ""
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, (int, float)):
            return value
        if isinstance(value, str):
            if value.strip() == "":
                return ""
            return value.strip()
        if isinstance(value, list):
            return [fix_value(item) for item in value] if value else []
        return value

    def process_service(service_data: Dict) -> Dict:
        """处理单个服务的数据，确保所有必需字段存在且格式正确"""
        field_template = {
            'servicename': "",
            'serviceprestart': "",
            'servicehealthcmd': "",
            'description': "",
            'id': None,
            'nameinlog': "",
            'level': None,
            'type': "",
            'profile': [],
            'status': "unknown",
            'log': [],
            'dp_service': [],
            'parent_id': None
        }
        
        fixed_data = {}
        for key, default in field_template.items():
            value = service_data.get(key, default)
            fixed_data[key] = fix_value(value)
        return fixed_data

    try:
        # 读取原始文件内容
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 预处理内容
        lines = content.split('\n')
        processed_lines = []
        current_service = None
        
        for line in lines:
            # 跳过空行和注释
            if not line.strip() or line.strip().startswith('#'):
                processed_lines.append(line)
                continue
            
            # 修复缩进（替换tab为空格）
            line = line.replace('\t', '  ')
            
            # 处理服务定义行
            if not line.startswith(' '):
                if 'services:' in line:
                    processed_lines.append(line)
                    continue
                    
                # 新服务定义
                current_service = line.strip().rstrip(':')
                processed_lines.append(f"  {current_service}:")
                continue
            
            # 处理服务属性
            if current_service and ':' in line:
                stripped = line.strip()
                key = stripped.split(':', 1)[0]
                value = stripped.split(':', 1)[1].strip()
                processed_lines.append(f"    {key}: {value}")
                continue
            
            processed_lines.append(line)
        
        # 重新组合处理后的内容
        processed_content = '\n'.join(processed_lines)
        
        # 解析YAML
        try:
            data = yaml.safe_load(processed_content)
        except yaml.YAMLError as e:
            print(f"YAML解析错误: {str(e)}")
            print("请检查原始文件的格式")
            raise
        
        # 处理services部分
        if 'services' in data:
            fixed_services = {}
            for service_name, service_data in sorted(data['services'].items()):
                fixed_services[service_name] = process_service(service_data)
            data['services'] = fixed_services
        
        # 写入修复后的YAML
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write("# VCSA8U3 All Services Configuration\n")
            f.write("# Last Updated: 2024-01-20\n")
            f.write("# 格式已统一化处理\n\n")
            
            class MyDumper(yaml.Dumper):
                def increase_indent(self, flow=False, indentless=False):
                    return super().increase_indent(flow, False)
            
            yaml.dump(
                data,
                f,
                Dumper=MyDumper,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                width=120,
                indent=2
            )
        
        print(f"成功修复YAML格式: {output_file}")
        
    except Exception as e:
        print(f"处理过程中发生错误: {str(e)}")
        print("请检查输入文件的格式是否正确")
        raise

if __name__ == "__main__":
    input_file = 'configs/vcsa8u3-all-services.yaml'
    output_file = 'configs/vcsa8u3-all-services-fixed.yaml'
    fix_yaml_format(input_file, output_file) 
    fix_yaml_format(input_file, output_file) 