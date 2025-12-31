#!/usr/bin/env bash
set -euo pipefail

# =========================
# Configuration
# =========================

RAMDISK_SIZE="24G"                   # Adjust based on model size + headroom
OLLAMA_DIR="$HOME/.ollama"
MODEL_DIR="$OLLAMA_DIR/models"
RAMDISK_BASE="/mnt/ollama-ramdisk"
RAMDISK_MODELS="$RAMDISK_BASE/models"
BACKUP_SUFFIX=".disk-backup"

# =========================
# Sanity checks
# =========================

if ! command -v ollama >/dev/null 2>&1; then
    echo "ERROR: ollama not found in PATH"
    exit 1
fi

if mountpoint -q "$MODEL_DIR"; then
    echo "Ollama models already mounted from RAM disk"
    exit 0
fi

# =========================
# Prepare directories
# =========================

echo "Creating RAM disk mount point..."
sudo mkdir -p "$RAMDISK_BASE"

echo "Mounting tmpfs..."
sudo mount -t tmpfs -o size="$RAMDISK_SIZE",mode=0755 tmpfs "$RAMDISK_BASE"

mkdir -p "$RAMDISK_MODELS"

# =========================
# Copy models into RAM
# =========================

if [ -d "$MODEL_DIR" ]; then
    echo "Copying Ollama models into RAM disk..."
    rsync -a --info=progress2 "$MODEL_DIR/" "$RAMDISK_MODELS/"
else
    echo "WARNING: No existing Ollama model directory found"
fi

# =========================
# Backup original directory
# =========================

if [ -d "$MODEL_DIR" ] && [ ! -d "${MODEL_DIR}${BACKUP_SUFFIX}" ]; then
    echo "Backing up original model directory..."
    mv "$MODEL_DIR" "${MODEL_DIR}${BACKUP_SUFFIX}"
fi

mkdir -p "$MODEL_DIR"

# =========================
# Bind mount RAM disk
# =========================

echo "Bind-mounting RAM disk over Ollama model path..."
sudo mount --bind "$RAMDISK_MODELS" "$MODEL_DIR"

echo "Ollama models are now running from RAM disk."
echo "Reboot will clear the RAM disk; rerun this script after boot."
