from __future__ import annotations

from flask import Flask, current_app, g
import mysql.connector as mysql_connector


class MySQLConnectionManager:
    """Small helper for opening and closing BakeWise MySQL connections."""

    connection_key = "bakewise_db_connection"

    def init_app(self, app: Flask) -> None:
        """Register cleanup so each request closes its own connection."""
        app.teardown_appcontext(self.close_connection)

    def get_connection(self):
        """Reuse one connection per request instead of reconnecting repeatedly."""
        if self.connection_key not in g:
            g[self.connection_key] = mysql_connector.connect(
                **current_app.config["MYSQL_SETTINGS"]
            )

        return g[self.connection_key]

    def get_cursor(self, dictionary: bool = True):
        """Create a cursor that future repositories can use for SQL queries."""
        return self.get_connection().cursor(dictionary=dictionary)

    def ping(self) -> bool:
        """Test whether the current database connection is reachable."""
        connection = self.get_connection()
        connection.ping(reconnect=True, attempts=1, delay=0)
        return True

    def close_connection(self, exception: Exception | None = None) -> None:
        """Close the request-scoped connection if one was opened."""
        connection = g.pop(self.connection_key, None)
        if connection is not None and connection.is_connected():
            connection.close()


mysql = MySQLConnectionManager()
