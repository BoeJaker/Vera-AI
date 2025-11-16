# Tamagochi - Interactive Agent Mascots

## Overview

Interactive animated mascots that provide visual feedback and personality to Vera's interface.

## Components

| File | Description |
|------|-------------|
| `tamagochi_robot.js` | Robot-themed interactive mascot |
| `tamagochi_duck.js` | Duck-themed interactive mascot |

## Features

- **Animated characters** with personality
- **State-based animations** (idle, thinking, speaking, error)
- **User interaction** (clicks, hovers)
- **Visual feedback** for system status
- **Customizable appearances**

## Usage

```javascript
// Initialize mascot
const mascot = new TamagochiRobot({
    container: 'mascot-container',
    size: 'medium'
});

// Trigger animations based on system state
mascot.setState('thinking');  // Shows thinking animation
mascot.setState('speaking');  // Lip sync during TTS
mascot.setState('idle');      // Default state
```

## States

- **idle** - Default resting state
- **thinking** - During LLM processing
- **speaking** - During voice output
- **listening** - During voice input
- **error** - On system errors
- **celebrating** - On task completion

## Customization

Mascots can be customized with:
- Different color schemes
- Custom animations
- Size variations
- Interaction behaviors

---

**Related:** [ChatUI](../README.md), [Speech Integration](../../Speech/)
