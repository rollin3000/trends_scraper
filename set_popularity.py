#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import psycopg2
from psycopg2.extras import NamedTupleCursor
import math

# --------------------------------------------------
#  1) 資料庫連線函式
# --------------------------------------------------
def get_postgres_connection():
    """
    取得 PostgreSQL 資料庫連線。
    若環境變數 DATABASE_URL 存在則優先使用，否則使用 external_db_url。
    """
    external_db_url = (
        "postgresql://newsdata_vc3p_user:"
        "HXLUZa2xgOH4wk1Eq2witr88llkm7bqG"
        "@dpg-cu0om3jtq21c73c06280-a.singapore-postgres.render.com/newsdata_vc3p"
    )
    db_url = os.getenv("DATABASE_URL", external_db_url)
    return psycopg2.connect(db_url)

# --------------------------------------------------
#  2) 加權公式與常數 (可調整)
# --------------------------------------------------
CATEGORY_WEIGHTS = {
    "11": 1.2,  # 綜合
    "10": 1.5,  # 法律與政府
    "14": 2.0,  # 政治
    "3": 1.1,   # 商業與財經
    # 其他類別 → 預設 1.0
}

def get_rank_weight(rank):
    """
    根據排名 (rank) 回傳對應的加權係數：
      - 1~5   → 1.1
      - 6~10  → 1.05
      - 11+   → 1.0
    """
    if rank <= 5:
        return 1.1
    elif rank <= 10:
        return 1.05
    else:
        return 1.0

def get_main_keyword_weight(related_count):
    """
    主關鍵字權重 = max(1.2 - 0.1 * related_count, 0.7)
    相關關鍵字越多，權重越低，最低不低於 0.7。
    """
    return max(1.2 - 0.1 * related_count, 0.7)

def calculate_main_keyword_score(category, rank, related_count, base_score=10):
    """
    計算主關鍵字「未折扣」前的完整分數：
      main_keyword_score = base_score * category_weight * rank_weight * main_keyword_weight
    """
    category_weight = CATEGORY_WEIGHTS.get(category, 1.0)
    rank_weight = get_rank_weight(rank)
    mk_weight = get_main_keyword_weight(related_count)
    return base_score * category_weight * rank_weight * mk_weight

# --------------------------------------------------
#  3) 主要邏輯 (支援多次加分, 只搜尋最近2天)
# --------------------------------------------------

def update_news_popularity(keywords_file_path):
    """
    1. 從 JSON 檔讀取各個關鍵字資料 (main_keyword, category, rank, related_keywords...)。
    2. 只搜尋符合 pub_date >= NOW() - INTERVAL '2 days' 的新聞。
    3. 相關關鍵字: 基礎 +1 分，再乘上 (0.5^processing_status) 做折扣。
    4. 主關鍵字: 先計算完整分數，再乘上 (0.5^processing_status) 做折扣。
    5. 每次更新後將 processing_status += 1。
    """

    if not os.path.exists(keywords_file_path):
        print(f"[Error] 找不到關鍵字文件: {keywords_file_path}")
        return

    # 讀取 JSON
    with open(keywords_file_path, "r", encoding="utf-8") as f:
        try:
            keywords_data = json.load(f)
        except json.JSONDecodeError:
            print("[Error] 無法解析關鍵字 JSON 文件")
            return

    conn = get_postgres_connection()
    cur = conn.cursor(cursor_factory=NamedTupleCursor)

    try:
        for entry in keywords_data:
            main_keyword = entry.get("main_keyword", "")
            category = str(entry.get("category", "11"))  # 若無預設 11 (綜合)
            rank = entry.get("rank", 999)               # 若無預設 999
            related_keywords = entry.get("related_keywords", [])

            # 計算主關鍵字的「完整分數」(尚未折扣)
            mk_score_raw = calculate_main_keyword_score(
                category,
                rank,
                len(related_keywords),
                base_score=10
            )

            # ----------------------------------------
            #  (A) 更新所有 related_keywords
            #      只搜尋「最近2天」的新聞
            # ----------------------------------------
            for rkw in related_keywords:
                cur.execute('''
                    SELECT id, popularity, processing_status
                    FROM news
                    WHERE pub_date >= NOW() - INTERVAL '2 days'
                      AND (title ILIKE %s OR content ILIKE %s)
                ''', (f"%{rkw}%", f"%{rkw}%"))
                rows = cur.fetchall()

                for news_item in rows:
                    news_id = news_item.id
                    current_pop = news_item.popularity
                    try:
                        proc_status = int(news_item.processing_status)
                    except:
                        # 如果意外發現不是數字, 一律視為0
                        proc_status = 0

                    # 第一次處理( status=0 ) → +1
                    # 第二次處理( status=1 ) → +1 * 0.5
                    # 第三次處理( status=2 ) → +1 * 0.25
                    related_incr = 1.0 * (0.5 ** proc_status)
                    new_pop = current_pop + related_incr
                    new_status = proc_status + 1

                    cur.execute('''
                        UPDATE news
                        SET popularity = %s,
                            processing_status = %s
                        WHERE id = %s
                    ''', (new_pop, new_status, news_id))

                    print(f"[Related] news_id={news_id}, old_pop={current_pop}, +{related_incr:.2f}, "
                          f"proc_status={proc_status}->{new_status}, keyword={rkw}")

            # ----------------------------------------
            #  (B) 更新 main_keyword
            # ----------------------------------------
            cur.execute('''
                SELECT id, popularity, processing_status
                FROM news
                WHERE pub_date >= NOW() - INTERVAL '2 days'
                  AND (title ILIKE %s OR content ILIKE %s)
            ''', (f"%{main_keyword}%", f"%{main_keyword}%"))
            main_rows = cur.fetchall()

            for news_item in main_rows:
                news_id = news_item.id
                current_pop = news_item.popularity
                try:
                    proc_status = int(news_item.processing_status)
                except:
                    proc_status = 0

                # 第一次處理( status=0 ) → mk_score_raw
                # 第二次( status=1 ) → mk_score_raw * 0.5
                # 第三次( status=2 ) → mk_score_raw * 0.25
                mk_incr = mk_score_raw * (0.5 ** proc_status)
                new_pop = current_pop + mk_incr
                new_status = proc_status + 1

                cur.execute('''
                    UPDATE news
                    SET popularity = %s,
                        processing_status = %s
                    WHERE id = %s
                ''', (new_pop, new_status, news_id))

                print(f"[Main] news_id={news_id}, old_pop={current_pop}, +{mk_incr:.2f}, "
                      f"proc_status={proc_status}->{new_status}, main_keyword={main_keyword}")

        conn.commit()
        print("新聞熱度更新完成!")
    except Exception as e:
        print(f"[Error] {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# --------------------------------------------------
#  4) 主程式入口
# --------------------------------------------------
if __name__ == "__main__":
    keywords_file_path = "/app/output/trending_keywords.json"  # Docker中預設路徑

    import sys
    if len(sys.argv) > 1:
        keywords_file_path = sys.argv[1]

    update_news_popularity(keywords_file_path)