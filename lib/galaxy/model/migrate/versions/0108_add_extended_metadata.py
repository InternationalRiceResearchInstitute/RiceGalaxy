"""
Add the ExtendedMetadata and ExtendedMetadataIndex tables
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, ForeignKey, Integer, MetaData, String, Table, TEXT

from galaxy.model.custom_types import JSONType

log = logging.getLogger(__name__)
metadata = MetaData()

ExtendedMetadata_table = Table("extended_metadata", metadata,
                               Column("id", Integer, primary_key=True),
                               Column("data", JSONType))

ExtendedMetadataIndex_table = Table("extended_metadata_index", metadata,
                                    Column("id", Integer, primary_key=True),
                                    Column("extended_metadata_id", Integer, ForeignKey("extended_metadata.id",
                                                                                       onupdate="CASCADE",
                                                                                       ondelete="CASCADE"),
                                           index=True),
                                    Column("path", String(255)),
                                    Column("value", TEXT))

extended_metadata_ldda_col = Column("extended_metadata_id", Integer, ForeignKey("extended_metadata.id"), nullable=True)


def upgrade(migrate_engine):
    print(__doc__)
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        ExtendedMetadata_table.create()
    except Exception:
        log.exception("Could not create ExtendedMetadata Table.")
    try:
        ExtendedMetadataIndex_table.create()
    except Exception:
        log.exception("Could not create ExtendedMetadataIndex Table.")
    # Add the extended_metadata_id to the ldda table
    try:
        ldda_table = Table("library_dataset_dataset_association", metadata, autoload=True)
        extended_metadata_ldda_col.create(ldda_table)
        assert extended_metadata_ldda_col is ldda_table.c.extended_metadata_id
    except Exception:
        log.exception("Adding column 'extended_metadata_id' to library_dataset_dataset_association table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    # Drop the LDDA table's extended metadata ID column.
    try:
        ldda_table = Table("library_dataset_dataset_association", metadata, autoload=True)
        extended_metadata_id = ldda_table.c.extended_metadata_id
        extended_metadata_id.drop()
    except Exception:
        log.exception("Dropping 'extended_metadata_id' column from library_dataset_dataset_association table failed.")
    try:
        ExtendedMetadataIndex_table.drop()
    except Exception:
        log.exception("Dropping 'extended_metadata_index' table failed.")

    try:
        ExtendedMetadata_table.drop()
    except Exception:
        log.exception("Dropping 'extended_metadata' table failed.")
