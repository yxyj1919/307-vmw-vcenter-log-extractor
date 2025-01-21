#!/usr/bin/env python3
import os
import sys
import stat
import yaml

def check_setup():
    """检查项目设置"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 检查必要的目录
    directories = {
        'uploads': 'uploads',
        'output': 'output',
        'configs': 'configs',
        'utils': 'utils',
        'templates': 'templates'
    }
    
    issues = []
    
    # 检查目录
    for name, path in directories.items():
        full_path = os.path.join(base_dir, path)
        if not os.path.exists(full_path):
            issues.append(f"{name} directory missing: {full_path}")
            continue
        
        if not os.path.isdir(full_path):
            issues.append(f"{name} is not a directory: {full_path}")
            continue
            
        # 检查权限
        try:
            mode = os.stat(full_path).st_mode
            if not mode & stat.S_IRWXU:
                issues.append(f"{name} directory lacks proper permissions: {full_path}")
        except Exception as e:
            issues.append(f"Error checking {name} directory: {str(e)}")
    
    # 检查必要的文件
    required_files = {
        'config': os.path.join(base_dir, 'configs', 'vcsa8u3-all-services-20250120.yaml'),
        'script': os.path.join(base_dir, 'utils', 'vmon_log_analysis_service_combined.py'),
        'template': os.path.join(base_dir, 'templates', 'index.html')
    }
    
    for name, path in required_files.items():
        if not os.path.exists(path):
            issues.append(f"Required file missing: {path}")
            continue
            
        if not os.path.isfile(path):
            issues.append(f"Not a file: {path}")
            continue
            
        # 检查文件权限
        try:
            mode = os.stat(path).st_mode
            if not mode & stat.S_IRUSR:
                issues.append(f"File lacks read permission: {path}")
        except Exception as e:
            issues.append(f"Error checking file: {path} - {str(e)}")
    
    return issues

if __name__ == '__main__':
    issues = check_setup()
    if issues:
        print("Setup issues found:", file=sys.stderr)
        for issue in issues:
            print(f"  - {issue}", file=sys.stderr)
        sys.exit(1)
    else:
        print("Setup looks good!")
        sys.exit(0) 