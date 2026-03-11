"""
Analysis Template for PSX Stock Indicator Bot
This file contains the comprehensive analysis template for the /test command
"""

ANALYSIS_TEMPLATE = """
🔹 Calculate values across all relevant timeframes 
🔹 Compute all indicator values on each timeframe — EMA, HMA, RSI, MACD, Stochastic, Williams %R, Volume, OBV,
   ATR, Bollinger Bands, CCI, ROC, SuperTrend, VWAP, etc.
🔹 Include key market data — open/close/high/low, volume, price ranges
🔹 Provide final output results with answers to all key questions

📍 Final Signal Summary

📉 What is the overall trend direction? (Bullish, Bearish, or Sideways, positive, Negative, Neutral)

📊 Provide a detailed breakdown of all indicators behavior.

🌡 Present a momentum heatmap — Is momentum rising or fading?

📉 Volume Analysis: Does volume support the price movement? Check OBV & MA comparisons

🧪 Historical Comparison: Compare current indicators with historically successful PSX setups

🔄 Breakout or Wait: Is this a breakout, or should we wait for confirmation?
🔄 Setup Type: Reversal or continuation? What confirms this setup?

📉 Price Structure: Are higher highs/lows forming, or is the structure breaking?

🌀 Fractal Patterns: Any repeating patterns from past cycles?

🐾 Over all Is this setup potentially a bull trap or bear trap?

🐾 Are traders overly long/short? Any squeeze setups forming?

🧮 Fibonacci Levels: Is price near key retracement or extension zones?

🧭 Is the price nearing any known liquidity pool zones?

📢 Do you think the price is more likely to decline from here, or is there a greater chance it will rise?

🧭 Sequential Levels High vs Low and probability weighting

🛡 Highlight ideal zones for entry, take profit, and stop-loss

🎯 Based on the setup, is TP1, TP2, or TP3 most likely to be hit?

🧭 According to pakistan time which time is best for entry and trade and exit time

🔁 After taking profit at TP1 or TP2, suggest re-entry levels for the next move

⏳ Compare signals across multiple timeframes (1H, 4H, Daily) — Is there confluence?

🐋 Detect whale movements vs. retail traders — Based on wallet activity or order book flow

✅ Correction will come or no? and Estimate Correction Ranges.

⏳ Intraday trading setup, best entry and exit points 

⏳ Scalping High & Low Table

⏳ Intraday High & Low Table

⏳ Forecast Overview

⏳ Current 24-Hour High & Low (Today)

✅ Best Plan and should I wait for these supports or these are already hit?

📅 Offer a 3-day or weekly forecast — What's the expected asset behavior?

📰 Is there any upcoming news or event that could impact the market or this asset?

📢 Offer final trading advice — Mindset, Psychology, and Position Sizing
"""

def get_analysis_template():
    """Return the analysis template text"""
    return ANALYSIS_TEMPLATE
