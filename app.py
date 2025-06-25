from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import threading
import json
import time
from datetime import datetime, timezone
import os
from trading_bot import LiveOandaTrader

app = Flask(__name__)
app.config['SECRET_KEY'] = 'forex-trading-bot-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global trader instance
trader = None
trader_thread = None

@app.route('/')
def dashboard():
    """Serve the main dashboard page"""
    return render_template('dashboard.html')

@app.route('/api/status')
def get_status():
    """API endpoint to get current bot status"""
    if trader:
        return jsonify(trader.get_dashboard_state())
    return jsonify({
        'connection_status': 'Not Started',
        'uptime': '0s',
        'instruments': {},
        'logs': []
    })

@app.route('/api/test-smc', methods=['POST'])
def test_smc():
    """Test SMC analysis with provided data"""
    from flask import request
    from smc_analysis import SMCBot
    
    try:
        data = request.get_json()
        if not data or 'h4_data' not in data or 'h1_data' not in data:
            return jsonify({'error': 'Missing h4_data or h1_data'}), 400
        
        # Create test bot
        bot = SMCBot('TEST_PAIR')
        
        # Run analysis
        result = bot.analyze(data['h4_data'], data['h1_data'])
        
        # Add swing point analysis for debugging
        h4_swings = bot._get_swing_points(data['h4_data'])
        h1_swings = bot._get_swing_points(data['h1_data'])
        
        debug_info = {
            'h4_swing_highs': len(h4_swings['highs']),
            'h4_swing_lows': len(h4_swings['lows']),
            'h1_swing_highs': len(h1_swings['highs']),
            'h1_swing_lows': len(h1_swings['lows']),
            'h4_swings': h4_swings,
            'h1_swings': h1_swings
        }
        
        return jsonify({
            'analysis_result': result,
            'debug_info': debug_info,
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    """Handle client connection"""
    print('Client connected')
    if trader:
        emit('status_update', trader.get_dashboard_state())

@socketio.on('start_bot')
def handle_start_bot():
    """Start the trading bot"""
    global trader, trader_thread
    
    if trader is None:
        # Configuration
        instruments = 'EUR_USD,USD_JPY,GBP_USD'
        trader = LiveOandaTrader(instruments, socketio)
        
        # Start trader in separate thread
        trader_thread = threading.Thread(target=trader.stream, daemon=True)
        trader_thread.start()
        
        emit('bot_started', {'status': 'Bot started successfully'})
    else:
        emit('bot_already_running', {'status': 'Bot is already running'})

@socketio.on('stop_bot')
def handle_stop_bot():
    """Stop the trading bot"""
    global trader
    if trader:
        trader.stop()
        trader = None
        emit('bot_stopped', {'status': 'Bot stopped successfully'})

def background_status_updates():
    """Send periodic status updates to connected clients"""
    while True:
        if trader:
            socketio.emit('status_update', trader.get_dashboard_state())
        time.sleep(1)  # Update every second

if __name__ == '__main__':
    # Start background status updates
    status_thread = threading.Thread(target=background_status_updates, daemon=True)
    status_thread.start()
    
    # Get port from environment for Replit compatibility
    port = int(os.environ.get('PORT', 5000))
    
    # Run the Flask-SocketIO server with public access
    socketio.run(app, host='0.0.0.0', port=port, debug=False, allow_unsafe_werkzeug=True)
