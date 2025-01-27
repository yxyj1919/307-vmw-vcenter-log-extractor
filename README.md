# vCenter vMon Service Checker

![](https://yxyj1919-imagebed.oss-cn-beijing.aliyuncs.com/rocket-image/202501221626059.png)

A web-based tool for analyzing vCenter Server vmon.log files and visualizing service dependencies.

## Features

- Upload vmon.log files directly or via URL
- Support for vCenter Server 7.x and 8.x
- Interactive service dependency visualization
- Service status analysis and monitoring
- Detailed service logs inspection
- Drag-and-drop file upload
- Mobile-friendly interface

## Version
- v0.1.0 2024-01-22
- v1.0.0 2024-01-26 

## Docker Deployment Guide


## Quick Start

1. **Pull the Docker Image**
```
docker pull yxyj1919/vcenter-vmon-service-checker:latest
```
2. **Run the Container**
```
docker run -d -p 5000:5000 yxyj1919/vcenter-vmon-service-checker:latest
```
3. **Access the Application**
Open your web browser and navigate to `http://localhost:5000`.

4. **Upload vmon.log file**

5. **Advanced Configuration**
```
mkdir -p /opt/vmon-checker/uploads
mkdir -p /opt/vmon-checker/output
```
```
bash
docker run -d \
--name vmon-checker \
-p 8080:5000 \ # Map to port 8080
-v /path/to/local/uploads:/app/uploads \
-v /path/to/local/output:/app/output \
yxyj1919/vcenter-vmon-service-checker:latest
```
## Contact
Bug Reports: chang.wang@broadcom.com 
