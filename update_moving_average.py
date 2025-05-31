import sqlite3

DB_PATH = "app.db"

def update_all_moving_averages():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 全銘柄IDを取得
    c.execute("SELECT security_id FROM securities")
    security_ids = [row[0] for row in c.fetchall()]

    for sid in security_ids:
        # 取引履歴を取引日・transaction_id順で取得
        c.execute(
            "SELECT transaction_id, txn_type, quantity, price FROM transactions WHERE security_id=? ORDER BY txn_date, transaction_id",
            (sid,)
        )
        rows = c.fetchall()
        holding_qty = 0.0
        holding_cost = 0.0
        for transaction_id, txn_type, qty, price in rows:
            if txn_type == "BUY":
                holding_cost += qty * price
                holding_qty += qty
            elif txn_type == "SEL":
                if holding_qty > 0:
                    avg = holding_cost / holding_qty if holding_qty > 0 else 0
                    sell_qty = min(qty, holding_qty)
                    holding_cost -= avg * sell_qty
                    holding_qty -= sell_qty
            moving_average = holding_cost / holding_qty if holding_qty > 0 else 0

            # moving_averageがNULLの場合のみ更新
            c.execute(
                "UPDATE transactions SET moving_average=? WHERE transaction_id=? AND (moving_average IS NULL OR moving_average=0)",
                (moving_average, transaction_id)
            )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_all_moving_averages()
    print("全ての移動平均を更新しました。")
