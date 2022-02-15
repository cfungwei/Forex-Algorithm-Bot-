import pandas as pd

def EMA(df,length):
    df["mid_c"] = df["mid_c"].apply(pd.to_numeric)
    multiplier = (2 / (length + 1))
    Sum = 0
    for price in df.mid_c[:length]:
        Sum = price + Sum   
    sma = Sum/length
    ema = [0] * (length-1)
    ema.append(sma)

    for price in df.mid_c[length:]:
        EMAlist = price * multiplier + ema[-1] * (1 - multiplier)
        ema.append(EMAlist)
    
    df[f'EMA_{length}'] = ema

    return df

def MACD(df,fast,slow,signal):
    #EMA_12
    df= EMA(df,fast)
    #EMA_26
    df = EMA(df,slow)

    df['MACD_LINE'] = df[f'EMA_{fast}'] - df[f'EMA_{slow}']
    
    multiplier = (2 / (signal + 1))
    Sum = 0
    for price in df.MACD_LINE[:9]:
        Sum = price + Sum    
    sma = Sum/signal
    ema = [0] * (signal-1)
    ema.append(sma)

    for price in df.MACD_LINE[9:]:
        EMAlist = price * multiplier + ema[-1] * (1 - multiplier)
        ema.append(EMAlist)
    
    df['SIGNAL_LINE'] = ema

    df['MACD_HIST'] = df['MACD_LINE'] - df['SIGNAL_LINE']
    df['PREV_MACD'] = df['MACD_HIST'].shift(1)
    df['MACD_DIFF'] = df['MACD_HIST'] - df['PREV_MACD']

    return df

def RSI(df,length):
    df["mid_c"] = df["mid_c"].apply(pd.to_numeric)
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

def Stochastic(df,length,Dsmooth,Ksmooth):
    df["mid_c"] = df["mid_c"].apply(pd.to_numeric)
    df["mid_h"] = df["mid_h"].apply(pd.to_numeric)
    df["mid_l"] = df["mid_l"].apply(pd.to_numeric)

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

def ADX(df,weight):
    df["mid_c"] = df["mid_c"].apply(pd.to_numeric)
    df["mid_h"] = df["mid_h"].apply(pd.to_numeric)
    df["mid_l"] = df["mid_l"].apply(pd.to_numeric)

    df["prevh"] = df["mid_h"].shift(1)
    df["prevl"] = df["mid_l"].shift(1)
    df["prevc"] = df["mid_c"].shift(1)
    df["+DM"] = df.apply(lambda r : (r["mid_h"] - r["prevh"]) if (r["mid_h"] - r["prevh"] > 0 and r["mid_h"] - r["prevh"] > r["prevl"] - r["mid_l"]) else 0, 1)
    df["-DM"] = df.apply(lambda r : r["prevl"] - r["mid_l"] if (r["prevl"] - r["mid_l"] > 0 and r["prevl"] - r["mid_l"] > r["mid_h"] - r["prevh"]) else 0, 1)
    df["TR"] = df.apply(lambda r: max(abs(r["mid_l"] - r["prevc"]), abs(r["mid_h"] - r["prevc"]), r["mid_h"] - r["mid_l"]), 1)
    df.loc[0,"TR"] = df["mid_h"].iloc[0] - df["mid_l"].iloc[0]

    pDM = [0]*weight; pDM.append(df["+DM"][:weight+1].sum())
    mDM = [0]*weight; mDM.append(df["-DM"][:weight+1].sum())
    TR14 = [0]*weight; TR14.append(df["TR"][:weight+1].sum())
    ATR = [0]*weight; ATR.append(df["TR"][:weight+1].sum()/weight)

    for idx in range(weight+1,len(df)):
        plusDM1 = pDM[-1] * ((weight - 1)/weight) + df["+DM"].iloc[idx]
        pDM.append(plusDM1)

        minusDM1 = mDM[-1] * ((weight - 1)/weight) + df["-DM"].iloc[idx]
        mDM.append(minusDM1)

        TR1 = TR14[-1] * ((weight - 1)/weight) + df["TR"].iloc[idx]
        TR14.append(TR1)

        ATR.append((ATR[-1]*13 + df["TR"].iloc[idx])/weight)

    df["ATR"] = ATR
    df["S+DM"] = pDM; df["+DI14"] = (df["S+DM"]/df["ATR"])*100
    df["S-DM"] = mDM; df["-DI14"] = (df["S-DM"]/df["ATR"])*100

    df["DI14 diff"] = abs(df["+DI14"] - df["-DI14"])
    df["DI14 sum"] = abs(df["+DI14"] + df["-DI14"])

    df["DX"] = (df["DI14 diff"]/df["DI14 sum"])*100
    
    ADX = [0]*(2*weight-1); ADX.append(df["DX"][weight: 2*weight].sum()/weight)

    for idx in range(2*weight,len(df)):
        ADX.append((ADX[-1]*(weight - 1) + df["DX"].iloc[idx])/weight)

    df["ADX"] = ADX

    return df