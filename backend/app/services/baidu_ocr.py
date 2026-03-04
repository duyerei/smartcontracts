import requests
import base64
import json
import os
import tempfile
from typing import Optional, Dict, Any
from app.config import config

class BaiduOCR:
    def __init__(self):
        self.api_key = config.BAIDU_OCR_API_KEY
        self.secret_key = config.BAIDU_OCR_SECRET_KEY
        self.access_token = None
    
    def get_access_token(self) -> str:
        if self.access_token:
            return self.access_token
        
        auth_url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        response = requests.post(auth_url, params=params)
        result = response.json()
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            return self.access_token
        else:
            raise Exception(f"获取百度OCR access_token失败: {result}")
    
    def recognize_text(self, image_path: str) -> Dict[str, Any]:
        access_token = self.get_access_token()
        
        url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"
        
        with open(image_path, 'rb') as f:
            image = base64.b64encode(f.read()).decode()
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {'image': image}
        
        response = requests.post(url, headers=headers, data=data)
        result = response.json()
        
        if "words_result" in result:
            text = "\n".join([w.get("words", "") for w in result.get("words_result", [])])
            return {
                "success": True,
                "text": text,
                "words_count": len(result.get("words_result", []))
            }
        else:
            return {
                "success": False,
                "error": result.get("error_msg", "未知错误"),
                "text": ""
            }
    
    def recognize_pdf_online(self, pdf_path: str, num_pages: int = 10) -> str:
        """使用百度OCR在线API识别PDF（推荐用于扫描件）- 使用通用OCR接口"""
        access_token = self.get_access_token()
        
        try:
            from pdf2image import convert_from_path
            
            images = convert_from_path(pdf_path, first_page=1, last_page=num_pages, dpi=150)
            all_text = []
            
            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={access_token}"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            for i, image in enumerate(images):
                import io
                img_byte_arr = io.BytesIO()
                image.save(img_byte_arr, format='JPEG', quality=90)
                img_base64 = base64.b64encode(img_byte_arr.getvalue()).decode()
                
                data = {'image': img_base64}
                response = requests.post(url, headers=headers, data=data, timeout=30)
                result = response.json()
                
                if "words_result" in result:
                    text = "\n".join([w.get("words", "") for w in result.get("words_result", [])])
                    all_text.append(f"--- 第{i+1}页 ---\n{text}")
                elif "error_code" in result:
                    return f"OCR识别失败: {result.get('error_msg', '未知错误')}"
            
            if all_text:
                return "\n\n".join(all_text)
            return "未能识别到文字"
            
        except ImportError:
            return "pdf2image未安装"
        except Exception as e:
            return f"PDF识别异常: {str(e)}"
    
    def recognize_pdf_with_fitz(self, pdf_path: str, num_pages: int = 10) -> str:
        """使用PyMuPDF(fitz)将PDF转为图片再识别（无需Poppler）"""
        try:
            import fitz
            import io
            
            doc = fitz.open(pdf_path)
            pages_to_read = min(num_pages, len(doc))
            all_text = []
            
            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/general_basic?access_token={self.get_access_token()}"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            for i in range(pages_to_read):
                page = doc[i]
                
                text = page.get_text()
                if text and len(text.strip()) > 10:
                    all_text.append(f"--- 第{i+1}页 ---\n{text}")
                    continue
                
                images = page.get_images()
                if images:
                    for img_index, img in enumerate(images):
                        xref = img[0]
                        base_image = doc.extract_image(xref)
                        img_bytes = base_image["image"]
                        
                        img_base64 = base64.b64encode(img_bytes).decode()
                        
                        data = {'image': img_base64}
                        response = requests.post(url, headers=headers, data=data, timeout=30)
                        result = response.json()
                        
                        if "words_result" in result:
                            text = "\n".join([w.get("words", "") for w in result.get("words_result", [])])
                            all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        elif "error_code" in result:
                            all_text.append(f"--- 第{i+1}页 --- OCR识别失败: {result.get('error_msg', '未知错误')}")
                        break
            
            doc.close()
            
            if all_text:
                return "\n\n".join(all_text)
            return "PDF解析失败: 未能提取任何内容"
            
        except ImportError:
            return "PyMuPDF未安装"
        except Exception as e:
            return f"PDF识别异常: {str(e)}"
    
    def recognize_pdf(self, pdf_path: str, num_pages: int = None) -> str:
        """智能选择PDF解析方式：优先使用PyMuPDF提取文字和图片
        
        Args:
            pdf_path: PDF文件路径
            num_pages: 最多读取页数，None表示智能判断
        """
        import fitz
        try:
            doc = fitz.open(pdf_path)
            total_pages = len(doc)
            
            # 智能判断读取页数
            if num_pages is None:
                if total_pages <= 20:
                    # 短合同：全部读取
                    num_pages = total_pages
                elif total_pages <= 50:
                    # 中等合同：前15页 + 最后5页
                    num_pages = 20
                else:
                    # 长合同：前20页 + 最后5页 + 中间抽样
                    num_pages = 30
            
            has_text = False
            has_images = False
            for i in range(min(num_pages, total_pages)):
                page = doc[i]
                text = page.get_text()
                if text and len(text.strip()) > 10:
                    has_text = True
                images = page.get_images()
                if images:
                    has_images = True
            
            doc.close()
            
            if has_text:
                return self._extract_text_with_fitz_smart(pdf_path, total_pages, num_pages)
            elif has_images:
                return self.recognize_pdf_with_fitz_smart(pdf_path, total_pages, num_pages)
            else:
                return "PDF解析失败: 无法识别PDF内容"
                
        except Exception as e:
            return f"PDF解析失败: {str(e)}"
    
    def _extract_text_with_fitz(self, pdf_path: str, num_pages: int = 10) -> str:
        """使用PyMuPDF提取PDF文本（简单版本，向后兼容）"""
        import fitz
        try:
            doc = fitz.open(pdf_path)
            all_text = []
            pages_to_read = min(num_pages, len(doc))
            
            for i in range(pages_to_read):
                page = doc[i]
                text = page.get_text()
                if text:
                    all_text.append(f"--- 第{i+1}页 ---\n{text}")
            
            doc.close()
            
            if all_text:
                return "\n\n".join(all_text)
            return ""
        except Exception as e:
            return f"文本提取失败: {str(e)}"
    
    def _extract_text_with_fitz_smart(self, pdf_path: str, total_pages: int, max_pages: int) -> str:
        """智能提取PDF文本：根据合同长度采用不同策略"""
        import fitz
        try:
            doc = fitz.open(pdf_path)
            all_text = []
            pages_read = []
            
            if total_pages <= 20:
                # 短合同：全部读取
                for i in range(total_pages):
                    page = doc[i]
                    text = page.get_text()
                    if text:
                        all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        pages_read.append(i+1)
            
            elif total_pages <= 50:
                # 中等合同：前15页 + 最后5页
                for i in range(min(15, total_pages)):
                    page = doc[i]
                    text = page.get_text()
                    if text:
                        all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        pages_read.append(i+1)
                
                # 最后5页
                for i in range(max(15, total_pages - 5), total_pages):
                    page = doc[i]
                    text = page.get_text()
                    if text:
                        all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        pages_read.append(i+1)
            
            else:
                # 长合同：前20页 + 最后5页 + 中间抽样
                for i in range(min(20, total_pages)):
                    page = doc[i]
                    text = page.get_text()
                    if text:
                        all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        pages_read.append(i+1)
                
                # 中间抽样（每10页读1页）
                for i in range(20, max(20, total_pages - 5), 10):
                    if i < total_pages:
                        page = doc[i]
                        text = page.get_text()
                        if text:
                            all_text.append(f"--- 第{i+1}页（抽样）---\n{text}")
                            pages_read.append(i+1)
                
                # 最后5页
                for i in range(max(20, total_pages - 5), total_pages):
                    page = doc[i]
                    text = page.get_text()
                    if text:
                        all_text.append(f"--- 第{i+1}页 ---\n{text}")
                        pages_read.append(i+1)
            
            doc.close()
            
            if all_text:
                summary = f"[已读取 {len(pages_read)}/{total_pages} 页]\n\n"
                return summary + "\n\n".join(all_text)
            return ""
        except Exception as e:
            return f"文本提取失败: {str(e)}"
    
    def recognize_pdf_with_fitz_smart(self, pdf_path: str, total_pages: int, max_pages: int) -> str:
        """智能OCR识别：根据合同长度采用不同策略
        
        对于图片拼接型PDF，将整页渲染为图片后再OCR识别
        """
        try:
            import fitz
            import io
            import time
            from PIL import Image
            
            doc = fitz.open(pdf_path)
            all_text = []
            pages_read = []
            
            url = f"https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic?access_token={self.get_access_token()}"
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            
            # 确定要读取的页码列表
            pages_to_read = []
            if total_pages <= 20:
                pages_to_read = list(range(total_pages))
            elif total_pages <= 50:
                pages_to_read = list(range(min(15, total_pages)))
                pages_to_read.extend(range(max(15, total_pages - 5), total_pages))
            else:
                pages_to_read = list(range(min(20, total_pages)))
                pages_to_read.extend(range(20, max(20, total_pages - 5), 10))
                pages_to_read.extend(range(max(20, total_pages - 5), total_pages))
            
            ocr_call_count = 0  # 记录OCR调用次数
            
            for i in pages_to_read:
                page = doc[i]
                
                # 先尝试提取文本
                text = page.get_text()
                if text and len(text.strip()) > 50:  # 提高阈值，确保是真正的文本
                    label = f"--- 第{i+1}页 ---" if i < 20 or i >= total_pages - 5 else f"--- 第{i+1}页（抽样）---"
                    all_text.append(f"{label}\n{text}")
                    pages_read.append(i+1)
                    continue
                
                # 如果没有文本或文本很少，将整页渲染为图片后OCR
                # 添加延迟避免QPS限制（每秒最多2次请求）
                if ocr_call_count > 0:
                    time.sleep(0.6)  # 600ms延迟
                
                try:
                    # 将页面渲染为图片（提高分辨率以改善OCR效果）
                    mat = fitz.Matrix(2.0, 2.0)  # 2倍缩放
                    pix = page.get_pixmap(matrix=mat)
                    img_bytes = pix.tobytes("png")
                    
                    # 转换为base64
                    img_base64 = base64.b64encode(img_bytes).decode()
                    
                    data = {'image': img_base64}
                    
                    # 添加重试机制
                    max_retries = 3
                    for retry in range(max_retries):
                        try:
                            response = requests.post(url, headers=headers, data=data, timeout=30)
                            result = response.json()
                            ocr_call_count += 1
                            
                            if "words_result" in result:
                                text = "\n".join([w.get("words", "") for w in result.get("words_result", [])])
                                label = f"--- 第{i+1}页 ---" if i < 20 or i >= total_pages - 5 else f"--- 第{i+1}页（抽样）---"
                                all_text.append(f"{label}\n{text}")
                                pages_read.append(i+1)
                                break
                            elif "error_code" in result:
                                error_msg = result.get('error_msg', '未知错误')
                                # 如果是QPS限制，等待后重试
                                if "qps" in error_msg.lower() or "limit" in error_msg.lower():
                                    if retry < max_retries - 1:
                                        wait_time = (retry + 1) * 2
                                        print(f"第{i+1}页遇到QPS限制，等待{wait_time}秒后重试...")
                                        time.sleep(wait_time)  # 递增等待时间
                                        continue
                                all_text.append(f"--- 第{i+1}页 --- OCR识别失败: {error_msg}")
                                break
                        except Exception as e:
                            if retry < max_retries - 1:
                                time.sleep(1)
                                continue
                            all_text.append(f"--- 第{i+1}页 --- OCR请求异常: {str(e)}")
                            break
                except Exception as e:
                    all_text.append(f"--- 第{i+1}页 --- 页面渲染失败: {str(e)}")
            
            doc.close()
            
            if all_text:
                summary = f"[已读取 {len(pages_read)}/{total_pages} 页]\n\n"
                return summary + "\n\n".join(all_text)
            return "PDF解析失败: 未能提取任何内容"
            
        except ImportError:
            return "PyMuPDF未安装"
        except Exception as e:
            return f"PDF识别异常: {str(e)}"
    
    def extract_text_from_file(self, file_path: str) -> str:
        ext = file_path.lower().split('.')[-1]
        
        if ext == 'pdf':
            return self.recognize_pdf(file_path)
        elif ext in ['jpg', 'jpeg', 'png', 'bmp']:
            result = self.recognize_text(file_path)
            return result.get("text", "")
        elif ext == 'docx':
            return self._extract_text_from_docx(file_path)
        elif ext == 'doc':
            return self._extract_text_from_doc(file_path)
        else:
            return "不支持的文件格式"
    
    def _extract_text_from_doc(self, file_path: str) -> str:
        """从旧版 .doc 文件提取文本
        策略：先用 COM 接口将 .doc 转为 PDF，再走已有的 PDF 解析流程
        优先级：WPS COM 转PDF → Word COM 转PDF → LibreOffice 转PDF
        """
        import os
        import shutil
        import tempfile
        abs_path = os.path.abspath(file_path)
        print(f"[DOC提取] 文件: {abs_path}")

        pdf_path = self._convert_doc_to_pdf(abs_path)
        if pdf_path:
            try:
                print(f"[DOC提取] 转PDF成功: {pdf_path}，开始解析PDF...")
                text = self.recognize_pdf(pdf_path)
                print(f"[DOC提取] PDF解析完成，文本长度: {len(text)}")
                # 清理临时PDF
                try:
                    os.remove(pdf_path)
                    os.rmdir(os.path.dirname(pdf_path))
                except:
                    pass
                return text
            except Exception as e:
                print(f"[DOC提取] PDF解析失败: {e}")
                try:
                    os.remove(pdf_path)
                    os.rmdir(os.path.dirname(pdf_path))
                except:
                    pass

        return "无法解析 .doc 文件，请转换为 .docx 后重试"

    def _convert_doc_to_pdf(self, abs_path: str) -> str:
        """将 .doc 文件转换为 PDF，返回临时 PDF 路径，失败返回 None"""
        import os
        import shutil
        import tempfile

        # 方案1：WPS COM 转 PDF（优先，因为 WPS 更稳定）
        try:
            import win32com.client
            import pythoncom
            pythoncom.CoInitialize()
            try:
                wps = win32com.client.Dispatch("Kwps.Application")
                wps.Visible = False
                tmp_dir = tempfile.mkdtemp()
                tmp_doc = os.path.join(tmp_dir, "temp_doc.doc")
                tmp_pdf = os.path.join(tmp_dir, "temp_doc.pdf")
                shutil.copy2(abs_path, tmp_doc)
                doc = wps.Documents.Open(tmp_doc, ReadOnly=True)
                # WPS SaveAs 格式17 = PDF
                doc.SaveAs(tmp_pdf, FileFormat=17)
                doc.Close(False)
                wps.Quit()
                if os.path.exists(tmp_pdf):
                    print(f"[DOC转PDF] WPS COM 转换成功")
                    return tmp_pdf
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception as e:
                print(f"[DOC转PDF] WPS COM 失败: {e}")
                try:
                    wps.Quit()
                except:
                    pass
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            pass

        # 方案2：Word COM (DispatchEx) 转 PDF
        try:
            import win32com.client
            import pythoncom
            pythoncom.CoInitialize()
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                tmp_dir = tempfile.mkdtemp()
                tmp_doc = os.path.join(tmp_dir, "temp_doc.doc")
                tmp_pdf = os.path.join(tmp_dir, "temp_doc.pdf")
                shutil.copy2(abs_path, tmp_doc)
                doc = word.Documents.Open(tmp_doc, ReadOnly=True, ConfirmConversions=False)
                # Word SaveAs2 格式17 = PDF
                doc.SaveAs2(tmp_pdf, FileFormat=17)
                doc.Close(False)
                word.Quit()
                if os.path.exists(tmp_pdf):
                    print(f"[DOC转PDF] Word COM 转换成功")
                    return tmp_pdf
                shutil.rmtree(tmp_dir, ignore_errors=True)
            except Exception as e:
                print(f"[DOC转PDF] Word COM 失败: {e}")
                try:
                    word.Quit()
                except:
                    pass
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            pass

        # 方案3：LibreOffice 转 PDF
        try:
            import subprocess
            tmp_dir = tempfile.mkdtemp()
            subprocess.run(
                ["soffice", "--headless", "--convert-to", "pdf", "--outdir", tmp_dir, abs_path],
                capture_output=True, timeout=60
            )
            pdf_name = os.path.splitext(os.path.basename(abs_path))[0] + ".pdf"
            pdf_path = os.path.join(tmp_dir, pdf_name)
            if os.path.exists(pdf_path):
                print(f"[DOC转PDF] LibreOffice 转换成功")
                return pdf_path
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as e:
            print(f"[DOC转PDF] LibreOffice 失败: {e}")

        print(f"[DOC转PDF] 所有方案均失败")
        return None

    def _extract_text_from_doc(self, file_path: str) -> str:
        """从旧版 .doc 文件提取文本
        优先级：win32com DispatchEx → WPS COM → LibreOffice 转 docx
        """
        import os
        abs_path = os.path.abspath(file_path)
        print(f"[DOC提取] 文件: {abs_path}")

        # 方案1：win32com DispatchEx（避免 Dispatch 的远程过程调用失败问题）
        try:
            import win32com.client
            import pythoncom
            import shutil
            import tempfile
            pythoncom.CoInitialize()
            try:
                word = win32com.client.DispatchEx("Word.Application")
                word.Visible = False
                word.DisplayAlerts = 0
                # 复制到临时目录（避免中文/Unicode路径问题）
                tmp_dir = tempfile.mkdtemp()
                tmp_path = os.path.join(tmp_dir, "temp_doc.doc")
                shutil.copy2(abs_path, tmp_path)
                doc = word.Documents.Open(tmp_path, ReadOnly=True, ConfirmConversions=False)
                text = doc.Content.Text
                doc.Close(False)
                word.Quit()
                shutil.rmtree(tmp_dir, ignore_errors=True)
                print(f"[DOC提取] win32com DispatchEx 成功，文本长度: {len(text)}")
                return text
            except Exception as e:
                print(f"[DOC提取] win32com DispatchEx 失败: {e}")
                try:
                    word.Quit()
                except:
                    pass
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            print("[DOC提取] win32com 未安装，跳过")

        # 方案2：WPS COM 接口（Kwps.Application）
        try:
            import win32com.client
            import pythoncom
            import shutil
            import tempfile
            pythoncom.CoInitialize()
            try:
                wps = win32com.client.Dispatch("Kwps.Application")
                wps.Visible = False
                tmp_dir = tempfile.mkdtemp()
                tmp_path = os.path.join(tmp_dir, "temp_doc.doc")
                shutil.copy2(abs_path, tmp_path)
                doc = wps.Documents.Open(tmp_path, ReadOnly=True)
                text = doc.Content.Text
                doc.Close(False)
                wps.Quit()
                shutil.rmtree(tmp_dir, ignore_errors=True)
                print(f"[DOC提取] WPS COM 成功，文本长度: {len(text)}")
                return text
            except Exception as e:
                print(f"[DOC提取] WPS COM 失败: {e}")
                try:
                    wps.Quit()
                except:
                    pass
            finally:
                pythoncom.CoUninitialize()
        except ImportError:
            pass

        # 方案3：LibreOffice 转成 docx 再提取
        try:
            import subprocess, tempfile, shutil
            tmp_dir = tempfile.mkdtemp()
            result = subprocess.run(
                ["soffice", "--headless", "--convert-to", "docx", "--outdir", tmp_dir, abs_path],
                capture_output=True, timeout=30
            )
            docx_name = os.path.splitext(os.path.basename(abs_path))[0] + ".docx"
            docx_path = os.path.join(tmp_dir, docx_name)
            if os.path.exists(docx_path):
                text = self._extract_text_from_docx(docx_path)
                shutil.rmtree(tmp_dir, ignore_errors=True)
                print(f"[DOC提取] LibreOffice 转换成功，文本长度: {len(text)}")
                return text
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception as e:
            print(f"[DOC提取] LibreOffice 失败: {e}")

        return "无法解析 .doc 文件，请转换为 .docx 后重试"

baidu_ocr = BaiduOCR()
