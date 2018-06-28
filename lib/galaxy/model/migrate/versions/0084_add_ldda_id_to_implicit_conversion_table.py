"""
Migration script to add 'ldda_id' column to the implicitly_converted_dataset_association table.
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, ForeignKey, Integer, MetaData, Table

log = logging.getLogger(__name__)
metadata = MetaData()


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        Implicitly_converted_table = Table("implicitly_converted_dataset_association", metadata, autoload=True)
        if migrate_engine.name != 'sqlite':
            c = Column("ldda_id", Integer, ForeignKey("library_dataset_dataset_association.id"), index=True, nullable=True)
        else:
            c = Column("ldda_id", Integer, index=True, nullable=True)
        c.create(Implicitly_converted_table, index_name="ix_implicitly_converted_ds_assoc_ldda_id")
        assert c is Implicitly_converted_table.c.ldda_id
    except Exception:
        log.exception("Adding ldda_id column to implicitly_converted_dataset_association table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        Implicitly_converted_table = Table("implicitly_converted_dataset_association", metadata, autoload=True)
        Implicitly_converted_table.c.ldda_id.drop()
    except Exception:
        log.exception("Dropping ldda_id column from implicitly_converted_dataset_association table failed.")
