# Project Rules

## Language Preference
- 始终使用简体中文与我交流。
- 代码注释、文档说明必须使用中文。

## Tech Stack Guidelines
- **后端**: FastAPI + SQLAlchemy。遵循 RESTful 规范。
- **前端**: Next.js 16 (App Router) + Tailwind CSS 4。
- **数据处理**: 优先使用 Pandas 处理 Excel/CSV 账单导入。

## Coding Style
- 使用类型注解 (Type Hints)。
- 前端组件优先使用 Lucide React 图标库。

## 数据安全规则：
- 严禁将 data/accounting.db 或任何包含真实账单的 .csv/.xlsx 文件内容上传到外部日志。
- 在编写测试用例时，必须使用 mock 数据或 data/ 目录下的示例文件。