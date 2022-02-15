import json

class Settings():
    def __init__(self,pair,units,ema_5,ema_10,stochastic,RSI,MACD):
        self.pair = pair
        self.units = units
        self.ema_5 = ema_5
        self.ema_10 = ema_10
        self.stochastic = stochastic
        self.RSI = RSI
        self.MACD = MACD

    def __repr__(self):
        return str(vars(self))

    @classmethod
    def from_file_ob(cls,ob):
        return Settings(ob['pair'],ob['units'],ob['EMA_5'],ob['EMA_10'],ob['stochastic'],ob['RSI'],ob['MACD'])
    
    @classmethod
    def load_settings(cls):
        data = json.loads(open('settings.json','r').read())
        return { k:cls.from_file_ob(v) for k,v in data.items() }
    
    @classmethod
    def get_pairs(cls):
        settings = cls.load_settings()
        return list(cls.load_settings().keys())

if __name__ == '__main__':
    print(Settings.load_settings())