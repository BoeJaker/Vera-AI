# Babelfish - Universal Protocol Translator

## Overview

**Babelfish** is Vera's protocol-agnostic communication toolkit that enables seamless interaction with any digital protocol. It acts as a universal translator, allowing Vera to speak HTTP, WebSockets, MQTT, SSH, IRC, LoRa, Matrix, Slack, and many more protocols through a unified interface.

## Purpose

Babelfish enables Vera to:
- **Communicate universally** across any digital protocol
- **Integrate legacy systems** without custom adapters
- **Build hybrid networks** combining multiple protocols
- **Create custom VPNs** and tunnels
- **Abstract protocol complexity** from agents and tools

## Core Concept

Every protocol in Babelfish has the same interface:
```python
connection = protocol.open()
connection.send(data)
response = connection.receive()
connection.close()
```

Whether it's HTTP, MQTT, or IRC, the agent doesn't need to know the underlying protocol details.

## Architecture

```
Agent/Tool Request
       ↓
Babelfish Translator
       ↓
Protocol Selection (HTTP, MQTT, SSH, etc.)
       ↓
Connection Management
       ↓
Data Transmission
       ↓
Response Handling
       ↓
Unified Response to Agent
```

## Supported Protocols

### Layer 1: Core Protocols (Production-Ready)

#### HTTP/HTTPS
**Use Cases:** REST APIs, web scraping, external services
```python
from Toolchain.Tools.babelfish.babelfish import HTTPCarrier

http = HTTPCarrier()
connection = http.open("https://api.example.com")
response = connection.send(
    method="POST",
    endpoint="/data",
    data={"key": "value"},
    headers={"Authorization": "Bearer token"}
)
print(response.json())
connection.close()
```

#### WebSockets
**Use Cases:** Real-time chat, live data feeds, bidirectional communication
```python
from Toolchain.Tools.babelfish.babelfish import WebSocketCarrier

ws = WebSocketCarrier()
connection = ws.open("wss://example.com/socket")

# Send message
connection.send({"type": "chat", "message": "Hello"})

# Receive streaming data
for message in connection.receive_stream():
    print(message)

connection.close()
```

#### MQTT
**Use Cases:** IoT devices, message queuing, pub/sub patterns
```python
from Toolchain.Tools.babelfish.babelfish import MQTTCarrier

mqtt = MQTTCarrier()
connection = mqtt.open(
    broker="mqtt.example.com",
    port=1883,
    client_id="vera_agent"
)

# Subscribe to topic
connection.subscribe("sensors/temperature")

# Publish message
connection.publish("actuators/light", {"state": "on"})

# Receive messages
for topic, message in connection.receive():
    print(f"{topic}: {message}")
```

#### SSH/SFTP
**Use Cases:** Remote command execution, file transfer, server management
```python
from Toolchain.Tools.babelfish.babelfish import SSHCarrier

ssh = SSHCarrier()
connection = ssh.open(
    host="server.example.com",
    username="user",
    key_file="/path/to/key.pem"
)

# Execute command
result = connection.send("ls -la /var/www")
print(result.stdout)

# File transfer (SFTP)
connection.upload("/local/file.txt", "/remote/file.txt")
connection.download("/remote/data.db", "/local/data.db")

connection.close()
```

### Layer 2: Extended Protocols (Supported)

#### IRC (Internet Relay Chat)
**Use Cases:** Chat integration, legacy systems, community engagement
```python
from Toolchain.Tools.babelfish.babelfish import IRCCarrier

irc = IRCCarrier()
connection = irc.open(
    server="irc.freenode.net",
    port=6667,
    nickname="vera_bot",
    channels=["#vera-ai"]
)

# Send message to channel
connection.send("#vera-ai", "Hello from Vera!")

# Receive messages
for channel, user, message in connection.receive():
    print(f"{user} in {channel}: {message}")
```

