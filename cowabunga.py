from os import stat
import pandas as pd
import math
import openpyxl
import json
import telebot

from timing import Timing
from oanda_api import OandaAPI
from settings import Settings

from defs import BUY, OANDA_URL, SELL, NONE, ACCOUNT_ID, TELE_API_KEY, USER_ID

class Cowabunga():
    def __init__(self, settings, api, pair, main_granularity, trade_granularity, log = None):
        self.settings = settings
        self.log = log
        self.api = api
        self.pair = pair
        self.main_granularity = main_granularity
        self.trade_granularity = trade_granularity
    
    def log_message(self,msg):
        if self.log is not None:
            self.log.logger.debug(msg)
    
    def fetch_candles(self, row_count, candle_time, granularity, tick = False):
        status_code, df = self.api.fetch_candles(self.pair, count = row_count, granularity = granularity, tick = tick)
        if df is None:
            self.log_message(f"Error fetching candles for pair:{self.pair} {candle_time}, df None")
            return None #change to try for a few more times and try to reconnect with the api
        elif df.iloc[-1].time != candle_time:
            self.log_message(f"Error fetching candles for pair:{self.pair} {candle_time} vs {df.iloc[-1].time}")
            return None
        else:
            return df
    
    def EMA(self,df,length):
        multiplier = (2 / (length + 1))
        Sum = 0
        for price in df.mid_c[:length]:
            Sum = price + Sum   
        sma = Sum/length
        ema = [0] * (length-1)
        ema.append(sma)

        for price in df.mid_c[length:]:
            EMA = price * multiplier + ema[-1] * (1 - multiplier)
            ema.append(EMA)
        
        df[f'EMA_{length}'] = ema

        return df

    def MACD(self,df,fast,slow,signal):
        #EMA_12
        df= self.EMA(df,fast)
        #EMA_26
        df = self.EMA(df,slow)

        df['MACD_LINE'] = df[f'EMA_{fast}'] - df[f'EMA_{slow}']
        
        multiplier = (2 / (signal + 1))
        Sum = 0
        for price in df.MACD_LINE[:9]:
            Sum = price + Sum    
        sma = Sum/signal
        ema = [0] * (signal-1)
        ema.append(sma)

        for price in df.MACD_LINE[9:]:
            EMA = price * multiplier + ema[-1] * (1 - multiplier)
            ema.append(EMA)
        
        df['SIGNAL_LINE'] = ema

        df['MACD_HIST'] = df['MACD_LINE'] - df['SIGNAL_LINE']
        df['PREV_MACD'] = df['MACD_HIST'].shift(1)
        df['MACD_DIFF'] = df['MACD_HIST'] - df['PREV_MACD']

        return df

    def RSI(self,df,length):
        df['prev_mid_c'] = df['mid_c'].shift(1)
        df['GAIN'] = df['mid_c'] - df['prev_mid_c']

        RSI = [0] * length

        total_gain = 0
        total_loss = 0

        for price in df.GAIN[1:(length + 1)]:
            if price < 0:
                total_loss += price
            else:
                total_gain += price    

        avg_gain = total_gain/length
        avg_loss = (-total_loss)/length

        if avg_loss != 0:
            RSI.append(100 - ( 100 / ( 1 + ( avg_gain / avg_loss ) ) ) )
        else:
            RSI.append(100)

        for change in df.GAIN[(length + 1):]:
            if change > 0:
                avg_gain = (avg_gain * (length-1) + change)/length
                avg_loss = (avg_loss * (length-1))/length
            else:
                avg_loss = (avg_loss * (length-1) - change)/length
                avg_gain = (avg_gain * (length-1))/length
                
            if avg_loss != 0:
                RSI.append( 100 - ( 100 / (1 + ( avg_gain / avg_loss ) )))
            else:
                RSI.append(100)

        df['RSI'] = RSI
        df['RSI_prev'] = df['RSI'].shift(1)
        df['RSI_diff'] = df['RSI'] - df['RSI_prev']

        return df
    
    def Stochastic(self,df,length,Dsmooth,Ksmooth):
        df['low_min']  = df["mid_l"].rolling( window = length ).min()
        df['high_max'] = df["mid_h"].rolling( window = length ).max()

        # Fast Stochastic
        df['k_fast'] = 100 * (df["mid_c"] - df['low_min'])/(df['high_max'] - df['low_min'])
        df['k_slow'] = df['k_fast'].rolling(window = Dsmooth).mean()
        df['d_slow'] = df['k_slow'].rolling(window = Ksmooth).mean()

        df["K_PREV"] = df["k_slow"].shift(1)
        df["D_PREV"] = df["d_slow"].shift(1)

        df["K_TREND"] = df["k_slow"] - df["K_PREV"]
        df["D_TREND"] = df["d_slow"] - df["D_PREV"]

        return df

    def process_candles(self,df_4H,df_15M):
        df_4H['PAIR'] = self.pair
        df_15M['PAIR'] = self.pair
        df_15M["mid_c"] = df_15M["mid_c"].apply(pd.to_numeric)
        df_4H["mid_c"] = df_4H["mid_c"].apply(pd.to_numeric)

        #===== df_4H =====

        #EMA_5 
        df_4H = self.EMA(df_4H,5)

        #EMA_10
        df_4H = self.EMA(df_4H,10)

        #Fast - Slow , if >0 fast above slow up trend, else <0 is a down trend
        df_4H['EMA_DIFF'] = df_4H['EMA_5'] - df_4H['EMA_10']

        #RSI(9)
        df_4H = self.RSI(df_4H,9)

        #stochastic
        df_4H = self.Stochastic(df_4H,10,3,3)

        # Main Trend
        last = df_4H.iloc[-1]
        if (last.EMA_DIFF > 0) and (last.RSI > 50) and (last.K_TREND > 0) and (last.D_TREND > 0):
            MAIN_TREND = BUY
        elif (last.EMA_DIFF < 0) and (last.RSI < 50) and (last.K_TREND < 0) and (last.D_TREND < 0):
            MAIN_TREND = SELL
        else:
            MAIN_TREND = NONE

        #===== df_15M =====

        #EMA_5 
        df_15M = self.EMA(df_15M,5)

        #EMA_10
        df_15M = self.EMA(df_15M,10)

        #Fast - Slow , if >0 fast above slow up trend, else <0 is a down trend
        df_15M['EMA_DIFF'] = df_15M['EMA_5'] - df_15M['EMA_10']

        #RSI(9)
        df_15M = self.RSI(df_15M,9)

        #stochastic
        df_15M = self.Stochastic(df_15M,10,3,3)

        #MACD
        df_15M = self.MACD(df_15M,12,26,9)

        #Decision

        last_15 = df_15M.iloc[-1]
        decision = NONE

        if MAIN_TREND == BUY:
            if (last_15.EMA_DIFF > 0) and (last_15.RSI > 50) and (last_15.RSI<65) and (last_15.K_TREND > 0) and (last_15.D_TREND > 0) and (50<last_15.k_slow < 80) and (50<last_15.d_slow < 80) and (last_15.MACD_DIFF > 0) and (last_15.RSI_prev > 0):
                decision = BUY
        if MAIN_TREND == SELL:    
            if (last_15.EMA_DIFF < 0) and (last_15.RSI < 50) and (last_15.RSI>35) and (last_15.K_TREND < 0) and (last_15.D_TREND < 0) and (50>last_15.k_slow > 20) and (50>last_15.d_slow > 20) and (last_15.MACD_DIFF < 0) and (last_15.RSI_prev < 0):
                decision = SELL

        log_cols_4H = ['PAIR','time','volume','mid_c','EMA_DIFF','RSI','K_TREND','D_TREND','k_slow','d_slow']
        log_cols_15M = ['PAIR','time','volume','mid_c','EMA_DIFF','RSI','K_TREND','D_TREND','k_slow','d_slow','MACD_DIFF']

        self.log_message(f"Processed_df_4H \n{df_4H[log_cols_4H].tail(2)}")
        self.log_message(f"Main_Trend: {MAIN_TREND}")
        self.log_message("")

        self.log_message(f"Processed_df_15M \n{df_15M[log_cols_15M].tail(2)}")
        self.log_message(f"Trade_Decision: {decision}")
        self.log_message
        
        return df_4H[log_cols_4H], MAIN_TREND, df_15M[log_cols_15M], decision

    def get_trade_decision(self,main_candle_time,trade_candle_time):
        print("Getting Trade Decision...")
        max_rows = (self.settings.MACD + 2 ) * 2 
        self.log_message("")
        self.log_message(f"get_trade_decision() pair:{self.pair} max_rows:{max_rows}")

        df = self.fetch_candles(max_rows, main_candle_time, self.main_granularity,True)
        df1 = self.fetch_candles(max_rows, trade_candle_time, self.trade_granularity)
        
        df_4H, main_trend, df_15M, decision = (None, None, None, None)
        price, units, open_price, take_profit, stop_loss = (NONE, NONE, NONE, NONE, NONE)

        if df is not None and df1 is not None:
            df_4H, main_trend, df_15M, decision = self.process_candles(df,df1)

            price = float(df_15M['mid_c'].iloc[-1])

            if main_trend != 0 and decision != 0:
                
                stop_loss = self.get_stop_loss(df,price,decision)
            
                if "JPY" in self.pair:
                    take_profit50 = int(math.ceil(price*100/50) * 50) / 100
                    if take_profit50 < price:
                        take_profit50 += 0.5
                    take_profit1 = (price*100 + 25)/100
                    take_profit = min(take_profit1,take_profit50)
                else:
                    take_profit50 = int(math.ceil(price*10000/50) * 50) / 10000
                    if take_profit50 < price:
                        take_profit50 += 0.005
                    take_profit1 = (price*10000 + 25)/10000
                    take_profit = min(take_profit1,take_profit50)

                units = 1500 * decision
            
            if main_trend == 1 and decision == 1:
                countTrade = self.cappedTrades()
                if countTrade < 3:
                    trade_id, open_price, ok = self.api.place_trade(self.pair, units, take_profit, stop_loss)
                    self.log_message("")
                    self.log_message(f"Trade Pair, {self.pair}, capped at {countTrade}")
                self.log_message("")
                self.log_message(f"Long Trade pair:{self.pair} units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")

            elif main_trend == -1 and decision == -1:
                countTrade = self.cappedTrades()
                if countTrade < 3:
                    trade_id, open_price, ok = self.api.place_trade(self.pair, units, take_profit, stop_loss)
                    self.log_message("")
                    self.log_message(f"Trade Pair, {self.pair}, capped at {countTrade}")
                self.log_message("")
                self.log_message(f"Short Trade pair:{self.pair} units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")
        
        return price, main_trend, decision, units, open_price, take_profit, stop_loss

    def low_swing(self,row):
        if row.mid_l < row.mid_l1 and row.mid_l1 < row.mid_l2:
            return True
        return False

    def high_swing(self,row):
        if row.mid_h > row.mid_h1 and row.mid_h1 > row.mid_h2:
            return True
        return False

    def get_stop_loss(self,df,price,decision):
        if decision == 1:
            df['mid_l1'] = df['mid_l'].shift(-1)
            df['mid_l2'] = df['mid_l1'].shift(-1)
            df.drop(df.tail(2).index, inplace = True)
            df['low_swing'] = df.apply(self.low_swing,axis = 1)
            while True:
                swing_df = df[df.low_swing == True]
                swing = float(swing_df.iloc[-1]['mid_l'])
                swing_df=swing_df.iloc[:-1]
                if swing < price:
                    return swing
                if df is None or df.shape[0] == 0:
                    return swing
        elif decision == -1:
            df['mid_h1'] = df['mid_h'].shift(-1)
            df['mid_h2'] = df['mid_h1'].shift(-1)
            df.drop(df.tail(2).index, inplace = True)
            df['high_swing'] = df.apply(self.high_swing,axis = 1)
            while True:
                swing_df = df[df.high_swing == True]
                swing =  float(swing_df.iloc[-1]['mid_h'])
                swing_df=swing_df.iloc[:-1]
                if swing > price:
                    return swing
                if df is None or df.shape[0] == 0:
                    return swing

    def check_open_trade(self,main_candle_time,trade_candle_time):
        url = f"{OANDA_URL}/accounts/{ACCOUNT_ID}/openTrades"
        status_code, json_data = self.api.make_request(url, code_ok=200)

        for i in range(5):
            if status_code == 200:
                if "trades" in json_data:
                    openTrades = json_data["trades"]
                    break

        max_rows = (self.settings.MACD + 2 ) * 2 
        df = self.fetch_candles(max_rows, main_candle_time, self.main_granularity, True)
        df1 = self.fetch_candles(max_rows, trade_candle_time, self.trade_granularity)

        status = []

        #Exit Trade when main trend changes => RSI cross 50, EMA crossover
        if df is not None and df1 is not None:
            df_4H, main_trend, df_15M, decision = self.process_candles(df,df1)
            
            if status_code == 200:
                for trade in openTrades:
                    if "instrument" in trade:
                        if trade["instrument"] == self.pair:
                            if float(trade["currentUnits"]) < 0:
                                last = df_15M.iloc[-1]
                                if last.RSI >= 50 or last.EMA_DIFF >= 0:
                                    status_code1 = self.exit_trade(trade["id"])
                            if float(trade["currentUnits"]) > 0:
                                last = df_15M.iloc[-1]
                                if last.RSI <= 50 or last.EMA_DIFF <= 0:
                                    status_code1 = self.exit_trade(trade["id"])
                            status.append(status_code1)
        
        return status       

    def cappedTrades(self):
        url = f"{OANDA_URL}/accounts/{ACCOUNT_ID}/openTrades"
        status_code, json_data = self.api.make_request(url, code_ok=200)

        if "trades" in json_data:
            trades = json_data['trades']
            itemList = []
            for item in trades:
                itemList.append(item['instrument'])
        
        return itemList.count(self.pair)
        

    
    def exit_trade(self,trade_id):
        url = f"{OANDA_URL}/accounts/{ACCOUNT_ID}/trades/{trade_id}/close"
        data = {"units":"ALL"}
        status_code, json_data = self.api.make_request(url, verb = 'put', data =json.dumps(data), code_ok=200)
        return status_code

if __name__ == "__main__":
    pass