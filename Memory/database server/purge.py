from neo4j import GraphDatabase

class Neo4jWiper:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def wipe(self):
        query = """
        MATCH (n)
        DETACH DELETE n
        """
        with self.driver.session() as session:
            session.run(query)
        print("✅ Database wiped successfully.")

if __name__ == "__main__":
    # Change these to match your Neo4j setup
    URI = "bolt://localhost:7687"
    USER = "neo4j"
    PASSWORD = "testpassword"

    wiper = Neo4jWiper(URI, USER, PASSWORD)
    wiper.wipe()
    wiper.close()
