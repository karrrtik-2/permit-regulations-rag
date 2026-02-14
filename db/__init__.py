"""
Database connection management for HeavyHaul AI.

Provides a singleton MongoDB client and typed access to all collections.
"""

import logging
from typing import Optional

from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from config.settings import settings

logger = logging.getLogger(__name__)


class MongoDatabase:
    """Manages MongoDB connection and provides collection accessors."""

    _instance: Optional["MongoDatabase"] = None
    _client: Optional[MongoClient] = None

    def __new__(cls) -> "MongoDatabase":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if self._client is None:
            self._connect()

    def _connect(self) -> None:
        """Establish MongoDB connection."""
        try:
            self._client = MongoClient(settings.mongo.uri)
            self._db: Database = self._client[settings.mongo.database]
            logger.info("Connected to MongoDB: %s", settings.mongo.database)
        except Exception as e:
            logger.error("Failed to connect to MongoDB: %s", e)
            raise

    @property
    def db(self) -> Database:
        """Get the database instance."""
        return self._db

    @property
    def orders(self) -> Collection:
        """All Orders collection."""
        return self._db[settings.mongo.orders_collection]

    @property
    def drivers(self) -> Collection:
        """Drivers collection."""
        return self._db[settings.mongo.drivers_collection]

    @property
    def clients(self) -> Collection:
        """Clients collection."""
        return self._db[settings.mongo.clients_collection]

    @property
    def companies(self) -> Collection:
        """Companies collection."""
        return self._db[settings.mongo.companies_collection]

    @property
    def states(self) -> Collection:
        """All States collection."""
        return self._db[settings.mongo.states_collection]

    @property
    def users(self) -> Collection:
        """All Users collection."""
        return self._db[settings.mongo.users_collection]

    def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            logger.info("MongoDB connection closed")
            MongoDatabase._client = None
            MongoDatabase._instance = None


def get_db() -> MongoDatabase:
    """Get the singleton database instance."""
    return MongoDatabase()
