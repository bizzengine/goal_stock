from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
from datetime import datetime
import numpy as np
import holidays
import json
import os
import io

app = Flask(__name__)

# 미국 공휴일 설정
us_holidays = holidays.US()

def load_tickers():
    """tickers.json 파일을 로드하는 함수"""
    try:
        tickers_path = os.path.join(app.static_folder, 'tickers.json')
        with open(tickers_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Warning: tickers.json 파일을 찾을 수 없습니다. 자동완성 기능이 비활성화됩니다.")
        return []
    except json.JSONDecodeError:
        print("Warning: tickers.json 파일 형식이 올바르지 않습니다.")
        return []

@app.route('/')
def index():
    return render_template('index.html')

# ← 이 부분을 꼭 추가!
@app.route('/autocomplete')
def autocomplete():
    return jsonify(load_tickers())


@app.route("/", methods=["GET", "POST"])
def profit_analyzer():
    if request.method == "GET":
        return render_template("index.html")
    
    try:
        target_profit = float(request.form["target_profit"])
        # getlist를 사용하여 여러 종목과 날짜를 리스트로 받습니다.
        tickers = request.form.getlist("tickers")
        dates = request.form.getlist("buy_dates")

        if not tickers or not dates or len(tickers) != len(dates):
            return jsonify({"error": "종목과 날짜를 올바르게 입력해주세요."})

        data = []
        errors = []
        
        for symbol, buy_date_str in zip(tickers, dates):
            if not symbol or not buy_date_str:
                continue

            try:
                symbol = symbol.strip().upper()
                buy_date = pd.to_datetime(buy_date_str.strip())
                
                # 현재 날짜보다 미래인 경우 체크
                if buy_date.date() > datetime.today().date():
                    errors.append(f"{symbol}: 매수일이 미래 날짜입니다.")
                    continue
                
                # 데이터 다운로드 (시작일을 하루 전으로 설정하여 정확한 첫날 데이터 확보)
                df = yf.download(symbol, start=buy_date, end=datetime.today().date(), progress=False)
                
                # MultiIndex 컬럼 처리
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')

                if df.empty:
                    errors.append(f"{symbol}: 데이터를 찾을 수 없습니다.")
                    continue

                buy_price = df.iloc[0]["Close"]
                current_price = df.iloc[-1]["Close"]
                max_price_ever = df["High"].max()

                target_price = buy_price * (1 + target_profit / 100)
                
                # 고가가 목표가에 도달한 적이 있는지 확인 (실현 여부)
                realized = max_price_ever >= target_price

                if realized:
                    # 목표가에 도달한 첫 날짜
                    reached_day = df[df["High"] >= target_price].index[0]
                    # 영업일 기준 보유 기간 계산
                    days_held = len(pd.bdate_range(buy_date, reached_day, freq='C', holidays=us_holidays))
                    data.append({
                        "symbol": symbol,
                        "buy_date": buy_date.strftime('%Y-%m-%d'),
                        "buy_price": float(buy_price),
                        "target_price": float(target_price),
                        "sell_price": float(target_price), # 목표가에 매도된 것으로 가정
                        "achieve_date": reached_day.strftime('%Y-%m-%d'),
                        "days": days_held,
                        "profit": target_profit, # 실현 수익률은 목표 수익률
                        "realized": True
                    })
                else:
                    # (O) 마지막 거래일(df.index[-1])을 기준으로 계산
                    last_trade = df.index[-1]
                    days_held = len(pd.bdate_range(buy_date, last_trade,
                                                freq='C', holidays=us_holidays))
                    current_profit = ((current_price - buy_price) / buy_price) * 100
                    data.append({
                        "symbol": symbol,
                        "buy_date": buy_date.strftime('%Y-%m-%d'),
                        "buy_price": float(buy_price),
                        "target_price": float(target_price),
                        "sell_price": float(current_price),
                        "achieve_date": None,
                        "days": days_held,
                        "profit": round(current_profit, 2),
                        "realized": False
                    })


            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                errors.append(f"{symbol}: 처리 중 오류가 발생했습니다.")

        if errors:
            return jsonify({"error": " / ".join(errors[:3])})  # 최대 3개 에러만 표시

        if not data:
            return jsonify({"error": "분석할 종목이 없습니다. 티커와 날짜를 올바르게 입력했는지 확인해주세요."})

        df_result = pd.DataFrame(data)
        realized_df = df_result[df_result["realized"]]
        unrealized_df = df_result[~df_result["realized"]]

        result = {
            "overall_avg_profit": round(df_result["profit"].mean(), 2) if not df_result.empty else 0,
            "realized_count": len(realized_df),
            "unrealized_count": len(unrealized_df),
            "avg_realized_days": round(realized_df["days"].mean(), 1) if not realized_df.empty else 0,
            "realized_list": realized_df.to_dict("records"),
            "unrealized_list": unrealized_df.to_dict("records")
        }
        
        return jsonify(result)

    except ValueError:
        return jsonify({"error": "목표 수익률은 숫자로 입력해주세요."})
    except Exception as e:
        print(f"Form processing error: {e}")
        return jsonify({"error": "입력 값에 오류가 있습니다. 모든 필드를 올바르게 채워주세요."})

if __name__ == "__main__":
    app.run(debug=True, port=5002)