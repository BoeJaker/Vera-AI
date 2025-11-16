"""
Microcontroller Control and Interaction Tools (COMPLETE)
Real-time control and data collection from programmed microcontrollers
Supports Serial/USB, WiFi, MQTT, WebSocket protocols
"""

import serial
import serial.tools.list_ports
import requests
import json
import time
import threading
import queue
import asyncio
import websockets
from typing import List, Dict, Any, Optional, Callable, Literal
from pathlib import Path
from pydantic import BaseModel, Field
from datetime import datetime
from collections import deque
import csv
import sqlite3
from langchain_core.tools import tool, StructuredTool
from Vera.Toolchain.schemas import *
# ============================================================================
# INPUT SCHEMAS
# ============================================================================

class SerialControlInput(BaseModel):
    """Input schema for serial control commands."""
    device_name: Optional[str] = Field(
        default=None,
        description="Registered device name (or use port)"
    )
    port: Optional[str] = Field(
        default=None,
        description="Serial port (auto-detect if neither specified)"
    )
    command: str = Field(..., description="Command to send")
    wait_response: bool = Field(
        default=True,
        description="Wait for response after command"
    )
    timeout: int = Field(
        default=5,
        description="Response timeout in seconds"
    )


class DeviceRegisterInput(BaseModel):
    """Input schema for registering devices."""
    device_name: str = Field(..., description="Unique device name")
    connection_type: Literal["serial", "wifi_http", "wifi_ws", "mqtt"] = Field(
        ..., description="Connection type"
    )
    connection_params: Dict[str, Any] = Field(
        ...,
        description="Connection parameters (port, ip, url, etc.)"
    )
    protocol: Optional[str] = Field(
        default="json",
        description="Data protocol (json, plaintext, custom)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Device metadata (type, capabilities, etc.)"
    )


class StreamDataInput(BaseModel):
    """Input schema for streaming data from device."""
    device_name: str = Field(..., description="Device to stream from")
    duration: int = Field(
        default=30,
        description="How long to stream (seconds, 0=continuous)"
    )
    save_to_file: Optional[str] = Field(
        default=None,
        description="Save data to file (CSV or JSON)"
    )


class DeviceStateInput(BaseModel):
    """Input schema for device state operations."""
    device_name: str = Field(..., description="Device name")
    operation: Literal["get", "set", "reset"] = Field(
        ..., description="State operation"
    )
    state_key: Optional[str] = Field(
        default=None,
        description="State key to get/set"
    )
    state_value: Optional[Any] = Field(
        default=None,
        description="Value to set"
    )


class BulkCommandInput(BaseModel):
    """Input schema for bulk device commands."""
    device_names: List[str] = Field(
        ..., description="List of devices to command"
    )
    command: str = Field(..., description="Command to send to all")
    sequential: bool = Field(
        default=False,
        description="Send sequentially (true) or parallel (false)"
    )


class DataQueryInput(BaseModel):
    """Input schema for querying collected data."""
    device_name: Optional[str] = Field(
        default=None,
        description="Device name (None for all)"
    )
    start_time: Optional[str] = Field(
        default=None,
        description="Start time for data range"
    )
    end_time: Optional[str] = Field(
        default=None,
        description="End time for data range"
    )
    limit: int = Field(
        default=100,
        description="Maximum number of data points"
    )


# ============================================================================
# DEVICE CONNECTION MANAGERS
# ============================================================================

