#!/bin/bash

# 检查必要目录
directories=("uploads" "output" "configs" "utils" "templates")

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        echo "Creating directory: $dir"
        mkdir -p "$dir"
    fi
done

# 设置权限
chmod 777 uploads output
chmod 755 configs utils templates

# 检查权限
echo "Checking directory permissions..."
for dir in "${directories[@]}"; do
    echo -n "$dir: "
    ls -ld "$dir"
done

# 检查关键文件权限
echo -e "\nChecking file permissions..."
find configs utils templates -type f -exec ls -l {} \; 