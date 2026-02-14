#!/usr/bin/env python3
"""
Pi-Connect 2.0 - Headless Raspberry Pi WiFi Configuration via BLE
A production-grade, zero-interference system service for WiFi provisioning.

Author: Senior Full-Stack IoT Engineer
License: MIT
"""

import os
import sys
import time
import hmac
import hashlib
import secrets
import subprocess
import threading
import logging
from logging.handlers import RotatingFileHandler
from enum import Enum
from typing import Optional, Tuple
import dbus
import dbus.service
import dbus.mainloop.glib
from gi.repository import GLib

try:
    from gpiozero import Button
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("Warning: gpiozero not available. Button feature disabled.")


# ============================================================================
# CONFIGURATION
# ============================================================================

class Config:
    """Central configuration for Pi-Connect"""
    
    # BLE Service and Characteristics UUIDs
    SERVICE_UUID = "12345678-1234-5678-1234-56789abcdef0"
    CHAR_AUTH_CHALLENGE_UUID = "12345678-1234-5678-1234-56789abcdef1"
    CHAR_WIFI_SSID_UUID = "12345678-1234-5678-1234-56789abcdef2"
    CHAR_WIFI_PASS_UUID = "12345678-1234-5678-1234-56789abcdef3"
    CHAR_STATUS_UUID = "12345678-1234-5678-1234-56789abcdef4"
    
    # Device Information
    DEVICE_NAME = "Pi-Connect"
    DEVICE_INTERFACE = "hci0"
    
    # Security
    SHARED_SECRET = os.getenv("PI_CONNECT_SECRET")
    NONCE_LIFETIME = 60  # seconds
    
    # State Machine Timings
    IDLE_CHECK_INTERVAL = 60  # seconds between connectivity checks when connected
    ADVERTISING_CHECK_INTERVAL = 10  # seconds between checks when advertising
    CONNECTION_TIMEOUT = 30  # seconds to wait for WiFi connection
    
    # GPIO Configuration
    BUTTON_GPIO = 27  # BCM numbering
    BUTTON_HOLD_TIME = 5  # seconds for long press
    
    # Logging
    LOG_FILE = "/var/log/pi_connect.log"
    LOG_MAX_BYTES = 1 * 1024 * 1024  # 1MB
    LOG_BACKUP_COUNT = 5


# ============================================================================
# LOGGING SETUP
# ============================================================================

def setup_logging() -> logging.Logger:
    """Configure rotating file logger"""
    logger = logging.getLogger("PiConnect")
    logger.setLevel(logging.INFO)
    
    # Create log directory if it doesn't exist
    log_dir = os.path.dirname(Config.LOG_FILE)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except PermissionError:
            # Fallback to local directory if /var/log is not writable
            Config.LOG_FILE = "./pi_connect.log"
    
    # Rotating file handler
    handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_BYTES,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Also log to console during development
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logging()


# ============================================================================
# STATE MACHINE
# ============================================================================

class SystemState(Enum):
    """Possible states of the Pi-Connect system"""
    BOOT = "BOOT"
    IDLE = "IDLE"  # WiFi connected, BLE off
    ADVERTISING = "ADVERTISING"  # No WiFi, BLE on
    CONNECTING = "CONNECTING"  # Processing credentials


class StateMachine:
    """Manages the reactive state transitions"""
    
    def __init__(self):
        self.current_state = SystemState.BOOT
        self.forced_config_mode = False
        self.lock = threading.Lock()
        logger.info("State Machine initialized")
    
    def get_state(self) -> SystemState:
        """Thread-safe state getter"""
        with self.lock:
            return self.current_state
    
    def set_state(self, new_state: SystemState, reason: str = ""):
        """Thread-safe state setter with logging"""
        with self.lock:
            if self.current_state != new_state:
                logger.info(f"State transition: {self.current_state.value} -> {new_state.value} ({reason})")
                self.current_state = new_state
    
    def force_config_mode(self):
        """Force advertising mode (triggered by button)"""
        logger.warning("Config mode FORCED by hardware button")
        self.forced_config_mode = True
        self.set_state(SystemState.ADVERTISING, "Hardware button pressed")
    
    def clear_forced_mode(self):
        """Clear forced config mode flag"""
        self.forced_config_mode = False


