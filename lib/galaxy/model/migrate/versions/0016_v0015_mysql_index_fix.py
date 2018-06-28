"""
This script fixes a problem introduced in 0015_tagging.py. MySQL has a name length
limit and thus the index "ix_hda_ta_history_dataset_association_id" has to be
manually created.
"""
from __future__ import print_function

import logging

from sqlalchemy import Column, ForeignKey, Index, Integer, MetaData, Table

# Need our custom types, but don't import anything else from model
from galaxy.model.custom_types import TrimmedString

log = logging.getLogger(__name__)
metadata = MetaData()


HistoryDatasetAssociationTagAssociation_table = Table("history_dataset_association_tag_association", metadata,
                                                      Column("history_dataset_association_id", Integer, ForeignKey("history_dataset_association.id"), index=True),
                                                      Column("tag_id", Integer, ForeignKey("tag.id"), index=True),
                                                      Column("user_tname", TrimmedString(255), index=True),
                                                      Column("value", TrimmedString(255), index=True),
                                                      Column("user_value", TrimmedString(255), index=True))


def upgrade(migrate_engine):
    metadata.bind = migrate_engine
    print(__doc__)
    metadata.reflect()
    i = Index("ix_hda_ta_history_dataset_association_id", HistoryDatasetAssociationTagAssociation_table.c.history_dataset_association_id)
    try:
        i.create()
    except Exception:
        log.exception("Adding index 'ix_hdata_history_dataset_association_id' to table 'history_dataset_association_tag_association' table failed.")


def downgrade(migrate_engine):
    metadata.bind = migrate_engine
    metadata.reflect()
    i = Index("ix_hda_ta_history_dataset_association_id", HistoryDatasetAssociationTagAssociation_table.c.history_dataset_association_id)
    try:
        i.drop()
    except Exception:
        log.exception("Removing index 'ix_hdata_history_dataset_association_id' to table 'history_dataset_association_tag_association' table failed.")
