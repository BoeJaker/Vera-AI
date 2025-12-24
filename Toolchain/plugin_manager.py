"""
Loads plugins from the plugins directory and provides methods to run them.

Dynamically reloads plugins if they change.
- PluginBase
    - plugin_preprocess
    - plugin_postprocess
- pluginManager
    - load_plugins
    - add_functions_from_plugins
    - run_all_transforms
    - get_plugin_names
    - get_class_plugin_names
    - run_all_plugins_on_node
    - set_ssh_host
    - connect_ssh
    - load_plugin
    - start_watcher
"""

import importlib
import os
import pprint
import glob
import inspect
import paramiko
import Vera.Toolchain.common.common as common
import json
import inspect
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import sys

plugins_directory='./Vera/Toolchain/GraphPlugins'

class PluginBase:
    """ Base class for all plugins """
    def __init__(self, graph_manager, socketio, args):
        try:
            self.target = None # Target node
            self.graph_manager = graph_manager
            self.socketio = socketio
            self.proxies = args.proxies # Proxies configuration
            self.args = args # Configuration and Command Line arguments
            self.output = None # Plugin output
        except Exception as e:
            common.log(f"Plugin Error:{e}","error",socketio=self.socketio)
    
    @staticmethod
    def class_types():
        """
        Returns compatible node class types
        """
        raise NotImplementedError("Subclasses must implement class_types()")
    
    @staticmethod
    def description():
        """
        Returns a human friendly description of the plugins function
        """
        raise NotImplementedError("Subclasses must implement description()")
    
    @staticmethod
    def output_type(self):
        """
        Returns the class of generated metadata
        """
        return(self.__class__.__name__)  
      
    @staticmethod
    def metadata_type(self):
        """
        Returns the class of generated metadata
        """
        return(self.__class__.__name__) 
    
    @staticmethod
    def output_class():
        """
        Stores the class of output data
        """
        raise NotImplementedError("Subclasses must implement output_class()")

    def unit_test(self):
        """
        Performs a set of validations on the plugin. Returns true if no errors found. Else false
        """
        raise NotImplementedError("Subclasses must implement unit_test()")

    def execute(self):
        raise NotImplementedError("Subclasses must implement execute()")

    def plugin_preprocess(func):
        def wrapper(*args):
            # Ensure at least one argument is provided
            if len(args) == 0:
                raise TypeError(f"{func.__name__}() missing required positional argument")
            else:
                arg1 = args[0]

            return func(arg1)

        return wrapper

    def plugin_postprocess(self, func):
        def inner(*args, **kwargs):
            raw = args[0]
            processed = args[1]
            graph = args[2]
            self.graph_manager.database.save_graph(graph) # save graph
            self.graph_manager.database.save_metadata(raw, processed) # Save metadata
            self.graph_manager.socketio.emit(graph) # Emit Graph
            self.graph_manager.socketio.emit(processed) # Emit metadata
            return()
        return(inner)

