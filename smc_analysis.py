from typing import List, Dict, Optional

class SMCBot:
    """Smart Money Concepts Analysis Engine"""
    
    def __init__(self, instrument_name: str):
        self.instrument = instrument_name
        self.mitigated_h4_pois = set()
        self.mitigated_h1_pois = set()

    def analyze(self, h4_data: List[Dict], h1_data: List[Dict]) -> Dict:
        """Main analysis method that combines 4H bias and 1H entry logic"""
        if len(h4_data) < 5 or len(h1_data) < 5:
            return self._format_no_trade("INVALID_STRUCTURE", "Waiting for more candle data.")

        # Get 4H bias
        bias_analysis = self._get_4h_bias(h4_data)
        if "error" in bias_analysis:
            return self._format_no_trade(bias_analysis["reason"], bias_analysis["error"])

        bias = bias_analysis["bias"]
        h4_poi = bias_analysis["poi"]
        
        # Check if 4H POI is mitigated
        if not self._is_mitigated(h4_poi, h4_data):
            return self._format_no_trade("WAITING_FOR_4H_POI_MITIGATION", f"Waiting for price to tap 4H POI for {bias}")
        
        # Mark 4H POI as mitigated
        if 'time' in h4_poi and h4_poi['time'] not in self.mitigated_h4_pois:
            self.mitigated_h4_pois.add(h4_poi['time'])
        
        # Get 1H entry
        entry_analysis = self._get_1h_entry(bias, h1_data)
        if "error" in entry_analysis:
            return self._format_no_trade(entry_analysis["reason"], entry_analysis["error"])
        
        h1_poi = entry_analysis["poi"]

        # Check if 1H POI is mitigated
        if not self._is_mitigated(h1_poi, h1_data):
            return self._format_no_trade("WAITING_FOR_1H_POI_MITIGATION", "Waiting for price to tap 1H POI")
        
        # Mark 1H POI as mitigated
        if 'time' in h1_poi and h1_poi['time'] not in self.mitigated_h1_pois:
            self.mitigated_h1_pois.add(h1_poi['time'])

        # Prepare trade
        return self._prepare_trade(bias, h1_poi, h1_data)

    def _get_4h_bias(self, h4_data: List[Dict]) -> Dict:
        """Determine 4H bias based on liquidity sweep and market structure shift"""
        swings = self._get_swing_points(h4_data)
        if not swings['highs'] or not swings['lows']:
            return {"error": "Insufficient swing points", "reason": "INVALID_STRUCTURE"}
        
        last_candle = h4_data[-1]
        
        # Check for bullish bias (sweep low -> MSS high -> price above MSS)
        swept_low = self._find_liquidity_sweep(swings['lows'], last_candle, "low")
        if swept_low:
            mss_high = self._find_mss(swept_low, swings['highs'], "bullish")
            if mss_high and last_candle['close'] > mss_high['high']:
                poi = self._find_poi_after_mss(mss_high, h4_data, "bullish")
                if poi:
                    return {"bias": "BUY", "poi": poi}
        
        # Check for bearish bias (sweep high -> MSS low -> price below MSS)
        swept_high = self._find_liquidity_sweep(swings['highs'], last_candle, "high")
        if swept_high:
            mss_low = self._find_mss(swept_high, swings['lows'], "bearish")
            if mss_low and last_candle['close'] < mss_low['low']:
                poi = self._find_poi_after_mss(mss_low, h4_data, "bearish")
                if poi:
                    return {"bias": "SELL", "poi": poi}

        return {"error": "Waiting for 4H liquidity sweep & MSS.", "reason": "NO_SETUP"}

    def _get_1h_entry(self, bias: str, h1_data: List[Dict]) -> Dict:
        """Find 1H entry based on bias direction"""
        swings = self._get_swing_points(h1_data)
        if not swings['highs'] or not swings['lows']:
            return {"error": "Insufficient swing points", "reason": "INVALID_STRUCTURE"}
        
        last_candle = h1_data[-1]

        if bias == "BUY":
            swept_low = self._find_liquidity_sweep(swings['lows'], last_candle, "low", is_mini=True)
            if swept_low:
                mss_high = self._find_mss(swept_low, swings['highs'], "bullish")
                if mss_high and last_candle['close'] > mss_high['high']:
                    poi = self._find_poi_after_mss(mss_high, h1_data, "bullish", is_1h=True)
                    if poi:
                        return {"poi": poi}

        elif bias == "SELL":
            swept_high = self._find_liquidity_sweep(swings['highs'], last_candle, "high", is_mini=True)
            if swept_high:
                mss_low = self._find_mss(swept_high, swings['lows'], "bearish")
                if mss_low and last_candle['close'] < mss_low['low']:
                    poi = self._find_poi_after_mss(mss_low, h1_data, "bearish", is_1h=True)
                    if poi:
                        return {"poi": poi}

        return {"error": "Waiting for 1H liquidity sweep & MSS.", "reason": "NO_SETUP"}
    
    def _get_swing_points(self, data: List[Dict]) -> Dict:
        """Identify swing highs and lows"""
        highs, lows = [], []
        if len(data) < 3:
            return {"highs": highs, "lows": lows}
        
        for i in range(1, len(data) - 1):
            # Swing high: higher than both neighbors
            if data[i]['high'] >= data[i-1]['high'] and data[i]['high'] > data[i+1]['high']:
                highs.append(data[i])
            # Swing low: lower than both neighbors
            if data[i]['low'] <= data[i-1]['low'] and data[i]['low'] < data[i+1]['low']:
                lows.append(data[i])
        
        return {"highs": highs, "lows": lows}

    def _find_liquidity_sweep(self, swings: List[Dict], current_candle: Dict, side: str, is_mini: bool = False) -> Optional[Dict]:
        """Find liquidity sweep events"""
        if not swings:
            return None
        
        last_swing = swings[-1]
        
        if side == "low" and current_candle['low'] < last_swing['low']:
            return last_swing
        if side == "high" and current_candle['high'] > last_swing['high']:
            return last_swing
        
        return None

    def _find_mss(self, swept_point: Dict, opposite_swings: List[Dict], direction: str) -> Optional[Dict]:
        """Find Market Structure Shift (MSS)"""
        # Get swings before the swept point
        relevant_swings = [s for s in opposite_swings if s['time'] < swept_point['time']]
        
        if not relevant_swings:
            return None
        
        # Return the most recent swing before the swept point
        return max(relevant_swings, key=lambda x: x['time'])

    def _find_poi_after_mss(self, mss_point: Dict, data: List[Dict], direction: str, is_1h: bool = False) -> Optional[Dict]:
        """Find Point of Interest (POI) after Market Structure Shift"""
        # Get candles after MSS
        search_range = [c for c in data if c['time'] > mss_point['time']]
        if not search_range:
            return None
        
        # Find order blocks
        order_blocks = self._find_order_blocks(search_range, direction)
        
        # Filter out already mitigated POIs
        mitigated_pois = self.mitigated_h1_pois if is_1h else self.mitigated_h4_pois
        valid_pois = [ob for ob in order_blocks if ob.get('time') not in mitigated_pois]
        
        # Return the most recent valid POI
        return valid_pois[-1] if valid_pois else None

    def _find_order_blocks(self, data: List[Dict], direction: str) -> List[Dict]:
        """Find order blocks (POIs) in the data"""
        order_blocks = []
        
        if len(data) < 2:
            return order_blocks
        
        for i in range(1, len(data)):
            prev_candle = data[i-1]
            current_candle = data[i]
            
            # Check for strong momentum candle
            prev_body = abs(prev_candle['close'] - prev_candle['open'])
            current_body = abs(current_candle['close'] - current_candle['open'])
            is_strong = current_body > prev_body
            
            if direction == "bullish":
                # Look for bearish to bullish reversal with strong momentum
                if (prev_candle['close'] < prev_candle['open'] and 
                    current_candle['close'] > current_candle['open'] and 
                    is_strong):
                    order_blocks.append(prev_candle)
            
            elif direction == "bearish":
                # Look for bullish to bearish reversal with strong momentum
                if (prev_candle['close'] > prev_candle['open'] and 
                    current_candle['close'] < current_candle['open'] and 
                    is_strong):
                    order_blocks.append(prev_candle)
        
        return order_blocks

    def _is_mitigated(self, poi: Dict, data: List[Dict]) -> bool:
        """Check if a POI has been mitigated (price has touched it)"""
        if not poi or 'time' not in poi:
            return False
        
        # Get candles after the POI
        candles_after = [c for c in data if c.get('time', 0) > poi['time']]
        
        # Check if any candle has touched the POI range
        for candle in candles_after:
            if candle['low'] <= poi['high'] and candle['high'] >= poi['low']:
                return True
        
        return False

    def _prepare_trade(self, bias: str, poi: Dict, h1_data: List[Dict]) -> Dict:
        """Prepare trade parameters with risk analysis"""
        # Set entry based on POI
        entry = float(poi['high'] if bias == "SELL" else poi['low'])
        
        # Get swing points for TP calculation
        swings = self._get_swing_points(h1_data)
        
        if bias == "BUY":
            # Stop loss below POI with buffer
            sl = float(poi['low']) * 0.9995
            
            # Take profit at next swing high or default
            future_highs = [s for s in swings['highs'] if s.get('time', 0) > poi.get('time', 0)]
            tp = float(future_highs[0]['high']) if future_highs else entry * 1.005
        else:  # SELL
            # Stop loss above POI with buffer
            sl = float(poi['high']) * 1.0005
            
            # Take profit at next swing low or default
            future_lows = [s for s in swings['lows'] if s.get('time', 0) > poi.get('time', 0)]
            tp = float(future_lows[0]['low']) if future_lows else entry * 0.995
        
        # Calculate risk analysis
        risk_analysis = self._calculate_risk_score(bias, entry, sl, tp, h1_data, poi)
        
        # Prepare trade dictionary
        trade = {
            "action": "taketrade",
            "order_type": bias,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "risk_level": risk_analysis["level"],
            "risk_score": risk_analysis["score"],
            "confidence": risk_analysis["confidence"],
            "recommendation": risk_analysis["recommendation"],
            "risk_factors": risk_analysis["factors"]
        }
        
        # Clear mitigated POIs after trade signal
        self.mitigated_h1_pois.clear()
        self.mitigated_h4_pois.clear()
        
        return trade

    def _calculate_risk_score(self, bias: str, entry: float, sl: float, tp: float, h1_data: List[Dict], poi: Dict) -> Dict:
        """Calculate comprehensive risk analysis"""
        risk_factors = []
        score = 0
        
        # 1. Risk-Reward Ratio (30% of score)
        risk = abs(entry - sl)
        reward = abs(tp - entry)
        rr_ratio = reward / risk if risk > 0 else 0
        
        if rr_ratio >= 3:
            score += 30
            risk_factors.append("Excellent R:R ratio (1:3+)")
        elif rr_ratio >= 2:
            score += 20
            risk_factors.append("Good R:R ratio (1:2+)")
        elif rr_ratio >= 1.5:
            score += 10
            risk_factors.append("Acceptable R:R ratio (1:1.5+)")
        else:
            risk_factors.append("Poor R:R ratio (<1:1.5)")
        
        # 2. POI Quality (25% of score)
        poi_strength = self._analyze_poi_quality(poi, h1_data)
        if poi_strength >= 0.8:
            score += 25
            risk_factors.append("Strong POI formation")
        elif poi_strength >= 0.6:
            score += 15
            risk_factors.append("Good POI formation")
        elif poi_strength >= 0.4:
            score += 8
            risk_factors.append("Weak POI formation")
        else:
            risk_factors.append("Very weak POI formation")
        
        # 3. Market Structure Alignment (20% of score)
        structure_score = self._analyze_market_structure(h1_data, bias)
        if structure_score >= 0.8:
            score += 20
            risk_factors.append("Strong market structure")
        elif structure_score >= 0.6:
            score += 12
            risk_factors.append("Good market structure")
        else:
            score += 5
            risk_factors.append("Weak market structure")
        
        # 4. Volume/Momentum (15% of score)
        momentum_score = self._analyze_momentum(h1_data)
        if momentum_score >= 0.7:
            score += 15
            risk_factors.append("Strong momentum")
        elif momentum_score >= 0.5:
            score += 10
            risk_factors.append("Moderate momentum")
        else:
            score += 3
            risk_factors.append("Weak momentum")
        
        # 5. Confluence Factors (10% of score)
        confluence = self._check_confluence(h1_data, poi)
        score += confluence * 10
        if confluence >= 0.7:
            risk_factors.append("Multiple confluence factors")
        
        # Determine risk level and recommendation
        if score >= 80:
            level = "LOW"
            confidence = f"{min(99, 85 + (score-80)//2)}%"
            recommendation = "STRONG BUY/SELL - Execute Trade"
        elif score >= 60:
            level = "MEDIUM"
            confidence = f"{min(85, 70 + (score-60)//3)}%"
            recommendation = "MODERATE - Consider Trade"
        elif score >= 40:
            level = "HIGH"
            confidence = f"{min(70, 50 + (score-40)//4)}%"
            recommendation = "RISKY - Avoid Trade"
        else:
            level = "VERY HIGH"
            confidence = f"{max(30, score)}%"
            recommendation = "DO NOT TRADE"
        
        return {
            "level": level,
            "score": score,
            "confidence": confidence,
            "recommendation": recommendation,
            "factors": risk_factors,
            "rr_ratio": round(rr_ratio, 2)
        }

    def _analyze_poi_quality(self, poi: Dict, h1_data: List[Dict]) -> float:
        """Analyze POI formation quality"""
        if not poi:
            return 0.0
        
        score = 0.5  # Base score
        
        # Check candle body size
        body_size = abs(poi['close'] - poi['open'])
        candle_range = poi['high'] - poi['low']
        
        if body_size / candle_range > 0.7:  # Strong body
            score += 0.3
        elif body_size / candle_range > 0.5:
            score += 0.2
        
        # Check wick rejection
        if poi['close'] > poi['open']:  # Bullish
            upper_wick = poi['high'] - poi['close']
            lower_wick = poi['open'] - poi['low']
            if lower_wick > upper_wick * 2:  # Strong rejection
                score += 0.2
        else:  # Bearish
            upper_wick = poi['high'] - poi['open']
            lower_wick = poi['close'] - poi['low']
            if upper_wick > lower_wick * 2:  # Strong rejection
                score += 0.2
        
        return min(1.0, score)

    def _analyze_market_structure(self, h1_data: List[Dict], bias: str) -> float:
        """Analyze market structure strength"""
        if len(h1_data) < 5:
            return 0.5
        
        recent_candles = h1_data[-5:]
        
        if bias == "BUY":
            # Check for higher lows pattern
            lows = [c['low'] for c in recent_candles]
            higher_lows = sum(1 for i in range(1, len(lows)) if lows[i] >= lows[i-1])
            return min(1.0, higher_lows / (len(lows) - 1))
        else:
            # Check for lower highs pattern
            highs = [c['high'] for c in recent_candles]
            lower_highs = sum(1 for i in range(1, len(highs)) if highs[i] <= highs[i-1])
            return min(1.0, lower_highs / (len(highs) - 1))

    def _analyze_momentum(self, h1_data: List[Dict]) -> float:
        """Analyze price momentum"""
        if len(h1_data) < 3:
            return 0.5
        
        recent = h1_data[-3:]
        
        # Calculate average body size (momentum indicator)
        body_sizes = [abs(c['close'] - c['open']) for c in recent]
        ranges = [c['high'] - c['low'] for c in recent]
        
        avg_body_ratio = sum(body_sizes[i] / ranges[i] for i in range(len(recent))) / len(recent)
        
        return min(1.0, avg_body_ratio * 1.5)

    def _check_confluence(self, h1_data: List[Dict], poi: Dict) -> float:
        """Check for confluence factors"""
        confluences = 0
        total_factors = 3
        
        # 1. Round number levels
        entry_level = poi.get('low', poi.get('high', 0))
        if self._is_round_number(entry_level):
            confluences += 1
        
        # 2. Previous support/resistance
        if self._is_previous_sr_level(entry_level, h1_data):
            confluences += 1
        
        # 3. Fibonacci levels (simplified)
        if self._is_fibonacci_level(entry_level, h1_data):
            confluences += 1
        
        return confluences / total_factors

    def _is_round_number(self, price: float) -> bool:
        """Check if price is near round number"""
        str_price = f"{price:.5f}"
        last_digits = str_price[-2:]
        return last_digits in ['00', '50'] or str_price[-3:] in ['000', '500']

    def _is_previous_sr_level(self, price: float, h1_data: List[Dict]) -> bool:
        """Check if price is near previous support/resistance"""
        tolerance = price * 0.001  # 0.1% tolerance
        
        for candle in h1_data[:-3]:  # Exclude recent candles
            if abs(candle['high'] - price) <= tolerance or abs(candle['low'] - price) <= tolerance:
                return True
        return False

    def _is_fibonacci_level(self, price: float, h1_data: List[Dict]) -> bool:
        """Simplified Fibonacci level check"""
        if len(h1_data) < 10:
            return False
        
        recent_high = max(c['high'] for c in h1_data[-10:])
        recent_low = min(c['low'] for c in h1_data[-10:])
        range_size = recent_high - recent_low
        
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        tolerance = range_size * 0.02  # 2% tolerance
        
        for fib in fib_levels:
            fib_price = recent_low + (range_size * fib)
            if abs(price - fib_price) <= tolerance:
                return True
        
        return False

    def _format_no_trade(self, reason: str, details: str) -> Dict:
        """Format no-trade response"""
        return {
            "action": "don'ttaketrade",
            "reason": reason,
            "details": details
        }
