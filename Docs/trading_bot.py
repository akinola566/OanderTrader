import requests
import json
from datetime import datetime, timezone
import time
import os
from typing import List, Dict, Optional
from smc_analysis import SMCBot

# Configuration
ACCESS_TOKEN = os.getenv('OANDA_ACCESS_TOKEN', '672f8f548ea2c0259ce2e043a27ccdf7-accd7e47d49e5eb316003deadbf45c56')
ACCOUNT_ID = os.getenv('OANDA_ACCOUNT_ID', '101-001-35653324-001')
ENVIRONMENT = os.getenv('OANDA_ENVIRONMENT', 'practice')

class LiveOandaTrader:
    def __init__(self, instruments: str, socketio=None):
        self.socketio = socketio
        self.domain = 'stream-fxpractice.oanda.com' if ENVIRONMENT == 'practice' else 'stream-fxtrade.oanda.com'
        self.url = f'https://{self.domain}/v3/accounts/{ACCOUNT_ID}/pricing/stream'
        self.headers = {'Authorization': f'Bearer {ACCESS_TOKEN}'}
        self.params = {'instruments': instruments}
        self.instrument_list = instruments.split(',')
        self.start_time = time.time()
        self.logs = []
        self.running = False
        
        # Spinner animation
        self.spinner_chars = ['|', '/', '—', '\\']
        self.spinner_index = 0

        # Initialize State for the Dashboard
        self.state = {
            'connection_status': 'Initializing...',
            'uptime': '0s',
            'instruments': {inst: {
                'price': 0.0,
                'analysis_status': 'Connecting...',
                'h1_candles_count': 0,
                'h4_candles_count': 0,
                'spinner': ' ',
                'active_trade': None
            } for inst in self.instrument_list},
            'logs': self.logs
        }
        
        # Bot Logic State Management
        self.smc_bots = {inst: SMCBot(inst) for inst in self.instrument_list}
        self.h1_candles = {inst: [] for inst in self.instrument_list}
        self.h4_candles = {inst: [] for inst in self.instrument_list}
        self.current_h1_candle = {inst: None for inst in self.instrument_list}
        self.current_h4_candle = {inst: None for inst in self.instrument_list}

    def get_spinner(self):
        """Get next spinner character"""
        char = self.spinner_chars[self.spinner_index]
        self.spinner_index = (self.spinner_index + 1) % len(self.spinner_chars)
        return char

    def get_dashboard_state(self):
        """Get current dashboard state"""
        # Update uptime
        uptime_seconds = int(time.time() - self.start_time)
        self.state['uptime'] = f"{uptime_seconds // 3600}h {(uptime_seconds % 3600) // 60}m {uptime_seconds % 60}s"
        return self.state

    def _add_log(self, message: str):
        """Add log message with timestamp"""
        timestamp = datetime.now(timezone.utc).strftime('%H:%M:%S')
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        
        # Keep only last 100 logs to prevent memory issues
        if len(self.logs) > 100:
            self.logs = self.logs[-100:]
        
        # Emit log update if socketio is available
        if self.socketio:
            self.socketio.emit('new_log', {'message': log_entry})

    def _update_candle(self, candle: Optional[Dict], price: float) -> Dict:
        """Update candle data with new price"""
        if not candle:
            return {
                'open': price,
                'high': price,
                'low': price,
                'close': price,
                'start_time': None
            }
        
        candle['high'] = max(candle['high'], price)
        candle['low'] = min(candle['low'], price)
        candle['close'] = price
        return candle

    def _handle_tick(self, tick: Dict):
        """Process incoming price tick"""
        try:
            if tick.get('type') != 'PRICE':
                return
            
            inst = tick['instrument']
            if inst not in self.instrument_list:
                return
            
            # Calculate mid price
            price = (float(tick['bids'][0]['price']) + float(tick['asks'][0]['price'])) / 2
            timestamp = datetime.fromisoformat(tick['time'].replace('Z', '+00:00'))

            # Update dashboard state
            self.state['instruments'][inst]['price'] = price
            self.state['instruments'][inst]['spinner'] = self.get_spinner()

            # Track active trade P/L
            if self.state['instruments'][inst]['active_trade']:
                self._track_active_trade(inst, price)
            
            # Aggregate candles
            self._aggregate_candles(inst, price, timestamp)
            
        except (KeyError, IndexError, ValueError) as e:
            self._add_log(f"Error processing tick: {str(e)}")

    def _track_active_trade(self, inst: str, price: float):
        """Track P/L for active trades"""
        trade = self.state['instruments'][inst]['active_trade']
        entry, sl, tp = trade['entry'], trade['sl'], trade['tp']
        pips_multiplier = 100 if 'JPY' in inst else 10000

        if trade['order_type'] == 'BUY':
            pips = (price - entry) * pips_multiplier
            if price <= sl:
                self._close_trade(inst, price, "STOP LOSS")
            elif price >= tp:
                self._close_trade(inst, price, "TAKE PROFIT")
        else:  # SELL
            pips = (entry - price) * pips_multiplier
            if price >= sl:
                self._close_trade(inst, price, "STOP LOSS")
            elif price <= tp:
                self._close_trade(inst, price, "TAKE PROFIT")
        
        # Update P/L if trade is still active
        if self.state['instruments'][inst]['active_trade']:
            self.state['instruments'][inst]['active_trade']['live_pnl_pips'] = pips

    def _close_trade(self, inst: str, price: float, reason: str):
        """Close active trade"""
        self._add_log(f"🎯 [{inst}] {reason} HIT AT {price}")
        self.state['instruments'][inst]['active_trade'] = None

    def _aggregate_candles(self, inst: str, price: float, timestamp: datetime):
        """Aggregate tick data into candles"""
        current_h1_start_time = timestamp.replace(minute=0, second=0, microsecond=0)
        current_h4_start_time = timestamp.replace(hour=(timestamp.hour//4)*4, minute=0, second=0, microsecond=0)
        
        # 1H Candles
        if self.current_h1_candle[inst] is None:
            self.current_h1_candle[inst] = self._update_candle(None, price)
            self.current_h1_candle[inst]['start_time'] = current_h1_start_time
        
        if current_h1_start_time > self.current_h1_candle[inst]['start_time']:
            # Close current candle
            c = self.current_h1_candle[inst]
            final_candle = {
                "time": int(c['start_time'].timestamp()),
                "open": c['open'],
                "high": c['high'],
                "low": c['low'],
                "close": c['close'],
                "volume": 0
            }
            self.h1_candles[inst].append(final_candle)
            self.state['instruments'][inst]['h1_candles_count'] = len(self.h1_candles[inst])
            self._add_log(f"🕯️ [{inst}] New 1H Candle Closed. Total: {len(self.h1_candles[inst])}")
            
            # Start new candle
            self.current_h1_candle[inst] = self._update_candle(None, price)
            self.current_h1_candle[inst]['start_time'] = current_h1_start_time
            
            # Run analysis if not in trade
            if not self.state['instruments'][inst]['active_trade']:
                self._run_smc_analysis(inst)
        
        # 4H Candles
        if self.current_h4_candle[inst] is None:
            self.current_h4_candle[inst] = self._update_candle(None, price)
            self.current_h4_candle[inst]['start_time'] = current_h4_start_time
        
        if current_h4_start_time > self.current_h4_candle[inst]['start_time']:
            # Close current candle
            c = self.current_h4_candle[inst]
            final_candle = {
                "time": int(c['start_time'].timestamp()),
                "open": c['open'],
                "high": c['high'],
                "low": c['low'],
                "close": c['close'],
                "volume": 0
            }
            self.h4_candles[inst].append(final_candle)
            self.state['instruments'][inst]['h4_candles_count'] = len(self.h4_candles[inst])
            self._add_log(f"🕯️ [{inst}] New 4H Candle Closed. Total: {len(self.h4_candles[inst])}")
            
            # Start new candle
            self.current_h4_candle[inst] = self._update_candle(None, price)
            self.current_h4_candle[inst]['start_time'] = current_h4_start_time
        
        # Update current candles with every tick
        self.current_h1_candle[inst] = self._update_candle(self.current_h1_candle[inst], price)
        self.current_h4_candle[inst] = self._update_candle(self.current_h4_candle[inst], price)

    def _run_smc_analysis(self, inst: str):
        """Run SMC analysis for instrument"""
        bot = self.smc_bots[inst]
        result = bot.analyze(self.h4_candles[inst], self.h1_candles[inst])
        
        # Update analysis status
        self.state['instruments'][inst]['analysis_status'] = result.get('details', 'Analysis complete')
        
        # Handle trade signal
        if result['action'] == 'taketrade':
            result['live_pnl_pips'] = 0.0  # Initialize P/L
            self.state['instruments'][inst]['active_trade'] = result
            self._add_log(f"🚨 [{inst}] TAKE TRADE SIGNAL: {result['order_type']} @ {result['entry']:.5f}")

    def stop(self):
        """Stop the trading bot"""
        self.running = False
        self._add_log("🔌 Trading bot stopped by user")

    def stream(self):
        """Main streaming loop with reconnection logic"""
        self.running = True
        self._add_log("🚀 Trading bot started")
        
        while self.running:
            try:
                self.state['connection_status'] = 'Connecting...'
                response = requests.get(
                    self.url,
                    headers=self.headers,
                    params=self.params,
                    stream=True,
                    timeout=30
                )
                
                if response.status_code != 200:
                    self.state['connection_status'] = f'Error {response.status_code}'
                    self._add_log(f"Connection Error: {response.text}")
                    time.sleep(15)
                    continue

                self.state['connection_status'] = 'Connected'
                self._add_log("✅ Connection successful")
                
                for line in response.iter_lines():
                    if not self.running:
                        break
                        
                    if line:
                        try:
                            data = json.loads(line.decode('utf-8'))
                            self._handle_tick(data)
                        except json.JSONDecodeError:
                            continue

            except requests.exceptions.RequestException as e:
                self.state['connection_status'] = 'Connection Lost'
                self._add_log(f"❌ Connection Error: {str(e)}")
                if self.running:
                    time.sleep(10)
            except Exception as e:
                self._add_log(f"❌ Unexpected error: {str(e)}")
                if self.running:
                    time.sleep(10)
        
        self._add_log("🔌 Trading bot stream ended")