# ============================================================================
# NETWORK UTILITIES
# ============================================================================

class NetworkManager:
    """Handles WiFi connectivity and internet checks"""
    
    @staticmethod
    def has_internet() -> bool:
        """Check internet connectivity by pinging Google DNS"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True,
                timeout=3
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @staticmethod
    def has_gateway() -> bool:
        """Check if we have a default gateway (local network connection)"""
        try:
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=2
            )
            return bool(result.stdout.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    @staticmethod
    def is_connected() -> bool:
        """Check if we have network connectivity (internet or gateway)"""
        return NetworkManager.has_internet() or NetworkManager.has_gateway()
    
    @staticmethod
    def connect_wifi(ssid: str, password: str) -> Tuple[bool, str]:
        """
        Connect to WiFi network using NetworkManager
        Returns: (success: bool, message: str)
        """
        try:
            logger.info(f"Attempting to connect to SSID: {ssid}")
            
            # First, try to delete existing connection if it exists
            subprocess.run(
                ["nmcli", "connection", "delete", ssid],
                capture_output=True,
                timeout=5
            )
            
            # Add and connect to the network
            result = subprocess.run(
                [
                    "nmcli", "device", "wifi", "connect", ssid,
                    "password", password
                ],
                capture_output=True,
                text=True,
                timeout=Config.CONNECTION_TIMEOUT
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully connected to {ssid}")
                return True, "Connected successfully"
            else:
                error_msg = result.stderr.strip() or result.stdout.strip()
                logger.error(f"Failed to connect to {ssid}: {error_msg}")
                return False, f"Connection failed: {error_msg}"
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout connecting to {ssid}")
            return False, "Connection timeout"
        except Exception as e:
            logger.error(f"Exception during WiFi connection: {e}")
            return False, f"Error: {str(e)}"
    
    @staticmethod
    def scan_networks() -> list:
        """Scan for available WiFi networks"""
        try:
            result = subprocess.run(
                ["nmcli", "-t", "-f", "SSID", "device", "wifi", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                networks = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                return networks
            return []
        except Exception as e:
            logger.error(f"Failed to scan networks: {e}")
            return []


# ============================================================================
# SECURITY MANAGER
# ============================================================================

class SecurityManager:
    """Handles authentication, nonce generation, and HMAC verification"""
    
    def __init__(self):
        self.current_nonce: Optional[bytes] = None
        self.nonce_created_at: Optional[float] = None
        self.authenticated = False
        self.lock = threading.Lock()
    
    def generate_nonce(self) -> bytes:
        """Generate a new cryptographically secure nonce"""
        with self.lock:
            self.current_nonce = secrets.token_bytes(32)
            self.nonce_created_at = time.time()
            self.authenticated = False
            logger.info("New nonce generated")
            return self.current_nonce
    
    def get_nonce(self) -> Optional[bytes]:
        """Get current nonce if still valid"""
        with self.lock:
            if self.current_nonce is None:
                return None
            
            # Check if nonce has expired
            if time.time() - self.nonce_created_at > Config.NONCE_LIFETIME:
                logger.warning("Nonce expired")
                self.current_nonce = None
                self.authenticated = False
                return None
            
            return self.current_nonce
    
    def verify_auth(self, client_hmac: bytes, ssid: str, password: str) -> bool:
        """
        Verify client's HMAC response
        Expected: HMAC-SHA256(shared_secret, nonce + ssid + password)
        """
        with self.lock:
            if self.current_nonce is None:
                logger.error("Auth verification failed: No nonce available")
                return False
            
            # Check nonce expiration
            if time.time() - self.nonce_created_at > Config.NONCE_LIFETIME:
                logger.error("Auth verification failed: Nonce expired")
                self.current_nonce = None
                return False
            
            # Calculate expected HMAC
            message = self.current_nonce + ssid.encode('utf-8') + password.encode('utf-8')
            expected_hmac = hmac.new(
                Config.SHARED_SECRET.encode('utf-8'),
                message,
                hashlib.sha256
            ).digest()
            
            # Constant-time comparison
            is_valid = hmac.compare_digest(client_hmac, expected_hmac)
            
            if is_valid:
                logger.info("Authentication successful")
                self.authenticated = True
                # Invalidate nonce immediately (replay protection)
                self.current_nonce = None
                self.nonce_created_at = None
            else:
                logger.warning("Authentication failed: Invalid HMAC")
                self.authenticated = False
            
            return is_valid
    
    def is_authenticated(self) -> bool:
        """Check if current session is authenticated"""
        with self.lock:
            return self.authenticated
    
    def reset(self):
        """Reset authentication state"""
        with self.lock:
            self.current_nonce = None
            self.nonce_created_at = None
            self.authenticated = False
            logger.info("Security context reset")


# ============================================================================
# BLE GATT SERVER (using BlueZ D-Bus)
# ============================================================================

class Characteristic(dbus.service.Object):
    """Base class for GATT Characteristics"""
    
    def __init__(self, bus, index, uuid, flags, service):
        self.path = service.path + '/char' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.service = service
        self.flags = flags
        self.value = []
        dbus.service.Object.__init__(self, bus, self.path)
    
    def get_properties(self):
        return {
            'org.bluez.GattCharacteristic1': {
                'Service': dbus.ObjectPath(self.service.path),
                'UUID': dbus.String(self.uuid),
                'Flags': dbus.Array(self.flags, signature='s'),
            }
        }
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    @dbus.service.method('org.bluez.GattCharacteristic1', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != 'org.bluez.GattCharacteristic1':
            raise Exception('org.bluez.Error.InvalidArguments', 'Invalid interface')
        return self.get_properties()['org.bluez.GattCharacteristic1']
    
    @dbus.service.method('org.bluez.GattCharacteristic1', in_signature='a{sv}', out_signature='ay')
    def ReadValue(self, options):
        logger.debug(f'ReadValue called on {self.uuid}')
        return self.value
    
    @dbus.service.method('org.bluez.GattCharacteristic1', in_signature='aya{sv}')
    def WriteValue(self, value, options):
        logger.debug(f'WriteValue called on {self.uuid}')
        self.value = value


class AuthChallengeCharacteristic(Characteristic):
    """Handles nonce distribution and HMAC verification"""
    
    def __init__(self, bus, index, service, security_manager, pi_connect_service):
        self.security_manager = security_manager
        self.pi_connect_service = pi_connect_service
        Characteristic.__init__(
            self, bus, index,
            Config.CHAR_AUTH_CHALLENGE_UUID,
            ['read', 'write'],
            service
        )
    
    def ReadValue(self, options):
        """Client reads nonce"""
        nonce = self.security_manager.generate_nonce()
        self.value = list(nonce)
        logger.info("Nonce sent to client")
        return self.value
    
    def WriteValue(self, value, options):
        """Client writes HMAC response"""
        self.value = value
        self.pi_connect_service.received_hmac = bytes(value)
        logger.info("Received auth challenge response from client")


class WiFiSSIDCharacteristic(Characteristic):
    """Receives WiFi SSID"""
    
    def __init__(self, bus, index, service, pi_connect_service):
        self.pi_connect_service = pi_connect_service
        Characteristic.__init__(
            self, bus, index,
            Config.CHAR_WIFI_SSID_UUID,
            ['write'],
            service
        )
    
    def WriteValue(self, value, options):
        self.value = value
        ssid = bytes(value).decode('utf-8')
        logger.info(f"Received SSID: {ssid}")
        self.pi_connect_service.received_ssid = ssid


class WiFiPasswordCharacteristic(Characteristic):
    """Receives WiFi password and triggers connection"""
    
    def __init__(self, bus, index, service, pi_connect_service):
        self.pi_connect_service = pi_connect_service
        Characteristic.__init__(
            self, bus, index,
            Config.CHAR_WIFI_PASS_UUID,
            ['write'],
            service
        )
    
    def WriteValue(self, value, options):
        self.value = value
        password = bytes(value).decode('utf-8')
        logger.info("Received WiFi password")
        self.pi_connect_service.received_password = password
        # Trigger connection attempt
        self.pi_connect_service.attempt_connection()


class StatusCharacteristic(Characteristic):
    """Notifies client of connection status"""
    
    def __init__(self, bus, index, service):
        Characteristic.__init__(
            self, bus, index,
            Config.CHAR_STATUS_UUID,
            ['read', 'notify'],
            service
        )
        self.notifying = False
    
    def update_status(self, status: str):
        """Update and notify status"""
        self.value = list(status.encode('utf-8'))
        logger.info(f"Status updated: {status}")
        if self.notifying:
            self.PropertiesChanged('org.bluez.GattCharacteristic1', {'Value': self.value}, [])
    
    @dbus.service.method('org.bluez.GattCharacteristic1')
    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True
        logger.info("Status notifications enabled")
    
    @dbus.service.method('org.bluez.GattCharacteristic1')
    def StopNotify(self):
        if not self.notifying:
            return
        self.notifying = False
        logger.info("Status notifications disabled")
    
    @dbus.service.signal('org.freedesktop.DBus.Properties', signature='sa{sv}as')
    def PropertiesChanged(self, interface, changed, invalidated):
        pass


class Service(dbus.service.Object):
    """GATT Service"""
    
    def __init__(self, bus, index, uuid, primary):
        self.path = '/org/bluez/piconnect/service' + str(index)
        self.bus = bus
        self.uuid = uuid
        self.primary = primary
        self.characteristics = []
        dbus.service.Object.__init__(self, bus, self.path)
    
    def get_properties(self):
        return {
            'org.bluez.GattService1': {
                'UUID': dbus.String(self.uuid),
                'Primary': dbus.Boolean(self.primary),
                'Characteristics': dbus.Array(
                    [dbus.ObjectPath(char.get_path()) for char in self.characteristics],
                    signature='o'
                )
            }
        }
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    def add_characteristic(self, characteristic):
        self.characteristics.append(characteristic)
    
    @dbus.service.method('org.bluez.GattService1', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != 'org.bluez.GattService1':
            raise Exception('org.bluez.Error.InvalidArguments', 'Invalid interface')
        return self.get_properties()['org.bluez.GattService1']


class Application(dbus.service.Object):
    """GATT Application"""
    
    def __init__(self, bus):
        self.path = '/org/bluez/piconnect'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    def add_service(self, service):
        self.services.append(service)
    
    @dbus.service.method('org.freedesktop.DBus.ObjectManager', out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            for char in service.characteristics:
                response[char.get_path()] = char.get_properties()
        return response


class Advertisement(dbus.service.Object):
    """BLE Advertisement"""
    
    def __init__(self, bus, index):
        self.path = '/org/bluez/piconnect/advertisement' + str(index)
        self.bus = bus
        self.ad_type = 'peripheral'
        self.service_uuids = [Config.SERVICE_UUID]
        self.local_name = Config.DEVICE_NAME
        self.include_tx_power = True
        dbus.service.Object.__init__(self, bus, self.path)
    
    def get_properties(self):
        properties = {
            'org.bluez.LEAdvertisement1': {
                'Type': dbus.String(self.ad_type),
                'ServiceUUIDs': dbus.Array(self.service_uuids, signature='s'),
                'LocalName': dbus.String(self.local_name),
                'IncludeTxPower': dbus.Boolean(self.include_tx_power)
            }
        }
        return properties
    
    def get_path(self):
        return dbus.ObjectPath(self.path)
    
    @dbus.service.method('org.freedesktop.DBus.Properties', in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        if interface != 'org.bluez.LEAdvertisement1':
            raise Exception('org.bluez.Error.InvalidArguments', 'Invalid interface')
        return self.get_properties()['org.bluez.LEAdvertisement1']
    
    @dbus.service.method('org.bluez.LEAdvertisement1', in_signature='', out_signature='')
    def Release(self):
        logger.info('Advertisement released')


# ============================================================================
# MAIN PI-CONNECT SERVICE
# ============================================================================

class PiConnectService:
    """Main service orchestrating all components"""
    
    def __init__(self):
        self.state_machine = StateMachine()
        self.security_manager = SecurityManager()
        self.network_manager = NetworkManager()
        
        # Received credentials
        self.received_ssid: Optional[str] = None
        self.received_password: Optional[str] = None
        self.received_hmac: Optional[bytes] = None
        
        # BLE components
        self.bus = None
        self.app = None
        self.adv = None
        self.service = None
        self.status_char = None
        self.gatt_manager = None
        self.ad_manager = None
        
        # Threading
        self.mainloop = None
        self.mainloop_thread = None
        self.watchdog_thread = None
        self.running = False
        
        # GPIO Button
        self.button = None
        
        logger.info("Pi-Connect Service initialized")
    
    def setup_ble(self):
        """Initialize BLE GATT server and advertisement"""
        try:
            dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
            self.bus = dbus.SystemBus()
            
            # Create application
            self.app = Application(self.bus)
            
            # Create service
            self.service = Service(self.bus, 0, Config.SERVICE_UUID, True)
            
            # Create characteristics
            auth_char = AuthChallengeCharacteristic(self.bus, 0, self.service, self.security_manager, self)
            ssid_char = WiFiSSIDCharacteristic(self.bus, 1, self.service, self)
            pass_char = WiFiPasswordCharacteristic(self.bus, 2, self.service, self)
            self.status_char = StatusCharacteristic(self.bus, 3, self.service)
            
            self.service.add_characteristic(auth_char)
            self.service.add_characteristic(ssid_char)
            self.service.add_characteristic(pass_char)
            self.service.add_characteristic(self.status_char)
            
            self.app.add_service(self.service)
            
            # Create advertisement
            self.adv = Advertisement(self.bus, 0)
            
            # Get managers
            adapter_obj = self.bus.get_object('org.bluez', '/org/bluez/hci0')
            self.gatt_manager = dbus.Interface(adapter_obj, 'org.bluez.GattManager1')
            self.ad_manager = dbus.Interface(adapter_obj, 'org.bluez.LEAdvertisingManager1')
            
            logger.info("BLE components initialized")
            
        except Exception as e:
            logger.error(f"Failed to setup BLE: {e}")
            raise
    
    def start_advertising(self):
        """Start BLE advertising"""
        try:
            # Register GATT application
            self.gatt_manager.RegisterApplication(
                self.app.get_path(), {},
                reply_handler=lambda: logger.info("GATT application registered"),
                error_handler=lambda e: logger.error(f"GATT registration failed: {e}")
            )
            
            # Register advertisement
            self.ad_manager.RegisterAdvertisement(
                self.adv.get_path(), {},
                reply_handler=lambda: logger.info("Advertisement registered"),
                error_handler=lambda e: logger.error(f"Advertisement registration failed: {e}")
            )
            
            logger.info("BLE advertising started")
            
        except Exception as e:
            logger.error(f"Failed to start advertising: {e}")
    
    def stop_advertising(self):
        """Stop BLE advertising"""
        try:
            if self.ad_manager and self.adv:
                self.ad_manager.UnregisterAdvertisement(self.adv.get_path())
                logger.info("Advertisement unregistered")
        except Exception as e:
            logger.error(f"Failed to stop advertising: {e}")
    
    def update_status(self, status: str):
        """Update client status"""
        if self.status_char:
            self.status_char.update_status(status)
    
    def attempt_connection(self):
        """Process received credentials and attempt WiFi connection"""
        if not self.received_ssid or not self.received_password:
            logger.error("Missing SSID or password")
            self.update_status("Error: Missing credentials")
            return
        
        # Verify HMAC authentication
        if not self.received_hmac:
            logger.warning("No HMAC received")
            self.update_status("Error: Authentication required")
            return
        
        # Verify the HMAC against the credentials
        if not self.security_manager.verify_auth(self.received_hmac, self.received_ssid, self.received_password):
            logger.warning("HMAC verification failed")
            self.update_status("Error: Authentication failed")
            self.security_manager.reset()
            self.received_ssid = None
            self.received_password = None
            self.received_hmac = None
            return
        
        # Double-check authentication status
        if not self.security_manager.is_authenticated():
            logger.warning("Unauthenticated connection attempt")
            self.update_status("Error: Authentication failed")
            self.security_manager.reset()
            self.received_ssid = None
            self.received_password = None
            return
        
        # Set state to CONNECTING
        self.state_machine.set_state(SystemState.CONNECTING, "Processing credentials")
        
        # Notify client
        self.update_status("Scanning networks...")
        time.sleep(1)
        
        # Attempt connection in background thread to avoid blocking
        connection_thread = threading.Thread(
            target=self._connect_worker,
            args=(self.received_ssid, self.received_password),
            daemon=True
        )
        connection_thread.start()
    
    def _connect_worker(self, ssid: str, password: str):
        """Background worker for WiFi connection"""
        try:
            self.update_status("Connecting...")
            success, message = self.network_manager.connect_wifi(ssid, password)
            
            if success:
                self.update_status("Success! Connected to WiFi")
                time.sleep(2)
                # Transition to IDLE after successful connection
                self.state_machine.set_state(SystemState.IDLE, "WiFi connected")
                self.state_machine.clear_forced_mode()
            else:
                self.update_status(f"Failed: {message}")
                time.sleep(3)
                # Return to ADVERTISING on failure
                self.state_machine.set_state(SystemState.ADVERTISING, "Connection failed")
        
        except Exception as e:
            logger.error(f"Connection worker error: {e}")
            self.update_status(f"Error: {str(e)}")
            self.state_machine.set_state(SystemState.ADVERTISING, "Connection error")
        
        finally:
            # Clear credentials
            self.received_ssid = None
            self.received_password = None
            self.received_hmac = None
            self.security_manager.reset()
    
    def setup_button(self):
        """Setup GPIO button for hardware trigger"""
        if not GPIO_AVAILABLE:
            logger.warning("GPIO not available, button disabled")
            return
        
        try:
            self.button = Button(
                Config.BUTTON_GPIO,
                pull_up=True,
                hold_time=Config.BUTTON_HOLD_TIME
            )
            
            def on_held():
                logger.warning(f"Button held for {Config.BUTTON_HOLD_TIME}s - forcing config mode")
                self.state_machine.force_config_mode()
            
            self.button.when_held = on_held
            logger.info(f"GPIO button initialized on GPIO {Config.BUTTON_GPIO}")
            
        except Exception as e:
            logger.error(f"Failed to setup button: {e}")
    
    def watchdog(self):
        """Main state machine watchdog loop"""
        logger.info("Watchdog thread started")
        
        while self.running:
            try:
                current_state = self.state_machine.get_state()
                
                if current_state == SystemState.BOOT:
                    # Check initial connectivity
                    if self.network_manager.is_connected():
                        logger.info("Boot: Internet detected")
                        self.state_machine.set_state(SystemState.IDLE, "Initial connection found")
                    else:
                        logger.info("Boot: No internet detected")
                        self.state_machine.set_state(SystemState.ADVERTISING, "No initial connection")
                
                elif current_state == SystemState.IDLE:
                    # Check if still connected
                    if not self.network_manager.is_connected() or self.state_machine.forced_config_mode:
                        if self.state_machine.forced_config_mode:
                            logger.info("Forced config mode active")
                        else:
                            logger.warning("Connection lost")
                        self.state_machine.set_state(SystemState.ADVERTISING, "Connection lost or forced")
                    
                    # CPU-friendly: long sleep when idle
                    time.sleep(Config.IDLE_CHECK_INTERVAL)
                    continue
                
                elif current_state == SystemState.ADVERTISING:
                    # Check if connection was restored
                    if self.network_manager.is_connected() and not self.state_machine.forced_config_mode:
                        logger.info("Connection restored")
                        self.state_machine.set_state(SystemState.IDLE, "Connection restored")
                    
                    # Moderate sleep when advertising
                    time.sleep(Config.ADVERTISING_CHECK_INTERVAL)
                    continue
                
                elif current_state == SystemState.CONNECTING:
                    # Wait for connection attempt to complete
                    # Don't check connectivity to avoid interfering
                    time.sleep(5)
                    continue
                
                # Default sleep
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Watchdog error: {e}")
                time.sleep(5)
        
        logger.info("Watchdog thread stopped")
    
    def state_manager(self):
        """Manages BLE based on current state"""
        logger.info("State manager thread started")
        current_advertising = False
        
        while self.running:
            try:
                state = self.state_machine.get_state()
                should_advertise = state in [SystemState.ADVERTISING, SystemState.CONNECTING]
                
                # Start advertising if needed
                if should_advertise and not current_advertising:
                    logger.info("Starting BLE advertising")
                    self.start_advertising()
                    current_advertising = True
                
                # Stop advertising if needed
                elif not should_advertise and current_advertising:
                    logger.info("Stopping BLE advertising")
                    self.stop_advertising()
                    current_advertising = False
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"State manager error: {e}")
                time.sleep(5)
        
        logger.info("State manager thread stopped")
    
    def run(self):
        """Start the service"""
        try:
            self.running = True
            
            # Setup BLE
            self.setup_ble()
            
            # Setup GPIO button
            self.setup_button()
            
            # Start watchdog thread
            self.watchdog_thread = threading.Thread(target=self.watchdog, daemon=False)
            self.watchdog_thread.start()
            
            # Start state manager thread
            state_manager_thread = threading.Thread(target=self.state_manager, daemon=False)
            state_manager_thread.start()
            
            # Run GLib mainloop in separate thread
            self.mainloop = GLib.MainLoop()
            self.mainloop_thread = threading.Thread(target=self.mainloop.run, daemon=False)
            self.mainloop_thread.start()
            
            logger.info("Pi-Connect service running")
            
            # Keep main thread alive
            while self.running:
                time.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
            self.stop()
        except Exception as e:
            logger.error(f"Service error: {e}", exc_info=True)
            self.stop()
    
    def stop(self):
        """Stop the service gracefully"""
        logger.info("Stopping Pi-Connect service...")
        self.running = False
        
        # Stop advertising
        self.stop_advertising()
        
        # Stop mainloop
        if self.mainloop:
            self.mainloop.quit()
        
        # Wait for threads
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=5)
        
        logger.info("Pi-Connect service stopped")


# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("Pi-Connect 2.0 - Starting")
    logger.info("=" * 60)
    
    # Check if running as root (required for BLE)
    if os.geteuid() != 0:
        logger.error("This service must run as root for BLE access")
        sys.exit(1)
    
    # Verify shared secret is set
    if Config.SHARED_SECRET == "CHANGE_ME_IN_PRODUCTION_USE_ENV_VAR":
        logger.warning("!" * 60)
        logger.warning("WARNING: Using default shared secret!")
        logger.warning("Set PI_CONNECT_SECRET environment variable in production")
        logger.warning("!" * 60)
    
    # Create and run service
    service = PiConnectService()
    service.run()


if __name__ == "__main__":
    main()
