# Activate the environment
source ../bin/activate

# Start the Vera API
python3 -m Vera.ChatUI.api.vera_api

# Build an agent
python3 -m Vera.Ollama.Agents.agent_manager build --agent tool-agent

# Sync an agent to a remote host
python3 /home/boejaker/langchain/app/Vera/Ollama/Agents/sync_agents.py --sync-all --vera-config ./Vera/Configuration/vera_config.yaml --directory ./Vera/Ollama/Agents/agents/triage-agent

# Pull a model to a host using the sync tool
.Ollama/Agents/agents/sync_agents.py --pull gemma2:latest --vera-config vera_config.yaml --sync-all -v

# Pull a model to a host
curl -X POST http://192.168.0.250:11435/api/pull   -H "Content-Type: application/json"   -d '{
    "name": "mistral:7b"
}'