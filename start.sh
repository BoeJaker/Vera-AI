cd /home/boejaker/langchain

source ./bin/activate

cd ./app/Vera

# CLI Vera
python3 vera.py

# Web Vera
streamlit run ./ui.py 

# Proactive Backround Thoughts (PBT) Vera
streamlit run ./pbt_ui.py

# Memory Dashboard
streamlit run ./Memory/dashboard/dashboard.py