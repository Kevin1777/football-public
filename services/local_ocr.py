"""
本地OCR服务模块
使用 ddddocr 进行验证码识别，无API限制
"""
import logging
from typing import Optional, Tuple
import base64

# 🔥 修复 Pillow 10.x 兼容性问题（ANTIALIAS 已重命名为 LANCZOS）
try:
    from PIL import Image
    if not hasattr(Image, 'ANTIALIAS'):
        Image.ANTIALIAS = Image.LANCZOS
except ImportError:
    pass

logger = logging.getLogger(__name__)

# 全局OCR实例（延迟初始化）
_ddddocr_instance = None


def _get_ddddocr():
    """获取ddddocr实例（延迟初始化）"""
    global _ddddocr_instance
    if _ddddocr_instance is None:
        try:
            import ddddocr
            # 尝试不同的初始化方式（兼容不同版本）
            try:
                _ddddocr_instance = ddddocr.DdddOcr(show_ad=False)
            except TypeError:
                # 新版本可能没有show_ad参数
                _ddddocr_instance = ddddocr.DdddOcr()
            logger.info("✅ ddddocr 本地OCR引擎已初始化")
        except ImportError:
            logger.warning("❌ ddddocr 未安装，请运行: pip install ddddocr")
            return None
        except Exception as e:
            logger.error(f"❌ ddddocr 初始化失败: {e}")
            return None
    return _ddddocr_instance


class LocalOCR:
    """本地OCR服务（基于ddddocr）"""
    
    def __init__(self):
        self._ocr = None
        self._initialized = False
    
    def _ensure_initialized(self) -> bool:
        """确保OCR引擎已初始化"""
        if not self._initialized:
            self._ocr = _get_ddddocr()
            self._initialized = True
        return self._ocr is not None
    
    def is_enabled(self) -> bool:
        """检查本地OCR是否可用"""
        return self._ensure_initialized()
    
    def recognize_captcha(self, image_data: bytes) -> Tuple[bool, Optional[str], str]:
        """
        识别验证码图片
        
        Args:
            image_data: 验证码图片的二进制数据
        
        Returns:
            (success, captcha_text, message)
        """
        if not self._ensure_initialized():
            return False, None, "本地OCR未初始化（ddddocr未安装）"
        
        try:
            # 使用ddddocr识别
            result = self._ocr.classification(image_data)
            
            if not result:
                return False, None, "本地OCR未识别出任何文字"
            
            # 清理结果：只保留数字（验证码是4位纯数字）
            import re
            captcha_text = re.sub(r'[^0-9]', '', result)
            
            if not captcha_text:
                logger.warning(f"本地OCR识别结果无数字: '{result}'")
                return False, None, f"识别结果无数字: {result}"
            
            # 验证码格式检查
            if len(captcha_text) != 4:
                logger.warning(f"⚠️ 本地OCR识别出 {len(captcha_text)} 位: '{captcha_text}'")
                if len(captcha_text) < 4:
                    return False, None, f"识别位数不足: {captcha_text}"
                elif len(captcha_text) > 4:
                    captcha_text = captcha_text[:4]
            
            logger.info(f"✅ 本地OCR识别成功: {captcha_text}")
            return True, captcha_text, "识别成功"
            
        except Exception as e:
            logger.exception("本地OCR识别异常")
            return False, None, f"本地OCR异常: {e}"
    
    def recognize_captcha_from_base64(self, image_b64: str) -> Tuple[bool, Optional[str], str]:
        """从base64字符串识别验证码"""
        try:
            image_data = base64.b64decode(image_b64)
            return self.recognize_captcha(image_data)
        except Exception as e:
            return False, None, f"解码base64失败: {e}"


# 单例实例
_local_ocr_instance: Optional[LocalOCR] = None


def get_local_ocr() -> LocalOCR:
    """获取本地OCR单例实例"""
    global _local_ocr_instance
    if _local_ocr_instance is None:
        _local_ocr_instance = LocalOCR()
    return _local_ocr_instance
