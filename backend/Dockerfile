# 使用本地预构建的基础镜像（含 LibreOffice），避免每次重新下载
# 首次部署需在服务器上先构建基础镜像：
#   docker build -t contract-base:latest -f Dockerfile.base .
FROM contract-base:latest

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --trusted-host pypi.tuna.tsinghua.edu.cn

# 复制应用代码
COPY . .

# 创建必要目录
RUN mkdir -p /app/data /app/storage/contracts /app/storage/temp /app/secure

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
