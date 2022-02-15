import json
import defs
import pandas as pd
import datetime

from oanda_api import OandaAPI
from settings import Settings

class Analysis():
    def __init__(self):
        self.api = OandaAPI()
        self.firstTransactionID = 607
        self.trade_pairs = Settings.get_pairs()

    def retrieve_activities(self,TransactionID):
        url = f"{defs.OANDA_URL}/accounts/{defs.ACCOUNT_ID}/transactions/sinceid"
        params = {'id' : TransactionID}
        
        #if error
        for i in range(5):
            status_code, json_data = self.api.make_request(url,params = params)
            if status_code == 200:
                last_ID = int(json_data["transactions"][-1]['id'])
                lastTransactionID = int(json_data['lastTransactionID'])

                return json_data['transactions'], last_ID, lastTransactionID
        # return error reaction

        

    def create_activities(self,activity):
        activity_df = pd.DataFrame([],columns = ['Datetime','Date','Time','TradeID','Pair','Units','TradeType','Open','TakeProfit','StopLoss','Close Date','Close Time','Close'])
        for item in activity:
            #Opened trades
            if item['type'] == 'ORDER_FILL' and item['reason'] == 'MARKET_ORDER':
                TradeID = item['id']
                Pair = item['instrument']
                Units = int(item['units'])
                if Units > 0:
                    TradeType = 'Long'
                else:
                    TradeType = 'Short'
                Open = float(item['tradeOpened']['price'])
                Datetime = pd.to_datetime(item['time'])
                Date = Datetime.date()
                Time = Datetime.time().replace(microsecond=0)

                newData = [item['time'],Date,Time,TradeID,Pair,Units,TradeType,Open,None,None,None,None,None]
                activity_df.loc[len(activity_df)] = newData
                
            #Closed trades 
            elif item['type'] == 'ORDER_FILL' and item['reason'] in ['MARKET_ORDER_TRADE_CLOSE','TAKE_PROFIT_ORDER','STOP_LOSS_ORDER']:
                Close = float(item['tradesClosed'][0]['price'])
                ID = item['tradesClosed'][0]['tradeID']
                activity_df.loc[activity_df.TradeID == ID,['Close']] = Close
                Datetime = pd.to_datetime(item['time'])
                closeDate = Datetime.date()
                closeTime = Datetime.time().replace(microsecond=0)
                activity_df.loc[activity_df.TradeID == ID,['Close Date']] = closeDate
                activity_df.loc[activity_df.TradeID == ID,['Close Time']] = closeTime
            #TP
            elif item['type'] == 'TAKE_PROFIT_ORDER':
                TakeProfit = float(item['price'])
                ID = item['tradeID']
                activity_df.loc[activity_df.TradeID == ID,['TakeProfit']] = TakeProfit
            #SL
            elif item['type'] == 'STOP_LOSS_ORDER':
                StopLoss = float(item['price'])
                ID = item['tradeID']
                activity_df.loc[activity_df.TradeID == ID,['StopLoss']] = StopLoss
        return activity_df
    
    def store_pair_activites(self,activity_df):
        for pairs in self.trade_pairs:
            df = activity_df.loc[activity_df.Pair == pairs]
            df.to_pickle(f"activity_data/{pairs}_Activity.pkl")

    def update_excel(self):
        xlwriter = pd.ExcelWriter(f'Activity.xlsx')

        df = pd.read_pickle("activity_data/MonthlyOverview.pkl")
        df.to_excel(xlwriter, sheet_name = "MonthlyOverview")

        df = pd.read_pickle("activity_data/WeeklyOverview.pkl")
        df.to_excel(xlwriter, sheet_name = "WeeklyOverview")

        for pair in self.trade_pairs:
            df = pd.read_pickle(f"activity_data/{pair}_Activity.pkl")
            df.to_excel(xlwriter, sheet_name = f"{pair}", index = False)

        xlwriter.close()

    def check_type(self,row):
        if row.Close is not None and row.Open is not None:
            if "JPY" in row.Pair:
                if row.TradeType == "Long":
                    return (row.Close - row.Open)*100
                else:
                    return (row.Open - row.Close)*100
            else:
                if row.TradeType == "Long":
                    return (row.Close - row.Open)*10000
                else:
                    return (row.Open - row.Close)*10000
        else:
            return None
    
    def update_pair_activities(self,activity_df):
        activity_df['Pip'] = activity_df.apply(self.check_type,axis = 1)

    def update_overview(self,activity_df):
        monthYear = pd.to_datetime(activity_df['Date']).dt.strftime('%b %Y').unique().tolist()
        
        week = pd.to_datetime(activity_df['Date']).dt.strftime('%W').unique().tolist()

        tuples = [monthYear,['Total Pip','No. of Trades','Average Pip']]
        index = pd.MultiIndex.from_product(tuples)

        tuplesWeek = [week,['Total Pip','No. of Trades','Average Pip']]
        indexWeek = pd.MultiIndex.from_product(tuplesWeek)

        indexed = pd.MultiIndex.from_tuples([("Pair","")]).append(index).append(pd.MultiIndex.from_tuples([("Total Pips","")]))
        indexedWeek = pd.MultiIndex.from_tuples([("Pair","")]).append(indexWeek).append(pd.MultiIndex.from_tuples([("Total Pips","")]))

        df1 = pd.DataFrame(columns = indexed)
        df2 = pd.DataFrame(columns = indexedWeek )

        df1['Pair'] = self.trade_pairs
        df2['Pair'] = self.trade_pairs

        total = []
        totalWeek = []
        monthArray = []
        weekArray = []

        for pair in self.trade_pairs:
            df = pd.read_pickle(f"activity_data/{pair}_Activity.pkl")
            monthTotal = []
            for date in monthYear:
                month_df = df.loc[pd.to_datetime(df['Date']).dt.strftime('%b %Y') == date]
                if month_df.Close.count() != 0:
                    avgPip = month_df.Pip.sum()/month_df.Close.count()
                else:
                    avgPip = 0
                monthTotal.append(month_df.Pip.sum())
                monthTotal.append(month_df.Close.count())
                monthTotal.append(round(avgPip,2))
            monthArray.append(monthTotal)
            total.append(df.Pip.sum())

        df1[index] = monthArray
        df1['Total Pips'] = total
        last = len(df1)
        df1.loc[last] = df1.sum()
        df1.loc[last,("Pair","")] = "Total"


        df1.to_pickle(f"activity_data/MonthlyOverview.pkl")

        for pair in self.trade_pairs:
            df = pd.read_pickle(f"activity_data/{pair}_Activity.pkl")
            weekTotal = []
            for weeks in week:
                week_df = df.loc[pd.to_datetime(activity_df['Date']).dt.strftime('%W') == weeks]
                if week_df.Close.count() != 0:
                    avgPip = week_df.Pip.sum()/week_df.Close.count()
                else:
                    avgPip = 0
                weekTotal.append(week_df.Pip.sum())
                weekTotal.append(week_df.Close.count())
                weekTotal.append(round(avgPip,2))
            weekArray.append(weekTotal)
            totalWeek.append(df.Pip.sum())
        
        df2[indexWeek] = weekArray
        df2['Total Pips'] = totalWeek
        last = len(df2)
        df2.loc[last] = df2.sum()
        df2.loc[last,("Pair","")] = "Total"

        df2.to_pickle(f"activity_data/WeeklyOverview.pkl")




    def run(self):
        json_data, last_id, lastTransactionID = self.retrieve_activities(self.firstTransactionID)
        while last_id != lastTransactionID:
            data, last_id, lastTransactionID = self.retrieve_activities(last_id)
            json_data += data
        activities_df = self.create_activities(json_data)
        self.update_pair_activities(activities_df)
        self.store_pair_activites(activities_df)
        self.update_overview(activities_df)
        self.update_excel()
        print("Excel files updated")


if __name__ == "__main__":
    print("Starting Analysis...")
    a = Analysis()
    a.run()

        

    
