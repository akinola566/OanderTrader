// Modern Crypto Trading Bot JavaScript
class CryptoTradingBot {
    constructor() {
        this.socket = null;
        this.isConnected = false;
        this.botRunning = false;
        this.instruments = {};
        this.signalsToday = 0;
        this.successRate = 0;
        this.startTime = null;
        
        this.initializeConnection();
        this.initializeEventListeners();
        this.startUptimeCounter();
    }

    initializeConnection() {
        try {
            this.socket = io();
            this.setupSocketEvents();
        } catch (error) {
            console.error('Socket.IO connection failed:', error);
            this.updateConnectionStatus('Connection Failed', 'error');
        }
    }

    setupSocketEvents() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
            this.isConnected = true;
            this.updateConnectionStatus('🟢 Connected', 'connected');
            this.loadInitialStatus();
        });

        this.socket.on('disconnect', () => {
            console.log('Disconnected from server');
            this.isConnected = false;
            this.updateConnectionStatus('🔴 Disconnected', 'error');
        });

        this.socket.on('status_update', (data) => {
            this.updateDashboard(data);
        });

        this.socket.on('bot_started', () => {
            this.botRunning = true;
            this.startTime = Date.now();
            this.updateBotControls();
            this.updateSignalIndicator('🚀 Bot Active - Scanning Markets...', 'active');
            this.addLogEntry('🚀 Trading bot started - Analyzing crypto markets');
        });

        this.socket.on('bot_stopped', () => {
            this.botRunning = false;
            this.startTime = null;
            this.updateBotControls();
            this.updateSignalIndicator('⏸️ Bot Stopped', 'stopped');
            this.addLogEntry('⏸️ Trading bot stopped');
        });
    }

    initializeEventListeners() {
        const startBtn = document.getElementById('start-bot');
        const stopBtn = document.getElementById('stop-bot');

        if (startBtn) {
            startBtn.addEventListener('click', () => this.startBot());
        }

        if (stopBtn) {
            stopBtn.addEventListener('click', () => this.stopBot());
        }
    }

    async loadInitialStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();
            
            if (data.bot_running) {
                this.botRunning = true;
                this.startTime = Date.now();
                this.updateSignalIndicator('🚀 Bot Active - Scanning Markets...', 'active');
            }
            
            this.updateBotControls();
            this.updateDashboard(data);
        } catch (error) {
            console.error('Failed to load initial status:', error);
        }
    }

    startBot() {
        if (this.isConnected && this.socket) {
            this.socket.emit('start_bot');
            this.addLogEntry('🔄 Starting trading bot...');
        } else {
            this.addLogEntry('❌ Cannot start bot - No connection to server');
        }
    }

    stopBot() {
        if (this.isConnected && this.socket) {
            this.socket.emit('stop_bot');
            this.addLogEntry('🔄 Stopping trading bot...');
        }
    }

    updateBotControls() {
        const startBtn = document.getElementById('start-bot');
        const stopBtn = document.getElementById('stop-bot');

        if (startBtn && stopBtn) {
            if (this.botRunning) {
                startBtn.disabled = true;
                stopBtn.disabled = false;
                startBtn.style.opacity = '0.5';
                stopBtn.style.opacity = '1';
            } else {
                startBtn.disabled = false;
                stopBtn.disabled = true;
                startBtn.style.opacity = '1';
                stopBtn.style.opacity = '0.5';
            }
        }
    }

    updateConnectionStatus(status, className = '') {
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = status;
            statusElement.className = `status-value ${className}`;
        }
    }

    updateSignalIndicator(text, status = 'analyzing') {
        const indicator = document.getElementById('signalIndicator');
        if (indicator) {
            const span = indicator.querySelector('span');
            if (span) {
                span.textContent = text;
            }
            
            // Update pulse dot color based on status
            const pulseDot = indicator.querySelector('.pulse-dot');
            if (pulseDot) {
                pulseDot.style.background = this.getStatusColor(status);
            }
        }
    }

    getStatusColor(status) {
        switch(status) {
            case 'active': return '#00ff88';
            case 'stopped': return '#ff4757';
            case 'analyzing': return '#ffa500';
            default: return '#42f5d7';
        }
    }

    updateDashboard(data) {
        if (data.instruments) {
            this.instruments = data.instruments;
            this.updateCryptoCards(data.instruments);
            this.updateStats(data);
        }
    }

    updateCryptoCards(instruments) {
        // Update Bitcoin card (using EUR_USD data as BTC/USDT placeholder)
        const btcData = instruments['EUR_USD'] || {};
        this.updateCryptoCard('btc', {
            price: btcData.price ? (btcData.price * 50000).toFixed(0) : '0', // Mock BTC price
            risk: this.mapRiskLevel(btcData.active_trade?.risk_level),
            confidence: btcData.active_trade?.confidence || '0%',
            recommendation: this.mapRecommendation(btcData.active_trade?.recommendation)
        });

        // Update Altcoins card (using USD_JPY data as altcoins placeholder)
        const altData = instruments['USD_JPY'] || {};
        this.updateCryptoCard('alt', {
            price: 'Multiple Pairs',
            risk: this.mapRiskLevel(altData.active_trade?.risk_level),
            confidence: altData.active_trade?.confidence || '0%',
            recommendation: this.mapRecommendation(altData.active_trade?.recommendation)
        });
    }

    updateCryptoCard(prefix, data) {
        // Update price
        const priceElement = document.getElementById(`${prefix}-price`);
        if (priceElement && data.price !== 'Multiple Pairs') {
            priceElement.textContent = `$${data.price}`;
        }

        // Update risk level
        const riskElement = document.getElementById(`${prefix}-risk`);
        if (riskElement) {
            riskElement.textContent = data.risk.text;
            riskElement.className = `risk-value ${data.risk.class}`;
        }

        // Update confidence
        const confidenceElement = document.getElementById(`${prefix}-confidence`);
        const confidenceBar = document.getElementById(`${prefix}-confidence-bar`);
        
        if (confidenceElement) {
            confidenceElement.textContent = data.confidence;
        }
        
        if (confidenceBar) {
            const percentage = parseInt(data.confidence) || 0;
            confidenceBar.style.width = `${percentage}%`;
        }

        // Update recommendation
        const recommendationElement = document.getElementById(`${prefix}-recommendation`);
        if (recommendationElement) {
            const textElement = recommendationElement.querySelector('.recommendation-text');
            const actionElement = recommendationElement.querySelector('.recommendation-action');
            
            if (textElement) {
                textElement.textContent = data.recommendation.text;
            }
            
            if (actionElement) {
                actionElement.textContent = data.recommendation.action;
                actionElement.className = `recommendation-action ${data.recommendation.class}`;
            }
        }
    }

    mapRiskLevel(riskLevel) {
        switch(riskLevel) {
            case 'LOW':
                return { text: 'LOW RISK', class: 'low' };
            case 'MEDIUM':
                return { text: 'MEDIUM RISK', class: 'medium' };
            case 'HIGH':
                return { text: 'HIGH RISK', class: 'high' };
            case 'VERY HIGH':
                return { text: 'VERY HIGH RISK', class: 'very-high' };
            default:
                return { text: 'ANALYZING', class: '' };
        }
    }

    mapRecommendation(recommendation) {
        if (!recommendation) {
            return {
                text: 'Collecting market data...',
                action: '',
                class: ''
            };
        }

        if (recommendation.includes('STRONG BUY')) {
            return {
                text: 'AI recommends:',
                action: 'STRONG BUY 🚀',
                class: 'buy'
            };
        } else if (recommendation.includes('STRONG SELL')) {
            return {
                text: 'AI recommends:',
                action: 'STRONG SELL 📉',
                class: 'sell'
            };
        } else if (recommendation.includes('DO NOT TRADE') || recommendation.includes('AVOID')) {
            return {
                text: 'AI recommends:',
                action: 'DO NOT TRADE ⚠️',
                class: 'wait'
            };
        } else {
            return {
                text: 'AI is analyzing...',
                action: 'WAIT FOR SIGNAL',
                class: 'wait'
            };
        }
    }

    updateStats(data) {
        // Update market status
        const marketStatus = document.getElementById('market-status');
        if (marketStatus) {
            marketStatus.textContent = this.botRunning ? '🟢 ACTIVE' : '🔴 INACTIVE';
        }

        // Update signals today (increment when new signals appear)
        if (data.instruments) {
            let activeSignals = 0;
            Object.values(data.instruments).forEach(inst => {
                if (inst.active_trade && inst.active_trade.recommendation) {
                    activeSignals++;
                }
            });
            
            if (activeSignals > this.signalsToday) {
                this.signalsToday = activeSignals;
            }
        }

        const signalsElement = document.getElementById('signals-today');
        if (signalsElement) {
            signalsElement.textContent = this.signalsToday;
        }

        // Update success rate (mock calculation)
        const successElement = document.getElementById('success-rate');
        if (successElement) {
            const rate = this.signalsToday > 0 ? Math.min(95, 75 + (this.signalsToday * 5)) : 0;
            successElement.textContent = `${rate}%`;
        }
    }

    addLogEntry(message) {
        const logContainer = document.getElementById('activity-log');
        if (logContainer) {
            const timestamp = new Date().toLocaleTimeString();
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            entry.textContent = `${timestamp} - ${message}`;
            
            logContainer.insertBefore(entry, logContainer.firstChild);
            
            // Keep only last 20 entries
            while (logContainer.children.length > 20) {
                logContainer.removeChild(logContainer.lastChild);
            }
        }
    }

    startUptimeCounter() {
        setInterval(() => {
            if (this.startTime) {
                const uptime = Date.now() - this.startTime;
                const hours = Math.floor(uptime / (1000 * 60 * 60));
                const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));
                const seconds = Math.floor((uptime % (1000 * 60)) / 1000);
                
                const uptimeElement = document.getElementById('uptime');
                if (uptimeElement) {
                    uptimeElement.textContent = 
                        `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
            }
        }, 1000);
    }
}

// Initialize the bot when page loads
document.addEventListener('DOMContentLoaded', () => {
    new CryptoTradingBot();
});

// Add some visual effects for better UX
document.addEventListener('DOMContentLoaded', () => {
    // Add hover effects to crypto cards
    const cryptoCards = document.querySelectorAll('.crypto-card');
    cryptoCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-5px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });

    // Add click ripple effect to buttons
    const buttons = document.querySelectorAll('.neon-btn');
    buttons.forEach(button => {
        button.addEventListener('click', function(e) {
            const ripple = document.createElement('span');
            const rect = this.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.cssText = `
                position: absolute;
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
                background: rgba(255, 255, 255, 0.3);
                border-radius: 50%;
                transform: scale(0);
                animation: ripple 0.6s ease-out;
                pointer-events: none;
            `;
            
            this.style.position = 'relative';
            this.style.overflow = 'hidden';
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });

    // Add CSS for ripple animation
    const style = document.createElement('style');
    style.textContent = `
        @keyframes ripple {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(style);
});