"""wishlist separee de status plus type de livre

Décision 16/08/2026 (SPEC.md §2 et §5) :
- `status` perd la valeur `wishlist` : les seules valeurs valides sont
  tbr | reading | read | dnf | on_hold. Un livre souhaité porte désormais
  `is_wishlist = 1` (flag indépendant du statut de lecture).
- `type` distingue livre | manga | comics | manhwa (déclaratif, manuel).

Migration :
1. `book.is_wishlist` (0/1, défaut 0) — même pattern qu'`is_primary_reading`.
2. `book.type` (TEXT, défaut 'livre') + CHECK `ck_book_type` (même pattern
   que le CHECK de `book_format.format`). SQLite n'a pas d'`ALTER TABLE ADD
   CONSTRAINT` : les deux colonnes et le CHECK passent en batch mode
   (recreate + copie), avec `foreign_keys` désactivé le temps de la
   recreate — sinon les `ON DELETE CASCADE` des tables filles emporteraient
   leurs lignes (même raison que ff98b093454f).
3. Backfill : toute ligne `status='wishlist'` passe à `is_wishlist=1`,
   `status='tbr'` — le statut d'un wishlist est sans objet mais doit rester
   une valeur valide de l'enum, on ne laisse jamais 'wishlist' traîner.

Le downgrade fait le miroir exact : les livres `is_wishlist=1` repassent à
l'ancien statut `wishlist` avant de perdre la colonne, puis les colonnes et
le CHECK sont retirés (re-upgrade propre, cycle vérifié par test).

Revision ID: 7e869700ed63
Revises: 1d5d73910b32
Create Date: 2026-08-16 10:02:28.671176

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel  # noqa: F401  — types AutoString utilisés par l'autogenerate


# revision identifiers, used by Alembic.
revision: str = '7e869700ed63'
down_revision: Union[str, Sequence[str], None] = '1d5d73910b32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _set_foreign_keys(on: bool) -> None:
    """`PRAGMA foreign_keys` est un no-op dans une transaction : l'exécuter
    hors transaction (autocommit_block) est obligatoire pour qu'il prenne
    effet sur la connexion de migration.

    Pourquoi : la recreate de `book` (batch mode) commence par DROP de
    l'ancienne table. Si les FK restent actives, les `ON DELETE CASCADE`
    des tables filles (reading_session, highlight…) emportent toutes leurs
    lignes — la bibliothèque existerait mais serait vide de lectures.
    """
    with op.get_context().autocommit_block():
        op.get_bind().exec_driver_sql(
            f"PRAGMA foreign_keys={'ON' if on else 'OFF'}"
        )


def upgrade() -> None:
    """Upgrade schema."""
    _set_foreign_keys(False)
    try:
        # Les deux colonnes + le CHECK en une passe : SQLite ne supporte pas
        # l'ajout d'une CHECK constraint autrement que par recreate. Le batch
        # reflète la table existante (index compris : `uq_book_primary_reading`,
        # `uq_book_booktrack_id`, `idx_book_status`…) et la recrée.
        with op.batch_alter_table("book") as batch_op:
            batch_op.add_column(sa.Column(
                'is_wishlist', sa.Integer(), server_default=sa.text('0'),
                nullable=False,
            ))
            batch_op.add_column(sa.Column(
                'type', sa.Text(), server_default=sa.text("'livre'"),
                nullable=False,
            ))
            batch_op.create_check_constraint(
                'ck_book_type',
                "type IN ('livre', 'manga', 'comics', 'manhwa')",
            )
        # Backfill : l'ancien statut `wishlist` devient le flag
        # `is_wishlist=1` avec un `status` valide de l'enum ('tbr', sans
        # objet tant que le livre est souhaité).
        op.execute(
            "UPDATE book SET is_wishlist = 1, status = 'tbr' "
            "WHERE status = 'wishlist'"
        )
    finally:
        _set_foreign_keys(True)


def downgrade() -> None:
    """Downgrade schema."""
    _set_foreign_keys(False)
    try:
        # Miroir du backfill : les wishlist repassent à l'ancien statut AVANT
        # de perdre la colonne, pour que le downgrade soit une vraie marche
        # arrière (re-upgrade ensuite = cycle propre).
        op.execute("UPDATE book SET status = 'wishlist' WHERE is_wishlist = 1")
        with op.batch_alter_table("book") as batch_op:
            batch_op.drop_constraint('ck_book_type', type_='check')
            batch_op.drop_column('type')
            batch_op.drop_column('is_wishlist')
    finally:
        _set_foreign_keys(True)
