import uvicorn
import sys
from app.config import config
from app.db_config import normalize_database_url, render_safe_database_url

if __name__ == "__main__":
    database_url = normalize_database_url(config.DATABASE_URL)
    print("=" * 50)
    print("AI智能合同管理系统 - 后端服务")
    print("=" * 50)
    print(f"存储路径: {config.STORAGE_PATH}")
    print(f"数据库: {render_safe_database_url(database_url)}")
    print("=" * 50)
    
    # 检查是否有--no-reload参数
    reload = "--no-reload" not in sys.argv
    
    if not reload:
        print("运行模式: 生产模式（禁用自动重载）")
    else:
        print("运行模式: 开发模式（启用自动重载）")
    print("=" * 50)
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=reload
    )
