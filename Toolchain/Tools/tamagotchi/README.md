# Tamagotchi - Interactive Monitoring Agents

## Overview

The **Tamagotchi** toolkit provides interactive, personality-driven monitoring agents that visualize system state, provide real-time feedback, and create an engaging user experience. These agents act as living indicators of Vera's health, activity, and performance.

## Purpose

Tamagotchi agents enable:
- **Visual system monitoring** through character animations
- **Personality-driven feedback** making errors and warnings engaging
- **Intuitive status display** without reading logs
- **Interactive troubleshooting** through character interactions
- **Emotional engagement** with the AI system

## Concept

Unlike traditional system monitors that show text logs or graphs, Tamagotchi agents are **living characters** that:
- Change appearance based on system state
- React to events with animations
- Provide feedback through emotes and actions
- Develop personality over time
- Create emotional connection with users

## Components

### 1. Tamagotchi Agent (`tamagochi.py`)
Core agent logic and state management.

### 2. Tamagotchi Generator (`tamagochi_gen.py`)
Procedural generation of agent personalities and appearances.

### 3. Tamagotchi UI (`tamagochi.html`)
Web-based visualization and interaction interface.

### 4. Generator UI (`tamagochi_gen.html`)
Interface for creating custom agents.

### 5. Robot Character (`robot.js`)
Robotic tamagotchi implementation with animations.

## Architecture

```
System State
     ↓
State Monitor
     ↓
Tamagotchi Agent
     ├─→ Mood Calculation
     ├─→ Animation Selection
     ├─→ Personality Response
     └─→ Visual Update
          ↓
     Character Display
          ↓
     User Interaction
```

## Character States

Tamagotchi agents display different states based on system conditions:

### Health States

**Healthy** (Green)
- System running smoothly
- No errors or warnings
- All services connected
- Resources within limits

**Happy Animation:**
```
   ___
  (^_^)
  /   \
  |   |
  L___J
```

**Tired** (Yellow)
- High resource usage
- Moderate load
- Some services slow
- Attention recommended

**Tired Animation:**
```
   ___
  (o_o)
  /   \
  |   |
  L___J
```

**Sick** (Orange)
- Errors occurring
- Services failing
- High error rate
- Needs attention

**Sick Animation:**
```
   ___
  (x_x)
  /   \
  |   |
  L___J
```

**Critical** (Red)
- System failure
- Multiple services down
- Critical errors
- Immediate action required

**Critical Animation:**
```
   ___
  (!!)
  /   \
  |   |
  L___J
   Blinking red
```

### Activity States

**Idle**
- No active tasks
- Waiting for input
- Low resource usage

**Thinking**
- LLM processing query
- Planning toolchain
- Reasoning

**Thinking Animation:**
```
   ___
  (? ?)
   ...
  /   \
  |   |
```

**Working**
- Executing toolchain
- Running background tasks
- Processing data

**Working Animation:**
```
   ___
  (O_O)
  /▔▔▔\
  | ⚙ |
  Spinning gears
```

**Sleeping**
- System idle
- Low power mode
- Background cognition only

**Sleeping Animation:**
```
   ___
  (z z)
  /   \
  |   |
  Zzzz...
```

## Usage

### Basic Integration

```python
from Toolchain.Tools.tamagotchi.tamagochi import TamagotchiAgent

# Create agent
agent = TamagotchiAgent(
    name="Vera-chan",
    personality="helpful",
    appearance="robot"
)

# Update based on system state
system_state = {
    "cpu_usage": 45,
    "memory_usage": 60,
    "active_tasks": 3,
    "error_count": 0,
    "services_online": 5,
    "services_offline": 0
}

agent.update_state(system_state)

# Get current mood and animation
mood = agent.get_mood()  # "happy", "tired", "sick", "critical"
animation = agent.get_animation()
message = agent.get_message()

print(f"Mood: {mood}")
print(f"Message: {message}")
# "Vera-chan is feeling great! All systems running smoothly! ^_^"
```

### Web UI Integration

**Start Tamagotchi UI:**
```bash
# Open in browser
open Toolchain/Tools/tamagotchi/tamagochi.html

# Or serve via HTTP
python3 -m http.server 8000
open http://localhost:8000/Toolchain/Tools/tamagotchi/tamagochi.html
```

**Features:**
- Real-time character animation
- Clickable interactions
- Status messages
- System metrics overlay
- Mood history graph

### With Vera Dashboard

```javascript
// In ChatUI
import { TamagotchiWidget } from './tamagotchi/robot.js';

const widget = new TamagotchiWidget({
    container: '#tamagotchi-container',
    name: 'Vera-chan',
    personality: 'helpful',
    updateInterval: 5000  // Update every 5 seconds
});

// Auto-updates based on system state
widget.start();
```

## Personality System

Tamagotchi agents have distinct personalities that affect their responses:

### Personality Types

**Helpful**
- Provides constructive feedback
- Encourages user actions
- Celebrates successes
- Gentle with errors

