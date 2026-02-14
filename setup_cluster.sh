#!/usr/bin/env bash

# Setup shared ZFS storage for Ollama models across multiple LXC containers.

set -euo pipefail

############################################
# USER CONFIGURATION
############################################


MANAGER_CTID=126
OLLAMA_CONTAINERS=(129 130 131 132)
CONFIG_PATH="./Vera/Configuration/vera_config.yaml"

MODEL_DATASET="${ZFS_POOL}/${ZFS_DATASET}"
MODEL_PATH="/${ZFS_POOL}/${ZFS_DATASET}"
TMP_DIR="/tmp/ollama_migration"

mkdir -p "$TMP_DIR"

############################################
# INTERACTIVE ZFS STORAGE SELECTION
############################################

echo "================================================="
echo " ZFS STORAGE SETUP"
echo "================================================="

echo
echo "Existing ZFS pools:"
zpool list -H -o name || true
echo

read -p "Use an existing pool? (y/n): " USE_EXISTING

if [[ "$USE_EXISTING" =~ ^[Yy]$ ]]; then
    echo
    echo "Select a pool:"
    mapfile -t POOLS < <(zpool list -H -o name)

    select pool in "${POOLS[@]}"; do
        if [[ -n "$pool" ]]; then
            ZFS_POOL="$pool"
            ZFS_DISK=""
            break
        fi
    done

else
    echo
    echo "Available disks (by-id):"
    mapfile -t DISKS < <(ls /dev/disk/by-id/ | grep -v part)

    select disk in "${DISKS[@]}"; do
        if [[ -n "$disk" ]]; then
            ZFS_DISK="/dev/disk/by-id/$disk"
            break
        fi
    done

    read -p "Enter name for new ZFS pool: " ZFS_POOL

    echo
    echo "WARNING: This will ERASE the disk!"
    read -p "Type YES to continue: " CONFIRM
    [[ "$CONFIRM" == "YES" ]] || exit 1
fi

echo
read -p "Enter dataset name for Ollama models [models]: " DATASET_INPUT
ZFS_DATASET=${DATASET_INPUT:-models}

echo
echo "Selected configuration:"
echo "Pool:     $ZFS_POOL"
echo "Disk:     ${ZFS_DISK:-'(existing pool)'}"
echo "Dataset:  $ZFS_DATASET"
echo

read -p "Proceed? (y/n): " CONFIRM
[[ "$CONFIRM" =~ ^[Yy]$ ]] || exit 1


echo "================================================="
echo " Vera Ollama Shared Model Bootstrap"
echo "================================================="

############################################
echo "STEP 1 — ZFS POOL"
############################################

if ! zpool list | grep -q "^${ZFS_POOL} "; then
    if [ -z "$ZFS_DISK" ]; then
        echo "ERROR: Pool ${ZFS_POOL} missing and no disk specified"
        exit 1
    fi
    echo "Creating ZFS pool ${ZFS_POOL} on $ZFS_DISK"
    zpool create -f "$ZFS_POOL" "$ZFS_DISK"
else
    echo "Pool ${ZFS_POOL} already exists"
fi

############################################
echo "STEP 2 — ZFS DATASET"
############################################

if ! zfs list "$MODEL_DATASET" >/dev/null 2>&1; then
    echo "Creating dataset ${MODEL_DATASET}"
    zfs create "$MODEL_DATASET"
else
    echo "Dataset exists"
fi

echo "Applying ZFS tuning"
zfs set compression=lz4 "$MODEL_DATASET"
zfs set atime=off "$MODEL_DATASET"
zfs set recordsize=1M "$MODEL_DATASET"
zfs set xattr=sa "$MODEL_DATASET"
zfs set mountpoint="$MODEL_PATH" "$MODEL_DATASET"

mkdir -p "$MODEL_PATH"
chmod 777 "$MODEL_PATH"

echo "Dataset ready at $MODEL_PATH"

############################################
echo "STEP 3 — MIGRATE EXISTING MODELS"
############################################

for CTID in "${OLLAMA_CONTAINERS[@]}"; do
    echo "Checking CT $CTID"

    if pct exec "$CTID" -- test -d /root/.ollama/models/blobs 2>/dev/null; then
        echo "  Found models in CT $CTID"

        TARFILE="$TMP_DIR/models_${CTID}.tar"
        pct exec "$CTID" -- tar -cf /tmp/models.tar -C /root/.ollama models
        pct pull "$CTID" /tmp/models.tar "$TARFILE"

        mkdir -p "$TMP_DIR/extract_$CTID"
        tar -xf "$TARFILE" -C "$TMP_DIR/extract_$CTID"

        rsync -avh --ignore-existing \
            "$TMP_DIR/extract_$CTID/models/" \
            "$MODEL_PATH/"

        echo "  Migration from CT $CTID complete"
    else
        echo "  No models found"
    fi
done

############################################
echo "STEP 4 — MOUNT SHARED STORAGE INTO LXCs"
############################################

for CTID in "${OLLAMA_CONTAINERS[@]}"; do
    CONF="/etc/pve/lxc/${CTID}.conf"

    if ! grep -q "$MODEL_PATH" "$CONF"; then
        echo "Adding mount to CT $CTID"
        echo "mp0: $MODEL_PATH,mp=/root/.ollama/models" >> "$CONF"
    else
        echo "Mount already present for CT $CTID"
    fi

    pct restart "$CTID"
done

############################################
echo "STEP 5 — EXTRACT MODELS FROM VERA CONFIG"
############################################

cat << 'PY' > /tmp/extract_models.py
import yaml, sys
cfg=yaml.safe_load(open(sys.argv[1]))
models=set()

for k,v in cfg["models"].items():
    if isinstance(v,str): models.add(v)

for m in cfg["ollama"]["gpu_only_models"]: models.add(m)
for m in cfg["ollama"]["gpu_preferred_models"]: models.add(m)

for entry in cfg["counsel"]["instances"]:
    if ":" in entry: models.add(entry.split(":",1)[1])

for v in cfg["agents"]["default_agents"].values():
    if ":" in v: models.add(v)

for m in sorted(models):
    print(m)
PY

MODEL_LIST=$(python3 /tmp/extract_models.py "$CONFIG_PATH")

echo "Models required:"
echo "$MODEL_LIST"

############################################
echo "STEP 6 — PULL MISSING MODELS"
############################################

for MODEL in $MODEL_LIST; do
    echo "Ensuring $MODEL exists..."
    pct exec $MANAGER_CTID -- ollama pull "$MODEL"
done

############################################
echo "================================================="
echo " COMPLETE — Shared Ollama model storage ready"
echo "================================================="
