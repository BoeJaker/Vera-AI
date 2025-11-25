"""
Vera Infrastructure Orchestration - Configuration
==================================================

Configuration templates for different deployment scenarios.
"""

import os
from typing import Dict, Any

# ============================================================================
# BASE CONFIGURATION
# ============================================================================

BASE_CONFIG = {
    # Task worker configuration
    "worker_pools": {
        "llm": 2,
        "whisper": 1,
        "tool": 4,
        "ml_model": 1,
        "background": 2,
        "general": 2
    },
    
    # CPU throttling
    "cpu_threshold": 85.0,  # Percentage
    
    # Resource limits
    "auto_scale": True,
    "max_resources": 10,
    
    # Redis (optional)
    "redis_url": None,  # e.g., "redis://localhost:6379/0"
}


# ============================================================================
# DOCKER CONFIGURATION
# ============================================================================

DOCKER_CONFIG = {
    "enabled": True,
    "docker_url": "unix://var/run/docker.sock",  # Local Docker daemon
    # "docker_url": "tcp://192.168.1.100:2375",  # Remote Docker daemon
    
    # Default images for task types
    "default_images": {
        "llm": "python:3.11-slim",
        "whisper": "python:3.11-slim",
        "tool": "python:3.11-slim",
        "ml_model": "pytorch/pytorch:latest",
        "background": "python:3.11-slim",
        "general": "python:3.11-slim"
    },
    
    # Resource specs for auto-provisioning
    "default_specs": {
        "llm": {
            "cpu_cores": 2.0,
            "memory_mb": 2048,
            "disk_gb": 10,
            "gpu_count": 0
        },
        "whisper": {
            "cpu_cores": 2.0,
            "memory_mb": 2048,
            "disk_gb": 10,
            "gpu_count": 0
        },
        "ml_model": {
            "cpu_cores": 4.0,
            "memory_mb": 8192,
            "disk_gb": 20,
            "gpu_count": 1,
            "gpu_memory_mb": 8192
        },
        "general": {
            "cpu_cores": 1.0,
            "memory_mb": 512,
            "disk_gb": 5,
            "gpu_count": 0
        }
    },
    
    # Network configuration
    "network_mode": "bridge",
    
    # Volume mounts (shared across containers)
    "volumes": {
        # "/host/path": {"bind": "/container/path", "mode": "rw"}
    },
    
    # Environment variables (global)
    "environment": {
        "PYTHONUNBUFFERED": "1",
        "TZ": "UTC"
    },
    
    # Cleanup policy
    "cleanup_idle_seconds": 300,  # 5 minutes
    "cleanup_interval_seconds": 60  # Check every minute
}


# ============================================================================
# PROXMOX CONFIGURATION
# ============================================================================

PROXMOX_CONFIG = {
    "enabled": False,  # Set to True when using Proxmox
    
    # Connection details
    "host": "proxmox.example.com",
    "port": 8006,
    "verify_ssl": False,
    
    # Authentication - METHOD 1: API Token (recommended)
    "user": "root@pam",
    "token_name": "orchestrator",
    "token_value": "your-token-value-here",
    
    # Authentication - METHOD 2: Password (alternative)
    # "user": "root@pam",
    # "password": "your-password-here",
    
    # Default node for provisioning
    "default_node": "pve",
    
    # Storage configuration
    "storage": "local-lvm",
    "storage_content": ["images", "rootdir"],
    
    # Network configuration
    "network_bridge": "vmbr0",
    
    # VM/LXC templates
    "templates": {
        "ubuntu_vm": {
            "type": "vm",
            "template_id": 9000,
            "ostype": "l26"
        },
        "ubuntu_lxc": {
            "type": "lxc",
            "template": "local:vztmpl/ubuntu-22.04-standard_22.04-1_amd64.tar.zst"
        }
    },
    
    # Resource specs for auto-provisioning
    "default_specs": {
        "llm": {
            "cpu_cores": 4,
            "memory_mb": 4096,
            "disk_gb": 20,
            "type": "vm"  # or "lxc"
        },
        "ml_model": {
            "cpu_cores": 8,
            "memory_mb": 16384,
            "disk_gb": 50,
            "type": "vm",
            "gpu_count": 1
        },
        "general": {
            "cpu_cores": 2,
            "memory_mb": 2048,
            "disk_gb": 10,
            "type": "lxc"
        }
    },
    
    # Starting VMID for auto-allocation
    "start_vmid": 100,
    
    # Cleanup policy
    "cleanup_idle_seconds": 600,  # 10 minutes
}


# ============================================================================
# DEPLOYMENT SCENARIOS
# ============================================================================

# Scenario 1: Local Development (Docker only)
LOCAL_DEV_CONFIG = {
    **BASE_CONFIG,
    "max_resources": 3,
    "docker": {
        **DOCKER_CONFIG,
        "enabled": True,
    },
    "proxmox": {
        **PROXMOX_CONFIG,
        "enabled": False,
    }
}

# Scenario 2: Production (Docker + Proxmox)
PRODUCTION_CONFIG = {
    **BASE_CONFIG,
    "max_resources": 50,
    "redis_url": "redis://redis-server:6379/0",
    "docker": {
        **DOCKER_CONFIG,
        "enabled": True,
        "docker_url": "tcp://docker-host:2375",
    },
    "proxmox": {
        **PROXMOX_CONFIG,
        "enabled": True,
        "host": os.getenv("PROXMOX_HOST", "proxmox.internal"),
        "user": os.getenv("PROXMOX_USER", "orchestrator@pam"),
        "token_name": os.getenv("PROXMOX_TOKEN_NAME"),
        "token_value": os.getenv("PROXMOX_TOKEN_VALUE"),
    }
}

