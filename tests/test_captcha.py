"""测试验证码获取"""
from services import BifawClient
import time

print("="*80)
print("🧪 测试验证码获取")
print("="*80)

client = BifawClient()

print("\n【步骤1】初始化浏览器（带反检测配置）")
driver = client._init_driver(headless=False)  # 不使用headless以便观察

try:
    print("✅ 浏览器初始化成功")
    
    print("\n【步骤2】访问登录页面")
    driver.get("https://www.bifaw.com/member/login.php")
    time.sleep(3)
    
    print(f"当前URL: {driver.current_url}")
    print(f"页面标题: {driver.title}")
    
    # 检查是否被拦截
    if "提示信息" in driver.title or "验证" in driver.title.lower():
        print("❌ 页面被拦截，显示验证提示")
        
        # 保存页面
        with open("debug_html/blocked_page.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        print("已保存页面: debug_html/blocked_page.html")
    else:
        print("✅ 页面正常加载")
        
        print("\n【步骤3】尝试获取验证码")
        try:
            captcha_b64 = client._capture_captcha_base64(driver)
            print(f"✅ 成功获取验证码，长度: {len(captcha_b64)} 字符")
            
            # 保存验证码图片
            import base64
            captcha_data = base64.b64decode(captcha_b64)
            with open("captcha_test.png", "wb") as f:
                f.write(captcha_data)
            print("验证码已保存: captcha_test.png")
            
        except Exception as e:
            print(f"❌ 获取验证码失败: {e}")
            
            # 保存页面
            with open("debug_html/captcha_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("已保存页面: debug_html/captcha_page.html")
    
    # 等待观察
    print("\n浏览器将保持打开30秒，请观察...")
    time.sleep(30)
    
finally:
    driver.quit()
    print("\n✅ 测试完成")

print("="*80)
