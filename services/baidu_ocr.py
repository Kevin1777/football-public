"""
百度OCR服务模块
用于自动识别必发网登录验证码
"""
import base64
import logging
import os
from typing import Optional, Tuple
import requests
from io import BytesIO

logger = logging.getLogger(__name__)


def preprocess_captcha_image(image_data: bytes) -> bytes:
    """
    预处理验证码图片，提升OCR识别率
    - 转灰度
    - 二值化
    - 去噪
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
        
        # 打开图片
        img = Image.open(BytesIO(image_data))
        
        # 转为灰度图
        img = img.convert('L')
        
        # 增强对比度
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(2.0)
        
        # 二值化处理
        threshold = 128
        img = img.point(lambda x: 0 if x < threshold else 255, '1')
        
        # 转回L模式进行去噪
        img = img.convert('L')
        
        # 中值滤波去噪
        img = img.filter(ImageFilter.MedianFilter(size=3))
        
        # 保存到字节流
        output = BytesIO()
        img.save(output, format='PNG')
        return output.getvalue()
        
    except Exception as e:
        logger.warning(f"图片预处理失败: {e}，使用原图")
        return image_data


class BaiduOCR:
    """百度OCR API封装类"""
    
    # API配置
    TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
    # 使用高精度版本，更适合识别复杂验证码
    OCR_URL = "https://aip.baidubce.com/rest/2.0/ocr/v1/accurate_basic"
    
    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        初始化百度OCR
        
        Args:
            api_key: 百度OCR API Key，如果为空则从环境变量读取
            secret_key: 百度OCR Secret Key，如果为空则从环境变量读取
        """
        self.api_key = api_key or os.getenv("BAIDU_OCR_API_KEY")
        self.secret_key = secret_key or os.getenv("BAIDU_OCR_SECRET_KEY")
        self.enabled = os.getenv("BAIDU_OCR_ENABLED", "0") == "1"
        
        if not self.api_key or not self.secret_key:
            logger.warning("百度OCR未配置API密钥，自动识别功能将不可用")
            self.enabled = False
        
        self._access_token: Optional[str] = None
    
    def is_enabled(self) -> bool:
        """检查OCR功能是否启用"""
        return self.enabled and bool(self.api_key) and bool(self.secret_key)
    
    def _get_access_token(self) -> str:
        """
        获取百度OCR Access Token
        
        Returns:
            Access Token字符串
        
        Raises:
            RuntimeError: 获取token失败
        """
        if self._access_token:
            return self._access_token
        
        try:
            response = requests.post(
                self.TOKEN_URL,
                params={
                    "grant_type": "client_credentials",
                    "client_id": self.api_key,
                    "client_secret": self.secret_key,
                },
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            if "access_token" not in result:
                raise RuntimeError(f"获取Access Token失败: {result}")
            
            self._access_token = result["access_token"]
            logger.info("✅ 百度OCR Access Token获取成功")
            return self._access_token
        
        except Exception as e:
            raise RuntimeError(f"获取百度OCR Access Token失败: {e}") from e
    
    def recognize_captcha(self, image_data: bytes) -> Tuple[bool, Optional[str], str]:
        """
        识别验证码图片
        
        Args:
            image_data: 验证码图片的二进制数据
        
        Returns:
            (success, captcha_text, message)
            - success: 是否识别成功
            - captcha_text: 识别出的验证码文字（如果成功）
            - message: 详细信息或错误提示
        """
        if not self.is_enabled():
            return False, None, "百度OCR未启用或未配置"
        
        try:
            # 获取Access Token
            access_token = self._get_access_token()
            
            # 🔥 高精度OCR接口对彩色验证码识别效果更好，不需要预处理
            # 如需启用预处理，取消下面两行的注释
            # logger.info("正在预处理验证码图片...")
            # image_data = preprocess_captcha_image(image_data)
            
            # 将图片转为base64
            image_b64 = base64.b64encode(image_data).decode('utf-8')
            
            # 调用OCR API
            response = requests.post(
                self.OCR_URL,
                params={"access_token": access_token},
                data={"image": image_b64},
                timeout=10
            )
            response.raise_for_status()
            
            result = response.json()
            
            # 检查是否有错误
            if "error_code" in result:
                error_msg = result.get("error_msg", "未知错误")
                logger.error(f"百度OCR识别失败: {error_msg}")
                return False, None, f"OCR识别失败: {error_msg}"
            
            # 提取识别结果
            words_result = result.get("words_result", [])
            if not words_result:
                logger.warning("百度OCR未识别出任何文字")
                return False, None, "未识别出验证码文字"
            
            # 合并所有识别出的文字（验证码通常是单行）
            captcha_text = "".join([item["words"] for item in words_result])
            
            # 🔥 清理识别结果：只保留数字（验证码是4位纯数字）
            import re
            captcha_text = re.sub(r'[^0-9]', '', captcha_text)  # 只保留数字
            
            if not captcha_text:
                return False, None, "识别结果为空（无数字）"
            
            # 🔥 验证码格式检查：必须是4位数字
            if len(captcha_text) != 4:
                logger.warning(f"⚠️  识别出 {len(captcha_text)} 位数字: '{captcha_text}' (期望4位)")
                # 如果识别出的数字少于4位，可能是识别错误
                if len(captcha_text) < 4:
                    return False, None, f"识别位数不足: {captcha_text} ({len(captcha_text)}位，期望4位)"
                # 如果多于4位，取前4位
                elif len(captcha_text) > 4:
                    logger.warning(f"   识别出{len(captcha_text)}位，截取前4位")
                    captcha_text = captcha_text[:4]
            
            logger.info(f"✅ 百度OCR识别成功: {captcha_text} (长度: {len(captcha_text)})")
            return True, captcha_text, "识别成功"
        
        except Exception as e:
            logger.exception("百度OCR识别异常")
            return False, None, f"OCR识别异常: {e}"
    
    def recognize_captcha_from_base64(self, image_b64: str) -> Tuple[bool, Optional[str], str]:
        """
        从base64字符串识别验证码
        
        Args:
            image_b64: base64编码的图片数据（不含data:image前缀）
        
        Returns:
            (success, captcha_text, message)
        """
        try:
            image_data = base64.b64decode(image_b64)
            return self.recognize_captcha(image_data)
        except Exception as e:
            logger.exception("解码base64图片失败")
            return False, None, f"解码base64失败: {e}"
    
    def recognize_captcha_from_file(self, image_path: str) -> Tuple[bool, Optional[str], str]:
        """
        从文件路径识别验证码
        
        Args:
            image_path: 验证码图片文件路径
        
        Returns:
            (success, captcha_text, message)
        """
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            return self.recognize_captcha(image_data)
        except Exception as e:
            logger.exception(f"读取验证码图片失败: {image_path}")
            return False, None, f"读取图片失败: {e}"


# 单例实例
_baidu_ocr_instance: Optional[BaiduOCR] = None


def get_baidu_ocr() -> BaiduOCR:
    """获取百度OCR单例实例"""
    global _baidu_ocr_instance
    if _baidu_ocr_instance is None:
        _baidu_ocr_instance = BaiduOCR()
    return _baidu_ocr_instance
