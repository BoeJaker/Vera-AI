# Plugins
An overview of the capabilities and usage of Arachne plugins.

## Plugin types
### Parsers:
Plugins the extract data into a particular format

### Transformers:
Plugins that obtain new data by running actions against an existing dataset

### Interfaces:
Plugins that interface with another application, typically parsing the output into a graph

## Plugin Usage Guide:

### Pre-requisites:

Create Yourplugin.py in the plugins folder  

Add project root to sys.path

    import sys
    import os
    # Add the project root (where main.py is) to sys.path
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

Import the PluginBase class from plugin_manager  

    from plugin_manager import PluginBase

Set the plugin parent class

    class youPlugin(PluginBase):

Set the following functions

    # @staticmethod
    def class_types(self):
        return( [
            "ip",
            "IP",
            "netblock",
            "domain",
            "subdomain",
            "ip6"
            ] )
    
    # @staticmethod
    def description(self):
        return("")
    
    @staticmethod
    def output_class():
        return "metadata"

Standalone or tetsing routines sohuld be placed inside

    if __name__ == '__main__':


### Inputs:

### Outputs: