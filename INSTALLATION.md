# Pi-Connect 2.0 - Installation Guide

## 📋 Prerequisites

- **Hardware:** Raspberry Pi 3B+ (or newer with Bluetooth)
- **OS:** Raspberry Pi OS Bookworm or Bullseye (32-bit or 64-bit)
- **Access:** SSH, keyboard/monitor, or temporary Ethernet connection
- **Permissions:** Root/sudo access

## 🚀 Quick Start (Copy-Paste Installation)

For experienced users, run this complete installation script:

```bash
# 1. Update system
sudo apt update && sudo apt upgrade -y

# 2. Install dependencies
sudo apt install -y python3 python3-pip python3-dbus python3-gi \
    bluetooth bluez bluez-tools rfkill \
    network-manager gpiozero

# 3. Install Python packages
pip3 install pydbus --break-system-packages

# 4. Create installation directory
sudo mkdir -p /opt/pi-connect
cd /opt/pi-connect

# 5. Download files (or copy manually)
# You'll need: pi_connect.py, pi-connect.service

# 6. Set permissions
sudo chmod +x /opt/pi-connect/pi_connect.py

# 7. Set shared secret
sudo mkdir -p /etc/pi-connect
echo "YOUR_RANDOM_SECRET_HERE" | sudo tee /etc/pi-connect/secret

# 8. Install systemd service
sudo cp pi-connect.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable pi-connect
sudo systemctl start pi-connect

# 9. Check status
sudo systemctl status pi-connect
```

---

## 📝 Detailed Step-by-Step Installation

### Step 1: Update System

```bash
sudo apt update
sudo apt upgrade -y
```

**Why?** Ensures you have the latest Bluetooth stack and security patches.

---

### Step 2: Install System Dependencies

```bash
sudo apt install -y \
    python3 \
    python3-pip \
    python3-dbus \
    python3-gi \
    bluetooth \
    bluez \
    bluez-tools \
    rfkill \
    network-manager \
    gpiozero
```

**Package breakdown:**
- `python3-dbus` - D-Bus Python bindings for BlueZ
- `python3-gi` - GObject introspection for GLib
- `bluetooth`, `bluez` - Bluetooth protocol stack
- `bluez-tools` - Bluetooth utilities
- `rfkill` - Manage wireless device states
- `network-manager` - WiFi connection management via nmcli
- `gpiozero` - GPIO control for button

---

### Step 3: Install Python Dependencies

```bash
pip3 install pydbus --break-system-packages
```

**Note:** The `--break-system-packages` flag is required on Raspberry Pi OS Bookworm. This is safe for system services.

**Verify installation:**
```bash
python3 -c "import dbus; import pydbus; print('Success!')"
```

---

### Step 4: Enable Bluetooth

```bash
# Unblock Bluetooth if blocked
sudo rfkill unblock bluetooth

# Start Bluetooth service
sudo systemctl start bluetooth
sudo systemctl enable bluetooth

# Verify Bluetooth is running
sudo systemctl status bluetooth
```

**Expected output:**
```
● bluetooth.service - Bluetooth service
   Active: active (running)
```

---

### Step 5: Configure NetworkManager

NetworkManager should be running by default on Raspberry Pi OS. Verify:

```bash
sudo systemctl status NetworkManager
```

If not running:
```bash
sudo systemctl start NetworkManager
sudo systemctl enable NetworkManager
```

**Test nmcli:**
```bash
nmcli device wifi list
```

---

### Step 6: Deploy Pi-Connect Files

Create the installation directory:
```bash
sudo mkdir -p /opt/pi-connect
cd /opt/pi-connect
```

Copy your files to `/opt/pi-connect/`:
- `pi_connect.py`
- `pi-connect.service`

**If transferring via SCP:**
```bash
# From your computer:
scp pi_connect.py pi@raspberrypi.local:/tmp/
scp pi-connect.service pi@raspberrypi.local:/tmp/

# On the Pi:
sudo mv /tmp/pi_connect.py /opt/pi-connect/
sudo mv /tmp/pi-connect.service /etc/systemd/system/
```

**Set permissions:**
```bash
sudo chmod +x /opt/pi-connect/pi_connect.py
sudo chown root:root /opt/pi-connect/pi_connect.py
```

---

### Step 7: Configure Shared Secret (CRITICAL SECURITY STEP)

**Generate a secure random secret:**
```bash
# Generate 32-byte random secret
openssl rand -base64 32
```

**Example output:** `3kF8mN2pQ7vR9sT1wX6yZ4aB5cD8eG0h`

**Save it to environment file:**
```bash
sudo mkdir -p /etc/pi-connect
sudo nano /etc/pi-connect/secret
```