# TODO Convert actions table so addins are assinged available classes rather than classes being assigned addins, reduces the complexity of the dataset
class PluginManager:
    """Loads plugins from the plugins directory and provides methods to run them."""
    def __init__(self, graph_manager, socketio, args):
        self.socketio = socketio
        self.graph_manager = graph_manager
        self.args = args
        self.plugins = {} # Stores plugins as callable objects
        self.plugin_functions = {} # Stores plugin functions as callable objects
        self.actions_queue = [{"id":0,None:None}]
        # actios refer to plugins defined in the plugins directory and called from the actions table
        # they are categorised by applicable node class_type
        # Initialize empty actions dictionary
        self.actions = {}
        
       
        
    def start(self):
        """Start the plugin manager."""
        self.load_plugins(plugins_directory)
        self.start_watcher() # Watches the plugins directory for changes

        #Extract class_types
        self.ct = [[k, v.class_types()] for k, v in self.plugins.items() ]
        # pprint.pprint(f"plugin classes:{self.ct}")
        # Process the plugin_classes list into actions
        for plugin, categories in self.ct:
            # print(plugin, categories)
            action_id = plugin.lower()  # Convert plugin name to lowercase for ID
            action_name = plugin  # Keep original name as action name
            
            for category in categories:
                if category not in self.actions:
                    self.actions[category] = []
                self.actions[category].append({"id": action_id, "name": action_name})
        # pprint.pprint(self.actions)
        self.functions = {k.lower(): {"function":self.plugins[k].execute, "arguments":""} for k in self.plugins.keys()}      
    
    def load_plugins(self, directory):
        """
        Load plugins from the specified directory.
        """
        for filepath in glob.glob(os.path.join(directory, "*.py")):
            
            try:
                module_name = os.path.splitext(os.path.basename(filepath))[0]
                module = importlib.import_module(f"Vera.Toolchain.GraphPlugins.{module_name}")
            except Exception as e:
                # logging.info(f"Error loading plugin :{module_name}\n{e}")
                # print(f"{bcolors.FAIL}Error loading plugin :{module_name}\n{e} {bcolors.ENDC}")
                common.log(f"Error loading module :{module_name}\n{e}","error", socketio=self.socketio)
            
            else:
                # print(module, module_name)
                for name, obj in inspect.getmembers(module):
                    # print(name, obj)
                    if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
                        
                        try:
                            self.plugins[name] = obj(self.graph_manager, self.socketio, self.args)
                            self.add_functions_from_plugin(name, obj)
                        except Exception as e:
                            # logging.info(f"Error loading plugin :{module_name}\n{e}")
                            common.log(f"Error loading plugin :{module_name}.{name}\n{e}","error",socketio=self.socketio)
                        else:
                            common.log(f"Plugin Loaded: {module_name}.{name}","ok",socketio=self.socketio)
                            

        # print(self.plugin_functions)
        return(self.plugins)


    def add_functions_from_plugin(self, plugin_name, plugin_class):
        """Add functions from a plugin class to the functions dictionary."""
        for func_name, func in inspect.getmembers(plugin_class, inspect.isfunction):
            print(func_name)
            self.plugin_functions[plugin_name] = {func_name: {"function": func, "arguments": ""}}

    def run_all_transforms(self, *args, **kwargs):
        """Execute all loaded plugins."""
        for name, plugin in self.plugins.items():
            print(f"Executing plugin: {name}")
            plugin.execute(*args, **kwargs)

    def get_plugin_names(self):
        """Return a list of all loaded plugins."""
        return list(self.plugins.keys())
    
    def get_class_plugin_names(self, class_type):
        """ Given a class type, return a list of plugins that can be applied to that class type."""
        available_plugins = []
        for k in self.plugins.keys():
            if class_type in self.plugins[k].class_types():
                available_plugins.append(k)

        return list(available_plugins)
    
    def get_class_node_names(self, plugin):
        """ given a plugin class type, return a list of nodes that can be applied to that plugin type."""
        available_nodes = []
        for k in self.graph_manager.graph.nodes:
            if self.graph_manager.graph.nodes["class_type"] in plugin.class_types():
                available_nodes.append(k)
        return list(available_nodes)
    
    def act(self, node_id, action):
        """ Run a plugin (action) against a node ID """
        try:
            actions = self.functions
            print(f"Running {action}")

            self.actions_queue.append({"id":self.actions_queue[-1]["id"]+1, node_id:action})
            print(self.actions_queue)
            # socketio.emit("update_tasks", {"target":json.dumps(node_id),"task": json.dumps(action)})

            results=actions[action]["function"](node_id,actions[action]["arguments"])
            
            self.graph_manager.update_node(node_id, {action:{"data":results, "metadata_type":"text"}})
            self.save_graph_data()
            self.database.set_metadata(node_id, action, "PROCESSED", json.dumps(results, default=common.convert_datetime))
            
            # socketio.emit("update_tasks", {"target":json.dumps(node_id),"task_complete": json.dumps(action)})
            # socketio.emit("display_results", {"results": json.dumps(results)})
            # socketio.emit("update_graph", app.graph_manager.get_graph_data())

            common.log(f"Results:{results}\nTransmitted successfully","info")           
        except Exception as e:
            common.log(f"Error running action {action} on {node_id}: {e}","error")
        return(results)
    
    def run_all_plugins_on_node(self, graph, node_id):
        """Run all plugins on a specific node in the graph."""
        if node_id not in graph:
            print(f"Node {node_id} does not exist in the graph.")
            return
        
        node_data = graph.nodes[node_id]  # Get node properties
        
        for name, plugin in self.plugins.items():
            if graph.nodes[node_id]["class_type"] in plugin.class_types(): 
                if name not in "delete_node delete_link":
                    try:
                        print(f"Running {plugin.__class__.__name__} on {node_id}")
                        plugin.execute(node_id, node_data)  # Pass node data instead of raw text
                    except Exception as e:
                        print(f"Error running {plugin.__class__.__name__}: {e}")
    
    def handle_data(self, data):
        """Handles incoming data from plugins and adds it to the graph."""
        if isinstance(data, nx.Graph):
            self.graph = nx.compose(self.graph, data)
        elif isinstance(data, tuple) and len(data) == 2 and isinstance(data[0], nx.Graph) and isinstance(data[1], str):
            append_graph, instruction = data
            if instruction == "append":
                self.graph = nx.compose(self.graph, append_graph)
        elif isinstance(data, str):
            node_to_append_to = next(iter(self.graph.nodes()), None)
            if node_to_append_to:
                self.graph.nodes[node_to_append_to]['data'] = data
        elif isinstance(data, (types.FunctionType, types.MethodType, type)):  # Function or class
            # Assign function/class to a new or existing node
            node_name = data.__name__  # Use the function/class name as the node ID
            if node_name not in self.graph:
                self.graph.add_node(node_name)
            self.graph.nodes[node_name]['callable'] = data
        else:
            raise ValueError(f"Unexpected data type: {type(data)}")
    
    def execute_node(self, node_name, *args, **kwargs):
        """Execute the function or class stored in the specified node."""
        if node_name in self.graph and 'callable' in self.graph.nodes[node_name]:
            func_or_class = self.graph.nodes[node_name]['callable']
            if callable(func_or_class):
                return func_or_class(*args, **kwargs)
            else:
                raise TypeError(f"Node '{node_name}' does not contain a callable object.")
        else:
            raise KeyError(f"Node '{node_name}' not found or does not contain a callable object.")  
         
    def set_ssh_host(self):
        self.ssh_host = 'octoprint.int'
        self.ssh_port = 22
        self.ssh_username = 'pi'
        self.ssh_password = '£7370Adalovelace'

    def connect_ssh(self):
        """
        Establish an SSH connection and return the channel.
        """
        global ssh_channel
        try:
            # Create and connect the SSH client
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(
                self.ssh_host, port=self.ssh_port, username=self.ssh_username, password=self.ssh_password
            )

            # Open a shell channel
            ssh_channel = ssh_client.invoke_shell()
            common.log("[DEBUG] SSH connection established.","info", socketio=self.socketio)
            return ssh_channel
        except Exception as e:
            common.log(f"[ERROR] Failed to connect to SSH: {e}","error", socketio=self.socketio)
            ssh_channel = None
            return None
    
    def load_plugin(self, filepath):
        """
        Load a single plugin from its file.
        """
        module_name = os.path.splitext(os.path.basename(filepath))[0]

        try:
            if module_name in self.plugins:
                # Reload existing plugin
                module = importlib.reload(self.plugins[module_name]['module'])
            else:
                # Import new plugin
                module = importlib.import_module(f"plugins.{module_name}")

            for name, obj in inspect.getmembers(module):
                if inspect.isclass(obj) and issubclass(obj, PluginBase) and obj != PluginBase:
                    instance = obj(self.graph_manager, self.socketio, self.args)
                    self.plugins[module_name] = {'module': module, 'instance': instance}
                    self.add_functions_from_plugin(name, obj)
                    common.log(f"Plugin Loaded: {module_name}.{name}", "ok",socketio=self.socketio)

        except Exception as e:
            common.log(f"Error loading plugin: {module_name}\n{e}", "error",socketio=self.socketio)
    
    def unload_plugin(self, module_name):
        """
        Unload a plugin to allow reloading.
        """
        if module_name in self.plugins:
            del self.plugins[module_name]  # Remove from the dictionary
            if module_name in sys.modules:
                del sys.modules[f"plugins.{module_name}"]  # Remove from import cache

    def start_watcher(self):
        """
        Start a watchdog observer to monitor plugin directory for changes.
        """
        class PluginChangeHandler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager
                # self.directory = 'plugins'

            def on_modified(self, event):
                """Reload plugin if modified."""
                if event.src_path.endswith(".py"):
                    module_name = os.path.splitext(os.path.basename(event.src_path))[0]
                    self.manager.unload_plugin(module_name)
                    self.manager.load_plugin(event.src_path)

            def on_created(self, event):
                """Load new plugin if a new .py file is added."""
                if event.src_path.endswith(".py"):
                    self.manager.load_plugin(event.src_path)

        observer = Observer()
        event_handler = PluginChangeHandler(self)
        observer.schedule(event_handler, plugins_directory, recursive=False)
        observer_thread = threading.Thread(target=observer.start, daemon=True)
        observer_thread.start()