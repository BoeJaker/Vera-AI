import docker

class RemoteDockerMapper:
    def __init__(self, host: str, port: int = 2375):
        """
        Initialize connection to the remote Docker server.
        :param host: The IP or hostname of the remote Docker server.
        :param port: The port of the remote Docker API (default is 2375).
        """
        self.base_url = f'tcp://{host}:{port}'
        self.client = docker.DockerClient(base_url=self.base_url)
        
    def form():
        return({
            'title': 'User Registration',
            'fields': [
                {'name': 'username', 'type': 'text', 'label': 'Username'},
                {'name': 'email', 'type': 'email', 'label': 'Email'},
                {'name': 'password', 'type': 'password', 'label': 'Password'}
            ]
        })
    
    def list_containers(self, all_containers=True):
        """Returns a list of all containers on the remote Docker server."""
        try:
            containers = self.client.containers.list(all=all_containers)
            return [{
                'id': container.id,
                'name': container.name,
                'status': container.status,
                'image': container.image.tags
            } for container in containers]
        except Exception as e:
            return f"Error retrieving containers: {e}"
    
    def list_images(self):
        """Returns a list of all images on the remote Docker server."""
        try:
            images = self.client.images.list()
            return [{
                'id': image.id,
                'tags': image.tags
            } for image in images]
        except Exception as e:
            return f"Error retrieving images: {e}"
    
    def list_networks(self):
        """Returns a list of all networks on the remote Docker server."""
        try:
            networks = self.client.networks.list()
            return [{
                'id': network.id,
                'name': network.name,
                'driver': network.driver
            } for network in networks]
        except Exception as e:
            return f"Error retrieving networks: {e}"
    
    def get_system_info(self):
        """Returns system information about the remote Docker server."""
        try:
            return self.client.info()
        except Exception as e:
            return f"Error retrieving system info: {e}"

    def close(self):
        """Closes the connection to the Docker client."""
        self.client.close()

# Example usage
if __name__ == "__main__":
    docker_mapper = RemoteDockerMapper("192.168.1.100")  # Replace with your Docker server's IP
    print("Containers:", docker_mapper.list_containers())
    print("Images:", docker_mapper.list_images())
    print("Networks:", docker_mapper.list_networks())
    print("System Info:", docker_mapper.get_system_info())
    docker_mapper.close()
