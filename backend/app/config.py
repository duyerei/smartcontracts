import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"
load_dotenv(env_path)

class Config:
    BAIDU_OCR_API_KEY = os.getenv("BAIDU_OCR_API_KEY", "")
    BAIDU_OCR_SECRET_KEY = os.getenv("BAIDU_OCR_SECRET_KEY", "")
    WENXIN_API_KEY = os.getenv("WENXIN_API_KEY", "")
    WENXIN_API_SECRET = os.getenv("WENXIN_API_SECRET", "")
    # 百度千帆平台配置 (AK/SK)
    QIANFAN_AK = os.getenv("QIANFAN_AK", "")
    QIANFAN_SK = os.getenv("QIANFAN_SK", "")
    # 百度千帆新配置
    BAIDUQIANFAN_API_KEY = os.getenv("BAIDUQIANFAN_API_KEY", "")
    BAIDUQIANFAN_SECRET_KEY = os.getenv("BAIDUQIANFAN_SECRET_KEY", "") or os.getenv("BAIDUQIANFAN_SECRET_KEY_", "")
    # 支持CLOUDBAIDU配置
    CLOUDBAIDU_API_NAME = os.getenv("CLOUDBAIDU_API_NAME", "")
    CLOUDBAIDU_API_KEY = os.getenv("CLOUDBAIDU_API_KEY", "")
    CLOUDBAIDU_API_SECRET = os.getenv("CLOUDBAIDU_API_SECRET", "")
    # 百度AppBuilder Agent（可选）
    APPBUILDER_API_URL = os.getenv("APPBUILDER_API_URL", "")
    APPBUILDER_API_TOKEN = os.getenv("APPBUILDER_API_TOKEN", "")
    APPBUILDER_APP_ID = os.getenv("APPBUILDER_APP_ID", "")
    APPBUILDER_USER_ID = os.getenv("APPBUILDER_USER_ID", "")
    APPBUILDER_AK = os.getenv("APPBUILDER_AK", "")
    APPBUILDER_SK = os.getenv("APPBUILDER_SK", "")
    # 火山引擎 ARK（豆包大模型）
    ARK_API_KEY = os.getenv("ARK_API_KEY", "")
    ARK_BOT_MODEL = os.getenv("ARK_BOT_MODEL", "")
    ARK_API_URL = os.getenv("ARK_API_URL", "https://ark.cn-beijing.volces.com/api/v3/bots/chat/completions")
    # JWT认证
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
    JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "480"))
    STORAGE_PATH = BASE_DIR / os.getenv("STORAGE_PATH", "storage")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./contracts.db")
    
    @classmethod
    def init_storage(cls):
        contracts_dir = cls.STORAGE_PATH / "contracts"
        temp_dir = cls.STORAGE_PATH / "temp"
        contracts_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

config = Config()