# Scenario 3: GPU Cluster (Multiple Docker hosts with GPUs)
GPU_CLUSTER_CONFIG = {
    **BASE_CONFIG,
    "max_resources": 20,
    "docker": {
        **DOCKER_CONFIG,
        "enabled": True,
        "default_specs": {
            **DOCKER_CONFIG["default_specs"],
            "llm": {
                "cpu_cores": 4.0,
                "memory_mb": 8192,
                "disk_gb": 20,
                "gpu_count": 1,
                "gpu_memory_mb": 24576  # 24GB VRAM
            }
        }
    },
    "proxmox": {
        **PROXMOX_CONFIG,
        "enabled": False,
    }
}

# Scenario 4: Hybrid (Docker for quick tasks, Proxmox for heavy compute)
HYBRID_CONFIG = {
    **BASE_CONFIG,
    "max_resources": 30,
    "redis_url": "redis://localhost:6379/0",
    "docker": {
        **DOCKER_CONFIG,
        "enabled": True,
        "default_specs": {
            "general": {"cpu_cores": 1.0, "memory_mb": 512, "disk_gb": 5},
            "tool": {"cpu_cores": 1.0, "memory_mb": 1024, "disk_gb": 5},
        }
    },
    "proxmox": {
        **PROXMOX_CONFIG,
        "enabled": True,
        "default_specs": {
            "llm": {"cpu_cores": 8, "memory_mb": 16384, "disk_gb": 50, "type": "vm"},
            "ml_model": {"cpu_cores": 16, "memory_mb": 32768, "disk_gb": 100, "type": "vm", "gpu_count": 2},
        }
    }
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_config(scenario: str = "local_dev") -> Dict[str, Any]:
    """
    Get configuration for a specific scenario.
    
    Args:
        scenario: One of "local_dev", "production", "gpu_cluster", "hybrid"
    
    Returns:
        Configuration dictionary
    """
    configs = {
        "local_dev": LOCAL_DEV_CONFIG,
        "production": PRODUCTION_CONFIG,
        "gpu_cluster": GPU_CLUSTER_CONFIG,
        "hybrid": HYBRID_CONFIG,
    }
    
    return configs.get(scenario, LOCAL_DEV_CONFIG)


def load_config_from_env() -> Dict[str, Any]:
    """
    Load configuration from environment variables.
    Useful for containerized deployments.
    """
    return {
        "worker_pools": {
            "llm": int(os.getenv("WORKERS_LLM", "2")),
            "whisper": int(os.getenv("WORKERS_WHISPER", "1")),
            "tool": int(os.getenv("WORKERS_TOOL", "4")),
            "ml_model": int(os.getenv("WORKERS_ML", "1")),
            "background": int(os.getenv("WORKERS_BACKGROUND", "2")),
            "general": int(os.getenv("WORKERS_GENERAL", "2")),
        },
        "cpu_threshold": float(os.getenv("CPU_THRESHOLD", "85.0")),
        "auto_scale": os.getenv("AUTO_SCALE", "true").lower() == "true",
        "max_resources": int(os.getenv("MAX_RESOURCES", "10")),
        "redis_url": os.getenv("REDIS_URL"),
        "docker": {
            "enabled": os.getenv("DOCKER_ENABLED", "true").lower() == "true",
            "docker_url": os.getenv("DOCKER_URL", "unix://var/run/docker.sock"),
        },
        "proxmox": {
            "enabled": os.getenv("PROXMOX_ENABLED", "false").lower() == "true",
            "host": os.getenv("PROXMOX_HOST"),
            "user": os.getenv("PROXMOX_USER"),
            "token_name": os.getenv("PROXMOX_TOKEN_NAME"),
            "token_value": os.getenv("PROXMOX_TOKEN_VALUE"),
            "password": os.getenv("PROXMOX_PASSWORD"),
        }
    }


def validate_config(config: Dict[str, Any]) -> bool:
    """
    Validate configuration.
    
    Returns:
        True if valid, raises ValueError if invalid
    """
    # Check required fields
    if "worker_pools" not in config:
        raise ValueError("Missing 'worker_pools' in configuration")
    
    # Validate Docker config
    if config.get("docker", {}).get("enabled"):
        if not config["docker"].get("docker_url"):
            raise ValueError("Docker enabled but 'docker_url' not specified")
    
    # Validate Proxmox config
    if config.get("proxmox", {}).get("enabled"):
        proxmox = config["proxmox"]
        if not proxmox.get("host"):
            raise ValueError("Proxmox enabled but 'host' not specified")
        if not proxmox.get("user"):
            raise ValueError("Proxmox enabled but 'user' not specified")
        
        # Check authentication
        has_token = proxmox.get("token_name") and proxmox.get("token_value")
        has_password = proxmox.get("password")
        
        if not (has_token or has_password):
            raise ValueError("Proxmox enabled but no authentication method specified")
    
    return True


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    import json
    
    print("Available configurations:")
    print("=" * 70)
    
    scenarios = ["local_dev", "production", "gpu_cluster", "hybrid"]
    
    for scenario in scenarios:
        print(f"\n{scenario.upper().replace('_', ' ')}:")
        config = get_config(scenario)
        print(json.dumps(config, indent=2, default=str))
        
        try:
            validate_config(config)
            print("✓ Configuration valid")
        except ValueError as e:
            print(f"✗ Configuration invalid: {e}")