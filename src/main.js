import CryptoJS from 'crypto-js';

// ============================================
// CONFIGURATION
// ============================================

const CONFIG = {
    SERVICE_UUID: '12345678-1234-5678-1234-56789abcdef0',
    CHAR_AUTH_CHALLENGE_UUID: '12345678-1234-5678-1234-56789abcdef1',
    CHAR_WIFI_SSID_UUID: '12345678-1234-5678-1234-56789abcdef2',
    CHAR_WIFI_PASS_UUID: '12345678-1234-5678-1234-56789abcdef3',
    CHAR_STATUS_UUID: '12345678-1234-5678-1234-56789abcdef4',
    CHAR_IP_ADDRESS_UUID: '12345678-1234-5678-1234-56789abcdef5',
    SHARED_SECRET: import.meta.env.VITE_SHARED_SECRET || 'CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR'
};

// ============================================
// STATE MANAGEMENT
// ============================================

class PiConnectClient {
    constructor() {
        this.device = null;
        this.server = null;
        this.service = null;
        this.characteristics = {};
        this.nonce = null;
        this.piIPAddress = null;
        
        this.initUI();
    }
    
    initUI() {
        // UI Elements
        this.connectBtn = document.getElementById('connectBtn');
        this.submitBtn = document.getElementById('submitBtn');
        this.disconnectBtn = document.getElementById('disconnectBtn');
        this.wifiForm = document.getElementById('wifiForm');
        this.statusBadge = document.getElementById('statusBadge');
        this.alertBox = document.getElementById('alertBox');
        this.statusMessage = document.getElementById('statusMessage');
        this.ssidInput = document.getElementById('ssid');
        this.passwordInput = document.getElementById('password');
        this.togglePassword = document.getElementById('togglePassword');
        this.ipDisplay = document.getElementById('ipDisplay');
        this.ipAddressText = document.getElementById('ipAddressText');
        this.refreshIpBtn = document.getElementById('refreshIpBtn');
        this.copyIpBtn = document.getElementById('copyIpBtn');
        
        // Event Listeners
        this.connectBtn.addEventListener('click', () => this.connect());
        this.submitBtn.addEventListener('click', () => this.configureWiFi());
        this.disconnectBtn.addEventListener('click', () => this.disconnect());
        this.togglePassword.addEventListener('click', () => this.togglePasswordVisibility());
        this.refreshIpBtn?.addEventListener('click', () => this.refreshIPAddress());
        this.copyIpBtn?.addEventListener('click', () => this.copyIPAddress());
        
        // Check Web Bluetooth support
        if (!navigator.bluetooth) {
            this.showAlert('error', 'Web Bluetooth is not supported in your browser. Please use Chrome, Edge, or Opera on desktop, or Chrome on Android.');
            this.connectBtn.disabled = true;
        }
    }
    
    // ============================================
    // BLUETOOTH CONNECTION
    // ============================================
    
    async connect() {
        try {
            this.updateStatus('connecting', 'Scanning for devices...');
            this.connectBtn.disabled = true;
            
            // Request device
            this.device = await navigator.bluetooth.requestDevice({
                filters: [{ name: 'Pi-Connect' }],
                optionalServices: [CONFIG.SERVICE_UUID]
            });
            
            this.updateStatus('connecting', 'Connecting to Pi...');
            
            // Add disconnect listener
            this.device.addEventListener('gattserverdisconnected', () => {
                this.onDisconnected();
            });
            
            // Connect to GATT server
            this.server = await this.device.gatt.connect();
            
            // Get service
            this.service = await this.server.getPrimaryService(CONFIG.SERVICE_UUID);
            
            // Get characteristics
            this.characteristics.auth = await this.service.getCharacteristic(CONFIG.CHAR_AUTH_CHALLENGE_UUID);
            this.characteristics.ssid = await this.service.getCharacteristic(CONFIG.CHAR_WIFI_SSID_UUID);
            this.characteristics.password = await this.service.getCharacteristic(CONFIG.CHAR_WIFI_PASS_UUID);
            this.characteristics.status = await this.service.getCharacteristic(CONFIG.CHAR_STATUS_UUID);
            this.characteristics.ip = await this.service.getCharacteristic(CONFIG.CHAR_IP_ADDRESS_UUID);
            
            // Subscribe to status notifications
            await this.characteristics.status.startNotifications();
            this.characteristics.status.addEventListener('characteristicvaluechanged', (event) => {
                this.onStatusUpdate(event.target.value);
            });
            
            // Read IP address
            await this.readIPAddress();
            
            this.updateStatus('connected', 'Connected to Pi');
            this.showAlert('success', 'Successfully connected to Pi-Connect!');
            this.wifiForm.classList.add('show');
            
        } catch (error) {
            console.error('Connection error:', error);
            this.updateStatus('disconnected', 'Connection failed');
            this.showAlert('error', `Connection failed: ${error.message}`);
            this.connectBtn.disabled = false;
        }
    }
    