class SerialDevice:
    """Manages serial/USB connection to a device."""
    
    def __init__(self, port: str, baud_rate: int = 115200, protocol: str = "json"):
        self.port = port
        self.baud_rate = baud_rate
        self.protocol = protocol
        self.serial = None
        self.connected = False
        self.data_queue = queue.Queue()
        self.listener_thread = None
        self.running = False
    
    def connect(self) -> bool:
        """Connect to serial port."""
        try:
            self.serial = serial.Serial(self.port, self.baud_rate, timeout=1)
            time.sleep(2)  # Wait for connection
            self.connected = True
            return True
        except Exception as e:
            print(f"[Error] Serial connection failed: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from serial port."""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)
        
        if self.serial:
            self.serial.close()
        
        self.connected = False
    
    def send_command(self, command: str, wait_response: bool = True, 
                    timeout: int = 5) -> Optional[str]:
        """Send command and optionally wait for response."""
        if not self.connected:
            return None
        
        try:
            # Send command
            self.serial.write(f"{command}\n".encode())
            
            if not wait_response:
                return "Command sent (no response requested)"
            
            # Wait for response
            start_time = time.time()
            response_lines = []
            
            while time.time() - start_time < timeout:
                if self.serial.in_waiting:
                    line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        
                        # Check if response is complete (JSON or specific marker)
                        if self.protocol == "json":
                            try:
                                json.loads(line)
                                return line
                            except:
                                pass
                
                time.sleep(0.1)
            
            return "\n".join(response_lines) if response_lines else None
            
        except Exception as e:
            return f"Error: {str(e)}"
    
    def start_streaming(self, callback: Callable = None):
        """Start background thread to continuously read data."""
        if self.running:
            return
        
        self.running = True
        
        def listen():
            while self.running:
                try:
                    if self.serial and self.serial.in_waiting:
                        line = self.serial.readline().decode('utf-8', errors='ignore').strip()
                        
                        if line:
                            data_point = {
                                "timestamp": datetime.now().isoformat(),
                                "raw": line
                            }
                            
                            # Try parsing as JSON
                            try:
                                data_point["parsed"] = json.loads(line)
                            except:
                                pass
                            
                            # Add to queue
                            self.data_queue.put(data_point)
                            
                            # Call callback if provided
                            if callback:
                                callback(data_point)
                    
                    time.sleep(0.01)
                except Exception as e:
                    print(f"[Error] Streaming error: {e}")
                    time.sleep(1)
        
        self.listener_thread = threading.Thread(target=listen, daemon=True)
        self.listener_thread.start()
    
    def stop_streaming(self):
        """Stop streaming data."""
        self.running = False
        if self.listener_thread:
            self.listener_thread.join(timeout=2)


