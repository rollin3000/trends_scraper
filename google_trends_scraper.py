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

# 爬蟲主邏輯
def scrape_trending_keywords():
    results = []
    output_path = "/app/output/trending_keywords.json"  # Docker 容器中的保存路徑

    with sync_playwright() as p:
        # 啟動無頭瀏覽器
        browser = p.chromium.launch(headless=True)

        try:
            # 爬取 Google Trends 的熱度資料
            print("開始爬取 Google Trends 資料...")
            for entry in urls:
                category = entry["category"]
                url = entry["url"]

                try:
                    page = browser.new_page()
                    page.goto(url, wait_until="load", timeout=120000)
                    print(f"正在處理分類 {category} 的資料...")

                    # 抓取目標區域
                    target_rows = page.query_selector_all(
                        "#trend-table > div.enOdEe-wZVHld-zg7Cn-haAclf > table > tbody:nth-child(3) > tr"
                    )

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

            # 爬取自由時報的熱度資料
            print("開始爬取自由時報的資料...")
            page = browser.new_page()

            # 重試邏輯
            for attempt in range(3):  # 最多嘗試 3 次
                try:
                    page.goto(ltn_url, wait_until="load", timeout=120000)
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

            # 保存結果到檔案
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            print(f"爬蟲完成，結果已儲存到 {output_path}")

        except Exception as e:
            print(f"爬取過程中出現錯誤: {e}")
            raise
        finally:
            browser.close()

# 運行爬蟲
if __name__ == "__main__":
    scrape_trending_keywords()