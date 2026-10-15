from dataclasses import dataclass


@dataclass
class Segment:
    start: float
    end: float
    text: str


@dataclass
class VideoMeta:
    id: str
    title: str
    uploader: str
    duration: int
    webpage_url: str
    extractor: str

    @property
    def duration_str(self) -> str:
        if not self.duration:
            return "unknown"
        return f"{self.duration // 60}:{self.duration % 60:02d}"