#### Matrix
**Use Cases:** Federated chat, E2E encrypted messaging
```python
from Toolchain.Tools.babelfish.babelfish import MatrixCarrier

matrix = MatrixCarrier()
connection = matrix.open(
    homeserver="https://matrix.org",
    username="@vera:matrix.org",
    password="password"
)

# Join room
connection.join_room("!roomid:matrix.org")

# Send encrypted message
connection.send(
    room="!roomid:matrix.org",
    message="Secure message",
    encrypt=True
)
```

#### Slack
**Use Cases:** Team notifications, bot integration
```python
from Toolchain.Tools.babelfish.babelfish import SlackCarrier

slack = SlackCarrier()
connection = slack.open(token="xoxb-your-token")

# Send message
connection.send(
    channel="#general",
    text="Deployment complete!",
    blocks=[{
        "type": "section",
        "text": {"type": "mrkdwn", "text": "*Success*: Build passed"}
    }]
)
```

### Layer 3: Experimental Protocols

#### WebRTC
**Use Cases:** Peer-to-peer communication, video/audio streaming

#### QUIC/HTTP3
**Use Cases:** Low-latency web communication

#### LoRa (Low-Power Radio)
**Use Cases:** IoT long-range communication

## Multi-Modal Tunnels

Babelfish can combine multiple protocols into hybrid communication channels:

### Example: HTTP over IRC Tunnel
```python
from Toolchain.Tools.babelfish.babelfish import HybridTunnel

# Create tunnel: HTTP data transmitted via IRC
tunnel = HybridTunnel()
tunnel.add_carrier("irc", IRCCarrier(server="irc.freenode.net"))
tunnel.add_carrier("http", HTTPCarrier())

# HTTP request sent through IRC
tunnel.route("http", "irc")
response = tunnel.send_http_over_irc(
    url="http://api.example.com/data",
    irc_channel="#vera-tunnel"
)
```

### Example: Multi-Protocol VPN
```python
# VPN using WebSocket + MQTT fallback
vpn = HybridTunnel()
vpn.add_carrier("primary", WebSocketCarrier(url="wss://vpn.example.com"))
vpn.add_carrier("fallback", MQTTCarrier(broker="mqtt.example.com"))

# Auto-failover
vpn.set_fallback("primary", "fallback")

# Send data (uses WebSocket, falls back to MQTT if unavailable)
vpn.send(data="encrypted_payload")
```

## Encryption and Security

### Built-in Encryption
```python
from Toolchain.Tools.babelfish.babelfish import EncryptedCarrier

# Wrap any carrier with encryption
encrypted_http = EncryptedCarrier(
    carrier=HTTPCarrier(),
    encryption="AES-256-GCM",
    key="your-encryption-key"
)

# All data automatically encrypted
connection = encrypted_http.open("http://api.example.com")
connection.send({"sensitive": "data"})  # Encrypted before transmission
```

### TLS/SSL
```python
# HTTPS with certificate validation
https = HTTPCarrier(
    verify_ssl=True,
    cert="/path/to/cert.pem",
    key="/path/to/key.pem"
)
```

### End-to-End Encryption
```python
# E2E encrypted Matrix messaging
matrix = MatrixCarrier(enable_e2ee=True)
connection = matrix.open(homeserver="https://matrix.org")
connection.send(room="!room:matrix.org", message="Secret", encrypt=True)
```

## Usage Patterns

### API Integration
```python
# Integrate with any REST API
api = HTTPCarrier()
connection = api.open("https://api.github.com")

repos = connection.send(
    method="GET",
    endpoint="/users/BoeJaker/repos",
    headers={"Authorization": "Bearer token"}
)

for repo in repos.json():
    print(repo['name'])
```

### IoT Device Communication
```python
# Control IoT devices via MQTT
iot = MQTTCarrier()
connection = iot.open(broker="iot.example.com")

# Subscribe to sensor data
connection.subscribe("home/sensors/#")

# Publish control command
connection.publish("home/lights/living-room", {"state": "on", "brightness": 80})

# Receive sensor readings
for topic, data in connection.receive():
    if topic.startswith("home/sensors/temperature"):
        temperature = data['value']
        if temperature > 25:
            connection.publish("home/ac", {"state": "on"})
```