```
System error occurred
Message: "Oops! Something went wrong. Let me help you fix it! (•‿•)"
```

**Energetic**
- Excited about everything
- Uses exclamation marks
- Enthusiastic animations
- High energy responses

```
Task completed
Message: "YES!! We did it!! That was AMAZING!! ＼(^o^)／"
```

**Calm**
- Measured responses
- Soothing messages
- Minimal animations
- Professional tone

```
High CPU usage
Message: "CPU usage is elevated. Consider closing unused processes."
```

**Playful**
- Makes jokes
- Uses emojis heavily
- Teasing messages
- Fun animations

```
Long-running task
Message: "Still working... I promise I didn't fall asleep! (＾▽＾)"
```

**Serious**
- Direct communication
- Minimal personality
- Focus on metrics
- Professional

```
Critical error
Message: "Critical error detected. Immediate attention required."
```

### Custom Personalities

```python
# Create custom personality
custom_personality = {
    "name": "Sarcastic",
    "responses": {
        "healthy": "Oh wow, everything works. Shocking.",
        "tired": "Feeling a bit worn out. Surprise, surprise.",
        "sick": "Great, now I'm sick. Perfect.",
        "critical": "This is fine. Everything is fine. *sips coffee*"
    },
    "emoji_style": "minimal",
    "animation_speed": "slow",
    "verbosity": "low"
}

agent = TamagotchiAgent(personality=custom_personality)
```

## Event Reactions

Tamagotchi agents react to specific events:

### Success Events

**Task Completion:**
```python
agent.trigger_event("task_complete")
# Animation: Jumping for joy
# Message: "Yay! Task completed successfully! ＼(^o^)／"
# Duration: 3 seconds
```

**Performance Improvement:**
```python
agent.trigger_event("performance_boost")
# Animation: Sparkles effect
# Message: "Wow! Things are running faster now! ✨"
```

### Warning Events

**High Resource Usage:**
```python
agent.trigger_event("resource_warning", {"resource": "CPU", "usage": 85})
# Animation: Wiping sweat
# Message: "Phew! CPU usage is getting high (85%). Maybe take a break? 💦"
```

**Memory Pressure:**
```python
agent.trigger_event("memory_pressure")
# Animation: Head getting heavy
# Message: "Memory is getting full... I feel a bit heavy... (×_×)"
```

### Error Events

**Service Failure:**
```python
agent.trigger_event("service_down", {"service": "Neo4j"})
# Animation: Falling over
# Message: "Oh no! Neo4j is down! I'll help you troubleshoot! (╥_╥)"
# Action: Display troubleshooting guide
```

**Connection Error:**
```python
agent.trigger_event("connection_error", {"target": "API"})
# Animation: Looking confused
# Message: "Can't reach the API... Are we disconnected? (・_・ヾ"
```

### Special Events

**Milestone Reached:**
```python
agent.trigger_event("milestone", {"achievement": "1000_queries"})
# Animation: Celebration dance
# Message: "🎉 1,000 queries processed! We're a great team! 🎉"
```

**Birthday:**
```python
# On Vera installation anniversary
agent.trigger_event("birthday")
# Animation: Party hat appears
# Message: "Happy birthday to us! 🎂 Thanks for a great year!"
```

## Agent Generation

### Procedural Generation

```python
from Toolchain.Tools.tamagotchi.tamagochi_gen import TamagotchiGenerator

generator = TamagotchiGenerator()

# Generate random agent
agent = generator.generate_random(
    personality_bias="helpful",  # Lean toward helpful personality
    appearance_style="cute",     # Cute visual style
    complexity="medium"          # Medium animation complexity
)

print(f"Generated: {agent.name}")
print(f"Personality: {agent.personality}")
print(f"Appearance: {agent.appearance}")
```

### Custom Agent Builder

**Via Web UI:**
```
1. Open tamagochi_gen.html
2. Choose base appearance (robot, creature, abstract)
3. Select personality traits
4. Customize colors and animations
5. Preview in real-time
6. Export configuration
```

**Configuration Export:**
```json
{
  "name": "Custom-chan",
  "personality": {
    "type": "helpful",
    "traits": ["optimistic", "supportive", "patient"],
    "verbosity": "high",
    "emoji_frequency": "medium"
  },
  "appearance": {
    "style": "robot",
    "colors": {
      "primary": "#4A90E2",
      "secondary": "#50E3C2",
      "accent": "#F5A623"
    },
    "animations": {
      "idle": "gentle_bounce",
      "thinking": "spin_head",
      "working": "arm_motion",
      "error": "shake"
    }
  }
}
```

## Interactions

### User Interactions

**Click:**
```javascript
// React to clicks
agent.on('click', () => {
    agent.trigger_event('poked');
    // Animation: Surprised reaction
    // Message: "Hey! That tickles! (＞﹏＜)"
});
```

**Hover:**
```javascript
// Show tooltip on hover
agent.on('hover', () => {
    agent.show_status_tooltip({
        cpu: "45%",
        memory: "60%",
        active_tasks: 3,
        mood: "happy"
    });
});
```

