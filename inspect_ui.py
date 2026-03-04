from playwright.sync_api import sync_playwright
import sys

def run():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            print("正在连接到 http://127.0.0.1:8000 ...")
            page.goto('http://127.0.0.1:8000', timeout=30000)
            page.wait_for_load_state('networkidle')
            
            print("正在检查页面标题和关键文本...")
            title = page.title()
            print(f"页面标题: {title}")
            
            # 检查是否包含我新添加的关键词
            content = page.content()
            has_new_feature = "AI 策略参考点位" in content
            print(f"检测到新功能文本 'AI 策略参考点位': {has_new_feature}")
            
            # 截图保存以便后续查看（如果需要）
            page.screenshot(path='debug_screenshot.png', full_page=True)
            print("截图已保存为 debug_screenshot.png")
            
            # 如果没有新文本，检查一下页面上的 DOM 结构
            if not has_new_feature:
                print("未发现新 UI，正在输出当前页面上的所有 label...")
                labels = page.locator('label').all_inner_texts()
                print("页面 Labels:", labels)
                
        except Exception as e:
            print(f"访问失败: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run()