    async disconnect() {
        if (this.device && this.device.gatt.connected) {
            this.device.gatt.disconnect();
        }
        this.onDisconnected();
    }
    
    onDisconnected() {
        this.updateStatus('disconnected', 'Disconnected');
        this.wifiForm.classList.remove('show');
        this.ipDisplay.classList.remove('show');
        this.connectBtn.disabled = false;
        this.device = null;
        this.server = null;
        this.service = null;
        this.characteristics = {};
        this.nonce = null;
        this.piIPAddress = null;
    }
    
    // ============================================
    // IP ADDRESS
    // ============================================
    
    async readIPAddress() {
        try {
            const ipValue = await this.characteristics.ip.readValue();
            this.piIPAddress = new TextDecoder().decode(ipValue);
            console.log('IP Address:', this.piIPAddress);
            
            if (this.ipAddressText && this.ipDisplay) {
                this.ipAddressText.textContent = this.piIPAddress;
                this.ipDisplay.classList.add('show');
            }
        } catch (error) {
            console.error('Failed to read IP address:', error);
        }
    }
    
    async refreshIPAddress() {
        if (!this.characteristics.ip) {
            this.showAlert('error', 'Not connected to Pi');
            return;
        }
        
        try {
            this.showAlert('info', 'Refreshing IP address...');
            await this.readIPAddress();
            this.showAlert('success', 'IP address refreshed!');
        } catch (error) {
            console.error('Failed to refresh IP:', error);
            this.showAlert('error', 'Failed to refresh IP address');
        }
    }
    
    copyIPAddress() {
        if (this.piIPAddress) {
            navigator.clipboard.writeText(this.piIPAddress).then(() => {
                this.showAlert('success', 'IP address copied to clipboard!');
            }).catch(err => {
                console.error('Failed to copy IP:', err);
                this.showAlert('error', 'Failed to copy IP address');
            });
        }
    }
    
    // ============================================
    // WIFI CONFIGURATION
    // ============================================
    
