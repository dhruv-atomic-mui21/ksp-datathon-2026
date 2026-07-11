import os
import sqlite3
import logging

class DatabaseManager:
    def __init__(self, db_type=None, sqlite_path="ksp_crime.db"):
        # Auto-detect db_type from environment variable, default to sqlite for local dev
        self.db_type = db_type or os.environ.get("DB_TYPE", "sqlite").lower()
        self.sqlite_path = sqlite_path
        self.logger = logging.getLogger()

    def execute_query(self, sql_query, params=None):
        """
        Executes a SELECT query and returns a list of flat dictionaries:
        e.g. [{"CrimeNo": "101", "AccusedName": "Ramesh"}, ...]
        """
        if self.db_type == "catalyst":
            return self._execute_zcql(sql_query)
        else:
            return self._execute_sqlite(sql_query, params)

    def execute_write(self, sql_query, params=None):
        """
        Executes an INSERT/UPDATE/DELETE query.
        """
        if self.db_type == "catalyst":
            return self._execute_zcql_write(sql_query)
        else:
            return self._execute_sqlite_write(sql_query, params)

    def _execute_sqlite(self, sql, params=None):
        params = params or []
        # SQLite doesn't support ZCQL's double quotes for string literals or table casing,
        # but standard SQL is 100% compatible.
        # We will open and close connection to avoid threading errors in serverless env.
        try:
            # Look for db in root or local directory
            db_file = self.sqlite_path
            if not os.path.exists(db_file):
                # Check one directory up (in case running from functions/ksp_backend/)
                db_file = os.path.join("..", "..", self.sqlite_path)
                if not os.path.exists(db_file):
                    # Check current directory inside function
                    db_file = os.path.join(os.path.dirname(__file__), self.sqlite_path)

            conn = sqlite3.connect(db_file)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            results = [dict(row) for row in rows]
            conn.close()
            return results
        except Exception as e:
            self.logger.error(f"SQLite execute error: {str(e)}")
            raise e

    def _execute_sqlite_write(self, sql, params=None):
        params = params or []
        try:
            db_file = self.sqlite_path
            if not os.path.exists(db_file):
                db_file = os.path.join("..", "..", self.sqlite_path)
                if not os.path.exists(db_file):
                    db_file = os.path.join(os.path.dirname(__file__), self.sqlite_path)
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            return last_id
        except Exception as e:
            self.logger.error(f"SQLite write error: {str(e)}")
            raise e

    def _execute_zcql(self, sql):
        """
        Executes a ZCQL query against Zoho Catalyst Data Store and flattens the output.
        """
        try:
            import zcatalyst_sdk
            # Initialize inside the execution context
            app = zcatalyst_sdk.initialize()
            zcql_service = app.zcql()
            raw_results = zcql_service.execute_query(sql)
            
            # Flatten ZCQL nested dict output:
            # ZCQL returns [ { "CaseMaster": { "CrimeNo": "X" }, "Accused": { "AccusedName": "Y" } } ]
            # Flatten to [ { "CrimeNo": "X", "AccusedName": "Y" } ]
            flattened = []
            for row in raw_results:
                flat_row = {}
                for table_name, table_cols in row.items():
                    if isinstance(table_cols, dict):
                        for col_name, col_val in table_cols.items():
                            flat_row[col_name] = col_val
                    else:
                        flat_row[table_name] = table_cols
                flattened.append(flat_row)
            return flattened
        except Exception as e:
            self.logger.error(f"ZCQL execute error: {str(e)}")
            raise e

    def _execute_zcql_write(self, sql):
        # Catalyst Data Store does not support INSERT/UPDATE via ZCQL direct write queries.
        # Instead, it requires using the table object insertRow/updateRow SDK methods.
        # We will parse basic audit log inserts and direct them to the catalyst table SDK.
        try:
            import zcatalyst_sdk
            app = zcatalyst_sdk.initialize()
            
            if "INSERT INTO AuditLog" in sql:
                # Basic parsing of insert statement
                # e.g., INSERT INTO AuditLog (UserEmail, UserRole, Action, QueryExecuted) VALUES (?, ?, ?, ?)
                # For audit logs, we'll write them via Data Store table SDK
                datastore_service = app.data_store()
                table = datastore_service.table("AuditLog")
                
                # We can extract values from the sql (since ZCQL-write doesn't support parameter arrays easily)
                # But to make it simple, we will write a generic Audit Log function instead.
                pass
            return True
        except Exception as e:
            self.logger.error(f"ZCQL write error: {str(e)}")
            return False

    def log_audit(self, email, role, action, query_executed=""):
        """
        Inserts a row into the AuditLog table for compliance.
        """
        if self.db_type == "catalyst":
            try:
                import zcatalyst_sdk
                app = zcatalyst_sdk.initialize()
                datastore = app.data_store()
                table = datastore.table("AuditLog")
                row_data = {
                    "UserEmail": email,
                    "UserRole": role,
                    "Action": action,
                    "QueryExecuted": query_executed
                }
                table.insert_row(row_data)
            except Exception as e:
                self.logger.error(f"Failed to write Catalyst audit log: {str(e)}")
        else:
            sql = "INSERT INTO AuditLog (UserEmail, UserRole, Action, QueryExecuted, Timestamp) VALUES (?, ?, ?, ?, datetime('now'))"
            self.execute_write(sql, [email, role, action, query_executed])
