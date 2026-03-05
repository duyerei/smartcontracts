import json
import re
from datetime import datetime
from typing import Optional, Dict, Any
from app.services.baidu_ocr import baidu_ocr

CONTRACT_TYPES = ["采购合同", "销售合同", "人力合同", "NDA保密协议", "租赁合同", "服务合同", "投资协议", "其他"]
DEPARTMENTS = ["科技中心", "财务中心", "法务合规中心", "风控中心", "普惠金融", "人力行政中心", "其他"]

class ContractParser:
    def __init__(self):
        self.ocr = baidu_ocr
    
    def parse_contract(self, file_path: str, metadata_hint: str = "") -> Dict[str, Any]:
        text = self.ocr.extract_text_from_file(file_path)
        
        # 仅在文本为空或极短且明确是错误信息时才判定失败
        # 避免合同正文中包含"失败""异常"等词被误判
        is_ocr_failure = (
            not text 
            or len(text.strip()) < 50 and ("失败" in text or "异常" in text or "未能识别" in text)
        )
        if is_ocr_failure:
            return {
                "success": True,
                "text_length": 0,
                "data": {
                    "contract_number": f"CT-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}",
                    "title": "未识别",
                    "parties": [],
                    "amount": None,
                    "contract_type": "其他",
                    "department": "其他",
                    "start_date": None,
                    "end_date": None,
                },
                "note": "OCR识别失败，合同信息未能自动提取"
            }
        
        combined_text = text + "\n\n" + metadata_hint if metadata_hint else text
        
        extracted = {
            "contract_number": self._extract_contract_number(combined_text),
            "title": self._extract_title(combined_text),
            "parties": self._extract_parties(combined_text),
            "amount": self._extract_amount(combined_text),
            "contract_type": self._classify_contract(combined_text),
            "department": self._extract_department(combined_text),
            "signed_date": self._extract_date(combined_text, "signed"),
            "start_date": self._extract_date(combined_text, "start"),
            "end_date": self._extract_date(combined_text, "end"),
        }
        
        return {
            "success": True,
            "text_length": len(text),
            "data": extracted,
            "raw_text": text
        }
    
    def _extract_contract_number(self, text: str) -> str:
        patterns = [
            r"合同编号[：:]\s*([A-Z0-9\-_]+)",
            r"编号[：:]\s*([A-Z0-9\-_]+)",
            r"CT[\-\s]?\d{4}[\-\s]?\d{3,}",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                num = match.group(1).strip()
                if len(num) >= 4:
                    return num
        
        return f"CT-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"
    
    def _extract_title(self, text: str) -> Optional[str]:
        lines = text.split('\n')
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 5 and len(line) < 100:
                if any(keyword in line for keyword in ["合同", "协议", "采购", "销售", "租赁", "服务"]):
                    return line
        return "未识别合同标题"
    
    def _extract_parties(self, text: str) -> list:
        parties = []

        # 公司名称通常包含这些关键词
        company_suffixes = ["有限公司", "股份有限公司", "集团有限公司", "有限责任公司",
                          "公司", "集团", "企业", "发展中公司"]

        # 单独提取甲方 - 匹配到公司名称为止
        party_a_patterns = [
            r"甲方[：:]\s*([^\n]{2,30}(?:有限公司|股份有限公司|集团有限公司|有限责任公司|公司|集团)?)",
        ]
        party_a_found = None
        for pattern in party_a_patterns:
            match = re.search(pattern, text)
            if match:
                party_a_found = match.group(1).strip()
                if party_a_found and len(party_a_found) > 2:
                    break

        # 如果上面没找到，尝试更通用的模式
        if not party_a_found:
            match = re.search(r"甲方[：:]\s*([^\n]{2,40})", text)
            if match:
                candidate = match.group(1).strip()
                # 检查是否包含公司关键词
                if any(suffix in candidate for suffix in company_suffixes):
                    party_a_found = candidate

        # 单独提取乙方
        party_b_patterns = [
            r"乙方[：:]\s*([^\n]{2,30}(?:有限公司|股份有限公司|集团有限公司|有限责任公司|公司|集团)?)",
        ]
        party_b_found = None
        for pattern in party_b_patterns:
            match = re.search(pattern, text)
            if match:
                party_b_found = match.group(1).strip()
                if party_b_found and len(party_b_found) > 2:
                    break

        # 如果上面没找到，尝试更通用的模式
        if not party_b_found:
            match = re.search(r"乙方[：:]\s*([^\n]{2,40})", text)
            if match:
                candidate = match.group(1).strip()
                # 检查是否包含公司关键词
                if any(suffix in candidate for suffix in company_suffixes):
                    party_b_found = candidate

        # 构建签约方列表
        if party_a_found:
            parties.append(party_a_found)
        if party_b_found:
            parties.append(party_b_found)

        # 如果没找到，尝试从"甲方是"、"乙方是"等模式提取
        if len(parties) < 2:
            if not party_a_found:
                match = re.search(r"甲方\s*(?:是|为)\s*([^\n，。]{2,30})", text)
                if match and any(s in match.group(1) for s in company_suffixes):
                    parties.insert(0, match.group(1).strip())

            if not party_b_found:
                match = re.search(r"乙方\s*(?:是|为)\s*([^\n，。]{2,30})", text)
                if match and any(s in match.group(1) for s in company_suffixes):
                    if len(parties) > 1:
                        parties[1] = match.group(1).strip()
                    else:
                        parties.append(match.group(1).strip())

        if not parties:
            parties = []

        return parties[:2]
    
    def _extract_amount(self, text: str) -> Optional[float]:
        # 优先匹配明确的合同总金额/合计行
        total_patterns = [
            r"(?:合同(?:金额|价款|总[价额])|总金额|总价款?|价税合计|合计|费用总?[额计])[：:]\s*(?:人民币|rmb)?\s*[【\[（(￥¥]?\s*([\d,]+(?:\.\d{1,2})?)\s*[】\]）)]?\s*(?:元|万)?",
            r"支付\s*(?:人民币|rmb)?\s*[【\[]?\s*([\d,]+(?:\.\d{1,2})?)\s*[】\]]?\s*(?:元|万)",
            r"人民币\s*[【\[]?\s*([\d,]+(?:\.\d{1,2})?)\s*[】\]]?\s*元",
        ]
        for pattern in total_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(",", "").replace("，", "")
                try:
                    amount = float(amount_str)
                    if "万" in match.group(0):
                        amount *= 10000
                    if amount > 0:
                        return amount
                except:
                    pass

        # 没有明确总金额时，收集所有￥金额，取最大值作为合同总金额
        all_amounts = []
        for match in re.finditer(r"(?:¥|￥)\s*[【\[]?\s*([\d,]+(?:\.\d{1,2})?)", text):
            amount_str = match.group(1).replace(",", "").replace("，", "")
            try:
                amount = float(amount_str)
                if amount > 0:
                    all_amounts.append(amount)
            except:
                pass

        # 万元模式
        for match in re.finditer(r"([\d,]+(?:\.\d{1,2})?)\s*万元", text):
            amount_str = match.group(1).replace(",", "").replace("，", "")
            try:
                amount = float(amount_str) * 10000
                if amount > 0:
                    all_amounts.append(amount)
            except:
                pass

        if all_amounts:
            return max(all_amounts)
        return None
    
    def _classify_contract(self, text: str) -> str:
        # 先从标题判断（权重最高）
        title = self._extract_title(text)
        title_lower = (title or "").lower()

        # 按优先级排序：采购优先于服务（标题常见"采购及服务"应归为采购）
        title_rules = [
            ("采购合同", ["采购", "购买", "购销", "买卖", "订购"]),
            ("销售合同", ["销售", "卖出", "经销"]),
            ("租赁合同", ["租赁", "租用", "出租"]),
            ("人力合同", ["劳动", "聘用", "雇佣", "用工"]),
            ("NDA保密协议", ["保密协议", "nda", "竞业"]),
            ("投资协议", ["投资", "融资", "股权"]),
            ("服务合同", ["服务", "运维", "技术服务", "咨询", "外包"]),
        ]
        for contract_type, kws in title_rules:
            if any(kw in title_lower for kw in kws):
                return contract_type

        # 标题无法判断时，按正文关键词频率判断
        # NDA需要"保密协议"整体出现才算，单独的"保密"是通用条款不计分
        keywords = {
            "NDA保密协议": ["保密协议", "NDA", "竞业禁止", "竞业限制"],
            "采购合同": ["采购", "购买", "供货", "供应商", "购销"],
            "销售合同": ["销售", "卖出", "经销", "代理销售"],
            "租赁合同": ["租赁", "租用", "出租", "场地租", "办公室"],
            "服务合同": ["服务", "咨询", "开发", "维护", "运维", "技术支持"],
            "人力合同": ["劳动合同", "聘用", "雇佣", "员工", "用工"],
            "投资协议": ["投资", "融资", "股权", "股东"],
        }
        
        text_lower = text.lower()
        scores = {}
        
        for contract_type, type_keywords in keywords.items():
            score = sum(text_lower.count(kw.lower()) for kw in type_keywords)
            if score > 0:
                scores[contract_type] = score
        
        if scores:
            return max(scores, key=scores.get)
        return "其他"
    
    def _extract_department(self, text: str) -> str:
        text_lower = text.lower()
        
        dept_keywords = {
            "科技中心": ["技术", "开发", "系统", "软件", "服务器", "云服务", "IT"],
            "财务中心": ["财务", "会计", "付款", "收款", "发票"],
            "法务合规中心": ["法务", "法律", "合规", "律师"],
            "风控中心": ["风控", "风险", "审计"],
            "普惠金融": ["金融", "贷款", "信贷", "普惠"],
            "人力行政中心": ["人力", "行政", "招聘", "员工", "人事"],
        }
        
        scores = {}
        for dept, keywords in dept_keywords.items():
            score = sum(1 for kw in keywords if kw.lower() in text_lower)
            if score > 0:
                scores[dept] = score
        
        if scores:
            return max(scores, key=scores.get)
        return "其他"
    
    def _extract_date(self, text: str, date_type: str = "start") -> Optional[str]:
        if date_type == "signed":
            # 签订时间优先从合同末尾（盖章处）提取手写日期
            # 策略1：优先匹配合同末尾的日期（通常是盖章处的手写日期）
            # 取文本最后2000字符（覆盖签字盖章页）
            tail_text = text[-2000:] if len(text) > 2000 else text
            
            # 匹配末尾的各种日期格式（手写日期通常在盖章处）
            tail_patterns = [
                # 匹配：2024年6月15日、2024年06月15日
                r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
                # 匹配：2024-06-15、2024/06/15
                r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
                # 匹配：二〇二四年六月十五日（中文数字）
                r"[二〇一九八七六五四三二一零]{4}年[一二三四五六七八九十]{1,2}月[一二三四五六七八九十]{1,3}日",
            ]
            
            # 从后往前查找最后一个日期（最接近盖章处）
            last_date = None
            for pattern in tail_patterns:
                matches = list(re.finditer(pattern, tail_text))
                if matches:
                    # 取最后一个匹配（最接近文档末尾）
                    last_match = matches[-1]
                    try:
                        if len(last_match.groups()) == 3:
                            year, month, day = last_match.groups()
                            date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                            # 验证日期有效性
                            datetime.strptime(date_str, "%Y-%m-%d")
                            last_date = date_str
                            break
                    except:
                        continue
            
            if last_date:
                return last_date
            
            # 策略2：如果末尾没找到，尝试匹配明确标注的签订日期
            patterns = [
                r"签订[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"签定[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"签署[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"签约[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        date_str = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
                        if "/" in date_str:
                            date_str = date_str.replace("/", "-")
                        datetime.strptime(date_str, "%Y-%m-%d")
                        return date_str
                    except:
                        pass
        elif date_type == "start":
            patterns = [
                r"生效[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"开始[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"起始[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"建立劳动关系[之的]?[日期时间]?[，,、即]\s*[【\[]?(\d{4})[】\]]?\s*年\s*[【\[]?(\d{1,2})[】\]]?\s*月\s*[【\[]?(\d{1,2})[】\]]?\s*日",
                r"自\s*[【\[]?(\d{4})[】\]]?\s*年\s*[【\[]?(\d{1,2})[】\]]?\s*月\s*[【\[]?(\d{1,2})[】\]]?\s*日",
                r"服务期限[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
            ]
        else:  # end
            patterns = [
                r"结束[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"终止[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"到期[日期时间]?[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"有效期[至到]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"期限[至到]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
                r"至\s*[【\[]?(\d{4})[】\]]?\s*年\s*[【\[]?(\d{1,2})[】\]]?\s*月\s*[【\[]?(\d{1,2})[】\]]?\s*日\s*止",
                r"止[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日]?)",
            ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if len(match.groups()) == 3:
                        year, month, day = match.groups()
                        date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                    else:
                        date_str = match.group(1).replace("年", "-").replace("月", "-").replace("日", "")
                    if "/" in date_str:
                        date_str = date_str.replace("/", "-")
                    
                    # 验证日期格式
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except:
                    pass
        
        # 如果上面的模式都没匹配到，尝试提取"自...至..."或"从...到..."格式
        if date_type == "start":
            range_match = re.search(r"[自从]\s*[【\[]?(\d{4})[】\]]?\s*年\s*[【\[]?(\d{1,2})[】\]]?\s*月\s*[【\[]?(\d{1,2})[】\]]?\s*日\s*[至到起]", text)
            if range_match:
                try:
                    year, month, day = range_match.groups()
                    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except:
                    pass
        elif date_type == "end":
            range_match = re.search(r"[至到]\s*[【\[]?(\d{4})[】\]]?\s*年\s*[【\[]?(\d{1,2})[】\]]?\s*月\s*[【\[]?(\d{1,2})[】\]]?\s*日\s*止?", text)
            if range_match:
                try:
                    year, month, day = range_match.groups()
                    date_str = f"{year}-{int(month):02d}-{int(day):02d}"
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except:
                    pass
        
        return None
    
    def analyze_risk(self, text: str) -> Dict[str, Any]:
        risk_points = []
        text_lower = text.lower()
        
        if "预付款" in text_lower or "首付" in text_lower:
            amount_match = re.search(r"预付款.*?(\d+)", text)
            if amount_match:
                risk_points.append({
                    "category": "付款条款",
                    "description": f"合同约定预付款: {amount_match.group(1)}",
                    "severity": "medium",
                    "suggestion": "建议确认预付款比例是否合理"
                })
        
        if "违约金" in text_lower:
            risk_points.append({
                "category": "违约责任",
                "description": "合同包含违约金条款",
                "severity": "low",
                "suggestion": "确认违约金比例是否在合理范围"
            })
        
        if "知识产权" in text_lower or "版权" in text_lower:
            risk_points.append({
                "category": "知识产权",
                "description": "合同涉及知识产权条款",
                "severity": "medium",
                "suggestion": "建议明确知识产权归属"
            })
        
        if "仲裁" in text_lower:
            risk_points.append({
                "category": "争议解决",
                "description": "约定仲裁解决争议",
                "severity": "low",
                "suggestion": "注意保留相关证据材料"
            })
        
        overall_risk = "high" if len(risk_points) >= 3 else "medium" if len(risk_points) >= 1 else "low"
        
        return {
            "overall_risk": overall_risk,
            "risk_points": risk_points,
            "summary": self._generate_risk_summary(risk_points)
        }
    
    def _generate_risk_summary(self, risk_points: list) -> str:
        if not risk_points:
            return "合同未发现明显风险点，请放心签署。"
        
        high_count = sum(1 for p in risk_points if p["severity"] == "high")
        medium_count = sum(1 for p in risk_points if p["severity"] == "medium")
        
        if high_count > 0:
            return f"合同存在 {high_count} 个高风险点和 {medium_count} 个中风险点，建议仔细审核后签署。"
        elif medium_count > 0:
            return f"合同存在 {medium_count} 个中风险点，建议关注相关条款后签署。"
        else:
            return "合同整体风险较低，可正常签署。"

contract_parser = ContractParser()
