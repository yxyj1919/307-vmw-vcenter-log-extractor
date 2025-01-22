FROM python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制应用文件
COPY . .

# 创建必要的目录并设置权限
RUN mkdir -p uploads output \
    && chmod 777 uploads output \
    && chmod 755 configs utils templates

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 设置环境变量
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV PYTHONUNBUFFERED=1
ENV DOCKER_ENV=true

# 暴露端口
EXPOSE 5000

# 启动命令（确保监听所有接口）
CMD ["python", "-u", "app.py"] 