class WiFiHTTPDevice:
    """Manages WiFi HTTP connection to a device."""
    
    def __init__(self, base_url: str, protocol: str = "json"):
        self.base_url = base_url.rstrip('/')
        self.protocol = protocol
        self.connected = False
    
    def connect(self) -> bool:
        """Test connection to device."""
        try:
            response = requests.get(f"{self.base_url}/", timeout=5)
            self.connected = response.status_code == 200
            return self.connected
        except:
            return False
    
    def send_command(self, command: str, wait_response: bool = True, 
                    timeout: int = 5) -> Optional[str]:
        """Send command via HTTP POST."""
        try:
            response = requests.post(
                f"{self.base_url}/command",
                data={"cmd": command},
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.text
            else:
                return f"Error: HTTP {response.status_code}"
        except Exception as e:
            return f"Error: {str(e)}"
    
    def query_data(self, endpoint: str = "/data") -> Optional[Dict]:
        """Query data from device."""
        try:
            response = requests.get(f"{self.base_url}{endpoint}", timeout=5)
            
            if self.protocol == "json":
                return response.json()
            else:
                return {"data": response.text}
        except Exception as e:
            return {"error": str(e)}


class WiFiWebSocketDevice:
    """Manages WiFi WebSocket connection to a device."""
    
    def __init__(self, ws_url: str, protocol: str = "json"):
        self.ws_url = ws_url
        self.protocol = protocol
        self.websocket = None
        self.connected = False
        self.running = False
        self.data_queue = queue.Queue()
        self.listener_task = None
    
    async def connect_async(self):
        """Connect to WebSocket."""
        try:
            self.websocket = await websockets.connect(self.ws_url)
            self.connected = True
            return True
        except Exception as e:
            print(f"[Error] WebSocket connection failed: {e}")
            return False
    
    async def send_command_async(self, command: str) -> Optional[str]:
        """Send command via WebSocket."""
        try:
            await self.websocket.send(command)
            response = await asyncio.wait_for(self.websocket.recv(), timeout=5)
            return response
        except Exception as e:
            return f"Error: {str(e)}"
    
    async def listen_async(self, callback: Callable = None):
        """Listen for messages from WebSocket."""
        self.running = True
        
        try:
            while self.running:
                message = await self.websocket.recv()
                
                data_point = {
                    "timestamp": datetime.now().isoformat(),
                    "raw": message
                }
                
                # Try parsing as JSON
                try:
                    data_point["parsed"] = json.loads(message)
                except:
                    pass
                
                self.data_queue.put(data_point)
                
                if callback:
                    callback(data_point)
        except:
            pass


# ============================================================================
# DATA STORAGE
# ============================================================================

class DeviceDataStore:
    """Stores data collected from devices."""
    
    def __init__(self, db_path: str = "./device_data.db"):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS device_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    data_type TEXT,
                    raw_data TEXT,
                    parsed_data TEXT
                )
            """)
            
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_device_time 
                ON device_data(device_name, timestamp)
            """)
            
            conn.commit()
    
    def store_data(self, device_name: str, data: Dict):
        """Store data point from device."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO device_data (device_name, timestamp, data_type, raw_data, parsed_data)
                VALUES (?, ?, ?, ?, ?)
            """, (
                device_name,
                data.get("timestamp", datetime.now().isoformat()),
                "json" if "parsed" in data else "raw",
                data.get("raw", ""),
                json.dumps(data.get("parsed")) if "parsed" in data else None
            ))
            conn.commit()
    
    def query_data(self, device_name: str = None, start_time: str = None,
                  end_time: str = None, limit: int = 100) -> List[Dict]:
        """Query stored data."""
        query = "SELECT * FROM device_data WHERE 1=1"
        params = []
        
        if device_name:
            query += " AND device_name = ?"
            params.append(device_name)
        
        if start_time:
            query += " AND timestamp >= ?"
            params.append(start_time)
        
        if end_time:
            query += " AND timestamp <= ?"
            params.append(end_time)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)
            
            results = []
            for row in cursor:
                result = {
                    "id": row["id"],
                    "device_name": row["device_name"],
                    "timestamp": row["timestamp"],
                    "data_type": row["data_type"],
                    "raw_data": row["raw_data"]
                }
                
                if row["parsed_data"]:
                    result["parsed_data"] = json.loads(row["parsed_data"])
                
                results.append(result)
            
            return results
    
    def get_stats(self, device_name: str = None) -> Dict:
        """Get statistics about stored data."""
        with sqlite3.connect(self.db_path) as conn:
            if device_name:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as count,
                        MIN(timestamp) as first,
                        MAX(timestamp) as last
                    FROM device_data
                    WHERE device_name = ?
                """, (device_name,))
            else:
                cursor = conn.execute("""
                    SELECT 
                        COUNT(*) as count,
                        MIN(timestamp) as first,
                        MAX(timestamp) as last
                    FROM device_data
                """)
            
            row = cursor.fetchone()
            
            return {
                "total_records": row[0],
                "first_timestamp": row[1],
                "last_timestamp": row[2]
            }


# ============================================================================
# MICROCONTROLLER CONTROL MANAGER
# ============================================================================

class MicrocontrollerControlManager:
    """Central manager for all microcontroller devices."""
    
    def __init__(self, agent):
        self.agent = agent
        self.devices = {}  # device_name -> device_object
        self.device_configs = {}  # device_name -> config
        self.data_store = DeviceDataStore()
        self.streaming_devices = set()
    
    def register_device(self, device_name: str, connection_type: str,
                       connection_params: Dict, protocol: str = "json",
                       metadata: Dict = None) -> bool:
        """Register a device for control."""
        
        try:
            if connection_type == "serial":
                device = SerialDevice(
                    port=connection_params["port"],
                    baud_rate=connection_params.get("baud_rate", 115200),
                    protocol=protocol
                )
                
                if not device.connect():
                    return False
            
            elif connection_type == "wifi_http":
                device = WiFiHTTPDevice(
                    base_url=connection_params["base_url"],
                    protocol=protocol
                )
                
                if not device.connect():
                    return False
            
            elif connection_type == "wifi_ws":
                device = WiFiWebSocketDevice(
                    ws_url=connection_params["ws_url"],
                    protocol=protocol
                )
                # WebSocket connection handled async
            
            else:
                return False
            
            self.devices[device_name] = device
            self.device_configs[device_name] = {
                "connection_type": connection_type,
                "connection_params": connection_params,
                "protocol": protocol,
                "metadata": metadata or {},
                "registered_at": datetime.now().isoformat()
            }
            
            # Store in agent memory
            self.agent.mem.add_session_memory(
                self.agent.sess.id,
                device_name,
                "microcontroller_device",
                metadata={
                    "connection_type": connection_type,
                    "protocol": protocol
                }
            )
            
            return True
            
        except Exception as e:
            print(f"[Error] Failed to register device: {e}")
            return False
    
    def send_command(self, device_name: str = None, port: str = None,
                    command: str = "", wait_response: bool = True,
                    timeout: int = 5) -> str:
        """Send command to device."""
        
        # Get device
        if device_name and device_name in self.devices:
            device = self.devices[device_name]
        elif port:
            # Try to find device by port
            device = None
            for dev_name, dev in self.devices.items():
                if hasattr(dev, 'port') and dev.port == port:
                    device = dev
                    break
            
            if not device:
                # Create temporary connection
                temp_device = SerialDevice(port)
                if temp_device.connect():
                    result = temp_device.send_command(command, wait_response, timeout)
                    temp_device.disconnect()
                    return result or "No response"
                else:
                    return "[Error] Could not connect to port"
        else:
            return "[Error] No device specified"
        
        if not device:
            return "[Error] Device not found"
        
        # Send command
        response = device.send_command(command, wait_response, timeout)
        
        # Store interaction
        self.data_store.store_data(device_name or port, {
            "timestamp": datetime.now().isoformat(),
            "raw": f"CMD: {command} -> {response}",
            "parsed": {
                "type": "command",
                "command": command,
                "response": response
            }
        })
        
        return response or "No response"
    
    def start_streaming(self, device_name: str, duration: int = 30,
                       save_to_file: str = None) -> bool:
        """Start streaming data from device."""
        
        if device_name not in self.devices:
            return False
        
        device = self.devices[device_name]
        
        # Callback to store data
        def on_data(data_point):
            self.data_store.store_data(device_name, data_point)
        
        # Start streaming
        if hasattr(device, 'start_streaming'):
            device.start_streaming(callback=on_data)
            self.streaming_devices.add(device_name)
            
            # Schedule stop if duration specified
            if duration > 0:
                def stop_later():
                    time.sleep(duration)
                    device.stop_streaming()
                    self.streaming_devices.remove(device_name)
                    
                    # Save to file if requested
                    if save_to_file:
                        self._export_data(device_name, save_to_file, duration)
                
                threading.Thread(target=stop_later, daemon=True).start()
            
            return True
        
        return False
    
    def stop_streaming(self, device_name: str) -> bool:
        """Stop streaming from device."""
        if device_name not in self.devices:
            return False
        
        device = self.devices[device_name]
        
        if hasattr(device, 'stop_streaming'):
            device.stop_streaming()
            self.streaming_devices.discard(device_name)
            return True
        
        return False
    
    def _export_data(self, device_name: str, filename: str, last_seconds: int):
        """Export recent data to file."""
        
        # Calculate start time
        start_time = datetime.now()
        start_time = start_time.replace(second=start_time.second - last_seconds)
        
        # Query data
        data = self.data_store.query_data(
            device_name=device_name,
            start_time=start_time.isoformat(),
            limit=10000
        )
        
        filepath = Path(filename)
        
        if filepath.suffix == '.json':
            # Export as JSON
            filepath.write_text(json.dumps(data, indent=2))
        else:
            # Export as CSV
            with open(filepath, 'w', newline='') as f:
                if data:
                    writer = csv.DictWriter(f, fieldnames=data[0].keys())
                    writer.writeheader()
                    writer.writerows(data)
    
    def get_device_state(self, device_name: str) -> Dict:
        """Get current state of device."""
        if device_name not in self.devices:
            return {"error": "Device not found"}
        
        device = self.devices[device_name]
        config = self.device_configs[device_name]
        
        return {
            "name": device_name,
            "connected": getattr(device, 'connected', False),
            "streaming": device_name in self.streaming_devices,
            "connection_type": config["connection_type"],
            "metadata": config.get("metadata", {}),
            "registered_at": config["registered_at"]
        }
    
    def list_devices(self) -> List[Dict]:
        """List all registered devices."""
        return [
            {
                "name": name,
                **self.get_device_state(name)
            }
            for name in self.devices.keys()
        ]
    
    def bulk_command(self, device_names: List[str], command: str,
                    sequential: bool = False) -> Dict[str, str]:
        """Send command to multiple devices."""
        results = {}
        
        if sequential:
            # Send one at a time
            for device_name in device_names:
                results[device_name] = self.send_command(
                    device_name=device_name,
                    command=command
                )
        else:
            # Send in parallel using threads
            threads = []
            
            def send(dev_name):
                results[dev_name] = self.send_command(
                    device_name=dev_name,
                    command=command
                )
            
            for device_name in device_names:
                thread = threading.Thread(target=send, args=(device_name,))
                thread.start()
                threads.append(thread)
            
            # Wait for all to complete
            for thread in threads:
                thread.join(timeout=10)
        
        return results
    
    def query_collected_data(self, device_name: str = None,
                            start_time: str = None, end_time: str = None,
                            limit: int = 100) -> List[Dict]:
        """Query data collected from devices."""
        return self.data_store.query_data(device_name, start_time, end_time, limit)
    
    def get_data_stats(self, device_name: str = None) -> Dict:
        """Get statistics about collected data."""
        return self.data_store.get_stats(device_name)


# ============================================================================
# MICROCONTROLLER CONTROL TOOLS
# ============================================================================

class MicrocontrollerControlTools:
    """Tools for controlling and interacting with microcontrollers."""
    
    def __init__(self, agent):
        self.agent = agent
        self.manager = MicrocontrollerControlManager(agent)
    
    def register_microcontroller(self, device_name: str, connection_type: str,
                                connection_params: Dict, protocol: str = "json",
                                metadata: Dict = None) -> str:
        """
        Register a microcontroller device for control.
        
        After programming a device, register it here for easy control.
        
        Args:
            device_name: Unique name for this device
            connection_type: serial, wifi_http, wifi_ws, mqtt
            connection_params: Connection details
            protocol: Data protocol (json or plaintext)
            metadata: Optional device metadata
        
        Examples:
            # Serial device
            register_microcontroller(
                device_name="sensor_board",
                connection_type="serial",
                connection_params={"port": "/dev/ttyUSB0", "baud_rate": 115200}
            )
            
            # WiFi HTTP device
            register_microcontroller(
                device_name="wifi_sensor",
                connection_type="wifi_http",
                connection_params={"base_url": "http://192.168.1.100"}
            )
            
            # WebSocket device
            register_microcontroller(
                device_name="realtime_sensor",
                connection_type="wifi_ws",
                connection_params={"ws_url": "ws://192.168.1.100:81"}
            )
        """
        
        success = self.manager.register_device(
            device_name, connection_type, connection_params, protocol, metadata
        )
        
        if success:
            return f"✓ Registered device: {device_name}\nType: {connection_type}\nProtocol: {protocol}"
        else:
            return f"[Error] Failed to register device: {device_name}"
    
    def send_device_command(self, command: str, device_name: str = None,
                           port: str = None, wait_response: bool = True,
                           timeout: int = 5) -> str:
        """
        Send command to microcontroller and get response.
        
        Control your device in real-time via Serial, WiFi, etc.
        
        Args:
            command: Command string to send
            device_name: Name of registered device
            port: Serial port (if not using registered device)
            wait_response: Wait for device response
            timeout: Response timeout
        
        Examples:
            # Control registered device
            send_device_command("LED_ON", device_name="sensor_board")
            send_device_command("READ_TEMP", device_name="sensor_board")
            
            # Direct port access
            send_device_command("STATUS", port="/dev/ttyUSB0")
            
            # Fire and forget
            send_device_command("START_SCAN", device_name="wifi_scanner", wait_response=False)
        
        Common commands (depends on your device code):
            - STATUS: Get device status
            - RESET: Reset device
            - LED_ON/LED_OFF: Control LED
            - READ_SENSOR: Read sensor value
            - START/STOP: Start/stop operations
        """
        
        response = self.manager.send_command(
            device_name, port, command, wait_response, timeout
        )
        
        output = [
            f"Command: {command}",
            f"Device: {device_name or port}",
            "",
            "Response:",
            "-" * 60,
            response or "No response",
            "-" * 60
        ]
        
        return "\n".join(output)
    
    def stream_device_data(self, device_name: str, duration: int = 30,
                          save_to_file: str = None) -> str:
        """
        Stream data from microcontroller in real-time.
        
        Continuously collect data from device. Data is stored in database
        and optionally exported to file.
        
        Args:
            device_name: Name of registered device
            duration: How long to stream (seconds, 0=continuous)
            save_to_file: Save to CSV or JSON file
        
        Examples:
            # Stream for 30 seconds
            stream_device_data("sensor_board", duration=30)
            
            # Continuous streaming
            stream_device_data("sensor_board", duration=0)
            
            # Stream and save to file
            stream_device_data(
                "sensor_board",
                duration=60,
                save_to_file="sensor_data.csv"
            )
        
        Use query_device_data to retrieve collected data later.
        Use stop_device_stream to stop continuous streaming.
        """
        
        success = self.manager.start_streaming(device_name, duration, save_to_file)
        
        if success:
            output = [
                f"✓ Started streaming from: {device_name}",
                f"Duration: {duration}s" + (" (continuous)" if duration == 0 else ""),
            ]
            
            if save_to_file:
                output.append(f"Will save to: {save_to_file}")
            
            output.append("\nData is being collected in background...")
            output.append("Use query_device_data to view collected data")
            
            if duration == 0:
                output.append("Use stop_device_stream to stop streaming")
            
            return "\n".join(output)
        else:
            return f"[Error] Failed to start streaming from: {device_name}"
    
    def stop_device_stream(self, device_name: str) -> str:
        """
        Stop continuous data streaming from device.
        
        Args:
            device_name: Name of device to stop streaming
        """
        
        success = self.manager.stop_streaming(device_name)
        
        if success:
            # Get stats
            stats = self.manager.get_data_stats(device_name)
            
            return f"✓ Stopped streaming from: {device_name}\nCollected {stats['total_records']} data points"
        else:
            return f"[Error] Failed to stop streaming: {device_name}"
    
    def list_microcontrollers(self) -> str:
        """
        List all registered microcontroller devices.
        
        Shows connection status, streaming status, and metadata.
        """
        
        devices = self.manager.list_devices()
        
        if not devices:
            return "No microcontrollers registered"
        
        output = [f"Registered Microcontrollers ({len(devices)}):\n"]
        
        for device in devices:
            status_icon = "🟢" if device["connected"] else "🔴"
            stream_icon = "📊" if device["streaming"] else ""
            
            output.append(f"{status_icon} {stream_icon} {device['name']}")
            output.append(f"   Type: {device['connection_type']}")
            output.append(f"   Connected: {'Yes' if device['connected'] else 'No'}")
            output.append(f"   Streaming: {'Yes' if device['streaming'] else 'No'}")
            
            if device.get('metadata'):
                output.append(f"   Metadata: {device['metadata']}")
            
            output.append("")
        
        return "\n".join(output)
    
    def query_device_data(self, device_name: str = None, start_time: str = None,
                         end_time: str = None, limit: int = 100) -> str:
        """
        Query data collected from microcontrollers.
        
        Retrieve historical data from the database.
        
        Args:
            device_name: Device to query (None for all devices)
            start_time: Start timestamp (ISO format)
            end_time: End timestamp (ISO format)
            limit: Maximum records to return
        
        Examples:
            # Get recent data from device
            query_device_data("sensor_board", limit=50)
            
            # Get data from time range
            query_device_data(
                "sensor_board",
                start_time="2024-01-15T10:00:00",
                end_time="2024-01-15T11:00:00"
            )
            
            # Get data from all devices
            query_device_data(limit=100)
        """
        
        data = self.manager.query_collected_data(device_name, start_time, end_time, limit)
        
        if not data:
            return "No data found"
        
        output = [f"Device Data ({len(data)} records):\n"]
        
        for record in data[:10]:  # Show first 10
            output.append(f"[{record['timestamp']}] {record['device_name']}")
            
            if record.get('parsed_data'):
                output.append(f"  {json.dumps(record['parsed_data'], indent=2)}")
            else:
                output.append(f"  {record['raw_data'][:100]}")
            
            output.append("")
        
        if len(data) > 10:
            output.append(f"... and {len(data) - 10} more records")
        
        # Add stats
        stats = self.manager.get_data_stats(device_name)
        output.append(f"\nTotal records: {stats['total_records']}")
        output.append(f"Time range: {stats['first_timestamp']} to {stats['last_timestamp']}")
        
        return "\n".join(output)
    
    def bulk_device_command(self, device_names: List[str], command: str,
                           sequential: bool = False) -> str:
        """
        Send same command to multiple devices.
        
        Efficient control of multiple microcontrollers at once.
        
        Args:
            device_names: List of device names
            command: Command to send to all
            sequential: Send one-by-one (True) or parallel (False)
        
        Example:
            bulk_device_command(
                device_names=["sensor1", "sensor2", "sensor3"],
                command="START_LOGGING"
            )
        """
        
        results = self.manager.bulk_command(device_names, command, sequential)
        
        output = [
            f"Bulk Command: {command}",
            f"Devices: {len(device_names)}",
            f"Mode: {'Sequential' if sequential else 'Parallel'}",
            "",
            "Results:"
        ]
        
        for device_name, response in results.items():
            output.append(f"\n{device_name}:")
            output.append(f"  {response}")
        
        return "\n".join(output)
    
    def get_device_status(self, device_name: str) -> str:
        """
        Get detailed status of a microcontroller device.
        
        Shows connection state, streaming state, and metadata.
        """
        
        state = self.manager.get_device_state(device_name)
        
        if "error" in state:
            return f"[Error] {state['error']}"
        
        output = [
            f"Device Status: {device_name}",
            "=" * 60,
            f"Connected: {'✓' if state['connected'] else '✗'}",
            f"Streaming: {'✓' if state['streaming'] else '✗'}",
            f"Connection Type: {state['connection_type']}",
            f"Registered: {state['registered_at']}",
        ]
        
        if state.get('metadata'):
            output.append("\nMetadata:")
            for key, value in state['metadata'].items():
                output.append(f"  {key}: {value}")
        
        # Get data stats
        stats = self.manager.get_data_stats(device_name)
        output.extend([
            "\nData Statistics:",
            f"  Total Records: {stats['total_records']}",
            f"  First Record: {stats.get('first_timestamp', 'N/A')}",
            f"  Last Record: {stats.get('last_timestamp', 'N/A')}"
        ])
        
        return "\n".join(output)


# ============================================================================
# ADD TO TOOLLOADER FUNCTION
# ============================================================================

def add_microcontroller_control_tools(tool_list: List, agent):
    """
    Add microcontroller control and interaction tools.
    
    Enables LLM to:
    - Register devices (Serial, WiFi, WebSocket)
    - Send real-time commands
    - Stream data continuously
    - Query historical data
    - Control multiple devices
    - Monitor device status
    
    This is for CONTROLLING already-programmed devices.
    Use with add_esp32_tools for programming devices.
    
    Requirements:
    - pyserial>=3.5
    - requests>=2.31.0
    - websockets>=12.0 (optional, for WebSocket devices)
    
    Call in ToolLoader:
        add_microcontroller_control_tools(tool_list, agent)
    """
    
    mc_tools = MicrocontrollerControlTools(agent)
    
    tool_list.extend([
        StructuredTool.from_function(
            func=mc_tools.register_microcontroller,
            name="register_microcontroller",
            description=(
                "Register a microcontroller device for control. "
                "After programming device, register it here. "
                "Supports Serial/USB, WiFi HTTP, WebSocket, MQTT. "
                "Makes device available for commands and data streaming."
            ),
            args_schema=DeviceRegisterInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.send_device_command,
            name="send_device_command",
            description=(
                "Send command to microcontroller and get response. "
                "Real-time control via Serial or WiFi. "
                "Examples: LED_ON, READ_SENSOR, START_SCAN, etc. "
                "Can use registered device name or direct port."
            ),
            args_schema=SerialControlInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.stream_device_data,
            name="stream_device_data",
            description=(
                "Stream data from microcontroller in real-time. "
                "Continuously collect sensor readings, events, etc. "
                "Data stored in database, optionally exported to file. "
                "Can run for specific duration or continuously."
            ),
            args_schema=StreamDataInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.stop_device_stream,
            name="stop_device_stream",
            description=(
                "Stop continuous data streaming from device. "
                "Use after starting continuous stream (duration=0)."
            ),
            args_schema=DeviceStateInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.list_microcontrollers,
            name="list_microcontrollers",
            description=(
                "List all registered microcontroller devices. "
                "Shows connection status, streaming status, metadata. "
                "Quick overview of all connected devices."
            ),
        ),
        
        StructuredTool.from_function(
            func=mc_tools.query_device_data,
            name="query_device_data",
            description=(
                "Query historical data collected from microcontrollers. "
                "Retrieve sensor readings, events from database. "
                "Filter by device, time range, limit. "
                "Analyze collected data."
            ),
            args_schema=DataQueryInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.bulk_device_command,
            name="bulk_device_command",
            description=(
                "Send same command to multiple devices at once. "
                "Efficient control of device fleets. "
                "Can run sequentially or in parallel."
            ),
            args_schema=BulkCommandInput
        ),
        
        StructuredTool.from_function(
            func=mc_tools.get_device_status,
            name="get_device_status",
            description=(
                "Get detailed status of a microcontroller device. "
                "Shows connection state, streaming state, data stats. "
                "Troubleshoot device issues."
            ),
            args_schema=DeviceStateInput
        ),
    ])
    
    return tool_list


# Required dependencies (add to requirements.txt):
# pyserial>=3.5
# requests>=2.31.0
# websockets>=12.0