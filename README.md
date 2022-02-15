# Forex-Algorithm-Bot- (Work In Progress)

Packages Requried
---
```
import json
import defs
import pandas as pd
import datetime
import pprint
import time
import telebot
from os import stat
import math
import openpyxl
import logging
import requests
from dateutil.parser import *
import sys
```

Using the REST API, we extract candlestick data from the Oanda website for us to make technical analysis and calculate take profit and stop loss if a trade is made which is to be specified in [strategy code](https://github.com/fungiiiii/Forex-Algorithm-Bot-/blob/main/cowabunga.py)

Some techncial Indicators can be found in [indicator.py](https://github.com/fungiiiii/Forex-Algorithm-Bot-/blob/main/indicators.py) which i have used to try and develop a strategy.
