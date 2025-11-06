 
"""

Connects to a host via SSH

"""
import sys
import os
# Add the project root (where main.py is) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from plugin_manager import PluginBase
from common.common import plot
import time
import paramiko

# SSH connection details
ssh_host = 'octoprint.int'
ssh_port = 22
ssh_username = 'pi'
ssh_password = '£7370Adalovelace'

capture_ssh_output = False

class sshConnect(PluginBase):
    
    @staticmethod
    def class_types():
        return( [
                "ip",
                "IP",
                "domain",
                "subdomain",
                ] )
    
    @staticmethod
    def description():
        return("")
    
    @staticmethod
    def output_class():
        return "metadata"

    def execute(self, base_path, args):
        # TODO # Send ssh connection form to UI
        ssh_port=args.ssh_port
        ssh_username=args.ssh_username
        ssh_password=args.ssh_password
        self.connect_ssh(ssh_host=base_path)

    def form():
        return({
            'title': 'SSH Connection',
            'fields': [
                {'name': 'username', 'type': 'text', 'label': 'Username'},
                {'name': 'password', 'type': 'text', 'label': 'Password'},
            ]
        })

    def connect_ssh(self, ssh_host=ssh_host, ssh_port=ssh_port, ssh_username=ssh_username, ssh_password=ssh_password):
        """
        Establish an SSH connection and return the channel.
        """
        global ssh_channel
        try:
            # Create and connect the SSH client
            ssh_client = paramiko.SSHClient()
            ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh_client.connect(
                ssh_host, port=ssh_port, username=ssh_username, password=ssh_password
            )

            # Open a shell channel
            ssh_channel = ssh_client.invoke_shell()
            print("[DEBUG] SSH connection established.")
            return ssh_channel
        except Exception as e:
            print(f"[ERROR] Failed to connect to SSH: {e}")
            ssh_channel = None
            return None
        
    # def read_output(self):
    #     """
    #     Continuously read output from the SSH channel and emit to the frontend.
    #     """
    #     global ssh_channel
    #     while ssh_channel and not ssh_channel.closed:
    #         try:
    #             if ssh_channel.recv_ready():
    #                 output = ssh_channel.recv(1024).decode('utf-8')
    #                 print(f"[DEBUG] SSH Output: {output}")  # Log output to console
    #                 self.socketio.emit('output', {'data': output})  # Broadcast to all clients
    #                 if capture_ssh_output == True:
    #                     pass
    #                     # TODO Capture to SQL
    #             time.sleep(0.1)  # Prevent tight loop
    #         except Exception as e:
    #             print(f"[ERROR] Error reading SSH output: {e}")
    #             break
    
    # @socketio.on('connect')
    # def handle_connect(self):
    #     """
    #     Handle new WebSocket connections.
    #     """
    #     global ssh_channel
    #     print("A client connected!")
    #     if ssh_channel is None or ssh_channel.closed:
    #         ssh_channel = connect_ssh()
    #         if ssh_channel:
    #             # Start a thread to read output from the SSH channel
    #             threading.Thread(target=read_output, daemon=True).start()
    #             socketio.emit('output', {'data': 'Connected to SSH server.\n'})
    #         else:
    #         self.socketio.emit('output', {'data': 'Failed to connect to SSH server.\n'})
    #         # TODO Implement a feed for terminal output of the app as well as ssh


    # @socketio.on('input')
    # def handle_input(self.data):
    #     """
    #     Handle input from the frontend and send it to the SSH channel.
    #     """
    #     global ssh_channel
    #     if ssh_channel and not ssh_channel.closed:
    #         try:
    #             command = data['data']
    #             ssh_channel.send(command)
    #         except Exception as e:
    #             self.socketio.emit('output', {'data': f'Error sending command: {str(e)}\n'})

