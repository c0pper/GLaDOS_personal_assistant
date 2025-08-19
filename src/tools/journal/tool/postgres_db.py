
from typing import Any, Dict, List, Optional
import psycopg2


class PostgresDB:
    """
    A class to handle communication with a PostgreSQL database.
    It encapsulates the connection, cursor, and common database operations.
    """
    def __init__(self, db_name, user, password, host, port):
        self.db_name = db_name
        self.user = user
        self.password = password
        self.host = host
        self.port = port
        self.conn = None
        self.cursor = None

    def connect(self):
        """Establishes a connection to the PostgreSQL database."""
        try:
            self.conn = psycopg2.connect(
                dbname=self.db_name,
                user=self.user,
                password=self.password,
                host=self.host,
                port=self.port
            )
            self.cursor = self.conn.cursor()
            print("Database connection successful.")
        except Exception as e:
            print(f"Error connecting to the database: {e}")

    def disconnect(self):
        """Closes the database connection."""
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()
            print("Database connection closed.")

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Executes a SQL query and returns the results."""
        if not self.conn or self.conn.closed:
            self.connect()
        try:
            self.cursor.execute(query, params)
            if query.strip().lower().startswith(('select', 'returning')):
                return self.cursor.fetchall()
            else:
                self.conn.commit()
                return []
        except Exception as e:
            self.conn.rollback()
            print(f"Error executing query: {e}")
            return []

    def select_row_by_id(self, table: str, row_id: str) -> Optional[Dict[str, Any]]:
        """
        Selects a row from a table by its 'id' and returns it as a dictionary.
        This method is a stand-in for the "Select today's row" n8n node.
        """
        try:
            self.cursor.execute(f"SELECT * FROM {table} WHERE id = %s", (row_id,))
            columns = [desc[0] for desc in self.cursor.description]
            row = self.cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
        except Exception as e:
            print(f"Error fetching row: {e}")
            return None

    def insert_row(self, table: str, data: Dict[str, Any]):
        """Inserts a new row into the table."""
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        self.execute_query(query, tuple(data.values()))

    def update_row(self, table: str, row_id: str, data: Dict[str, Any]):
        """Updates an existing row in the table."""
        set_clause = ', '.join([f"{key} = %s" for key in data.keys()])
        query = f"UPDATE {table} SET {set_clause} WHERE id = %s"
        params = list(data.values()) + [row_id]
        self.execute_query(query, tuple(params))

    def get_all_people(self) -> List[str]:
        """Retrieves all people from the 'people' table."""
        query = "SELECT * FROM people"
        people = self.execute_query(query)
        people_names = [person[1].lower() for person in people]
        return people_names


if __name__ == "__main__":
    from src.config import Config

    db = PostgresDB(
        db_name=Config.POSTGRES_DB_NAME,
        user=Config.POSTGRES_DB_USER,
        password=Config.POSTGRES_DB_PASSWORD,
        host=Config.POSTGRES_DB_HOST,
        port=Config.POSTGRES_DB_PORT
    )
    db.connect()
    print(db.select_row_by_id("journal", "17082025"))
    people = db.get_all_people()
    print(people)
    db.disconnect()