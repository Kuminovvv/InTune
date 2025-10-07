"""Utilities for turning files and folders into document chunks."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Iterable, List

import aiofiles
from pypdf import PdfReader

from .rag import DocumentChunk, chunk_text

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}


async def _read_text_file(path: Path) -> str:
    async with aiofiles.open(path, "r", encoding="utf-8", errors="ignore") as fh:
        return await fh.read()


def _read_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


async def _read_docx(path: Path) -> str:
    import docx  # type: ignore

    document = await asyncio.get_running_loop().run_in_executor(None, docx.Document, str(path))
    paragraphs = [para.text for para in document.paragraphs if para.text.strip()]
    return "\n".join(paragraphs)


async def _extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md", ".markdown"}:
        return await _read_text_file(path)
    if suffix == ".pdf":
        return await asyncio.get_running_loop().run_in_executor(None, _read_pdf, path)
    if suffix == ".docx":
        return await _read_docx(path)
    raise ValueError(f"Unsupported file type: {suffix}")


async def build_chunks(paths: Iterable[str], profile: str, embed_model: str) -> List[DocumentChunk]:
    """Produce document chunks for the provided files/folders."""

    logger.info("Building knowledge base chunks with embedding model %s", embed_model)
    tasks = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for file_path in path.rglob("*"):
                if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    tasks.append(_process_path(file_path, profile))
        elif path.suffix.lower() in SUPPORTED_EXTENSIONS:
            tasks.append(_process_path(path, profile))
        else:
            logger.warning("Skipping unsupported file: %s", path)
    chunks_nested = await asyncio.gather(*tasks)
    chunks: List[DocumentChunk] = [chunk for group in chunks_nested for chunk in group]
    logger.info("Generated %s chunks from %s inputs", len(chunks), len(paths))
    return chunks


async def _process_path(path: Path, profile: str) -> List[DocumentChunk]:
    text = await _extract_text(path)
    chunks = chunk_text(text)
    return [DocumentChunk(text=chunk, source_path=str(path), profile=profile, section=None) for chunk in chunks if chunk]


__all__ = ["build_chunks"]
