# Pi-Connect 2.0 - Hardware Guide

## 🔧 GPIO Button Setup (Rescue/Config Mode Trigger)

### Overview
The rescue button allows you to manually force the Pi into configuration mode, even when WiFi is working. This is useful for:
- Switching to a different WiFi network
- Recovering from network issues
- Testing the BLE configuration interface

### Pin Selection: GPIO 27 (BCM Numbering)

**Why GPIO 27?**
- Safe general-purpose I/O pin
- Not used by common HATs or peripherals
- Avoids conflicts with:
  - I2C (GPIO 2, 3)
  - SPI (GPIO 7-11)
  - UART (GPIO 14, 15)
  - Hardware PWM (GPIO 12, 13, 18, 19)

### Raspberry Pi 3B+ GPIO Pinout Reference

```
    3.3V [ 1] [ 2] 5V
   GPIO2 [ 3] [ 4] 5V
   GPIO3 [ 5] [ 6] GND
   GPIO4 [ 7] [ 8] GPIO14
     GND [ 9] [10] GPIO15
  GPIO17 [11] [12] GPIO18
  GPIO27 [13] [14] GND       ← WE USE THESE TWO PINS
  GPIO22 [15] [16] GPIO23
    3.3V [17] [18] GPIO24
  GPIO10 [19] [20] GND
   GPIO9 [21] [22] GPIO25
  GPIO11 [23] [24] GPIO8
     GND [25] [26] GPIO7
```

### Wiring Instructions

#### Option 1: Simple Button (Recommended)
Connect a momentary push button between:
- **Pin 13** (GPIO 27) ←→ One side of button
- **Pin 14** (GND) ←→ Other side of button

```
┌──────────────────────────────────┐
│  Raspberry Pi 3B+                │
│                                  │
│  [13] GPIO27 ──┐                │
│                 │                │
│                 └──[BUTTON]──┐   │
│                              │   │
│  [14] GND ───────────────────┘   │
│                                  │
└──────────────────────────────────┘
```

**Internal Pull-Up:** The software configures GPIO 27 with an internal pull-up resistor, so no external resistors are needed.

#### Option 2: Button with External Pull-Up (Advanced)
If you prefer an external pull-up resistor:

```
     3.3V
      │
     ┌┴┐
     │ │ 10kΩ
     └┬┘
      │
      ├────────── GPIO27 (Pin 13)
      │
    ┌─┴─┐
    │BTN│  Momentary Switch
    └─┬─┘
      │
     GND ────── GND (Pin 14)
```

Component List:
- 1x Momentary push button (normally open)
- 1x 10kΩ resistor (if using Option 2)
- 2x Female-to-female jumper wires

### Button Behavior

**Normal Press (< 5 seconds):**
- No effect
- System continues normal operation

**Long Press (≥ 5 seconds):**
- Forces system into BLE advertising mode
- Allows WiFi reconfiguration
- LED indicator (if connected) will flash
- Event logged to `/var/log/pi_connect.log`

### Testing the Button

1. After installation, monitor the service logs:
   ```bash
   sudo journalctl -u pi-connect -f
   ```

2. Press and hold the button for 5+ seconds

3. You should see:
   ```
   Button held for 5s - forcing config mode
   State transition: IDLE -> ADVERTISING (Hardware button pressed)
   ```

4. The Pi will start advertising "Pi-Connect" over Bluetooth

5. Release the button and connect via the web interface

### Optional: LED Indicator

To add a visual indicator when config mode is active:

**Wiring:**
```
GPIO17 (Pin 11) ──┬── [220Ω] ──┬── LED (+)
                  │            │
                  │         LED (-)
                  │            │
                  └────────── GND (Pin 14)
```

**Code modification** (add to `pi_connect.py`):
```python
# In setup_button() method
if GPIO_AVAILABLE:
    from gpiozero import LED
    self.led = LED(17)  # GPIO 17
    
    def on_held():
        self.led.blink(on_time=0.5, off_time=0.5)  # Flash LED
        self.state_machine.force_config_mode()
    
    self.button.when_held = on_held
```

### Safety Notes

⚠️ **Important:**
- Always use a momentary switch (normally open)
- Never connect GPIO pins directly to 5V (only 3.3V tolerant)
- Double-check pin numbers before connecting
- Test with a multimeter if unsure about continuity

### Troubleshooting

| Issue | Solution |
|-------|----------|
| Button doesn't respond | Check wiring, ensure GPIO 27 is correctly connected |
| Random triggering | Add debounce capacitor (0.1µF across button) |
| No log messages | Verify gpiozero is installed: `pip3 install gpiozero` |
| Service won't start | Check permissions: service must run as root |

### Physical Button Recommendations

**Recommended buttons:**
- Adafruit Tactile Button (product #367)
- SparkFun Momentary Pushbutton Switch
- Any standard 6mm x 6mm tactile switch
- Panel-mount push button for permanent installations

### Case Integration

If mounting in a case:
1. Drill appropriate hole for button
2. Use panel-mount button with nut
3. Route wires cleanly to GPIO header
4. Consider strain relief for cables
5. Label button clearly: "WiFi Config" or "Reset Network"

---

## 📚 Additional Resources

- [Raspberry Pi GPIO Pinout](https://pinout.xyz/)
- [gpiozero Documentation](https://gpiozero.readthedocs.io/)
- [Button Debouncing Guide](https://www.raspberrypi.org/documentation/usage/gpio/)

---

**Ready to proceed?** → See `INSTALLATION.md` for software setup
