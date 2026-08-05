from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_console.config import ROOT, settings


@dataclass
class KnowledgeHit:
    source: str
    content: str
    score: float


class KnowledgeBase:
    def __init__(self, knowledge_dir: Path | None = None) -> None:
        self.knowledge_dir = knowledge_dir or ROOT / "agent_console" / "rag_system" / "wiki"
        self._chunks = self._load_markdown_chunks()

    def search(self, query: str, k: int = 4) -> list[KnowledgeHit]:
        if not query.strip():
            return []
        return self._keyword_search(query, k=k)

    def _load_markdown_chunks(self) -> list[KnowledgeHit]:
        chunks: list[KnowledgeHit] = []
        for path in sorted(self.knowledge_dir.glob("*.md")):
            text = path.read_text(encoding="utf-8")
            current_title = path.name
            current_lines: list[str] = []
            for line in text.splitlines():
                if line.startswith("## ") and current_lines:
                    chunks.append(KnowledgeHit(source=current_title, content="\n".join(current_lines).strip(), score=0.0))
                    current_lines = []
                if line.startswith("#"):
                    current_title = f"{path.name}:{line.lstrip('#').strip()}"
                current_lines.append(line)
            if current_lines:
                chunks.append(KnowledgeHit(source=current_title, content="\n".join(current_lines).strip(), score=0.0))
        return [chunk for chunk in chunks if chunk.content]

    def _keyword_search(self, query: str, k: int) -> list[KnowledgeHit]:
        query_terms = {term.lower() for term in _tokenize(query)}
        scored: list[KnowledgeHit] = []
        for chunk in self._chunks:
            content_terms = [term.lower() for term in _tokenize(chunk.content)]
            if not content_terms:
                continue
            overlap = sum(1 for term in content_terms if term in query_terms)
            zh_overlap = sum(1 for char in query if char.strip() and char in chunk.content)
            score = overlap * 3 + zh_overlap / max(len(query), 1)
            if score > 0:
                scored.append(KnowledgeHit(source=chunk.source, content=chunk.content, score=round(score, 3)))
        return sorted(scored, key=lambda hit: hit.score, reverse=True)[:k]


def _tokenize(text: str) -> list[str]:
    return [token.strip(".,:;!?()[]{}<>\"'`").lower() for token in text.replace("/", " ").split() if token.strip()]

kb = KnowledgeBase()
