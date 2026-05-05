"""Figure extraction pipeline for SPBE RAG ingestion."""
from app.core.ingestion.figures.types import FigureExtraction, FIGURE_TYPES
from app.core.ingestion.figures.processor import process_figures

__all__ = ["FigureExtraction", "FIGURE_TYPES", "process_figures"]
