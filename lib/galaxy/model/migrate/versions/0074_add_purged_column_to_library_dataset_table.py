"""
Migration script to add 'purged' column to the library_dataset table.
"""
from __future__ import print_function

import logging

from sqlalchemy import Boolean, Column, MetaData, Table

log = logging.getLogger(__name__)
metadata = MetaData()


def engine_false(migrate_engine):
    if migrate_engine.name in ['postgres', 'postgresql']:
        return "FALSE"
    elif migrate_engine.name in ['mysql', 'sqlite']:
        return 0
    else:
        raise Exception('Unknown database type: %s' % migrate_engine.name)


def engine_true(migrate_engine):
    if migrate_engine.name in ['postgres', 'postgresql']:
        return "TRUE"
    elif migrate_engine.name in ['mysql', 'sqlite']:
        return 1
    else:
        raise Exception('Unknown database type: %s' % migrate_engine.name)


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    try:
        LibraryDataset_table = Table("library_dataset", metadata, autoload=True)
        c = Column("purged", Boolean, index=True, default=False)
        c.create(LibraryDataset_table, index_name='ix_library_dataset_purged')
        assert c is LibraryDataset_table.c.purged
    except Exception:
        log.exception("Adding purged column to library_dataset table failed.")
    # Update the purged flag to the default False
    cmd = "UPDATE library_dataset SET purged = %s;" % engine_false(migrate_engine)
    try:
        migrate_engine.execute(cmd)
    except Exception:
        log.exception("Setting default data for library_dataset.purged column failed.")

    # Update the purged flag for those LibaryDatasets whose purged flag should be True.  This happens
    # when the LibraryDataset has no active LibraryDatasetDatasetAssociations.
    cmd = "SELECT * FROM library_dataset WHERE deleted = %s;" % engine_true(migrate_engine)
    deleted_lds = migrate_engine.execute(cmd).fetchall()
    for row in deleted_lds:
        cmd = "SELECT * FROM library_dataset_dataset_association WHERE library_dataset_id = %d AND library_dataset_dataset_association.deleted = %s;" % (int(row.id), engine_false(migrate_engine))
        active_lddas = migrate_engine.execute(cmd).fetchall()
        if not active_lddas:
            print("Updating purged column to True for LibraryDataset id : ", int(row.id))
            cmd = "UPDATE library_dataset SET purged = %s WHERE id = %d;" % (engine_true(migrate_engine), int(row.id))
            migrate_engine.execute(cmd)


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    try:
        LibraryDataset_table = Table("library_dataset", metadata, autoload=True)
        LibraryDataset_table.c.purged.drop()
    except Exception:
        log.exception("Dropping purged column from library_dataset table failed.")
