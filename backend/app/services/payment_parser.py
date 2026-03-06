"""OA付款申请PDF解析器 - 从PDF中提取付款信息"""
import re
from typing import Dict, Any, Optional
from datetime import datetime


class PaymentParser:
    """解析OA付款申请表单PDF"""

    def parse_payment_pdf(self, file_path: str) -> Dict[str, Any]:
        """从PDF提取付款信息"""
        text = self._extract_text(file_path)
        if not text or len(text.strip()) < 20:
            return {"success": False, "error": "无法从PDF中提取文字"}

        data = {
            "payment_theme": self._extract_theme(text),
            "operator": self._extract_field(text, ["经办人"]),
            "department": self._extract_field(text, ["部门名称", "部门"]),
            "payment_date": self._extract_date(text, ["申请日期"]),
            "application_number": self._extract_field(text, ["申请单号"]),
            "contract_number": self._extract_field(text, ["合同编号"]),
            "project_name": self._extract_field(text, ["项目名称"]),
            "cost_center": self._extract_cost_center(text),
            "payment_reason": self._extract_payment_reason(text),
            "amount": self._extract_total_amount(text),
            "counterparty": self._extract_field(text, ["收款单位", "对方单位"]),
        }

        return {
            "success": True,
            "data": data,
            "raw_text": text[:5000],
        }

    def _extract_text(self, file_path: str) -> str:
        """提取PDF文本：先用PyMuPDF，失败或文字太少则用百度OCR"""
        # 先尝试PyMuPDF（速度快，适合文字型PDF）
        text = ''
        try:
            import fitz
            doc = fitz.open(file_path)
            pages_text = []
            for page in doc:
                pages_text.append(page.get_text())
            doc.close()
            text = "\n".join(pages_text)
        except Exception as e:
            print(f"[PaymentParser] PyMuPDF提取失败: {e}")

        # 如果提取到的文字太少（扫描件/图片型PDF），改用百度OCR
        if not text or len(text.strip()) < 50:
            print(f"[PaymentParser] PyMuPDF文字不足({len(text.strip())}字)，改用百度OCR")
            try:
                from app.services.baidu_ocr import BaiduOCR
                ocr = BaiduOCR()
                text = ocr.recognize_pdf(file_path)
                print(f"[PaymentParser] 百度OCR提取完成，长度: {len(text)}")
            except Exception as e:
                print(f"[PaymentParser] 百度OCR提取失败: {e}")

        return text

    def _extract_theme(self, text: str) -> str:
        """提取付款主题（通常是PDF标题/第一行有意义的文字）"""
        lines = text.strip().split('\n')
        for line in lines[:10]:
            line = line.strip()
            if len(line) > 5 and ("付款" in line or "申请" in line or "报销" in line):
                return line
        # 兜底：取第一行非空文字
        for line in lines[:5]:
            line = line.strip()
            if len(line) > 3:
                return line
        return "OA付款申请"

    def _extract_field(self, text: str, keywords: list) -> Optional[str]:
        """通用字段提取：关键词后面的值"""
        for kw in keywords:
            patterns = [
                rf"{kw}\s*[：:]\s*(.+?)(?:\n|$)",
                rf"{kw}\s+(.+?)(?:\n|$)",
                rf"{kw}\s*[：:]\s*(.+?)(?:\s{{2,}}|\n|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, text)
                if match:
                    val = match.group(1).strip()
                    # 清理多余空格和后续字段
                    val = re.split(r'\s{2,}', val)[0].strip()
                    if val and len(val) < 200:
                        return val
        return None

    def _extract_date(self, text: str, keywords: list) -> Optional[str]:
        """提取日期字段"""
        for kw in keywords:
            match = re.search(rf"{kw}\s*[：:]\s*(\d{{4}}[-/年]\d{{1,2}}[-/月]\d{{1,2}}[日]?)", text)
            if match:
                date_str = match.group(1).replace("年", "-").replace("月", "-").replace("日", "").replace("/", "-")
                try:
                    datetime.strptime(date_str, "%Y-%m-%d")
                    return date_str
                except Exception:
                    pass
        # 兜底：找文本中第一个日期
        match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
        if match:
            return f"{match.group(1)}-{int(match.group(2)):02d}-{int(match.group(3)):02d}"
        return None

    def _extract_cost_center(self, text: str) -> Optional[str]:
        """提取成本中心"""
        match = re.search(r"(?:归属成本中心|成本中心|所属成本中心)\s*[：:]?\s*(.+?)(?:\n|$)", text)
        if match:
            val = match.group(1).strip()
            val = re.split(r'\s{2,}', val)[0].strip()
            if val:
                return val
        # 从费用分摊表格中提取
        match = re.search(r"(?:成本中心)\s*\n?\s*(.+?)(?:\n|技术|业务)", text)
        if match:
            return match.group(1).strip()
        return None

    def _extract_payment_reason(self, text: str) -> Optional[str]:
        """提取付款事由"""
        match = re.search(r"付款事由\s*[：:]?\s*(.+?)(?:\n附件|\n费用分摊|\n合计|$)", text, re.DOTALL)
        if match:
            reason = match.group(1).strip()
            # 限制长度
            if len(reason) > 1000:
                reason = reason[:1000]
            return reason if reason else None
        return None

    def _extract_total_amount(self, text: str) -> Optional[float]:
        """提取合计金额"""
        # 优先匹配"合计分摊金额"或"合计"行
        patterns = [
            r"合计分摊金额[：:]\s*([\d,]+\.?\d*)",
            r"合计.*?([\d,]+\.?\d{2})\s*$",
            r"合\s*计\s*([\d,]+\.?\d{2})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                amount_str = match.group(1).replace(",", "")
                try:
                    amount = float(amount_str)
                    if amount > 0:
                        return amount
                except Exception:
                    pass

        # 兜底：找"分摊金额"列的数字并求和
        amounts = re.findall(r"分摊金额\s*\n?\s*([\d,]+\.?\d{2})", text)
        if not amounts:
            amounts = re.findall(r"([\d,]+\.\d{2})\s*\n", text)
        
        total = 0.0
        for a in amounts:
            try:
                total += float(a.replace(",", ""))
            except Exception:
                pass
        return total if total > 0 else None


payment_parser = PaymentParser()
