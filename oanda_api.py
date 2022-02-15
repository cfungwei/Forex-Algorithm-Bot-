import requests
import pandas as pd
from dateutil.parser import *
import defs
import utils
import sys
import json
import math

class OandaAPI():
    def __init__(self):
        self.session = requests.Session()    

    def make_request(self, url, params={}, added_headers=None, verb='get', data=None, code_ok=200):

        headers = defs.SECURE_HEADER

        if added_headers is not None:   
            for k in added_headers.keys():
                headers[k] = added_headers[k]
                
        try:
            response = None
            if verb == 'post':
                response = self.session.post(url,params=params,headers=headers,data=data)
            elif verb == 'put':
                response = self.session.put(url,params=params,headers=headers,data=data)
            else:
                response = self.session.get(url,params=params,headers=headers,data=data)

            status_code = response.status_code

            if status_code == code_ok:
                json_response = response.json()
                return status_code, json_response
            else:
                return status_code, None   

        except:
            print("ERROR")
            return 400, None 

    def fetch_instruments(self):
        url =  f'{defs.OANDA_URL}/accounts/{defs.ACCOUNT_ID}/instruments'
        status_code, data = self.make_request(url)
        return status_code, data

    def get_instruments_df(self):
        code, data = self.fetch_instruments()
        if code == 200:
            df = pd.DataFrame.from_dict(data['instruments'])
            return df[['name','type','displayName','pipLocation','marginRate']]
        else:
            return None

    def save_instruments(self):
        df = self.get_instruments_df()
        if df is not None:
            df.to_pickle(utils.get_instruments_data_filename())

    def fetch_candles(self, pair_name, count=10, granularity = "H4", tick = False):
        url = f"{defs.OANDA_URL}/instruments/{pair_name}/candles"

        params = dict(
            granularity = granularity,
            price = "MBA"
        )
        
        params['count'] = count
        
        status_code, data = self.make_request(url, params=params)

        #Check for Error codes and do a pass
        if status_code != 200 or data == None:
            return status_code, data
        
        df = OandaAPI.candles_to_df(data['candles'])

        if tick == False:
            df.drop(df.tail(1).index, inplace = True)

        return status_code, df

    def last_complete_candle(self, pair_name, granularity="H4"):
        code, df = self.fetch_candles(pair_name, granularity=granularity)
        if df is None or df.shape[0] == 0:
            return None
        return df.iloc[-1].time     

    def close_trade(self, trade_id):
        url = f"{defs.OANDA_URL}/accounts/{defs.ACCOUNT_ID}/trades/{trade_id}/close"
        status_code, json_data = self.make_request(url, verb = 'put', code_ok=200)
        if status_code != 200:
            return False
        return True

    def set_sl_tp(self, price, order_type, trade_id):
        url = f"{defs.OANDA_URL}/accounts/{defs.ACCOUNT_ID}/orders"

        data = {
            "order" : {
                "timeInForce" : "GTC",
                "price" : str(price), 
                "type" : order_type,
                "tradeID" : str(trade_id)
            }
        }

        status_code, json_data = self.make_request(url, verb = 'post', data =json.dumps(data), code_ok=201)

        if status_code != 201:
            return False
        return True

    def place_trade(self,pair,units,take_profit,stop_loss):
        url = f"{defs.OANDA_URL}/accounts/{defs.ACCOUNT_ID}/orders"

        data = {
            "order" : {
                "units" : units,
                "instrument" : pair,
                "timeInForce" : "FOK",
                "type" : "MARKET",
                "positionFill" : "DEFAULT"
            }
        }
        status_code, json_data = self.make_request(url, verb = 'post', data =json.dumps(data), code_ok=201)

        trade_id = None
        ok = True
        price = None

        if "orderFillTransaction" in json_data and "price" in json_data['orderFillTransaction']:
            price = float(json_data["orderFillTransaction"]["price"])
     
        if "orderFillTransaction" in json_data and "tradeOpened" in json_data['orderFillTransaction']:
            trade_id =  int(json_data["orderFillTransaction"]["tradeOpened"]["tradeID"])
            if (self.set_sl_tp(take_profit, "TAKE_PROFIT", trade_id) == False):
                ok = False
            if (self.set_sl_tp(stop_loss, "STOP_LOSS", trade_id) == False):
                ok = False    
        
        return trade_id, price, ok

    @classmethod
    def candles_to_df(cls, json_data):
        prices = ['mid', 'bid', 'ask']
        ohlc = ['o', 'h', 'l', 'c']

        our_data = []
        for candle in json_data:
            # if candle['complete'] == False: 
            #      continue
            new_dict = {}
            new_dict['time'] = candle['time']
            new_dict['volume'] = candle['volume']
            for price in prices:
                for oh in ohlc:
                    new_dict[f"{price}_{oh}"] = float(candle[price][oh])
            our_data.append(new_dict)   
        df = pd.DataFrame.from_dict(our_data)
        df["time"] = [parse(x) for x in df.time]
        return df 

if __name__ == "__main__":
    api = OandaAPI()
    print(api.last_complete_candle("EUR_USD"))