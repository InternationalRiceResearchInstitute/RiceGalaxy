"""
Migration script to add the repository_dependency and repository_repository_dependency_association tables.
"""
from __future__ import print_function

import datetime
import logging
import sys

from sqlalchemy import Column, DateTime, ForeignKey, Integer, MetaData, Table

now = datetime.datetime.utcnow
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
format = "%(name)s %(levelname)s %(asctime)s %(message)s"
formatter = logging.Formatter(format)
handler.setFormatter(formatter)
log.addHandler(handler)

metadata = MetaData()

RepositoryDependency_table = Table("repository_dependency", metadata,
                                   Column("id", Integer, primary_key=True),
                                   Column("create_time", DateTime, default=now),
                                   Column("update_time", DateTime, default=now, onupdate=now),
                                   Column("tool_shed_repository_id", Integer, ForeignKey("tool_shed_repository.id"), index=True, nullable=False))

RepositoryRepositoryDependencyAssociation_table = Table("repository_repository_dependency_association", metadata,
                                                        Column("id", Integer, primary_key=True),
                                                        Column("create_time", DateTime, default=now),
                                                        Column("update_time", DateTime, default=now, onupdate=now),
                                                        Column("tool_shed_repository_id", Integer, ForeignKey("tool_shed_repository.id"), index=True),
                                                        Column("repository_dependency_id", Integer, ForeignKey("repository_dependency.id"), index=True))


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        RepositoryDependency_table.create()
    except Exception:
        log.exception("Creating repository_dependency table failed.")
    try:
        RepositoryRepositoryDependencyAssociation_table.create()
    except Exception:
        log.exception("Creating repository_repository_dependency_association table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        RepositoryRepositoryDependencyAssociation_table.drop()
    except Exception:
        log.exception("Dropping repository_repository_dependency_association table failed.")
    try:
        RepositoryDependency_table.drop()
    except Exception:
        log.exception("Dropping repository_dependency table failed.")
