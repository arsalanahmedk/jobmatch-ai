"""JobMatch AI — score how well a resume matches a job description."""

from .matcher import analyze, extract_keywords, extract_skills

__version__ = "1.0.0"

__all__ = ["analyze", "extract_skills", "extract_keywords", "__version__"]
