# Pi-Connect 2.0 - Quick Reference Card

## 🚀 Essential Commands

### **Service Control**
```bash
# Start service
sudo systemctl start pi-connect

# Stop service
sudo systemctl stop pi-connect

# Restart service
sudo systemctl restart pi-connect

# Enable on boot
sudo systemctl enable pi-connect

# Disable on boot
sudo systemctl disable pi-connect

# Check status
sudo systemctl status pi-connect
```

### **Monitoring**
```bash
# Real-time logs (follow mode)
sudo journalctl -u pi-connect -f

# Last 50 lines
sudo journalctl -u pi-connect -n 50

# Since boot
sudo journalctl -u pi-connect -b

# View log file
sudo tail -f /var/log/pi_connect.log

# Check resource usage
top -p $(pgrep -f pi_connect.py)
```

### **Bluetooth Diagnostics**
```bash
# Scan for BLE devices
sudo hcitool lescan

# Check Bluetooth status
sudo systemctl status bluetooth
hciconfig hci0

# Restart Bluetooth
sudo systemctl restart bluetooth

# Unblock Bluetooth
sudo rfkill unblock bluetooth
```

### **Network Diagnostics**
```bash
# List WiFi networks
nmcli device wifi list

# Show connections
nmcli connection show

# Check NetworkManager
sudo systemctl status NetworkManager

# Test connectivity
ping 8.8.8.8 -c 3
```

### **Configuration**
```bash
# Edit service configuration
sudo nano /etc/systemd/system/pi-connect.service

# Reload after changes
sudo systemctl daemon-reload
sudo systemctl restart pi-connect

# View current environment
sudo systemctl show pi-connect | grep Environment

# Change shared secret
sudo nano /etc/systemd/system/pi-connect.service
# Update: Environment="PI_CONNECT_SECRET=your_new_secret"
sudo systemctl daemon-reload
sudo systemctl restart pi-connect
```

---

## 🔍 State Machine Reference

| State | Description | BLE Status | CPU Usage |
|-------|-------------|------------|-----------|
| **BOOT** | Initial startup, checking connectivity | Variable | ~2% |
| **IDLE** | WiFi connected, system sleeping | OFF | <0.5% |
| **ADVERTISING** | No WiFi, waiting for configuration | ON | ~1% |
| **CONNECTING** | Processing credentials, connecting | ON | ~2% |

**State Transitions:**
- BOOT → IDLE (if WiFi connected)
- BOOT → ADVERTISING (if no WiFi)
- IDLE → ADVERTISING (connection lost or button pressed)
- ADVERTISING → CONNECTING (credentials received)
- CONNECTING → IDLE (success)
- CONNECTING → ADVERTISING (failure)

---

## 🔧 GPIO Pin Reference

| Pin | BCM GPIO | Function | Direction |
|-----|----------|----------|-----------|
| 13 | GPIO 27 | Rescue Button | Input (Pull-up) |
| 14 | GND | Ground | - |
| 11 | GPIO 17 | LED (Optional) | Output |

**Button Behavior:**
- Short press (<5s): No effect
- Long press (≥5s): Force config mode

---

## 📝 Log Message Quick Reference

### **Normal Operation**
```
✓ "State transition: BOOT -> IDLE" - WiFi connected
✓ "BLE advertising started" - Ready for configuration
✓ "Successfully connected to [SSID]" - WiFi configured
✓ "Stopping BLE advertising" - Entering power-save mode
```

### **Warnings (Expected)**
```
⚠ "Connection lost" - WiFi disconnected
⚠ "Config mode FORCED" - Button pressed
⚠ "Using default shared secret" - Need to set custom secret
```

### **Errors (Requires Action)**
```
✗ "Authentication failed" - Wrong shared secret
✗ "Failed to connect to [SSID]" - Check credentials
✗ "Failed to setup BLE" - Restart bluetooth
✗ "GPIO not available" - Install gpiozero
```

---

## 🌐 Web Interface URLs

### **Development**
```
http://localhost:8080/index.html
```

### **Production (Example)**
```
https://your-project.vercel.app
```

### **Testing Web Bluetooth**
- ✅ Chrome Desktop (Windows, Mac, Linux)
- ✅ Chrome Android
- ✅ Edge Desktop
- ✅ Opera Desktop
- ❌ Safari (not supported)
- ❌ Firefox (not supported)
- ❌ iOS (not supported)

---

## 🔐 Security Checklist

- [ ] Changed default shared secret
- [ ] Updated secret in both Pi and web client
- [ ] Secret is 32+ random characters
- [ ] Service running as root (required for BLE)
- [ ] Logs show no authentication failures
- [ ] Bluetooth only active when needed
- [ ] Physical access to button secured

---

