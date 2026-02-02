# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""Async database manager with adapter pattern and table registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .adapters import DbAdapter, get_adapter

if TYPE_CHECKING:
    from .table import Table


class SqlDb:
    """Async database manager with adapter pattern.

    Supports multiple database types via adapters:
    - SQLite: "/path/to/db.sqlite" or "sqlite:/path/to/db"
    - PostgreSQL: "postgresql://user:pass@host/db"

    Features:
    - Table class registration via add_table()
    - Table access via table(name)
    - Schema creation and verification
    - CRUD operations via adapter
    - Encryption key access via parent.encryption_key

    Usage:
        db = SqlDb("/data/mail.db", parent=proxy)
        await db.connect()

        db.add_table(TenantsTable)
        db.add_table(AccountsTable)
        await db.check_structure()

        tenant = await db.table('tenants').select_one(where={"id": "acme"})

        await db.close()
    """

    def __init__(self, connection_string: str, parent: Any = None):
        """Initialize database manager.

        Args:
            connection_string: Database connection string.
            parent: Parent object (e.g., proxy) that provides encryption_key.
        """
        self.connection_string = connection_string
        self.parent = parent
        self.adapter: DbAdapter = get_adapter(connection_string)
        self.tables: dict[str, Table] = {}

    @property
    def encryption_key(self) -> bytes | None:
        """Get encryption key from parent. Returns None if not configured."""
        if self.parent is None:
            return None
        return getattr(self.parent, "encryption_key", None)

    async def connect(self) -> None:
        """Connect to database."""
        await self.adapter.connect()

    async def close(self) -> None:
        """Close database connection."""
        await self.adapter.close()

    def add_table(self, table_class: type[Table]) -> Table:
        """Register and instantiate a table class.

        Args:
            table_class: Table manager class (must have name attribute).

        Returns:
            The instantiated table.
        """
        if not hasattr(table_class, "name") or not table_class.name:
            raise ValueError(f"Table class {table_class.__name__} must define 'name'")

        instance = table_class(self)
        self.tables[instance.name] = instance
        return instance

    def table(self, name: str) -> Table:
        """Get table instance by name.

        Args:
            name: Table name.

        Returns:
            Table instance.

        Raises:
            ValueError: If table not registered.
        """
        if name not in self.tables:
            raise ValueError(f"Table '{name}' not registered. Use add_table() first.")
        return self.tables[name]

    async def check_structure(self) -> None:
        """Create all registered tables if they don't exist.

        Tables are sorted by foreign key dependencies to ensure referenced
        tables are created before tables that reference them.
        """
        sorted_tables = self._sort_tables_by_dependencies()
        for table in sorted_tables:
            await table.create_schema()

    def _sort_tables_by_dependencies(self) -> list:
        """Sort tables so that tables with FK dependencies come after their targets."""
        # Build dependency graph: table_name -> set of tables it depends on
        dependencies: dict[str, set[str]] = {}
        for name, table in self.tables.items():
            deps = set()
            for col in table.columns.values():
                if col.relation_table and col.relation_table in self.tables:
                    deps.add(col.relation_table)
            dependencies[name] = deps

        # Topological sort (Kahn's algorithm)
        result = []
        no_deps = [name for name, deps in dependencies.items() if not deps]

        while no_deps:
            name = no_deps.pop(0)
            result.append(self.tables[name])
            # Remove this table from all dependency sets
            for deps in dependencies.values():
                deps.discard(name)
            # Find new tables with no remaining dependencies
            for other_name, deps in dependencies.items():
                if not deps and other_name not in [t.name for t in result] and other_name not in no_deps:
                    no_deps.append(other_name)

        # Add any remaining tables (shouldn't happen with valid schema)
        for _name, table in self.tables.items():
            if table not in result:
                result.append(table)

        return result

    # -------------------------------------------------------------------------
    # Direct adapter access
    # -------------------------------------------------------------------------

    async def execute(self, query: str, params: dict[str, Any] | None = None) -> int:
        """Execute raw query, return affected row count."""
        return await self.adapter.execute(query, params)

    async def fetch_one(
        self, query: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Execute raw query, return single row."""
        return await self.adapter.fetch_one(query, params)

    async def fetch_all(
        self, query: str, params: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Execute raw query, return all rows."""
        return await self.adapter.fetch_all(query, params)

    async def commit(self) -> None:
        """Commit transaction."""
        await self.adapter.commit()

    async def rollback(self) -> None:
        """Rollback transaction."""
        await self.adapter.rollback()


__all__ = ["SqlDb"]
