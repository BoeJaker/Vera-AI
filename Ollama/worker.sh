#NVIDIA Setup
apt install lshw || apt install lspci
OLLAMA_GPU=1

#Ollama Setup
curl -fsSL https://ollama.com/install.sh | sh