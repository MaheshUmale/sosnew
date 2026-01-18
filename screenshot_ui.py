import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://localhost:8501")
        await page.wait_for_timeout(5000)
        await page.screenshot(path="streamlit_ui_final.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
