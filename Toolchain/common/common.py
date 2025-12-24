"""
Common Functions

- bcolors           - Terminal print color scheme
- convert_datetime  - Json datetime converter
- log               - An enhanced print function that also logs to a file 
                      and colors output text based on exit conditions
- plot              - Plots a networkx graph

"""

import datetime
import logging
import matplotlib.pyplot as plt
import networkx as nx
import json
import inspect

log_level = 3 # info - 1, , error - 2, ok - 3, none - 0
verbosity = 3
DEBUG_MODE = True

#Logging file setup - location & format
logging.basicConfig(filename="command_log.txt", level=logging.INFO, format="%(asctime)s - %(message)s")

class bcolors:
    """Terminal print color scheme"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

# Convert datetime objects to string
def convert_datetime(obj):
    """Json datetime converter"""
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    raise TypeError("Type not serializable")


def log(text,level, socketio=None):
    # Get the caller's frame
    caller_frame = inspect.currentframe().f_back
    
    # Get the caller's function name
    caller_function_name = caller_frame.f_code.co_name
    
    # Get the caller's class name (if it exists)
    caller_class = None
    if 'self' in caller_frame.f_locals:
        caller_class = caller_frame.f_locals['self'].__class__.__name__
    """ An enhanced print function that also logs to a file """
    if(level == "info"):
        if (log_level >= 1): logging.info(f"{caller_class}.{caller_function_name} - {str(text)}")
        if (verbosity >= 1): print(f"{bcolors.OKBLUE}{caller_class}.{caller_function_name} - {text}{bcolors.ENDC}")
    
    if(level == "error"):
        if (log_level >= 2):logging.error(f"{caller_class}.{caller_function_name} - {str(text)}", exc_info=True)
        if (verbosity >= 2):print(f"{bcolors.FAIL}{caller_class}.{caller_function_name} - {text}{bcolors.ENDC}")

    if(level == "ok"):
        if (log_level >= 3): logging.info(f"{caller_class}.{caller_function_name} - {str(text)}")
        if (verbosity >= 3): print(f"{bcolors.OKGREEN}{caller_class}.{caller_function_name} - {text}{bcolors.ENDC}")
    
    if socketio:
        socketio.emit("update_status", {"task": json.dumps(text)})
        
def debug_print(message):
    if not DEBUG_MODE:
        return

    # Get caller's frame
    caller_frame = inspect.currentframe().f_back
    caller_function = caller_frame.f_code.co_name
    caller_class = None
    instance_info = None

    # Identify class and instance data
    if 'self' in caller_frame.f_locals:
        instance = caller_frame.f_locals['self']
        caller_class = instance.__class__.__name__
        instance_info = pprint.pformat(instance.__dict__)  # Pretty format instance details

    # Get file and line number for traceability
    file_name = caller_frame.f_code.co_filename
    line_number = caller_frame.f_lineno

    # Format output
    print(f"\n{'='*40}")
    print(f"DEBUG INFO")
    print(f"{'-'*40}")
    print(f"File: {file_name}")
    print(f"Line: {line_number}")
    if caller_class:
        print(f"Class: {caller_class}")
    print(f"Function: {caller_function}")
    print(f"Message: {message}")
    if instance_info:
        print(f"Instance Data: {instance_info}")
    print(f"{'='*40}\n")

def plot(G):
    """ Plots a networkx graph """
    # Try to use a planar layout (if graph is planar)
    if nx.check_planarity(G)[0]:
        pos = nx.planar_layout(G)
    else:
        pos = nx.spring_layout(G)  # Fallback to spring layout

    # Draw the graph
    nx.draw(G, pos, with_labels=True, node_color="lightblue", edge_color="gray", node_size=500)

    plt.show()
