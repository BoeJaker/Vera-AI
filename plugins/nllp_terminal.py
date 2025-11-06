"""

Parses terminal output to extract entities and table data

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot

import re
import spacy
from transformers import pipeline

class nlpTerminal(PluginBase):
    # Load spaCy model for NER (you might need to download it via: python -m spacy download en_core_web_sm)
    nlp = spacy.load("en_core_web_sm")

    # Load a summarization model (make sure to install transformers and torch)
    summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
    
    @staticmethod
    def class_types():
        return( [
            "command",
            ])
    
    def execute(self, terminal_output, args):
        info = extract_info_from_terminal_output(terminal_output)
        print("Extracted Information:")
        print("Entities:", info["Entities"])
        print("Table Data:", info["TableData"])
        print("Summary:", info["Summary"])
        return(info)



    def extract_info_from_terminal_output(output_text):
        """
        Extracts key information from terminal command output using NLP.

        Parameters:
            output_text (str): The raw text output from a terminal command.

        Returns:
            dict: A dictionary containing named entities, extracted table data (if detected),
                and a text summary.
        """
        # Preprocessing: Remove extra header lines if necessary (example for table-like outputs)
        # Here we assume that the first line could be a header, so we split it off.
        lines = output_text.strip().splitlines()
        if len(lines) > 1 and re.search(r"^(USER|PID|COMMAND)", lines[0]):
            header = lines[0]
            body = "\n".join(lines[1:])
        else:
            header = ""
            body = output_text

        # Use spaCy to perform Named Entity Recognition (NER)
        doc = nlp(body)
        entities = [(ent.text, ent.label_) for ent in doc.ents]

        # Optional: Custom extraction for table-like data
        table_data = []
        # Example: If output resembles a table with columns separated by spaces
        # You might want to parse each row into a dict if you know the header structure.
        if header:
            # Tokenize header to know column names
            columns = re.split(r"\s+", header.strip())
            for line in lines[1:]:
                # Only process lines that seem to be data rows (basic check)
                if re.search(r"\S", line):
                    # Split by whitespace
                    values = re.split(r"\s+", line.strip())
                    if len(values) >= len(columns):
                        row_dict = dict(zip(columns, values))
                        table_data.append(row_dict)

        # Use a summarization model if the text is long enough
        # (Transformer summarization typically requires a certain length of text)
        if len(body.split()) > 50:
            summary = summarizer(body, max_length=100, min_length=30, do_sample=False)[0]['summary_text']
        else:
            summary = body

        return {
            "Entities": entities,
            "TableData": table_data,
            "Summary": summary
        }

if __name__ == '__main__':
    nlpp = nlpTerminal()

    # Example Terminal Output (simulate output from a command like `ps aux`)
    terminal_output = """
    USER       PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
    root         1  0.0  0.1  22520  4100 ?        Ss   08:43   0:01 /sbin/init splash
    daemon       2  0.0  0.0      0     0 ?        S    08:43   0:00 [kthreadd]
    root      999  0.2  0.5 349564 21080 ?        Ssl  08:45   0:03 /usr/lib/snapd/snapd
    """

    # Extract key information from the terminal output
    info = nlpp.extract_info_from_terminal_output(terminal_output)
    print("Extracted Information:")
    print("Entities:", info["Entities"])
    print("Table Data:", info["TableData"])
    print("Summary:", info["Summary"])

