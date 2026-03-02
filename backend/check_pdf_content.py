"""
检查PDF内容类型
"""
import fitz
import os

def check_pdf():
    file_path = "storage/contracts/eb7677bb-f4ab-4352-9611-5c63df78c957.pdf"
    
    # 查找最新合同的文件
    import sys
    sys.path.insert(0, os.path.dirname(__file__))
    from app.database import get_db, Contract
    
    db = next(get_db())
    contract = db.query(Contract).filter(Contract.id == 23).first()
    
    if contract:
        file_path = os.path.join("storage", contract.file_path)
        print(f"检查合同ID 23: {contract.contract_number}")
    else:
        print("使用默认文件路径")
    
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return
    
    doc = fitz.open(file_path)
    total_pages = len(doc)
    
    print(f"PDF总页数: {total_pages}")
    print(f"\n检查每一页的内容类型:")
    print("="*60)
    
    for i in range(total_pages):
        page = doc[i]
        
        # 检查文本
        text = page.get_text()
        text_len = len(text.strip())
        
        # 检查图片
        images = page.get_images()
        image_count = len(images)
        
        # 检查绘图对象
        drawings = page.get_drawings()
        drawing_count = len(drawings)
        
        print(f"第{i+1}页:")
        print(f"  文本长度: {text_len} 字符")
        print(f"  图片数量: {image_count}")
        print(f"  绘图对象: {drawing_count}")
        
        if text_len > 50:
            print(f"  文本预览: {text[:100].replace(chr(10), ' ')}")
        
        if i < 5 or i >= total_pages - 2:  # 显示前5页和后2页的详细信息
            if image_count > 0:
                for idx, img in enumerate(images):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    print(f"    图片{idx+1}: {base_image['width']}x{base_image['height']}, {base_image['ext']}")
        
        print()
    
    doc.close()

if __name__ == "__main__":
    check_pdf()
