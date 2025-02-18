# docker run --rm -it google-trends-scraper python google_trends_scraper.py
from playwright.sync_api import sync_playwright
import json
import os
import time

# 定義爬取的 URL 和分類
urls = [
    {"category": "11", "url": "https://trends.google.com.tw/trending?geo=TW&hours=24&category=11"},  # 其他
    {"category": "10", "url": "https://trends.google.com.tw/trending?geo=TW&hours=24&category=10"},  # 法律與政府
    {"category": "14", "url": "https://trends.google.com.tw/trending?geo=TW&hours=24&category=14"},  # 政治
    {"category": "3", "url": "https://trends.google.com.tw/trending?geo=TW&hours=24&category=3"}     # 商業與財經
]

# 自由時報的 URL
ltn_url = "https://www.ltn.com.tw/"

def scrape_trending_keywords():
    results = []
    output_path = "/app/output/trending_keywords.json"  # Docker 容器中的保存路徑

    with sync_playwright() as p:
        # 1. 啟動瀏覽器時，關閉自動化偵測標記，增加隱匿性
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"]  # 關閉自動化檢測
        )

        try:
            # 2. 創建帶自訂 User-Agent / Headers 的 Context
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/114.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept-Language": "zh-TW,zh;q=0.9",
                    "Referer": "https://www.google.com/",
                    "Connection": "keep-alive"
                }
            )

            # ---------------------------
            # 爬取 Google Trends 的熱度資料
            # ---------------------------
            print("開始爬取 Google Trends 資料...")
            for entry in urls:
                category = entry["category"]
                url = entry["url"]

                try:
                    page = context.new_page()
                    # 使用 networkidle 等待網頁完全載入
                    page.goto(url, wait_until="networkidle", timeout=120000)
                    print(f"正在處理分類 {category} 的資料...")

                    # 顯式等待 table 的元素 (最多等 10 秒)
                    selector = "#trend-table > div.enOdEe-wZVHld-zg7Cn-haAclf > table > tbody:nth-child(3) > tr"
                    try:
                        page.wait_for_selector(selector, timeout=10_000)
                    except:
                        print("指定的表格元素在逾時內仍未出現，可能無資料或載入過慢。")

                    # 簡單重試機制：若抓到 0 筆，就 reload 再嘗試一次
                    max_sub_attempts = 2
                    target_rows = []
                    for sub_attempt in range(max_sub_attempts):
                        target_rows = page.query_selector_all(selector)
                        if target_rows:
                            break
                        else:
                            print(f"[分類 {category}] 第 {sub_attempt+1} 次抓取 0 筆，稍等 3 秒後重新整理...")
                            page.wait_for_timeout(8_000)
                            page.reload(wait_until="networkidle")
                            try:
                                page.wait_for_selector(selector, timeout=10_000)
                            except:
                                pass  # 如果還是抓不到，就繼續回圈，最後還是 0 筆

                    # 開始擷取資料
                    for rank, row in enumerate(target_rows, start=1):
                        main_keyword = row.query_selector(".mZ3RIc")
                        main_keyword_text = main_keyword.text_content().strip() if main_keyword else ""

                        related_keywords = [
                            el.get_attribute("data-term") or ""
                            for el in row.query_selector_all('[data-idom-class="b5M0dd"]')
                        ]

                        results.append({
                            "source": "Google Trends",
                            "category": category,
                            "rank": rank,
                            "main_keyword": main_keyword_text,
                            "related_keywords": related_keywords,
                        })

                    print(f"分類 {category} 資料處理完成，共 {len(target_rows)} 條。")

                except Exception as e:
                    print(f"爬取分類 {category} 時出現錯誤: {e}")
                finally:
                    page.close()

            # ---------------------------
            # 爬取自由時報的熱度資料
            # ---------------------------
            print("開始爬取自由時報的資料...")
            page = context.new_page()

            for attempt in range(3):  # 最多嘗試 3 次
                try:
                    # 同樣改用 networkidle
                    page.goto(ltn_url, wait_until="networkidle", timeout=120000)

                    # 若要更精準，可再 wait_for_selector(...) 看自由時報頁面結構
                    hot_keywords = page.query_selector_all('[id^="hot_keyword_area_word_"]')[:20]
                    if not hot_keywords:
                        print("未找到自由時報的熱度關鍵字")
                    else:
                        for rank, element in enumerate(hot_keywords, start=1):
                            try:
                                keyword_text = element.get_attribute("data-desc") or ""
                                link_element = element.query_selector("a")
                                link = link_element.get_attribute("href") if link_element else ""
                                results.append({
                                    "source": "自由時報",
                                    "rank": rank,
                                    "main_keyword": keyword_text,
                                    "link": link,
                                })
                            except Exception as e:
                                print(f"爬取自由時報第 {rank} 條熱度關鍵字時出現錯誤: {e}")

                    print("自由時報資料處理完成，共 {} 條。".format(len(hot_keywords)))
                    break

                except Exception as e:
                    print(f"爬取自由時報資料失敗，重試次數 {attempt + 1}/3：{e}")
                    time.sleep(5)  # 等待 5 秒後重試
                finally:
                    page.close()

            # ---------------------------
            # 保存結果到檔案
            # ---------------------------
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"爬蟲完成，結果已儲存到 {output_path}")

        except Exception as e:
            print(f"爬取過程中出現錯誤: {e}")
            raise
        finally:
            browser.close()


if __name__ == "__main__":
    scrape_trending_keywords()