"""Asset Library — persistent, tagged, browsable repository of story building blocks.

Every ``--deep`` deconstruction deposits assets here automatically. The library
accumulates over time: styles, shapes, worlds, and beat templates, each tagged
with metadata (source story, author, genre, era, notes) for browsing and
recombination.

Library layout (under ``library_root``)::

    library/
        styles/
            poe_cask.yaml           # StyleProfile + _meta header
            the_lantern.yaml
        worlds/
            poe_cask.json           # WorldSeed + _meta header
        beat_templates/
            the_lantern_4beat.json  # BeatPlan + _meta header
        index.json                  # searchable metadata index
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field


# ---------- Asset metadata schema -------------------------------------------


AssetType = Literal["style", "world", "beat_template"]


class AssetMeta(BaseModel):
    """Metadata envelope for any library asset."""

    type: AssetType
    asset_id: str = Field(description="Unique slug for this asset (e.g. 'poe_cask').")
    source_story: str | None = Field(default=None, description="Title of the story this was extracted from.")
    source_file: str | None = Field(default=None, description="Path to the source text file.")
    source_author: str | None = Field(default=None, description="Author of the source story.")
    source_era: str | None = Field(default=None, description="Era of the source story (e.g. '19th century').")
    extracted_from: str | None = Field(default=None, description="Content-addressed analysis directory.")
    extracted_at: str | None = Field(default=None, description="ISO timestamp of extraction.")
    shape: str | None = Field(default=None, description="Classified emotional arc shape (e.g. 'man_in_hole').")
    tags: list[str] = Field(default_factory=list, description="Free-form tags for browsing.")
    genre: list[str] = Field(default_factory=list, description="Genre classifications.")
    structural_template: str | None = Field(default=None, description="Classified structural plot template (e.g. 'three_act').")
    tropes: list[str] = Field(default_factory=list, description="List of unique tropes present in this asset.")
    notes: str | None = Field(default=None, description="Human-readable notes about this asset.")


class LibraryIndex(BaseModel):
    """Searchable index of all library assets."""

    assets: list[AssetMeta] = Field(default_factory=list)
    updated_at: str | None = None


# ---------- Slug / naming helpers -------------------------------------------


def _slug(text: str) -> str:
    """Convert a filename or title to a clean slug."""
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "extracted"


def _title_from_slug(slug: str) -> str:
    """Best-effort title from a slug: poe_cask -> Poe Cask."""
    return slug.replace("_", " ").title()


# ---------- Library ---------------------------------------------------------


DEFAULT_LIBRARY_DIR = Path("library")


@dataclass
class AssetLibrary:
    """A persistent, file-backed asset library."""

    root: Path

    @classmethod
    def open(cls, root: Path | None = None) -> "AssetLibrary":
        root = root or DEFAULT_LIBRARY_DIR
        root.mkdir(parents=True, exist_ok=True)
        return cls(root=root)

    # ---- directories -------------------------------------------------------

    @property
    def styles_dir(self) -> Path:
        d = self.root / "styles"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def per_author_styles_dir(self) -> Path:
        d = self.styles_dir / "per-author"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def worlds_dir(self) -> Path:
        d = self.root / "worlds"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def beat_templates_dir(self) -> Path:
        d = self.root / "beat_templates"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    # ---- index management --------------------------------------------------

    def _load_index(self) -> LibraryIndex:
        if self.index_path.exists():
            return LibraryIndex.model_validate_json(self.index_path.read_text())
        return LibraryIndex()

    def _save_index(self, index: LibraryIndex) -> None:
        index.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self.index_path.write_text(index.model_dump_json(indent=2))

    def _upsert_meta(self, meta: AssetMeta) -> None:
        """Add or replace an asset's metadata in the index."""
        index = self._load_index()
        index.assets = [a for a in index.assets if not (a.type == meta.type and a.asset_id == meta.asset_id)]
        index.assets.append(meta)
        self._save_index(index)

    # ---- deposit methods ---------------------------------------------------

    def deposit_style(
        self,
        style,  # StyleProfile
        *,
        asset_id: str | None = None,
        meta: AssetMeta | None = None,
        source_file: str | None = None,
        source_author: str | None = None,
        shape: str | None = None,
        analysis_dir: str | None = None,
        genre: list[str] | None = None,
        structural_template: str | None = None,
        tropes: list[str] | None = None,
        notes: str | None = None,
    ) -> Path:
        """Deposit a StyleProfile into the library with metadata."""
        from .schemas import StyleProfile

        if asset_id is None:
            asset_id = _slug(style.name)
        style_out = style.model_copy(update={"id": f"style_{asset_id}", "name": asset_id})
        path = self.styles_dir / f"{asset_id}.yaml"

        if meta is None:
            meta = AssetMeta(
                type="style",
                asset_id=asset_id,
                source_story=_title_from_slug(asset_id),
                source_file=source_file,
                source_author=source_author,
                shape=shape,
                extracted_from=analysis_dir,
                extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                genre=genre or [],
                structural_template=structural_template,
                tropes=tropes or [],
                notes=notes,
            )

        # Write style YAML with _meta header
        data = style_out.model_dump()
        data["_meta"] = meta.model_dump(exclude_none=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        self._upsert_meta(meta)
        return path

    def deposit_author_style(self, style, author_name: str) -> Path:
        """Deposit a consolidated author style profile."""
        from .schemas import StyleProfile

        author_id = _slug(author_name)
        style_out = style.model_copy(update={"id": f"style_author_{author_id}", "name": f"author_{author_id}"})
        path = self.per_author_styles_dir / f"{author_id}.yaml"

        meta = AssetMeta(
            type="style",
            asset_id=f"author_{author_id}",
            source_story=f"Corpus: {author_name}",
            source_author=author_name,
            extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            notes=f"Consolidated composite style profile for {author_name}.",
        )

        data = style_out.model_dump()
        data["_meta"] = meta.model_dump(exclude_none=True)
        path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
        self._upsert_meta(meta)
        return path

    def deposit_world(
        self,
        world,  # WorldSeed
        *,
        asset_id: str,
        meta: AssetMeta | None = None,
        source_file: str | None = None,
        source_author: str | None = None,
        shape: str | None = None,
        analysis_dir: str | None = None,
        genre: list[str] | None = None,
        structural_template: str | None = None,
        tropes: list[str] | None = None,
        notes: str | None = None,
    ) -> Path:
        """Deposit a WorldSeed into the library with metadata."""
        path = self.worlds_dir / f"{asset_id}.json"

        if meta is None:
            meta = AssetMeta(
                type="world",
                asset_id=asset_id,
                source_story=_title_from_slug(asset_id),
                source_file=source_file,
                source_author=source_author,
                shape=shape,
                extracted_from=analysis_dir,
                extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                genre=genre or [],
                structural_template=structural_template,
                tropes=tropes or [],
                notes=notes,
            )

        data = json.loads(world.model_dump_json())
        data["_meta"] = meta.model_dump(exclude_none=True)
        path.write_text(json.dumps(data, indent=2))
        self._upsert_meta(meta)
        return path

    def deposit_beats(
        self,
        beats,  # BeatPlan
        *,
        asset_id: str,
        meta: AssetMeta | None = None,
        source_file: str | None = None,
        source_author: str | None = None,
        shape: str | None = None,
        analysis_dir: str | None = None,
        genre: list[str] | None = None,
        structural_template: str | None = None,
        tropes: list[str] | None = None,
        notes: str | None = None,
    ) -> Path:
        """Deposit a BeatPlan into the library with metadata."""
        n = len(beats.beats)
        filename = f"{asset_id}_{n}beat.json"
        path = self.beat_templates_dir / filename

        beat_asset_id = f"{asset_id}_{n}beat"
        if meta is None:
            meta = AssetMeta(
                type="beat_template",
                asset_id=beat_asset_id,
                source_story=_title_from_slug(asset_id),
                source_file=source_file,
                source_author=source_author,
                shape=shape,
                extracted_from=analysis_dir,
                extracted_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                genre=genre or [],
                structural_template=structural_template,
                tropes=tropes or [],
                notes=notes,
            )

        data = json.loads(beats.model_dump_json())
        data["_meta"] = meta.model_dump(exclude_none=True)
        path.write_text(json.dumps(data, indent=2))
        self._upsert_meta(meta)
        return path

    # ---- deposit all from an analysis --------------------------------------

    def deposit_analysis(
        self,
        analysis,  # StoryAnalysis
        *,
        source_author: str | None = None,
    ) -> dict[str, Path]:
        """Deposit all extractable assets from a StoryAnalysis.

        Returns a dict of {type: path} for each deposited asset.
        """
        asset_id = _slug(Path(analysis.source).stem)
        analysis_dir = None  # could be wired from store
        deposited: dict[str, Path] = {}

        genre = analysis.classification.genre if getattr(analysis, "classification", None) else []
        structural_template = analysis.classification.structural_template if getattr(analysis, "classification", None) else None
        notes = analysis.classification.notes if getattr(analysis, "classification", None) else None

        tropes = []
        if getattr(analysis, "beats", None) and analysis.beats:
            seen_tropes = set()
            for b in analysis.beats.beats:
                if getattr(b, "tropes", None):
                    seen_tropes.update(b.tropes)
            tropes = sorted(list(seen_tropes))

        common = dict(
            source_file=analysis.source,
            source_author=source_author,
            shape=analysis.shape.best,
            analysis_dir=analysis_dir,
            genre=genre,
            structural_template=structural_template,
            tropes=tropes,
            notes=notes,
        )

        # Always deposit style (it's always present)
        deposited["style"] = self.deposit_style(analysis.style, asset_id=asset_id, **common)

        # Deposit world and beats if present (--deep)
        if analysis.world is not None:
            deposited["world"] = self.deposit_world(
                analysis.world, asset_id=asset_id, **common
            )
        if analysis.beats is not None:
            deposited["beats"] = self.deposit_beats(
                analysis.beats, asset_id=asset_id, **common
            )

        return deposited

    # ---- query methods -----------------------------------------------------

    def list_assets(
        self,
        asset_type: AssetType | None = None,
        genre: str | None = None,
        author: str | None = None,
        tag: str | None = None,
        shape: str | None = None,
        trope: str | None = None,
    ) -> list[AssetMeta]:
        """List assets with optional filters."""
        index = self._load_index()
        results = index.assets

        if asset_type is not None:
            results = [a for a in results if a.type == asset_type]
        if genre is not None:
            genre_lower = genre.lower()
            results = [a for a in results if any(g.lower() == genre_lower for g in a.genre)]
        if author is not None:
            author_lower = author.lower()
            results = [
                a for a in results
                if a.source_author and author_lower in a.source_author.lower()
            ]
        if tag is not None:
            tag_lower = tag.lower()
            results = [a for a in results if any(t.lower() == tag_lower for t in a.tags)]
        if shape is not None:
            shape_lower = shape.lower()
            results = [a for a in results if a.shape and a.shape.lower() == shape_lower]
        if trope is not None:
            trope_lower = trope.lower()
            results = [a for a in results if any(tr.lower() == trope_lower for tr in a.tropes)]

        return results

    def get_asset(self, asset_type: AssetType, asset_id: str) -> AssetMeta | None:
        """Get a specific asset's metadata."""
        index = self._load_index()
        for a in index.assets:
            if a.type == asset_type and a.asset_id == asset_id:
                return a
        return None

    def search(self, query: str) -> list[AssetMeta]:
        """Search all assets by keyword across all text fields."""
        index = self._load_index()
        q = query.lower()
        results = []
        for a in index.assets:
            searchable = " ".join(
                filter(None, [
                    a.asset_id, a.source_story, a.source_author, a.source_era,
                    a.shape, a.notes, " ".join(a.tags), " ".join(a.genre),
                    " ".join(a.tropes),
                ])
            ).lower()
            if q in searchable:
                results.append(a)
        return results

    def asset_path(self, asset_type: AssetType, asset_id: str) -> Path | None:
        """Get the file path for an asset."""
        if asset_type == "style":
            p = self.styles_dir / f"{asset_id}.yaml"
        elif asset_type == "world":
            p = self.worlds_dir / f"{asset_id}.json"
        elif asset_type == "beat_template":
            # beat templates include beat count in filename
            for f in self.beat_templates_dir.iterdir():
                if f.stem.startswith(asset_id):
                    return f
            return None
        else:
            return None
        return p if p.exists() else None

    # ---- load methods (returns the Pydantic model, stripping _meta) --------

    def load_style(self, asset_id: str):
        """Load a StyleProfile from the library by asset_id."""
        from .schemas import StyleProfile

        p = self.styles_dir / f"{asset_id}.yaml"
        if not p.exists():
            raise FileNotFoundError(f"style '{asset_id}' not in library ({p})")
        data = yaml.safe_load(p.read_text())
        data.pop("_meta", None)
        return StyleProfile.model_validate(data)

    def load_world(self, asset_id: str):
        """Load a WorldSeed from the library by asset_id."""
        from .schemas import WorldSeed

        p = self.worlds_dir / f"{asset_id}.json"
        if not p.exists():
            raise FileNotFoundError(f"world '{asset_id}' not in library ({p})")
        data = json.loads(p.read_text())
        data.pop("_meta", None)
        return WorldSeed.model_validate(data)

    def load_beats(self, asset_id: str):
        """Load a BeatPlan from the library by asset_id."""
        from .schemas import BeatPlan

        for f in self.beat_templates_dir.iterdir():
            if f.stem.startswith(asset_id) and f.suffix == ".json":
                data = json.loads(f.read_text())
                data.pop("_meta", None)
                return BeatPlan.model_validate(data)
        raise FileNotFoundError(f"beat_template '{asset_id}' not in library")