Paste your generated secret, save (Ctrl+O, Enter, Ctrl+X).

**Update the systemd service:**
```bash
sudo nano /etc/systemd/system/pi-connect.service
```

Find this line:
```
Environment="PI_CONNECT_SECRET=CHANGE_THIS_TO_YOUR_SECRET_KEY"
```

Change to:
```
Environment="PI_CONNECT_SECRET=3kF8mN2pQ7vR9sT1wX6yZ4aB5cD8eG0h"
```

**⚠️ IMPORTANT:** Also update the same secret in your `index.html` file:

Edit `index.html`:
```javascript
const CONFIG = {
    // ... other config ...
    SHARED_SECRET: '3kF8mN2pQ7vR9sT1wX6yZ4aB5cD8eG0h'  // Same secret!
};
```

**Security note:** Keep this secret confidential. Do not commit it to public repositories.

---

### Step 8: Install and Start the Service

```bash
# Copy service file
sudo cp pi-connect.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (auto-start on boot)
sudo systemctl enable pi-connect

# Start service
sudo systemctl start pi-connect

# Check status
sudo systemctl status pi-connect
```

**Expected output:**
```
● pi-connect.service - Pi-Connect 2.0 - Headless WiFi Configuration Service
   Loaded: loaded (/etc/systemd/system/pi-connect.service; enabled)
   Active: active (running) since ...
```

---

### Step 9: Verify Operation

**Check logs:**
```bash
sudo journalctl -u pi-connect -f
```

**Expected log output:**
```
Pi-Connect 2.0 - Starting
State Machine initialized
BLE components initialized
Watchdog thread started
State transition: BOOT -> ADVERTISING (No initial connection)
BLE advertising started
Pi-Connect service running
```

**Check Bluetooth advertising:**
```bash
sudo hcitool lescan
```

You should see `Pi-Connect` in the list.

**Test connectivity check:**
```bash
ping 8.8.8.8 -c 1
```

---

### Step 10: Deploy Web Interface

**Local Development:**
```bash
# Install dependencies
npm install

# Configure environment
cp .env.example .env
nano .env  # Set VITE_SHARED_SECRET=your_secret_here

# Start dev server
npm run dev  # Opens at http://localhost:3000
```

**Deploy to Vercel (Recommended):**
1. Push project to GitHub
2. Import to Vercel: https://vercel.com/new
3. Add environment variable: `VITE_SHARED_SECRET` (must match Pi secret)
4. Deploy

**Production Build:**
```bash
npm run build  # Creates optimized dist/ folder
npm run preview  # Test production build locally
```

**Note:** Shared secret must match between Pi (`pi-connect.service`) and web client (`.env` or Vercel env vars).

---

## 🔌 Hardware Button Setup

Follow the wiring instructions in `HARDWARE_GUIDE.md`.

**Test the button:**
```bash
# Monitor logs
sudo journalctl -u pi-connect -f

# Press and hold button for 5+ seconds
# You should see:
# "Button held for 5s - forcing config mode"
```

---

## 🧪 Testing the Complete System

### Test 1: Initial Boot (No WiFi)
```bash
# Disable WiFi temporarily
sudo nmcli radio wifi off

# Restart service
sudo systemctl restart pi-connect

# Check logs - should enter ADVERTISING mode
sudo journalctl -u pi-connect -n 50
```

### Test 2: BLE Connection
1. Open the web interface on your phone/computer
2. Enable Bluetooth
3. Click "Connect to Pi"
4. Select "Pi-Connect" from device list
5. Should show "Connected to Pi"

### Test 3: WiFi Configuration
1. In the web interface, enter your WiFi credentials
2. Click "Configure WiFi"
3. Watch the status messages
4. Should see "Success! Connected to WiFi"

### Test 4: Auto-Transition to IDLE
```bash
# After successful WiFi connection, watch logs
sudo journalctl -u pi-connect -f

# After ~60 seconds, you should see:
# "State transition: ADVERTISING -> IDLE (WiFi connected)"
# "Stopping BLE advertising"
```

### Test 5: Hardware Button
1. While connected to WiFi (IDLE mode)
2. Press and hold button for 5+ seconds
3. Should force ADVERTISING mode
4. Can reconfigure WiFi again

---

## 📊 Monitoring & Troubleshooting

### View Real-Time Logs
```bash
sudo journalctl -u pi-connect -f
```

### View Log File
```bash
sudo tail -f /var/log/pi_connect.log
```

### Check Service Status
```bash
sudo systemctl status pi-connect
```

### Restart Service
```bash
sudo systemctl restart pi-connect
```

