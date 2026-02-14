for CTID in 102 103 104; do
  sed -i 's|mp=/root/.ollama/models|mp=/root/.ollama/models,ro=1|' /etc/pve/lxc/${CTID}.conf
  pct restart $CTID
done
