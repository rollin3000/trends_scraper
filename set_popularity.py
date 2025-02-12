import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor

# 資料庫連線函數
def get_postgres_connection():
    external_db_url = "postgresql://newsdata_vc3p_user:HXLUZa2xgOH4wk1Eq2witr88llkm7bqG@dpg-cu0om3jtq21c73c06280-a.singapore-postgres.render.com/newsdata_vc3p"
    db_url = os.getenv("DATABASE_URL", external_db_url)
    return psycopg2.connect(db_url)

# 動態熱度加分邏輯
def calculate_popularity_score(keyword, base_score=10):
    # 根據不同關鍵字性質調整分數
    if "政治" in keyword:
        return base_score * 2
    elif "娛樂" in keyword:
        return base_score * 1.5
    elif "災害" in keyword:
        return base_score * 1.2
    else:
        return base_score

# 主要邏輯
def update_news_popularity(keywords_file_path):
    # 檢查關鍵字文件是否存在
    if not os.path.exists(keywords_file_path):
        print(f"無法找到關鍵字文件: {keywords_file_path}")
        return

    # 讀取關鍵字文件
    with open(keywords_file_path, "r", encoding="utf-8") as f:
        try:
            keywords_data = json.load(f)
        except json.JSONDecodeError:
            print("無法解析關鍵字 JSON 文件")
            return

    # 連接資料庫
    conn = get_postgres_connection()
    cur = conn.cursor()

    try:
        for keyword_entry in keywords_data:
            keyword = keyword_entry.get("main_keyword")
            score = calculate_popularity_score(keyword)

            # 查詢匹配的新聞
            cur.execute('''
                SELECT id, title, content, popularity, processing_status
                FROM news
                WHERE (title ILIKE %s OR content ILIKE %s)
                AND processing_status = '未處理'
            ''', (f"%{keyword}%", f"%{keyword}%"))
            matching_news = cur.fetchall()

            # 更新匹配新聞的熱度值和狀態
            for news in matching_news:
                news_id = news[0]
                current_popularity = news[3]
                updated_popularity = current_popularity + score

                cur.execute('''
                    UPDATE news
                    SET popularity = %s, processing_status = '已處理'
                    WHERE id = %s
                ''', (updated_popularity, news_id))
                print(f"更新新聞 ID {news_id}: 熱度 {current_popularity} -> {updated_popularity}")

        conn.commit()
        print("所有關鍵字處理完成，新聞資料已更新")
    except Exception as e:
        print(f"處理過程中發生錯誤: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    # 關鍵字文件路徑
    keywords_file_path = "/app/output/trending_keywords.json"  # Docker 容器中的路徑

    # 更新新聞熱度
    update_news_popularity(keywords_file_path)