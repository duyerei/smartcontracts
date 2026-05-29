"""
LLM服务 - 使用阿里云百炼（DashScope）智能体解析合同内容
参考文档: https://help.aliyun.com/zh/model-studio/developer-reference/api-reference-of-Chinese-application
"""
import json
import re
import requests
from typing import Optional
from app.config import config


class LLMService:
    def __init__(self):
        self.api_key = config.DASHSCOPE_API_KEY
        # 合同解析用的APP_ID（优先使用专用的，回退到通用的）
        self.app_id = config.DASHSCOPE_CONTRACT_APP_ID or config.DASHSCOPE_APP_ID
        if self.api_key:
            print(f"百炼配置: API_KEY=已配置, APP_ID={self.app_id or 'None'}")
        else:
            print("百炼API Key未配置，LLM解析不可用")

    def _sanitize_input(self, text: str) -> str:
        """清理输入文本，防止prompt注入攻击"""
        if not text:
            return ""
        if len(text) > 50000:
            text = text[:50000]
        suspicious_patterns = [
            r'忽略.*?指令', r'ignore.*?instruction', r'disregard.*?prompt',
            r'forget.*?previous', r'system.*?prompt', r'你是.*?助手', r'你现在是',
            r'请返回.*?密码', r'请输出.*?密钥', r'reveal.*?secret', r'show.*?password',
        ]
        for pattern in suspicious_patterns:
            text = re.sub(pattern, '[内容已过滤]', text, flags=re.IGNORECASE)
        return text

    def _get_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

    def _call_bailian(self, prompt: str, session_id: str = "") -> str:
        """调用百炼智能体应用API"""
        if not self.api_key or not self.app_id:
            print("百炼API Key或APP_ID未配置")
            return ""

        url = f"https://dashscope.aliyuncs.com/api/v1/apps/{self.app_id}/completion"
        payload = {
            "input": {"prompt": prompt},
            "parameters": {},
            "debug": {},
        }
        if session_id:
            payload["input"]["session_id"] = session_id

        for attempt in range(2):
            try:
                timeout = 120 if attempt == 0 else 180
                response = requests.post(url, json=payload, headers=self._get_headers(), timeout=timeout)
                result = response.json()
                print(f"百炼响应状态: {response.status_code}")

                if response.status_code == 200 and result.get("output"):
                    text = result["output"].get("text", "")
                    print(f"百炼响应内容长度: {len(text)}")
                    return text
                else:
                    error_msg = result.get("message", result.get("code", str(result)))
                    print(f"百炼调用失败: {error_msg}")
                    return ""
            except requests.exceptions.ReadTimeout:
                print(f"百炼调用超时 (第{attempt+1}次, timeout={timeout}s)")
                if attempt == 0:
                    print("正在重试...")
                    continue
                return ""
            except Exception as e:
                print(f"百炼调用错误: {e}")
                import traceback
                traceback.print_exc()
                return ""

    def call_llm(self, prompt: str, text: str) -> str:
        """调用百炼智能体解析合同文本"""
        if not self.api_key:
            print("百炼API Key未配置，跳过LLM解析")
            return ""

        text = self._sanitize_input(text)
        if not text:
            print("文本为空或无效，跳过LLM解析")
            return ""

        # 智能截取：前3000字符（合同开头）+ 后1500字符（签字盖章页）
        if len(text) > 4500:
            text_head = text[:3000]
            text_tail = text[-1500:]
            text_sample = text_head + "\n\n...[中间内容省略]...\n\n" + text_tail
        else:
            text_sample = text

        full_prompt = f"""请从以下合同文本中提取关键信息，并以JSON格式返回。
需要提取以下字段：
1. 甲方（公司全称）
2. 乙方（公司全称）
3. 丙方（如果存在三方合同，提取丙方公司全称；如果没有则返回null）
4. 合同名称
5. 签订日期（格式：YYYY-MM-DD，合同签字盖章的日期，**优先从合同末尾盖章处提取手写日期**）
6. 服务期限开始日期（格式：YYYY-MM-DD，注意区分签订日期和服务开始日期）
7. 服务期限结束日期（格式：YYYY-MM-DD，注意提取"至"、"到期"、"终止"等关键词后的日期；如果合同没有明确的结束日期，返回null）
8. 服务地点
9. 合作内容/签约背景
10. 乙方工作内容/服务内容（列出所有条款）
11. 服务费用总额（大写数字，也可能叫"合同金额"、"合同标额"、"合同总金额"、"合同价款"）
12. 付款方式（分期付款的每期金额和时间）
13. 发票要求

重要提示：
- 如果合同中明确提到"丙方"或存在第三方签约主体，请务必提取丙方信息
- 三方合同通常在合同开头会列出"甲方"、"乙方"、"丙方"
- 如果只有甲乙双方，丙方字段返回null即可
- **签订日期提取规则**：
  * 优先从合同末尾（签字盖章页）提取日期，这通常是手写的签订日期
  * 签订日期是合同签字盖章的实际日期，通常在合同最后一页
  * 如果末尾有多个日期，取最后一个（最接近文档结尾的）
  * 签订日期可能是手写的，格式如：2024年6月15日、2024-06-15等
- 服务期限提取规则：
  * 服务期限开始日期：服务实际开始的日期
  * 服务期限结束日期：服务结束的日期
  * 如果合同没有明确的结束日期（如长期有效、永久有效等），结束日期返回null
  * 服务期限通常表述为"自XXXX年XX月XX日至XXXX年XX月XX日"

请确保完整提取所有内容，特别是表格中的付款信息和准确的日期。

合同文本如下：
{text_sample}

请返回JSON格式结果，格式示例：
{{
  "甲方": "公司名称",
  "乙方": "公司名称",
  "丙方": "公司名称或null",
  "合同名称": "...",
  "签订日期": "YYYY-MM-DD",
  "服务期限开始日期": "YYYY-MM-DD",
  "服务期限结束日期": "YYYY-MM-DD或null",
  ...
}}

不要返回其他内容。"""

        return self._call_bailian(full_prompt)

    def parse_contract_with_llm(self, text: str) -> dict:
        """使用LLM解析合同，返回结构化数据"""
        if not text or len(text) < 100:
            print("文本太短，跳过LLM解析")
            return {}

        result_text = self.call_llm("parse_contract", text)
        if not result_text:
            return {}

        try:
            start = result_text.find('{')
            end = result_text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = result_text[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON解析失败: {e}, 原始结果: {result_text[:200]}")
        return {}

    def extract_price_table(self, text: str) -> str:
        """使用LLM提取价格明细表"""
        match = re.search(r"第五条服务费用和付款方式.*?(?:第六条|$)", text, re.DOTALL)
        if match:
            price_section = match.group(0)[:3000]
        else:
            price_section = text[:3000]

        full_prompt = f"""请从以下合同文本中提取价格明细表信息。

要求：
1. 提取"价格明细表"或"服务费用明细"表格中的所有行
2. 每行包含：项目类别、项目描述、价格、税率、总价、备注
3. 以Markdown表格格式返回，确保格式美观整洁
4. 如果没有价格明细表，请返回"无"

合同文本：
{price_section}

请直接返回表格，不要其他解释文字。"""

        result_text = self._call_bailian(full_prompt)
        if result_text:
            table_text = result_text.strip()
            if "无" in table_text and len(table_text) < 10:
                return ""
            return table_text
        return ""

    def extract_full_summary(self, text: str) -> str:
        """使用LLM智能提取合同的主要合作内容与付款方式"""
        text = self._sanitize_input(text)
        if not text or len(text.strip()) < 100:
            print("文本为空或太短，跳过LLM提取")
            return ""

        has_contract_keywords = any(kw in text for kw in ["合同", "协议", "甲方", "乙方", "服务", "产品", "付款", "金额"])
        if not has_contract_keywords:
            print("文本不包含合同关键词，可能是OCR识别失败")
            return ""

        # 智能截取策略
        if len(text) <= 8000:
            text_sample = text
        else:
            text_head = text[:3000]
            text_tail = text[-1500:]

            key_content = ""
            has_page_markers = "--- 第" in text
            if has_page_markers:
                segments = text.split("--- 第")
            else:
                segments = re.split(r'\n(?=第[一二三四五六七八九十\d]+[条章节]|附件|ANNEX)', text)
                if len(segments) <= 2:
                    segments = re.split(r'\n{2,}', text)

            table_keywords = ["附件", "明细", "清单", "价格表", "报价", "费用表"]
            content_keywords = ["服务内容", "工作内容", "合作内容", "项目概况", "服务范围", "维保", "运维"]
            price_pattern = r'\d+[,，]?\d*\.?\d*\s*元'

            for seg in segments:
                if any(kw in seg for kw in table_keywords):
                    has_table = (
                        ("序号" in seg or "编号" in seg or re.search(r'^\s*\d+[、\.\)]', seg, re.MULTILINE)) and
                        ("产品" in seg or "服务" in seg or "项目" in seg or "内容" in seg or "名称" in seg) and
                        (re.search(price_pattern, seg) or "价格" in seg or "金额" in seg or "费用" in seg or "单价" in seg)
                    )
                    if has_table:
                        key_content = seg[:2500]
                        print(f"找到附件/明细表格内容，长度: {len(key_content)}")
                        break

            if not key_content:
                for seg in segments:
                    if any(kw in seg for kw in content_keywords):
                        price_matches = re.findall(price_pattern, seg)
                        if len(price_matches) >= 1 or len(seg) > 200:
                            key_content = seg[:2500]
                            print(f"找到合作内容段落，长度: {len(key_content)}")
                            break

            if not key_content:
                for seg in segments:
                    price_matches = re.findall(price_pattern, seg)
                    if len(price_matches) >= 2:
                        key_content = seg[:2500]
                        print(f"找到价格密集段落，价格数量: {len(price_matches)}")
                        break

            if not key_content:
                for seg in segments:
                    if any(kw in seg for kw in ["付款", "结算", "支付", "账期"]):
                        key_content = seg[:2500]
                        print(f"找到付款方式段落，长度: {len(key_content)}")
                        break

            if key_content:
                text_sample = text_head + "\n\n...[前部分省略]...\n\n" + key_content + "\n\n...[中间部分省略]...\n\n" + text_tail
            else:
                mid_start = len(text) // 3
                mid_end = mid_start + 2500
                text_mid = text[mid_start:mid_end]
                text_sample = text_head + "\n\n...[前部分省略]...\n\n" + text_mid + "\n\n...[中间部分省略]...\n\n" + text_tail
                print("未找到关键段落，使用中间位置采样")

        full_prompt = f"""你是一个专业的合同分析助手。请仔细阅读以下合同全文，提取以下内容并用Markdown格式输出。

## 重要规则
**严禁编造内容**：
- 如果合同文本为空、无效或无法识别，请直接返回"无法识别合同内容"
- 只提取文本中实际存在的信息，不要添加任何示例、模板或虚构内容
- 如果某个部分在文本中不存在，请明确说明"未找到相关内容"

## 输出结构要求

### 主要合作内容
- 对于服务协议：提取服务范围、服务内容、双方权利义务、服务标准等
- 对于采购合同：提取产品清单、交付物、服务内容等

### 产品/服务明细表
- 如果包含产品清单、价格明细、费用清单、附件表格等，必须完整提取所有行并使用标准Markdown表格格式输出
- 表格必须使用标准Markdown表格语法
- 提取合同中的所有产品/服务项，不要遗漏

### 付款方式
- 提取付款条件、付款比例、付款时间节点、发票要求等

## 其他要求
1. 忠实于原文，完整保留关键细节
2. 金额、日期、百分比等数字务必准确
3. 绝对不要添加原文没有的内容

合同文本：
{text_sample}

请直接输出Markdown格式的内容。"""

        result_text = self._call_bailian(full_prompt)
        if result_text:
            invalid_phrases = [
                "由于您未提供", "示例输出结构", "当您提供实际合同",
                "虚构数据", "示例为虚构", "无法识别合同内容"
            ]
            if any(phrase in result_text for phrase in invalid_phrases):
                print("LLM返回无效内容，跳过")
                return ""
            return self._fix_markdown_tables(result_text.strip())
        return ""

    def _fix_markdown_tables(self, text: str) -> str:
        """修复LLM生成的Markdown中被缩进/嵌套的表格"""
        lines = text.split('\n')
        result = []
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('|') and stripped.endswith('|') and line != stripped:
                result.append(stripped)
            else:
                result.append(line)
        return '\n'.join(result)

    def analyze_risk(self, text: str) -> str:
        """使用LLM智能分析合同风险点"""
        text = self._sanitize_input(text)
        text_sample = text[:4000] if len(text) > 4000 else text

        full_prompt = f"""你是一位资深的法律风险分析师。请仔细阅读以下合同全文，从专业角度分析其中的风险点。

请按以下维度逐一分析，使用Markdown格式输出：

1. **合同条款完整性**：是否缺少关键条款（如违约责任、争议解决、保密条款、不可抗力等）
2. **付款风险**：付款条件是否对我方不利，是否有预付款过高、付款周期过长等问题
3. **知识产权风险**：知识产权归属是否明确
4. **违约责任**：违约条款是否对等、违约金是否合理
5. **争议解决**：争议解决方式是否合理（仲裁/诉讼、管辖地）
6. **其他风险**：任何其他值得注意的风险点

要求：
- 每个风险点标注风险等级（🔴 高风险 / 🟡 中风险 / 🟢 低风险）
- 给出具体的改进建议
- 最后给出整体风险评估和签署建议
- 不要编造合同中没有的内容

合同文本：
{text_sample}

请直接输出Markdown格式的分析报告。"""

        result_text = self._call_bailian(full_prompt)
        if result_text:
            return result_text.strip()
        return ""


llm_service = LLMService()