### Remote Server Management
```python
# Execute commands on remote servers
ssh = SSHCarrier()
servers = [
    ("web1.example.com", "user", "/keys/web1.pem"),
    ("web2.example.com", "user", "/keys/web2.pem")
]

for host, user, key in servers:
    connection = ssh.open(host=host, username=user, key_file=key)

    # Deploy application
    connection.send("cd /var/www && git pull origin main")
    connection.send("systemctl restart nginx")

    # Check status
    result = connection.send("systemctl status nginx")
    print(f"{host}: {result.stdout}")

    connection.close()
```

### Chat Bot Integration
```python
# Multi-platform chat bot
from threading import Thread

def irc_handler():
    irc = IRCCarrier()
    conn = irc.open(server="irc.freenode.net", channels=["#vera"])
    for channel, user, message in conn.receive():
        if message.startswith("!vera"):
            response = vera.process_query(message[6:])
            conn.send(channel, f"{user}: {response}")

def slack_handler():
    slack = SlackCarrier()
    conn = slack.open(token="xoxb-token")
    for event in conn.receive_events():
        if event['type'] == 'message':
            response = vera.process_query(event['text'])
            conn.send(channel=event['channel'], text=response)

# Run both handlers concurrently
Thread(target=irc_handler).start()
Thread(target=slack_handler).start()
```

## Configuration

### Carrier Configuration
```python
# Configure carrier defaults
carrier_config = {
    "http": {
        "timeout": 30,
        "retries": 3,
        "verify_ssl": True
    },
    "mqtt": {
        "keepalive": 60,
        "qos": 1,
        "clean_session": True
    },
    "ssh": {
        "timeout": 10,
        "compression": True,
        "look_for_keys": True
    }
}
```

### Environment Variables
```bash
# HTTP Carrier
HTTP_TIMEOUT=30
HTTP_RETRIES=3
HTTP_USER_AGENT="Vera-AI/1.0"

# MQTT Carrier
MQTT_BROKER=mqtt.example.com
MQTT_PORT=1883
MQTT_USERNAME=vera
MQTT_PASSWORD=secret

# SSH Carrier
SSH_KEY_PATH=/keys/default.pem
SSH_KNOWN_HOSTS=/home/user/.ssh/known_hosts
```

## Advanced Features

### Connection Pooling
```python
# Reuse connections for efficiency
http = HTTPCarrier(pool_connections=10, pool_maxsize=20)

# Multiple requests use same connection
for i in range(100):
    response = http.send("GET", "https://api.example.com/data")
```

### Automatic Retries
```python
# Retry failed requests
http = HTTPCarrier(
    retries=3,
    backoff_factor=2,  # Exponential backoff
    retry_on=[408, 429, 500, 502, 503, 504]
)
```

### Rate Limiting
```python
# Respect API rate limits
http = HTTPCarrier(rate_limit=100)  # 100 requests per minute
```

### Caching
```python
# Cache responses
http = HTTPCarrier(cache_enabled=True, cache_ttl=3600)

# First request fetches from API
response1 = http.send("GET", "https://api.example.com/data")

# Second request served from cache
response2 = http.send("GET", "https://api.example.com/data")
```

## Error Handling

```python
from Toolchain.Tools.babelfish.exceptions import (
    ConnectionError,
    TimeoutError,
    AuthenticationError,
    ProtocolError
)

try:
    http = HTTPCarrier()
    connection = http.open("https://api.example.com")
    response = connection.send("GET", "/data")

except ConnectionError as e:
    print(f"Failed to connect: {e}")

except TimeoutError as e:
    print(f"Request timed out: {e}")

except AuthenticationError as e:
    print(f"Authentication failed: {e}")

except ProtocolError as e:
    print(f"Protocol error: {e}")

finally:
    if connection:
        connection.close()
```

