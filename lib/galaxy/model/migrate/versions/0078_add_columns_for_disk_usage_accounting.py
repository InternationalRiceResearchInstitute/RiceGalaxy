"""
Migration script to add 'total_size' column to the dataset table, 'purged'
column to the HDA table, and 'disk_usage' column to the User and GalaxySession
tables.
"""
from __future__ import print_function

import logging

from sqlalchemy import Boolean, Column, MetaData, Numeric, Table

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()

    try:
        Dataset_table = Table("dataset", metadata, autoload=True)
        c = Column('total_size', Numeric(15, 0))
        c.create(Dataset_table)
        assert c is Dataset_table.c.total_size
    except Exception:
        log.exception("Adding total_size column to dataset table failed.")

    try:
        HistoryDatasetAssociation_table = Table("history_dataset_association", metadata, autoload=True)
        c = Column("purged", Boolean, index=True, default=False)
        c.create(HistoryDatasetAssociation_table, index_name="ix_history_dataset_association_purged")
        assert c is HistoryDatasetAssociation_table.c.purged
        migrate_engine.execute(HistoryDatasetAssociation_table.update().values(purged=False))
    except Exception:
        log.exception("Adding purged column to history_dataset_association table failed.")

    try:
        User_table = Table("galaxy_user", metadata, autoload=True)
        c = Column('disk_usage', Numeric(15, 0), index=True)
        c.create(User_table, index_name="ix_galaxy_user_disk_usage")
        assert c is User_table.c.disk_usage
    except Exception:
        log.exception("Adding disk_usage column to galaxy_user table failed.")

    try:
        GalaxySession_table = Table("galaxy_session", metadata, autoload=True)
        c = Column('disk_usage', Numeric(15, 0), index=True)
        c.create(GalaxySession_table, index_name="ix_galaxy_session_disk_usage")
        assert c is GalaxySession_table.c.disk_usage
    except Exception:
        log.exception("Adding disk_usage column to galaxy_session table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        Dataset_table = Table("dataset", metadata, autoload=True)
        Dataset_table.c.total_size.drop()
    except Exception:
        log.exception("Dropping total_size column from dataset table failed.")

    try:
        HistoryDatasetAssociation_table = Table("history_dataset_association", metadata, autoload=True)
        HistoryDatasetAssociation_table.c.purged.drop()
    except Exception:
        log.exception("Dropping purged column from history_dataset_association table failed.")

    try:
        User_table = Table("galaxy_user", metadata, autoload=True)
        User_table.c.disk_usage.drop()
    except Exception:
        log.exception("Dropping disk_usage column from galaxy_user table failed.")

    try:
        GalaxySession_table = Table("galaxy_session", metadata, autoload=True)
        GalaxySession_table.c.disk_usage.drop()
    except Exception:
        log.exception("Dropping disk_usage column from galaxy_session table failed.")
