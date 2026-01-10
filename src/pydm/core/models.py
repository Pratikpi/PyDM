from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional
import json

class SegmentStatus(Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

@dataclass
class Segment:
    id: int
    start: int
    end: int
    status: SegmentStatus = SegmentStatus.PENDING
    downloaded_bytes: int = 0

    def to_dict(self):
        data = asdict(self)
        data['status'] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data):
        data['status'] = SegmentStatus(data['status'])
        return cls(**data)

@dataclass
class DownloadState:
    url: str
    output_file: str
    total_size: int
    segments: List[Segment]
    
    def to_json(self) -> str:
        return json.dumps({
            'url': self.url,
            'output_file': self.output_file,
            'total_size': self.total_size,
            'segments': [s.to_dict() for s in self.segments]
        }, indent=4)

    @classmethod
    def from_json(cls, json_str: str) -> 'DownloadState':
        data = json.loads(json_str)
        segments = [Segment.from_dict(s) for s in data['segments']]
        return cls(
            url=data['url'],
            output_file=data['output_file'],
            total_size=data['total_size'],
            segments=segments
        )
