"""schema v2 -- series, formats, achat, lecture principale, pile ordonnee

Les 6 décisions produit du 15/08/2026 (handoff design-ui -> backend) :
- Série : table `series` + `book.series_id` / `book.series_index` (décimal,
  ex. 1.5 pour un hors-série).
- Format x possession : table `book_format` (format non exclusif, `owned`
  PAR format) — un livre peut avoir le papier acheté et le digital emprunté.
- Prix payé / date d'achat : un champ chacun, jamais remplis en wishlist
  (règle applicative, pas de contrainte SQL : un livre marqué read puis
  repassé en wishlist ne doit pas être bloqué par la base).
- `book.is_primary_reading` : flag exclusif parmi les livres `reading` —
  contrainte réelle par index partiel unique. SQLite n'ayant ni `ALTER TABLE
  ADD CONSTRAINT` ni drop de colonne référencée par une FK, la colonne
  `book.series_id` est posée via le mode batch (recreate + copie).
- Pile à lire = sélection ordonnée : `book.tbr_rank` (+ `tbr_note`),
  distincts du simple filtre `status='tbr'`.

Revision ID: ff98b093454f
Revises: 36ce8285e200
Create Date: 2026-08-15 13:18:12.788472

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ff98b093454f'
down_revision: Union[str, Sequence[str], None] = '36ce8285e200'
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
        op.create_table('series',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
        sqlite_autoincrement=True
        )
        op.create_table('book_format',
        sa.Column('book_id', sa.Integer(), nullable=False),
        sa.Column('format', sa.Text(), nullable=False),
        sa.Column('owned', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.CheckConstraint("format IN ('physique', 'digital', 'audio')", name='ck_book_format_type'),
        sa.ForeignKeyConstraint(['book_id'], ['book.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('book_id', 'format')
        )
        # SQLite n'a pas d'ALTER TABLE ADD CONSTRAINT : une colonne portant une
        # FK impose le mode batch (recreate de `book` + copie des lignes). Coût
        # négligeable sur une bibliothèque perso (quelques milliers de lignes).
        with op.batch_alter_table("book") as batch_op:
            batch_op.add_column(sa.Column(
                'series_id', sa.Integer(),
                sa.ForeignKey('series.id', ondelete='SET NULL', name='fk_book_series_id_series'),
                nullable=True,
            ))
        op.add_column('book', sa.Column('series_index', sa.Numeric(precision=5, scale=2), nullable=True))
        op.add_column('book', sa.Column('price_paid', sa.Float(), nullable=True))
        op.add_column('book', sa.Column('purchased_at', sa.Text(), nullable=True))
        op.add_column('book', sa.Column('is_primary_reading', sa.Integer(), server_default=sa.text('0'), nullable=False))
        op.add_column('book', sa.Column('tbr_rank', sa.Integer(), nullable=True))
        op.add_column('book', sa.Column('tbr_note', sa.Text(), nullable=True))
        # Exclusivité du livre « en cours » : au plus un (reading, primary=1).
        op.create_index('uq_book_primary_reading', 'book', ['is_primary_reading'], unique=True, sqlite_where=sa.text("status = 'reading' AND is_primary_reading = 1"))
    finally:
        _set_foreign_keys(True)


def downgrade() -> None:
    """Downgrade schema."""
    _set_foreign_keys(False)
    try:
        op.drop_index('uq_book_primary_reading', table_name='book', sqlite_where=sa.text("status = 'reading' AND is_primary_reading = 1"))
        op.drop_column('book', 'tbr_note')
        op.drop_column('book', 'tbr_rank')
        op.drop_column('book', 'is_primary_reading')
        op.drop_column('book', 'purchased_at')
        op.drop_column('book', 'price_paid')
        op.drop_column('book', 'series_index')
        # SQLite interdit de dropper une colonne référencée par sa propre FK
        # (« unknown column in foreign key definition ») : batch mode pour
        # recréer la table sans la FK et la colonne en une passe.
        with op.batch_alter_table("book") as batch_op:
            batch_op.drop_column('series_id')
        op.drop_table('book_format')
        op.drop_table('series')
    finally:
        _set_foreign_keys(True)