**Drag:**
```javascript
// Allow repositioning
agent.enable_dragging();

// Agent waves when placed in new location
agent.on('drag_end', () => {
    agent.wave();
    agent.say("Nice spot! I like the view! (＾▽＾)");
});
```

### Voice Interaction

```python
# Agent speaks messages
from Speech.speech import VoiceCommunication

voice = VoiceCommunication()

agent.on_message(lambda msg: voice.speak(msg))

# Agent responds to voice
voice_input = voice.listen()
agent.process_voice_command(voice_input)
```

## Integration Examples

### Dashboard Widget

```javascript
// Add to ChatUI dashboard
const tamagotchi = new TamagotchiWidget({
    container: '#status-widget',
    name: 'Vera-chan',
    personality: 'helpful',
    position: 'bottom-right',
    size: 'small'
});

// Auto-update from system metrics
setInterval(() => {
    const metrics = getSystemMetrics();
    tamagotchi.update(metrics);
}, 5000);
```

### CLI Status Indicator

```python
# Terminal-based tamagotchi
from Toolchain.Tools.tamagotchi.tamagochi import ASCIITamagotchi

ascii_agent = ASCIITamagotchi(name="Vera")

# Print in terminal
print(ascii_agent.render())
#    ___
#   (^_^)  Vera is happy!
#   /   \  All systems operational
#   |   |
#   L___J
```

### Notification System

```python
# Use as notification agent
agent = TamagotchiAgent(name="Alert-chan")

# System notifications through agent
def notify(event, message):
    agent.trigger_event(event)
    agent.say(message)

    # OS notification with agent image
    show_notification(
        title=f"{agent.name} - {event}",
        message=message,
        icon=agent.get_current_image()
    )

# Usage
notify("error", "Database connection failed!")
# Agent appears sick, shows error message
```

## State Persistence

```python
# Save agent state
agent.save_state("vera_tamagotchi_state.json")

# Load later
agent = TamagotchiAgent.load_state("vera_tamagotchi_state.json")

# State includes:
# - Personality
# - Mood history
# - Interaction count
# - Preferences learned
# - Milestone achievements
```

## Best Practices

### 1. Meaningful States
Map states to actual system conditions:
```python
# Good
if cpu_usage > 80:
    agent.set_mood("tired")

# Bad
agent.set_mood("happy")  # Always happy regardless of state
```

### 2. Appropriate Personalities
Match personality to context:
```python
# Production system
agent = TamagotchiAgent(personality="calm")

# Development environment
agent = TamagotchiAgent(personality="playful")

# Monitoring dashboard
agent = TamagotchiAgent(personality="serious")
```

### 3. Non-Intrusive
Don't distract from work:
```python
agent = TamagotchiAgent(
    animation_frequency="low",
    message_frequency="alerts_only",
    size="small"
)
```

### 4. Accessibility
Provide alternatives:
```python
# Text fallback for screen readers
agent.enable_accessibility_mode()

# Alternative: Status text
print(agent.get_status_text())
# "System healthy. CPU: 45%, Memory: 60%, Tasks: 3"
```

## Configuration

```json
{
  "tamagotchi": {
    "enabled": true,
    "name": "Vera-chan",
    "personality": "helpful",
    "appearance": "robot",
    "size": "medium",
    "position": "bottom-right",
    "update_interval": 5000,
    "animations": {
      "enabled": true,
      "speed": "normal",
      "complexity": "medium"
    },
    "messages": {
      "enabled": true,
      "frequency": "normal",
      "duration": 5000
    },
    "interactions": {
      "clickable": true,
      "draggable": true,
      "voice_enabled": false
    }
  }
}
```

## Troubleshooting

### Agent Not Updating
```javascript
// Check update interval
console.log(agent.getUpdateInterval());

// Force update
agent.forceUpdate();
```

### Animations Not Working
```javascript
// Check if animations enabled
if (!agent.animationsEnabled) {
    agent.enableAnimations();
}

// Clear animation queue
agent.clearAnimationQueue();
```

### High CPU Usage from Agent
```python
# Reduce animation complexity
agent.set_animation_complexity("low")

# Increase update interval
agent.set_update_interval(10000)  # 10 seconds

# Disable in background
agent.pause_when_hidden()
```

## Related Documentation

- [ChatUI](../../../ChatUI/) - Dashboard integration
- [Background Cognition](../../../BackgroundCognition/) - System state monitoring
- [Speech](../../../Speech/) - Voice integration

## Contributing

To create new tamagotchi characters:
1. Design character sprites/animations
2. Define personality responses
3. Map states to system conditions
4. Implement in `robot.js` or create new file
5. Add to generator options

---

**Related Components:**
- [ChatUI](../../../ChatUI/) - Visual interface
- [Toolchain](../../) - System status source
- [Memory](../../../Memory/) - State persistence

**Note:** Tamagotchi agents are optional. Disable if you prefer traditional monitoring.
