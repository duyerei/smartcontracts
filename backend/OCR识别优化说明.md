# OCR识别优化说明

## 问题描述

合同附件内容识别不准确，主要表现为：
1. 合同ID 22（CT-20260301-172438）：附件中的产品明细表（4个产品）完全识别错误
2. 合同ID 23（CT-20260301-180231）：LLM返回"由于您未提供具体的合同文本"，说明OCR识别失败

## 根本原因

### 问题1：图片拼接型PDF识别失败
- 合同22的PDF每页包含几十个小图片（16x20px这种碎片）
- 原OCR策略是逐个识别小图片，导致：
  - 文字被切割成碎片，OCR无法识别完整内容
  - 识别率极低（20页只提取到682字符）
  - 触发百度OCR API的QPS限制

### 问题2：QPS限制导致识别中断
- 百度OCR API有请求频率限制（QPS）
- 原代码没有添加延迟，连续请求导致大量失败
- 错误信息："Open api qps request limit reached"

### 问题3：附件内容采样不准确
- 原采样策略查找"附件"+"价格"关键词
- 但对于表格结构识别不够精确
- 采样窗口太小（1500字符），可能截断表格

## 解决方案

### 1. 整页渲染OCR策略（核心改进）

**文件**: `backend/app/services/baidu_ocr.py` - `recognize_pdf_with_fitz_smart`方法

**改进**:
```python
# 旧策略：逐个识别小图片
for img in page.get_images():
    img_bytes = extract_image(img)
    ocr_result = ocr_api(img_bytes)  # 识别碎片

# 新策略：整页渲染为一张大图
mat = fitz.Matrix(2.0, 2.0)  # 2倍分辨率
pix = page.get_pixmap(matrix=mat)  # 渲染整页
img_bytes = pix.tobytes("png")
ocr_result = ocr_api(img_bytes)  # 识别完整页面
```

**优势**:
- 保留完整的文字布局和上下文
- 提高OCR识别准确率
- 减少API调用次数（每页1次而不是几十次）

### 2. 使用高精度OCR API

**改进**:
```python
# 旧：通用OCR
url = "https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic"

# 新：高精度OCR
url = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
```

**优势**:
- 识别准确率更高
- 对复杂排版支持更好
- 适合合同这种正式文档

### 3. 添加QPS限制处理

**改进**:
```python
# 添加延迟避免QPS限制
if ocr_call_count > 0:
    time.sleep(0.6)  # 600ms延迟，确保每秒不超过2次请求

# 添加重试机制
max_retries = 3
for retry in range(max_retries):
    try:
        response = ocr_api(data)
        if "qps" in error_msg or "limit" in error_msg:
            wait_time = (retry + 1) * 2  # 递增等待时间
            time.sleep(wait_time)
            continue
    except Exception:
        if retry < max_retries - 1:
            time.sleep(1)
            continue
```

**优势**:
- 避免触发QPS限制
- 遇到限制时自动重试
- 提高识别成功率

### 4. 优化附件内容采样

**文件**: `backend/app/services/llm_service.py` - `extract_full_summary`方法

**改进**:
```python
# 多级查找策略
# 优先级1：查找"附件"+表格特征（序号+产品+价格）
has_table_structure = (
    ("序号" in page or re.search(r'^\s*\d+[、\.]', page)) and
    ("产品" in page or "服务" in page) and
    (re.search(r'\d+[,，]?\d*\.?\d*\s*元', page))
)

# 优先级2：查找"明细"+"多个价格"（至少2个）
price_matches = re.findall(r'\d+[,，]?\d*\.?\d*\s*元', page)
if len(price_matches) >= 2:
    key_content = page[:2000]  # 增加到2000字符

# 优先级3：查找包含3个以上价格的页面
if len(price_matches) >= 3:
    key_content = page[:2000]
```

**优势**:
- 更精确地识别表格页面
- 采样窗口更大（2000字符），避免截断
- 多级查找确保不遗漏

### 5. 增强LLM提示词

**改进**:
```markdown
### 产品/服务明细表
**重要**：如果合同中包含产品清单、价格明细、费用清单、附件表格等，
**必须完整提取所有行**并使用标准Markdown表格格式输出。

表格格式要求：
- 必须使用标准Markdown表格语法（| 列1 | 列2 | 列3 |）
- 表格必须作为独立段落，前后各空一行
- 不能缩进，不能嵌套在列表内
- 必须包含表头行和分隔行（|---|---|---|）
- 提取合同中的所有产品/服务项，不要遗漏
- 保留原始的列名
- 数字保持原样，包括千分位逗号
- 最后一行加上"合计"行

**特别注意**：如果文本中包含"附件"部分，务必提取附件中的表格内容
```

## 使用方法

### 对于已上传的合同
1. 在合同详情页点击"重新解析"按钮
2. 系统会使用新的OCR策略重新识别
3. 等待1-2分钟（取决于页数）
4. 查看更新后的识别结果

### 对于新上传的合同
- 系统会自动使用新的OCR策略
- 无需手动操作

## 测试脚本

### 1. 检查PDF内容类型
```bash
cd backend
python check_pdf_content.py
```
显示每页的文本长度、图片数量等信息

### 2. 测试OCR识别
```bash
cd backend
python check_ocr_text.py
```
实际调用OCR API识别合同（需要1-2分钟）

### 3. 查看合同摘要
```bash
cd backend
python check_contract_summary.py
```
查看数据库中存储的summary内容

## 预期效果

### 识别准确率提升
- 图片拼接型PDF：从几乎无法识别提升到正常识别
- 扫描件PDF：识别准确率显著提高
- 表格内容：能够完整提取所有行

### 识别速度
- 短合同（<20页）：约10-15秒
- 中等合同（20-50页）：约20-30秒
- 长合同（>50页）：约30-60秒

### API调用优化
- 每页只调用1次OCR API（而不是几十次）
- 添加延迟避免QPS限制
- 自动重试机制提高成功率

## 注意事项

1. **API配额**：高精度OCR API可能有调用次数限制，请注意配额使用情况
2. **识别时间**：整页渲染+高精度识别需要更长时间，请耐心等待
3. **重新解析**：对于已上传的合同，必须点击"重新解析"才能使用新策略
4. **网络延迟**：如果网络不稳定，可能需要更长时间

## 后续优化建议

1. **缓存OCR结果**：避免重复识别同一份合同
2. **异步处理**：将OCR识别放到后台队列，避免阻塞用户操作
3. **进度提示**：显示OCR识别进度（已识别X/总共Y页）
4. **本地OCR**：考虑使用本地OCR引擎（如Tesseract）作为备选方案
5. **PDF文本层检测**：优先使用PDF自带的文本层，只对扫描件使用OCR
