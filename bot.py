import pprint
import time
import telebot

from settings import Settings
from log_wrapper import LogWrapper
from timing import Timing
from oanda_api import OandaAPI
from cowabunga import Cowabunga
from defs import NONE, BUY, SELL,TELE_API_KEY, USER_ID

tbot = telebot.TeleBot(TELE_API_KEY)

MAIN_GRANULARITY = "H4"
TRADE_GRANULARITY = "M15"
SLEEP = 30

@tbot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    update = str(message)
    if message.chat.id != USER_ID:
        tbot.reply_to(message, f"Bye {message.from_user.username}")
    else:
        tbot.reply_to(message, f"Welcome {message.from_user.username}")

class TradingBot():
    
    def __init__(self):    
        self.log = LogWrapper("TradingBot")
        self.tech_log = LogWrapper("TechnicalsBot")
        self.trade_pairs = Settings.get_pairs()
        self.settings = Settings.load_settings()
        self.api = OandaAPI()
        self.main_timings = { p: Timing(self.api.last_complete_candle(p, MAIN_GRANULARITY)) for p in self.trade_pairs }
        self.timings = { p: Timing(self.api.last_complete_candle(p, TRADE_GRANULARITY)) for p in self.trade_pairs }
        self.log_message(f"Bot started with\n{pprint.pformat(self.settings)}")
        self.log_message(f"Bot Timings\n{pprint.pformat(self.timings)}")
        
    def log_message(self, msg):
        self.log.logger.debug(msg)       
    
    def update_timings(self):        
        for pair in self.trade_pairs:
            main_current = self.api.last_complete_candle(pair, MAIN_GRANULARITY)
            current = self.api.last_complete_candle(pair, TRADE_GRANULARITY)
            self.main_timings[pair].ready = False
            self.timings[pair].ready = False
            if current != None:
                if current > self.timings[pair].last_candle:
                    self.timings[pair].ready = True
                    self.timings[pair].last_candle = current
                    self.log_message(f"{pair} new candle {current}")
            if main_current != None:
                if main_current > self.main_timings[pair].last_candle:
                    self.main_timings[pair].ready = True
                    self.main_timings[pair].last_candle = main_current
                    self.log_message(f"{pair} new candle {current}")                

    def process_pairs(self):    
        for pair in self.trade_pairs:   
            if self.timings[pair].ready == True:    
                techs = Cowabunga(self.settings[pair], self.api, pair, MAIN_GRANULARITY, TRADE_GRANULARITY, log=self.tech_log)
                price, trend, decision ,units, open_price, take_profit, stop_loss= techs.get_trade_decision(self.main_timings[pair].last_candle, self.timings[pair].last_candle)
                # tbot.send_message(USER_ID,f" {pair} \n Timing: {self.timings[pair].last_candle} \n trend : {trend} decision : {decision} price : {float(price)}")
                if trend == 1 and decision == 1:
                    print(f"\n Long Trade pair:{pair} units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss} \n")
                    tbot.send_message(USER_ID,f"Long Trade {pair} \n Timing: {self.timings[pair].last_candle} \n units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")
                    self.log_message(f"Long Trade {pair} \n Timing: {self.timings[pair].last_candle} \n units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")            
                elif trend == -1 and decision == -1:
                    print(f"\n Short Trade pair:{pair} units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss} \n")
                    tbot.send_message(USER_ID,f"Short Trade {pair} \n Timing: {self.timings[pair].last_candle} \n units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")
                    self.log_message(f"Short Trade {pair} \n Timing: {self.timings[pair].last_candle} \n units:{units} price: {open_price} take profit:{take_profit} stop_loss:{stop_loss}")

    def update_trades(self):
        for pair in self.trade_pairs:
            techs = Cowabunga(self.settings[pair], self.api, pair, MAIN_GRANULARITY, TRADE_GRANULARITY)
            status = techs.check_open_trade(self.main_timings[pair].last_candle, self.timings[pair].last_candle)
            if status == [] or status == None:
                pass
            else:
                if 400 in status:
                    tbot.send_message(USER_ID,f"FAILED TO EXIT {pair} TRADE! Exit Trade manually.")
                elif 404:
                    pass
                else:
                    tbot.send_message(USER_ID,f"{pair} closed manually")

    def run(self):
        while True:
            print('update_timings()...')
            self.update_timings()
            print('process_pairs()...')
            self.process_pairs()
            print('update_trades()...')
            self.update_trades()
            print('sleep()...')
            time.sleep(SLEEP)


if __name__ == "__main__":
    b = TradingBot()
    b.run()