## Best Practices

### 1. Always Close Connections
```python
# Use context managers
with HTTPCarrier() as http:
    connection = http.open("https://api.example.com")
    response = connection.send("GET", "/data")
    # Connection auto-closed
```

### 2. Handle Errors Gracefully
```python
# Implement retry logic
for attempt in range(3):
    try:
        response = connection.send(request)
        break
    except TimeoutError:
        if attempt < 2:
            time.sleep(2 ** attempt)  # Exponential backoff
        else:
            raise
```

### 3. Use Encryption for Sensitive Data
```python
# Always encrypt sensitive communications
encrypted = EncryptedCarrier(carrier=MQTTCarrier())
```

### 4. Configure Timeouts
```python
# Prevent hanging connections
carrier = HTTPCarrier(timeout=30)
```

### 5. Log Protocol Activity
```python
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("babelfish")

# Detailed protocol logs
carrier = HTTPCarrier(logger=logger)
```

## Integration with Vera

### As a Tool
```python
# Babelfish exposed as Vera tool
from Toolchain.tools import Tool

http_tool = Tool(
    name="HTTPRequest",
    func=lambda url: HTTPCarrier().open(url).send("GET", "/"),
    description="Make HTTP request to URL"
)
```

### In Toolchain Plans
```json
{
  "query": "Fetch data from API and publish to MQTT",
  "plan": [
    {
      "tool": "BabelfishHTTP",
      "input": "https://api.example.com/data"
    },
    {
      "tool": "BabelfishMQTT",
      "input": {
        "broker": "mqtt.example.com",
        "topic": "data/updates",
        "payload": "{step_1}"
      }
    }
  ]
}
```

## Extending Babelfish

### Adding Custom Protocols
```python
from Toolchain.Tools.babelfish.base import BaseCarrier

class CustomProtocolCarrier(BaseCarrier):
    """Implement your custom protocol"""

    def open(self, **kwargs):
        # Connection logic
        self.connection = CustomProtocolClient(**kwargs)
        return self

    def send(self, data):
        # Send data via protocol
        return self.connection.transmit(data)

    def receive(self):
        # Receive data
        return self.connection.read()

    def close(self):
        # Cleanup
        self.connection.disconnect()
```

### Protocol Adapters
```python
# Adapt existing libraries
class TelegramCarrier(BaseCarrier):
    """Telegram Bot API carrier"""

    def __init__(self):
        from telegram import Bot
        self.Bot = Bot

    def open(self, token):
        self.bot = self.Bot(token=token)
        return self

    def send(self, chat_id, text):
        return self.bot.send_message(chat_id=chat_id, text=text)
```

## Troubleshooting

### Connection Failures
```bash
# Test connectivity
ping mqtt.example.com
telnet api.example.com 443
```

### Authentication Issues
```python
# Verify credentials
carrier = HTTPCarrier(debug=True)  # Verbose logging
connection = carrier.open("https://api.example.com")
```

### Protocol Errors
```python
# Check protocol compatibility
carrier = HTTPCarrier()
print(carrier.supported_methods)  # ['GET', 'POST', 'PUT', 'DELETE', ...]
```

## Related Documentation

- [Toolchain Engine](../../README.md) - Tool orchestration
- [API Integration Shim](../../../README.md#api-integration-shim) - External API usage
- [Babelfish Architecture](../../../Vera%20Assistant%20Docs/Babelfish.md) - Deep dive

## Contributing

To add support for new protocols:
1. Extend `BaseCarrier` class
2. Implement required methods (open, send, receive, close)
3. Add protocol-specific configuration
4. Write tests
5. Document usage examples

---

**Related Components:**
- [Toolchain](../../) - Execution engine
- [Agents](../../../Agents/) - Use Babelfish for communication
- [External Knowledge](../../../Memory/) - Layer 5 integration
