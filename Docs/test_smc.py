
"""
Test script to validate SMC analysis with provided JSON data
"""
import json
from smc_analysis import SMCBot

def test_smc_analysis():
    # Create test data that will generate a trade signal
    test_data = {
        "h4_data": [
            {"time": 1719000000, "open": 110.00, "high": 112.00, "low": 108.00, "close": 111.00, "volume": 0},
            {"time": 1719003600, "open": 111.00, "high": 113.00, "low": 107.00, "close": 109.00, "volume": 0},  # Swing low at 107
            {"time": 1719007200, "open": 109.00, "high": 114.00, "low": 109.00, "close": 113.00, "volume": 0},  # Swing high at 114
            {"time": 1719010800, "open": 113.00, "high": 115.00, "low": 110.00, "close": 112.00, "volume": 0},  # Higher high
            {"time": 1719014400, "open": 112.00, "high": 113.00, "low": 106.50, "close": 108.00, "volume": 0},  # Low sweep (breaks 107)
            {"time": 1719018000, "open": 108.00, "high": 111.00, "low": 107.50, "close": 110.50, "volume": 0},  # Recovery
            {"time": 1719021600, "open": 110.50, "high": 115.50, "low": 110.00, "close": 115.00, "volume": 0}   # MSS (breaks 114)
        ],
        "h1_data": [
            {"time": 1719025200, "open": 115.00, "high": 116.00, "low": 114.50, "close": 115.50, "volume": 0},
            {"time": 1719028800, "open": 115.50, "high": 116.50, "low": 113.00, "close": 114.00, "volume": 0},  # Swing low at 113
            {"time": 1719032400, "open": 114.00, "high": 117.00, "low": 113.50, "close": 116.50, "volume": 0},  # Swing high at 117
            {"time": 1719036000, "open": 116.50, "high": 117.50, "low": 112.50, "close": 113.50, "volume": 0},  # Low sweep (breaks 113)
            {"time": 1719039600, "open": 113.50, "high": 115.00, "low": 113.00, "close": 114.50, "volume": 0},  # Bullish candle (POI)
            {"time": 1719043200, "open": 114.50, "high": 118.00, "low": 114.00, "close": 117.50, "volume": 0},  # Strong bullish (MSS breaks 117)
            {"time": 1719046800, "open": 117.50, "high": 118.50, "low": 114.00, "close": 114.20, "volume": 0}   # Price taps POI at 114
        ]
    }
    
    print("=" * 60)
    print("SMC ANALYSIS TEST")
    print("=" * 60)
    
    # Create SMC bot instance
    bot = SMCBot("TEST_PAIR")
    
    # Run analysis
    print("Running SMC analysis on test data...")
    result = bot.analyze(test_data["h4_data"], test_data["h1_data"])
    
    print("\nANALYSIS RESULT:")
    print("-" * 40)
    print(json.dumps(result, indent=2))
    
    # Detailed breakdown
    print("\nDETAILED BREAKDOWN:")
    print("-" * 40)
    
    # Check swing points
    h4_swings = bot._get_swing_points(test_data["h4_data"])
    h1_swings = bot._get_swing_points(test_data["h1_data"])
    
    print(f"4H Swing Highs: {len(h4_swings['highs'])}")
    for i, swing in enumerate(h4_swings['highs']):
        print(f"  High {i+1}: {swing['high']} at time {swing['time']}")
    
    print(f"4H Swing Lows: {len(h4_swings['lows'])}")
    for i, swing in enumerate(h4_swings['lows']):
        print(f"  Low {i+1}: {swing['low']} at time {swing['time']}")
    
    print(f"\n1H Swing Highs: {len(h1_swings['highs'])}")
    for i, swing in enumerate(h1_swings['highs']):
        print(f"  High {i+1}: {swing['high']} at time {swing['time']}")
    
    print(f"1H Swing Lows: {len(h1_swings['lows'])}")
    for i, swing in enumerate(h1_swings['lows']):
        print(f"  Low {i+1}: {swing['low']} at time {swing['time']}")
    
    # Test 4H bias
    print("\n4H BIAS Analysis:")
    print("-" * 20)
    bias_result = bot._get_4h_bias(test_data["h4_data"])
    print(json.dumps(bias_result, indent=2))
    
    # Test liquidity sweeps
    print("\nLIQUIDITY SWEEP Tests:")
    print("-" * 20)
    last_h4_candle = test_data["h4_data"][-1]
    last_h1_candle = test_data["h1_data"][-1]
    
    h4_low_sweep = bot._find_liquidity_sweep(h4_swings['lows'], last_h4_candle, "low")
    h4_high_sweep = bot._find_liquidity_sweep(h4_swings['highs'], last_h4_candle, "high")
    
    print(f"4H Low Sweep: {'Found' if h4_low_sweep else 'None'}")
    if h4_low_sweep:
        print(f"  Swept Low: {h4_low_sweep['low']} at time {h4_low_sweep['time']}")
        print(f"  Current Low: {last_h4_candle['low']}")
    
    print(f"4H High Sweep: {'Found' if h4_high_sweep else 'None'}")
    if h4_high_sweep:
        print(f"  Swept High: {h4_high_sweep['high']} at time {h4_high_sweep['time']}")
        print(f"  Current High: {last_h4_candle['high']}")
    
    print("\n" + "=" * 60)
    
    # Summary
    if result["action"] == "taketrade":
        print("TRADE SIGNAL GENERATED!")
        print(f"Direction: {result['order_type']}")
        print(f"Entry: {result['entry']}")
        print(f"Stop Loss: {result['sl']}")
        print(f"Take Profit: {result['tp']}")
    else:
        print("NO TRADE SIGNAL")
        print(f"Reason: {result['reason']}")
        print(f"Details: {result['details']}")
    
    return result

if __name__ == "__main__":
    test_smc_analysis()