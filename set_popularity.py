#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import psycopg2
from psycopg2.extras import NamedTupleCursor
import math
import logging

# ---------------------------
# 設定日誌
# ---------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# ---------------------------
# 取得資料庫連線
# ---------------------------
def get_postgres_connection():
    external_db_url = (
        "postgresql://newsdata_vc3p_user:HXLUZa2xgOH4wk1Eq2witr88llkm7bqG@dpg-cu0om3jtq21c73c06280-a.singapore-postgres.render.com/newsdata_vc3p"
    )
    db_url = os.getenv("DATABASE_URL", external_db_url)
    return psycopg2.connect(db_url)

# ---------------------------
# 加權公式與常數
# ---------------------------
CATEGORY_WEIGHTS = {
    "11": 1.2,  # 綜合
    "10": 1.5,  # 法律與政府
    "14": 2.0,  # 政治
    "3": 1.1,   # 商業與財經
}

def get_rank_weight(rank):
    if rank <= 5:
        return 1.1
    elif rank <= 10:
        return 1.05
    else:
        return 1.0

def get_main_keyword_weight(related_count):
    return max(1.2 - 0.1 * related_count, 0.7)

def calculate_main_keyword_score(category, rank, related_count, base_score=10):
    category_weight = CATEGORY_WEIGHTS.get(category, 1.0)
    rank_weight = get_rank_weight(rank)
    mk_weight = get_main_keyword_weight(related_count)
    return base_score * category_weight * rank_weight * mk_weight

# ---------------------------
# 更新新聞熱度：僅針對最新 limit_count 筆新聞進行處理
# ---------------------------
def update_news_popularity(keywords_file_path, limit_count=3000):
    if not os.path.exists(keywords_file_path):
        logging.error(f"找不到關鍵字文件: {keywords_file_path}")
        return

    with open(keywords_file_path, "r", encoding="utf-8") as f:
        try:
            keywords_data = json.load(f)
        except json.JSONDecodeError:
            logging.error("無法解析關鍵字 JSON 文件")
            return

    conn = get_postgres_connection()
    cur = conn.cursor(cursor_factory=NamedTupleCursor)

    try:
        for entry in keywords_data:
            main_keyword = entry.get("main_keyword", "")
            category = str(entry.get("category", "11"))
            rank = entry.get("rank", 999)
            related_keywords = entry.get("related_keywords", [])

            mk_score_raw = calculate_main_keyword_score(category, rank, len(related_keywords), base_score=10)

            # ----------------------------
            # (A) 更新所有 related_keywords
            # ----------------------------
            for rkw in related_keywords:
                cur.execute('''
                    SELECT id, popularity, processing_status
                    FROM news
                    WHERE id IN (
                        SELECT id FROM news ORDER BY id DESC LIMIT %s
                    )
                    AND (title ILIKE %s OR content ILIKE %s)
                ''', (limit_count, f"%{rkw}%", f"%{rkw}%"))
                rows = cur.fetchall()

                for news_item in rows:
                    news_id = news_item.id
                    current_pop = news_item.popularity
                    try:
                        proc_status = int(news_item.processing_status)
                    except (ValueError, TypeError):
                        logging.warning(f"[Warning] 無法解析 processing_status，將其視為 0: {news_item.processing_status}")
                        proc_status = 0

                    related_incr = 1.0 * (0.5 ** proc_status)
                    new_pop = current_pop + related_incr
                    new_status = proc_status + 1

                    cur.execute('''
                        UPDATE news
                        SET popularity = %s,
                            processing_status = %s
                        WHERE id = %s
                    ''', (new_pop, new_status, news_id))

                    logging.info(f"[Related] news_id={news_id}, old_pop={current_pop}, +{related_incr:.2f}, "
                                 f"proc_status={proc_status}->{new_status}, keyword={rkw}")

            # ----------------------------
            # (B) 更新 main_keyword
            # ----------------------------
            cur.execute('''
                SELECT id, popularity, processing_status
                FROM news
                WHERE id IN (
                    SELECT id FROM news ORDER BY id DESC LIMIT %s
                )
                AND (title ILIKE %s OR content ILIKE %s)
            ''', (limit_count, f"%{main_keyword}%", f"%{main_keyword}%"))
            main_rows = cur.fetchall()

            for news_item in main_rows:
                news_id = news_item.id
                current_pop = news_item.popularity
                try:
                    proc_status = int(news_item.processing_status)
                except (ValueError, TypeError):
                    logging.warning(f"[Warning] 無法解析 processing_status，將其視為 0: {news_item.processing_status}")
                    proc_status = 0

                mk_incr = mk_score_raw * (0.5 ** proc_status)
                new_pop = current_pop + mk_incr
                new_status = proc_status + 1

                cur.execute('''
                    UPDATE news
                    SET popularity = %s,
                        processing_status = %s
                    WHERE id = %s
                ''', (new_pop, new_status, news_id))

                logging.info(f"[Main] news_id={news_id}, old_pop={current_pop}, +{mk_incr:.2f}, "
                             f"proc_status={proc_status}->{new_status}, main_keyword={main_keyword}")

        conn.commit()
        logging.info("✅ 新聞熱度更新完成!")
    except Exception as e:
        logging.error(f"[Error] {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# ---------------------------
# 主程式入口
# ---------------------------
if __name__ == "__main__":
    keywords_file_path = "/app/output/trending_keywords.json"
    import sys
    if len(sys.argv) > 1:
        keywords_file_path = sys.argv[1]
    LIMIT_COUNT = 3000  # 僅處理最新3000筆新聞
    update_news_popularity(keywords_file_path, limit_count=LIMIT_COUNT)