## 🆘 Emergency Recovery

### **Lost WiFi and no button?**
```bash
# Option 1: USB/Ethernet connection
sudo systemctl restart pi-connect
# Wait 60s, should auto-enter ADVERTISING

# Option 2: Manual network connection
sudo nmcli device wifi connect "YourSSID" password "YourPassword"

# Option 3: Edit config directly
sudo nano /etc/NetworkManager/system-connections/YourNetwork.nmconnection
sudo systemctl restart NetworkManager
```

### **Service crashed?**
```bash
# Check crash logs
sudo journalctl -u pi-connect --since "1 hour ago"

# Force restart
sudo systemctl restart pi-connect

# If still failing, run manually for debug
sudo python3 /opt/pi-connect/pi_connect.py
```

### **Bluetooth not working?**
```bash
# Full Bluetooth reset
sudo systemctl stop bluetooth
sudo rfkill block bluetooth
sleep 2
sudo rfkill unblock bluetooth
sudo systemctl start bluetooth
sudo systemctl restart pi-connect
```

---

## 📊 Performance Monitoring

### **Resource Usage**
```bash
# CPU & Memory (real-time)
top -p $(pgrep -f pi_connect.py)

# Detailed process info
ps aux | grep pi_connect

# SystemD resource limits
systemctl show pi-connect | grep -E "CPU|Memory"
```

### **Expected Values**
- **CPU (IDLE):** 0-1%
- **CPU (ADVERTISING):** 1-2%
- **Memory:** 30-50MB
- **Threads:** 3-4

---

## 🔄 Update Procedure

```bash
# 1. Backup current version
sudo cp /opt/pi-connect/pi_connect.py \
       /opt/pi-connect/pi_connect.py.backup.$(date +%Y%m%d)

# 2. Stop service
sudo systemctl stop pi-connect

# 3. Copy new version
sudo cp /path/to/new/pi_connect.py /opt/pi-connect/

# 4. Set permissions
sudo chmod +x /opt/pi-connect/pi_connect.py

# 5. Start service
sudo systemctl start pi-connect

# 6. Verify
sudo systemctl status pi-connect
sudo journalctl -u pi-connect -f
```

---

## 📦 File Locations

| File | Location | Purpose |
|------|----------|---------|
| Service script | `/opt/pi-connect/pi_connect.py` | Main Python service |
| SystemD unit | `/etc/systemd/system/pi-connect.service` | Service configuration |
| Logs | `/var/log/pi_connect.log` | Rotating log file |
| Journal | `journalctl -u pi-connect` | SystemD logs |
| Web client | `index.html` | Deployed to Vercel/web server |

---

## 🎯 Quick Diagnostics

### **"Is it running?"**
```bash
sudo systemctl is-active pi-connect
# Should output: active
```

### **"Is BLE advertising?"**
```bash
sudo hcitool lescan | grep "Pi-Connect"
# Should show: Pi-Connect if advertising
```

### **"What state am I in?"**
```bash
sudo journalctl -u pi-connect | grep "State transition" | tail -1
# Shows last state change
```

### **"Is WiFi connected?"**
```bash
nmcli device status | grep wifi
# Shows: connected or disconnected
```

---

## 💾 Backup & Restore

### **Backup Configuration**
```bash
# Create backup directory
mkdir -p ~/pi-connect-backup

# Backup files
sudo cp /opt/pi-connect/pi_connect.py ~/pi-connect-backup/
sudo cp /etc/systemd/system/pi-connect.service ~/pi-connect-backup/
sudo cp /var/log/pi_connect.log ~/pi-connect-backup/ 2>/dev/null

# Backup shared secret (careful with security!)
sudo grep "PI_CONNECT_SECRET" /etc/systemd/system/pi-connect.service > ~/pi-connect-backup/secret.txt
```

### **Restore**
```bash
# Stop service
sudo systemctl stop pi-connect

# Restore files
sudo cp ~/pi-connect-backup/pi_connect.py /opt/pi-connect/
sudo cp ~/pi-connect-backup/pi-connect.service /etc/systemd/system/

# Reload and start
sudo systemctl daemon-reload
sudo systemctl start pi-connect
```

---

## 📞 Support Quick Links

- **Documentation:** `INSTALLATION.md`, `HARDWARE_GUIDE.md`
- **Bluetooth API:** https://developer.mozilla.org/docs/Web/API/Web_Bluetooth_API
- **BlueZ:** http://www.bluez.org/
- **NetworkManager:** https://networkmanager.dev/
- **Raspberry Pi Forums:** https://forums.raspberrypi.com/

---

**💡 Pro Tip:** Bookmark this file! Keep it accessible via SSH or print it for field deployments.

---

*Last updated: February 2026*
