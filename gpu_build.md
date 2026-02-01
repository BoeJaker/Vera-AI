
```
echo "deb http://download.proxmox.com/debian/pve bookworm pve-no-subscription" > /etc/apt/sources.list.d/pve-no-subscription.list

apt install pve-headers-$(uname -r) build-essential dkms -y

echo "blacklist nouveau" > /etc/modprobe.d/blacklist-nouveau.conf
echo "blacklist nvidiafb" > /etc/modprobe.d/blacklist-nvidia.conf
update-initramfs -u

reboot

```

```
wget https://us.download.nvidia.com/XFree86/Linux-x86_64/580.126.09/NVIDIA-Linux-x86_64-580.126.09.run

chmod +x ./NVIDIA-Linux-x86_64-580.126.09.run

./NVIDIA-Linux-x86_64-580.126.09.run

```

```
root@corp:~# lspci -nnk -s 84:00.0
84:00.0 3D controller [0302]: NVIDIA Corporation Device [10de:1df4] (rev a1)
        Subsystem: NVIDIA Corporation Device [10de:1365]
        Kernel driver in use: nvidia
        Kernel modules: nvidiafb, nouveau, nvidia_drm, nvidia
        
~# dkms status
nvidia/580.126.09, 6.8.4-2-pve, x86_64: installed

~# nvidia-smi
Sat Jan 31 19:13:02 2026       
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 580.126.09             Driver Version: 580.126.09     CUDA Version: 13.0     |
+-----------------------------------------+------------------------+----------------------+
| GPU  Name                 Persistence-M | Bus-Id          Disp.A | Volatile Uncorr. ECC |
| Fan  Temp   Perf          Pwr:Usage/Cap |           Memory-Usage | GPU-Util  Compute M. |
|                                         |                        |               MIG M. |
|=========================================+========================+======================|
|   0  Tesla V100-PCIE-12GB           Off |   00000000:84:00.0 Off |                    0 |
| N/A   47C    P0             38W /  250W |       0MiB /  12288MiB |      3%      Default |
|                                         |                        |                  N/A |
+-----------------------------------------+------------------------+----------------------+

+-----------------------------------------------------------------------------------------+
| Processes:                                                                              |
|  GPU   GI   CI              PID   Type   Process name                        GPU Memory |
|        ID   ID                                                               Usage      |
|=========================================================================================|
|  No running processes found                                                             |
+-----------------------------------------------------------------------------------------+
```

```
apt remove --purge '^nvidia-.*' -y
apt autoremove -y
```

```
lxc.cgroup2.devices.allow: c 195:* rwm
lxc.cgroup2.devices.allow: c 511:* rwm
lxc.mount.entry: /usr/bin/nvidia-smi usr/bin/nvidia-smi none bind,ro,create=file
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1 none bind,r>
#lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libnvidia-ml.so usr/lib/x86_64-linux-gnu/libnvidia-ml.so none bind,ro,cr>
lxc.mount.entry: /usr/lib/x86_64-linux-gnu/libcuda.so.1 usr/lib/x86_64-linux-gnu/libcuda.so.1 none bind,ro,create=f>
lxc.mount.entry: /dev/nvidia0 dev/nvidia0 none bind,optional,create=file
lxc.mount.entry: /dev/nvidiactl dev/nvidiactl none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm dev/nvidia-uvm none bind,optional,create=file
lxc.mount.entry: /dev/nvidia-uvm-tools dev/nvidia-uvm-tools none bind,optional,create=file
lxc.apparmor.profile: unconfined
lxc.cap.drop:
```