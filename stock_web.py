import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import pandas as pd
from pykrx import stock
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import json
import os

# 기본 종목
DEFAULT_STOCKS = {
    "대우건설": "047040",
    "희림": "037440",
    "한국전력": "015760",
    "대한항공": "003490",
}

USER_STOCKS_FILE = "my_stocks.json"
REFRESH_MS = 5000


def find_stock_code_by_name(name):
    market_list = stock.get_market_ticker_list()
    for ticker in market_list:
        if stock.get_market_ticker_name(ticker) == name:
            return ticker
    return None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("주식 분석 프로그램")
        self.root.geometry("1200x820")

        self.stocks = self.load_stocks()
        self.canvas = None
        self.auto_job = None

        self.create_ui()
        self.update_data()

    def load_stocks(self):
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

    def save_stocks(self):
        user = {k: v for k, v in self.stocks.items() if k not in DEFAULT_STOCKS}
        with open(USER_STOCKS_FILE, "w", encoding="utf-8") as f:
            json.dump(user, f, ensure_ascii=False, indent=2)

    def create_ui(self):
        top = tk.Frame(self.root)
        top.pack(pady=10)

        self.stock_var = tk.StringVar(value="한국전력")
        self.combo = ttk.Combobox(
            top,
            textvariable=self.stock_var,
            values=list(self.stocks.keys()),
            state="readonly",
            width=15
        )
        self.combo.grid(row=0, column=0, padx=5)

        self.start = tk.Entry(top, width=12)
        self.start.insert(0, "20250101")
        self.start.grid(row=0, column=1, padx=5)

        self.end = tk.Entry(top, width=12)
        self.end.grid(row=0, column=2, padx=5)

        tk.Button(top, text="분석", command=self.manual_update).grid(row=0, column=3, padx=5)

        self.auto_var = tk.BooleanVar(value=True)
        tk.Checkbutton(top, text="자동 갱신", variable=self.auto_var, command=self.toggle_auto).grid(row=0, column=4, padx=5)

        add_frame = tk.Frame(self.root)
        add_frame.pack(pady=5)

        self.name_entry = tk.Entry(add_frame, width=18)
        self.name_entry.grid(row=0, column=0, padx=5)

        self.code_entry = tk.Entry(add_frame, width=12)
        self.code_entry.grid(row=0, column=1, padx=5)

        tk.Button(add_frame, text="추가", command=self.add_stock).grid(row=0, column=2, padx=5)
        tk.Button(add_frame, text="선택 종목 삭제", command=self.remove_stock).grid(row=0, column=3, padx=5)

        guide = tk.Label(
            self.root,
            text="왼쪽: 종목 선택 / 가운데: 시작일 / 오른쪽 빈칸: 종료일(비우면 오늘) / 아래: 종목명만 넣고 추가 가능",
            font=("맑은 고딕", 10)
        )
        guide.pack(pady=3)

        self.info = tk.Label(self.root, text="", font=("맑은 고딕", 11), justify="left")
        self.info.pack(pady=5)

        self.chart_frame = tk.Frame(self.root)
        self.chart_frame.pack(fill="both", expand=True)

    def add_stock(self):
        name = self.name_entry.get().strip()
        code = self.code_entry.get().strip()

        if not name:
            messagebox.showwarning("입력 오류", "종목명을 입력해줘.")
            return

        if not code:
            code = find_stock_code_by_name(name)
            if not code:
                messagebox.showwarning("오류", "종목명을 찾지 못했어. 정확한 이름으로 입력해줘.")
                return

        if not code.isdigit() or len(code) != 6:
            messagebox.showwarning("입력 오류", "종목코드는 숫자 6자리여야 해.")
            return

        if name in self.stocks:
            messagebox.showwarning("중복", "이미 등록된 종목명이야.")
            return

        if code in self.stocks.values():
            messagebox.showwarning("중복", "이미 등록된 종목코드야.")
            return

        self.stocks[name] = code
        self.save_stocks()
        self.combo["values"] = list(self.stocks.keys())
        self.stock_var.set(name)

        self.name_entry.delete(0, tk.END)
        self.code_entry.delete(0, tk.END)

        messagebox.showinfo("완료", f"{name} ({code}) 추가 완료")

    def remove_stock(self):
        selected = self.stock_var.get()

        if selected in DEFAULT_STOCKS:
            messagebox.showwarning("삭제 불가", "기본 종목은 삭제하지 못하게 해뒀어.")
            return

        if selected not in self.stocks:
            messagebox.showwarning("오류", "삭제할 종목이 없어.")
            return

        ok = messagebox.askyesno("삭제 확인", f"{selected} 종목을 삭제할까?")
        if not ok:
            return

        del self.stocks[selected]
        self.save_stocks()

        self.combo["values"] = list(self.stocks.keys())
        if self.stocks:
            self.stock_var.set(list(self.stocks.keys())[0])

        messagebox.showinfo("완료", f"{selected} 삭제 완료")
        self.manual_update()

    def calculate_rsi(self, series, period=14):
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)

        avg_gain = gain.rolling(period).mean()
        avg_loss = loss.rolling(period).mean()

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def fetch_df(self):
        code = self.stocks[self.stock_var.get()]
        today = datetime.today().strftime("%Y%m%d")
        start = self.start.get().strip() or "20250101"
        end = self.end.get().strip() or today

        df = stock.get_market_ohlcv_by_date(start, end, code)
        if df.empty:
            raise ValueError("데이터가 없어.")

        df["MA20"] = df["종가"].rolling(20).mean()
        df["RSI"] = self.calculate_rsi(df["종가"], 14)

        # 매수 타이밍: 종가가 MA20 아래 -> 위로 올라오는 시점
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

    def manual_update(self):
        self.update_data(show_error=True)

    def update_data(self, show_error=False):
        try:
            df = self.fetch_df()
            self.update_info(df)
            self.draw(df)
        except Exception as e:
            if show_error:
                messagebox.showerror("오류", str(e))
            else:
                print(e)

        if self.auto_var.get():
            if self.auto_job is not None:
                self.root.after_cancel(self.auto_job)
            self.auto_job = self.root.after(REFRESH_MS, self.update_data)

    def toggle_auto(self):
        if self.auto_var.get():
            self.update_data()
        else:
            if self.auto_job is not None:
                self.root.after_cancel(self.auto_job)
                self.auto_job = None

    def update_info(self, df):
        latest = df.iloc[-1]
        latest_date = df.index[-1].strftime("%Y-%m-%d")
        latest_close = int(latest["종가"])
        latest_ma20 = latest["MA20"]
        latest_rsi = latest["RSI"]

        prev_close = int(df["종가"].iloc[-2]) if len(df) >= 2 else latest_close
        diff = latest_close - prev_close
        diff_pct = (diff / prev_close * 100) if prev_close else 0

        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "-"

        if pd.notna(latest_ma20):
            trend = "상승 추세 가능성" if latest_close > latest_ma20 else "약한 흐름 또는 하락 추세"
        else:
            trend = "판단 불가"

        if pd.notna(latest_rsi):
            if latest_rsi >= 70:
                rsi_text = "과매수"
            elif latest_rsi <= 30:
                rsi_text = "과매도"
            else:
                rsi_text = "중립"
        else:
            rsi_text = "판단 불가"

        signal_count = int(df["BuySignal"].sum())

        text = (
            f"종목: {self.stock_var.get()}    날짜: {latest_date}\n"
            f"종가: {latest_close:,}원  ({arrow} {diff:+,}원 / {diff_pct:+.2f}%)\n"
            f"MA20: {latest_ma20:,.2f}    RSI: {latest_rsi:.2f}\n"
            f"추세: {trend}    RSI 상태: {rsi_text}\n"
            f"매수 타이밍 발생 횟수: {signal_count}회"
        )
        self.info.config(text=text)

    def draw(self, df):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()

        plt.rcParams["font.family"] = "Malgun Gothic"
        plt.rcParams["axes.unicode_minus"] = False

        fig = plt.Figure(figsize=(11, 7))
        ax = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)

        # 위 그래프: 종가 + MA20 + 매수 신호
        ax.plot(df.index, df["종가"], label="종가")
        ax.plot(df.index, df["MA20"], label="MA20")

        buy_df = df[df["BuySignal"] == 1]
        ax.scatter(buy_df.index, buy_df["종가"], label="매수 타이밍", zorder=5)

        ax.set_title(f"{self.stock_var.get()} 가격 차트")
        ax.legend()
        ax.grid(True)

        # 아래 그래프: RSI
        ax2.plot(df.index, df["RSI"], label="RSI")
        ax2.axhline(70, linestyle="--")
        ax2.axhline(30, linestyle="--")
        ax2.set_title("RSI")
        ax2.legend()
        ax2.grid(True)

        fig.tight_layout()

        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
