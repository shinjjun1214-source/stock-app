import os
import json
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from pykrx import stock


DEFAULT_STOCKS = {
    "대우건설": "047040",
    "희림": "037440",
    "한국전력": "015760",
    "대한항공": "003490",
}

USER_STOCKS_FILE = "my_stocks.json"


def load_stocks():
    stocks = DEFAULT_STOCKS.copy()
    if os.path.exists(USER_STOCKS_FILE):
        try:
            with open(USER_STOCKS_FILE, "r", encoding="utf-8") as f:
                user_stocks = json.load(f)
            if isinstance(user_stocks, dict):
                stocks.update(user_stocks)
        except Exception:
            pass
    return stocks


def save_stocks(stocks):
    user_stocks = {k: v for k, v in stocks.items() if k not in DEFAULT_STOCKS}
    with open(USER_STOCKS_FILE, "w", encoding="utf-8") as f:
        json.dump(user_stocks, f, ensure_ascii=False, indent=2)


def find_stock_code_by_name(name):
    market_list = stock.get_market_ticker_list()
    for ticker in market_list:
        if stock.get_market_ticker_name(ticker) == name:
            return ticker
    return None


def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def fetch_df(code, start_date, end_date):
    df = stock.get_market_ohlcv_by_date(start_date, end_date, code)
    if df.empty:
        raise ValueError("해당 기간의 데이터가 없어.")

    df["MA20"] = df["종가"].rolling(20).mean()
    df["RSI"] = calculate_rsi(df["종가"], 14)
    df["BuySignal"] = 0

    for i in range(1, len(df)):
        if (
            pd.notna(df["MA20"].iloc[i])
            and pd.notna(df["MA20"].iloc[i - 1])
            and df["종가"].iloc[i] > df["MA20"].iloc[i]
            and df["종가"].iloc[i - 1] <= df["MA20"].iloc[i - 1]
        ):
            df.loc[df.index[i], "BuySignal"] = 1

    return df


def make_chart(df, stock_name):
    plt.rcParams["font.family"] = "Malgun Gothic"
    plt.rcParams["axes.unicode_minus"] = False

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

    ax1.plot(df.index, df["종가"], label="종가")
    ax1.plot(df.index, df["MA20"], label="MA20")

    buy_df = df[df["BuySignal"] == 1]
    ax1.scatter(buy_df.index, buy_df["종가"], label="매수 타이밍", zorder=5)

    ax1.set_title(f"{stock_name} 가격 차트")
    ax1.legend()
    ax1.grid(True)

    ax2.plot(df.index, df["RSI"], label="RSI")
    ax2.axhline(70, linestyle="--")
    ax2.axhline(30, linestyle="--")
    ax2.set_title("RSI")
    ax2.legend()
    ax2.grid(True)

    fig.tight_layout()
    return fig


st.set_page_config(page_title="주식 분석 웹앱", layout="wide")
st.title("주식 분석 웹앱")

if "stocks" not in st.session_state:
    st.session_state.stocks = load_stocks()

stocks = st.session_state.stocks
today = datetime.today().strftime("%Y%m%d")

with st.sidebar:
    st.header("종목 설정")

    selected_name = st.selectbox("종목 선택", list(stocks.keys()), index=0)

    start_date = st.text_input("시작일 (YYYYMMDD)", value="20250101")
    end_date = st.text_input("종료일 (비워두면 오늘)", value="")

    st.divider()
    st.subheader("종목 추가")

    new_name = st.text_input("새 종목명")
    new_code = st.text_input("종목코드 6자리 (비워두면 자동 찾기)")

    if st.button("종목 추가"):
        name = new_name.strip()
        code = new_code.strip()

        if not name:
            st.warning("종목명을 입력해줘.")
        else:
            if not code:
                code = find_stock_code_by_name(name)

            if not code:
                st.warning("종목명을 찾지 못했어. 정확한 이름으로 입력해줘.")
            elif not code.isdigit() or len(code) != 6:
                st.warning("종목코드는 숫자 6자리여야 해.")
            elif name in stocks:
                st.warning("이미 등록된 종목명이야.")
            elif code in stocks.values():
                st.warning("이미 등록된 종목코드야.")
            else:
                stocks[name] = code
                save_stocks(stocks)
                st.success(f"{name} ({code}) 추가 완료")
                st.rerun()

    st.divider()
    st.subheader("종목 삭제")

    if selected_name in DEFAULT_STOCKS:
        st.caption("기본 종목은 삭제 불가")
    else:
        if st.button("선택 종목 삭제"):
            del stocks[selected_name]
            save_stocks(stocks)
            st.success(f"{selected_name} 삭제 완료")
            st.rerun()

if not end_date.strip():
    end_date = today

code = stocks[selected_name]

try:
    df = fetch_df(code, start_date.strip(), end_date.strip())

    latest = df.iloc[-1]
    latest_date = df.index[-1].strftime("%Y-%m-%d")
    latest_close = int(latest["종가"])
    latest_open = int(latest["시가"])
    latest_high = int(latest["고가"])
    latest_low = int(latest["저가"])
    latest_volume = int(latest["거래량"])
    latest_ma20 = latest["MA20"]
    latest_rsi = latest["RSI"]

    prev_close = int(df["종가"].iloc[-2]) if len(df) >= 2 else latest_close
    diff = latest_close - prev_close
    diff_pct = (diff / prev_close * 100) if prev_close else 0
    signal_count = int(df["BuySignal"].sum())

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("종가", f"{latest_close:,}원", f"{diff:+,}원")
    c2.metric("등락률", f"{diff_pct:+.2f}%")
    c3.metric("RSI", f"{latest_rsi:.2f}" if pd.notna(latest_rsi) else "계산중")
    c4.metric("매수 신호 횟수", f"{signal_count}회")

    st.write(
        f"""
**종목:** {selected_name}  
**마지막 반영 날짜:** {latest_date}  
**시가 / 고가 / 저가:** {latest_open:,} / {latest_high:,} / {latest_low:,}  
**거래량:** {latest_volume:,}  
**MA20:** {latest_ma20:,.2f}  
"""
    )

    fig = make_chart(df, selected_name)
    st.pyplot(fig)

    buy_df = df[df["BuySignal"] == 1]
    if not buy_df.empty:
        st.subheader("매수 타이밍 날짜")
        st.dataframe(buy_df[["종가", "MA20", "RSI"]])
    else:
        st.info("현재 기간에는 매수 타이밍이 없어.")

    st.caption("이 앱은 일봉 기준 분석용이야. 장중 실시간 체결가와는 차이가 날 수 있어.")

except Exception as e:
    st.error(f"오류: {e}")
