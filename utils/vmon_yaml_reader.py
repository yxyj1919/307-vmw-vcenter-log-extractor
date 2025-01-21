import yaml
from typing import Dict, List, Any
from pathlib import Path
import sys

class YamlReader:
    """YAML文件读取器"""
    
    def __init__(self, yaml_file: str):
        """初始化读取器
        
        Args:
            yaml_file: YAML文件路径
        """
        self.yaml_file = yaml_file
        self.data = self._load_yaml()
    
    def _load_yaml(self) -> Dict:
        """加载YAML文件"""
        try:
            with open(self.yaml_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"读取YAML文件时发生错误: {str(e)}")
            sys.exit(1)
    
    def get_all_services(self) -> List[str]:
        """获取所有服务名称"""
        return sorted(self.data.get('services', {}).keys())
    
    def get_service_info(self, service_name: str) -> Dict[str, Any]:
        """获取指定服务的信息"""
        return self.data.get('services', {}).get(service_name, {})
    
    def get_services_by_type(self, service_type: str) -> List[str]:
        """获取指定类型的所有服务"""
        return [
            name for name, info in self.data.get('services', {}).items()
            if info.get('type') == service_type
        ]
    
    def get_services_by_level(self, level: int) -> List[str]:
        """获取指定级别的所有服务"""
        return [
            name for name, info in self.data.get('services', {}).items()
            if info.get('level') == level
        ]
    
    def get_services_with_prestart(self) -> List[str]:
        """获取所有有prestart命令的服务"""
        return [
            name for name, info in self.data.get('services', {}).items()
            if info.get('serviceprestart')
        ]

    def get_services_by_profile(self, profile_name: str) -> List[str]:
        """获取指定配置文件的所有服务
        
        Args:
            profile_name: 配置文件名称
            
        Returns:
            包含指定配置文件的服务列表
        """
        return [
            name for name, info in self.data.get('services', {}).items()
            if profile_name in info.get('profile', [])
        ]

def test_yaml_reader():
    """测试YAML读取功能"""
    yaml_file = 'configs/vcsa8u3-all-services-20250120.yaml'
    reader = YamlReader(yaml_file)
    
    print("\n=== YAML文件内容分析 ===")
    
    # 1. 基本信息
    all_services = reader.get_all_services()
    print(f"\n总服务数量: {len(all_services)}")
    
    # 2. 服务类型统计
    service_types = set()
    for service in all_services:
        service_info = reader.get_service_info(service)
        service_types.add(service_info.get('type', ''))
    
    print("\n服务类型统计:")
    for stype in sorted(service_types):
        services = reader.get_services_by_type(stype)
        print(f"- {stype}: {len(services)}个服务")
    
    # 3. 服务级别统计
    print("\n服务级别统计:")
    for level in range(1, 4):  # 假设有1-3级
        services = reader.get_services_by_level(level)
        print(f"- Level {level}: {len(services)}个服务")
    
    # 4. Prestart服务统计
    prestart_services = reader.get_services_with_prestart()
    print(f"\n有prestart命令的服务数量: {len(prestart_services)}")
    print("服务列表:")
    for service in sorted(prestart_services):
        service_info = reader.get_service_info(service)
        print(f"- {service}: {service_info['serviceprestart']}")
    
    # 5. 详细信息示例
    print("\n服务详细信息示例:")
    sample_service = all_services[0]  # 第一个服务作为示例
    service_info = reader.get_service_info(sample_service)
    print(f"\n{sample_service}服务信息:")
    for key, value in service_info.items():
        print(f"- {key}: {value}")

if __name__ == "__main__":
    test_yaml_reader() 