### Check Bluetooth Status
```bash
sudo systemctl status bluetooth
hciconfig hci0
```

### Check NetworkManager
```bash
nmcli device status
nmcli connection show
```

### Check CPU/Memory Usage
```bash
# Should be <1% CPU when IDLE
top -p $(pgrep -f pi_connect.py)
```

---

## 🐛 Common Issues & Solutions

### Issue: "Web Bluetooth is not supported"
**Solution:** Use Chrome, Edge, or Opera (desktop), or Chrome on Android. Safari and Firefox don't support Web Bluetooth.

### Issue: Service fails to start
**Check:**
```bash
# View detailed error
sudo journalctl -u pi-connect -n 100 --no-pager

# Common causes:
# - Python dependencies missing
# - Permission issues
# - Bluetooth not enabled
```

### Issue: Can't see "Pi-Connect" in Bluetooth scan
**Solution:**
```bash
# Check if advertising
sudo hcitool lescan

# Verify Bluetooth is unblocked
sudo rfkill list

# Restart Bluetooth
sudo systemctl restart bluetooth
sudo systemctl restart pi-connect
```

### Issue: Authentication fails
**Solution:**
- Verify shared secret matches in both `pi-connect.service` AND `index.html`
- Check for typos
- Regenerate and update both sides

### Issue: WiFi connection fails
**Check:**
```bash
# Verify password is correct
# Check if SSID exists
nmcli device wifi list

# Try manual connection
nmcli device wifi connect "YourSSID" password "YourPassword"
```

### Issue: High CPU usage in IDLE mode
**Check:**
```bash
# Should sleep 60s between checks
# Verify IDLE_CHECK_INTERVAL in code

# Monitor state
sudo journalctl -u pi-connect -f
```

### Issue: Button not responding
**Check:**
```bash
# Test GPIO
python3 -c "from gpiozero import Button; b = Button(27); print('Waiting...'); b.wait_for_press(); print('Pressed!')"

# Verify wiring (see HARDWARE_GUIDE.md)
```

---

## 🔄 Updating Pi-Connect

```bash
# Stop service
sudo systemctl stop pi-connect

# Backup current version
sudo cp /opt/pi-connect/pi_connect.py /opt/pi-connect/pi_connect.py.backup

# Copy new version
sudo cp /path/to/new/pi_connect.py /opt/pi-connect/

# Restart service
sudo systemctl start pi-connect

# Check logs
sudo journalctl -u pi-connect -f
```

---

## 🗑️ Uninstallation

```bash
# Stop and disable service
sudo systemctl stop pi-connect
sudo systemctl disable pi-connect

# Remove files
sudo rm /etc/systemd/system/pi-connect.service
sudo rm -rf /opt/pi-connect
sudo rm -rf /etc/pi-connect

# Reload systemd
sudo systemctl daemon-reload
```

---

## 🔒 Security Best Practices

1. **Change the shared secret** immediately after installation
2. **Use a strong random secret** (32+ characters)
3. **Keep the secret confidential** - don't share publicly
4. **Update Raspberry Pi OS regularly** for security patches
5. **Disable SSH password authentication** if exposed to internet
6. **Use firewall rules** if connecting to untrusted networks
7. **Monitor logs regularly** for suspicious activity

---

## 📈 Performance Tuning

The service is designed to be zero-interference. Default settings:

- **IDLE mode:** 60-second check interval (CPU ~0%)
- **CPU Quota:** 10% max (systemd limit)
- **Memory limit:** 100MB max
- **Nice value:** 10 (low priority)

To adjust, edit `/etc/systemd/system/pi-connect.service`:

```ini
# More aggressive resource limits
CPUQuota=5%
MemoryMax=50M
Nice=15
```

Then reload:
```bash
sudo systemctl daemon-reload
sudo systemctl restart pi-connect
```

---

## 📚 Additional Resources

- [BlueZ Documentation](http://www.bluez.org/documentation/)
- [NetworkManager CLI Guide](https://networkmanager.dev/docs/api/latest/nmcli.html)
- [systemd Service Tutorial](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Web Bluetooth API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Bluetooth_API)

---

## ✅ Installation Checklist

- [ ] System updated
- [ ] Dependencies installed
- [ ] Bluetooth enabled
- [ ] NetworkManager running
- [ ] Files copied to `/opt/pi-connect`
- [ ] Shared secret generated and configured
- [ ] Service installed and started
- [ ] Web interface deployed
- [ ] Shared secret matches in web interface
- [ ] Hardware button wired (optional)
- [ ] System tested end-to-end
- [ ] Logs verified

---

**🎉 Congratulations!** Your Pi-Connect 2.0 system is ready. Enjoy seamless headless WiFi configuration!