    async configureWiFi() {
        const ssid = this.ssidInput.value.trim();
        const password = this.passwordInput.value;
        
        if (!ssid) {
            this.showAlert('error', 'Please enter a WiFi network name');
            return;
        }
        
        if (!password) {
            this.showAlert('error', 'Please enter a WiFi password');
            return;
        }
        
        try {
            this.submitBtn.disabled = true;
            this.submitBtn.innerHTML = 'Configuring... <span class="spinner"></span>';
            
            // Step 1: Read nonce from Pi
            this.updateStatusMessage('Reading challenge from Pi...');
            const nonceValue = await this.characteristics.auth.readValue();
            this.nonce = new Uint8Array(nonceValue.buffer);
            console.log('Nonce received:', Array.from(this.nonce).map(b => b.toString(16).padStart(2, '0')).join(''));
            
            // Step 2: Calculate HMAC
            this.updateStatusMessage('Calculating authentication...');
            const hmac = this.calculateHMAC(this.nonce, ssid, password);
            console.log('HMAC calculated:', Array.from(hmac).map(b => b.toString(16).padStart(2, '0')).join(''));
            
            // Step 3: Write HMAC back to auth characteristic
            this.updateStatusMessage('Authenticating...');
            await this.characteristics.auth.writeValue(hmac);
            
            // Small delay to allow Pi to process auth
            await this.sleep(500);
            
            // Step 4: Write SSID
            this.updateStatusMessage('Sending WiFi credentials...');
            const ssidBytes = new TextEncoder().encode(ssid);
            await this.characteristics.ssid.writeValue(ssidBytes);
            
            // Step 5: Write password (this triggers connection attempt)
            const passwordBytes = new TextEncoder().encode(password);
            await this.characteristics.password.writeValue(passwordBytes);
            
            this.updateStatusMessage('Configuration sent! Waiting for Pi...');
            this.showAlert('info', 'Configuration sent to Pi. Please wait...');
            
        } catch (error) {
            console.error('Configuration error:', error);
            this.showAlert('error', `Configuration failed: ${error.message}`);
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '✓ Configure WiFi';
        }
    }
    
    // ============================================
    // SECURITY (HMAC)
    // ============================================
    
    calculateHMAC(nonce, ssid, password) {
        // Concatenate: nonce + ssid + password
        const nonceHex = CryptoJS.lib.WordArray.create(nonce);
        const ssidWords = CryptoJS.enc.Utf8.parse(ssid);
        const passwordWords = CryptoJS.enc.Utf8.parse(password);
        
        const message = nonceHex.concat(ssidWords).concat(passwordWords);
        
        // Calculate HMAC-SHA256
        const hmacHash = CryptoJS.HmacSHA256(message, CONFIG.SHARED_SECRET);
        
        // Convert to Uint8Array
        const hmacHex = hmacHash.toString(CryptoJS.enc.Hex);
        const hmacBytes = new Uint8Array(hmacHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
        
        return hmacBytes;
    }
    
    // ============================================
    // STATUS UPDATES
    // ============================================
    
    onStatusUpdate(value) {
        const status = new TextDecoder().decode(value);
        console.log('Status update from Pi:', status);
        this.updateStatusMessage(status);
        
        if (status.includes('Success')) {
            this.showAlert('success', status);
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '✓ Configure WiFi';
            
            // Auto-disconnect after success
            setTimeout(() => {
                this.disconnect();
                this.showAlert('info', 'Pi is now connected to WiFi. You can close this page.');
            }, 3000);
            
        } else if (status.includes('Failed') || status.includes('Error') || status.includes('Scanning')) {
            // Reset button state for any failure or intermediate status
            if (status.includes('Failed') || status.includes('Error')) {
                this.showAlert('error', status);
            }
            this.submitBtn.disabled = false;
            this.submitBtn.innerHTML = '✓ Configure WiFi';
        }
    }
    
    updateStatus(state, message) {
        this.statusBadge.className = `status-badge status-${state}`;
        this.statusBadge.textContent = message;
    }
    
    updateStatusMessage(message) {
        this.statusMessage.textContent = message;
    }
    
    showAlert(type, message) {
        this.alertBox.className = `alert alert-${type} show`;
        this.alertBox.textContent = message;
        
        setTimeout(() => {
            this.alertBox.classList.remove('show');
        }, 5000);
    }
    
    // ============================================
    // UI HELPERS
    // ============================================
    
    togglePasswordVisibility() {
        const type = this.passwordInput.type === 'password' ? 'text' : 'password';
        this.passwordInput.type = type;
        this.togglePassword.textContent = type === 'password' ? '👁️' : '🙈';
    }
    
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
}

// ============================================
// INITIALIZE
// ============================================

const client = new PiConnectClient();

// Warning about shared secret
if (CONFIG.SHARED_SECRET === 'CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR') {
    console.warn('⚠️ WARNING: Using default shared secret! Change this in production!');
}
