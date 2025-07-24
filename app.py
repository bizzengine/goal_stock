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

@app.route('/autocomplete')
def autocomplete():
    return jsonify(load_tickers())


@app.route("/", methods=["GET", "POST"])
def profit_analyzer():
    if request.method == "GET":
        return render_template("index.html")
    
    try:
        target_profit = float(request.form["target_profit"])
        
        tickers = []
        dates = []

        # 파일이 업로드되었는지 확인
        if 'excel_file' in request.files:
            excel_file = request.files['excel_file']
            if excel_file and excel_file.filename != '':
                if excel_file.filename.endswith('.csv'):
                    # io.StringIO를 사용하여 파일 내용을 문자열로 읽고 pandas로 파싱
                    df_uploaded = pd.read_csv(io.StringIO(excel_file.stream.read().decode('utf-8')))
                elif excel_file.filename.endswith('.xlsx'):
                    # xlsx 파일은 직접 읽을 수 있음
                    df_uploaded = pd.read_excel(excel_file)
                else:
                    return jsonify({"error": "지원하지 않는 파일 형식입니다. CSV 또는 XLSX 파일을 업로드해주세요."})
                
                if df_uploaded is not None and 'Ticker' in df_uploaded.columns and 'BuyDate' in df_uploaded.columns:
                    tickers = df_uploaded['Ticker'].astype(str).tolist()
                    dates = df_uploaded['BuyDate'].astype(str).tolist() # 날짜를 문자열로 변환
                else:
                    return jsonify({"error": "업로드된 파일에 'Ticker' 또는 'BuyDate' 컬럼이 없습니다. 올바른 템플릿을 사용해주세요."})
            else:
                # 파일이 제출되었지만 내용이 없는 경우 (예: 파일 선택 안 함)
                tickers = request.form.getlist("tickers")
                dates = request.form.getlist("buy_dates")
        else:
            # 파일이 업로드되지 않은 경우, 기존 폼 데이터 처리
            tickers = request.form.getlist("tickers")
            dates = request.form.getlist("buy_dates")

        if not tickers or not dates or len(tickers) != len(dates):
            return jsonify({"error": "종목과 날짜를 올바르게 입력해주세요. 또는 엑셀 파일 형식을 확인해주세요."})

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
                
                # 수정된 부분 - 매수일 다음 영업일부터 목표가 달성 여부 확인

                # 데이터 다운로드
                df = yf.download(symbol, start=buy_date, end=datetime.today().date(), progress=False, auto_adjust=False)

                # MultiIndex 컬럼 처리
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.droplevel('Ticker')

                if df.empty:
                    errors.append(f"{symbol}: 데이터를 찾을 수 없습니다.")
                    continue

                buy_price = df.iloc[0]["Close"]
                current_price = df.iloc[-1]["Close"]

                target_price = buy_price * (1 + target_profit / 100)

                # 매수일 다음 영업일부터의 데이터만 고려하여 목표가 달성 여부 확인
                if len(df) > 1:  # 매수일 이후 데이터가 있는 경우
                    df_after_buy = df.iloc[1:]  # 매수일 다음 영업일부터의 데이터
                    max_price_after_buy = df_after_buy["High"].max()
                    realized = max_price_after_buy >= target_price
                    
                    if realized:
                        # 목표가에 도달한 첫 날짜 (매수일 다음 영업일부터)
                        reached_day = df_after_buy[df_after_buy["High"] >= target_price].index[0]
                        # 영업일 기준 보유 기간 계산
                        days_held = len(pd.bdate_range(buy_date + pd.Timedelta(days=1), reached_day, freq='C', holidays=us_holidays))
                        data.append({
                            "symbol": symbol,
                            "buy_date": buy_date.strftime('%Y-%m-%d'),
                            "buy_price": float(buy_price),
                            "target_price": float(target_price),
                            "sell_price": float(target_price),
                            "achieve_date": reached_day.strftime('%Y-%m-%d'),
                            "days": days_held,
                            "profit": target_profit,
                            "realized": True
                        })
                    else:
                        # 목표가 미달성
                        last_trade = df.index[-1]
                        days_held = len(pd.bdate_range(buy_date + pd.Timedelta(days=1), last_trade, freq='C', holidays=us_holidays))
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
                else:
                    # 매수일 당일 데이터만 있는 경우 (아직 다음 영업일이 오지 않음)
                    data.append({
                        "symbol": symbol,
                        "buy_date": buy_date.strftime('%Y-%m-%d'),
                        "buy_price": float(buy_price),
                        "target_price": float(target_price),
                        "sell_price": float(buy_price),  # 현재가 = 매수가
                        "achieve_date": None,
                        "days": 0,
                        "profit": 0.0,
                        "realized": False
                    })

            except Exception as e:
                print(f"Error processing {symbol}: {e}")
                errors.append(f"{symbol}: 처리 중 오류가 발생했습니다. {e}")

        if errors:
            # 모든 에러를 반환하여 클라이언트에서 처리
            return jsonify({"error": " / ".join(errors)})

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

    except ValueError as e:
        return jsonify({"error": f"입력 값 오류: {e}. 목표 수익률은 숫자로 입력해주세요."})
    except Exception as e:
        print(f"Form processing error: {e}")
        return jsonify({"error": f"서버 처리 중 알 수 없는 오류가 발생했습니다. {e}"})

if __name__ == "__main__":
    app.run(debug=True, port=5002)