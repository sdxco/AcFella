"""
Project Management for AcFella

Manages rooms/projects so users can save and recall room configurations.
Data stored in-memory with optional JSON persistence.
"""

import os
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')


@dataclass
class Project:
    """A project representing a room or space."""
    id: str
    name: str
    description: str = ''
    room_type: str = 'mixing_mastering'
    geometry: Optional[Dict[str, Any]] = None
    tags: List[str] = field(default_factory=list)
    notes: str = ''
    created_at: str = ''
    updated_at: str = ''

    @property
    def volume(self) -> Optional[float]:
        if self.geometry:
            return self.geometry.get('volume')
        return None

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'room_type': self.room_type,
            'geometry': self.geometry,
            'tags': self.tags,
            'notes': self.notes,
            'volume': self.volume,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
        }


class ProjectManager:
    """Manages projects with in-memory store and JSON persistence."""

    def __init__(self):
        self._projects: Dict[str, Project] = {}
        self._load()
        if not self._projects:
            self._seed()

    def _data_path(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        return os.path.join(DATA_DIR, 'projects.json')

    def _load(self):
        path = self._data_path()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                for pd in data:
                    p = Project(**pd)
                    self._projects[p.id] = p
            except Exception:
                pass

    def _save(self):
        path = self._data_path()
        with open(path, 'w') as f:
            json.dump([p.to_dict() for p in self._projects.values()], f, indent=2)

    def _seed(self):
        """Create Sean's Studio as the default project with real measurements."""
        now = datetime.utcnow().isoformat()
        self._projects['seans-studio'] = Project(
            id='seans-studio',
            name="Sean's Studio",
            description='Mixing and mastering room with asymmetric walls, sloped ceiling, and structural beam.',
            room_type='mixing_mastering',
            geometry={
                'length': 4.20,
                'width': 2.83,
                'height': 2.41,
                'volume': round(4.20 * 2.83 * 2.41, 2),
                'surface_area': round(2*(4.20*2.83 + 4.20*2.41 + 2.83*2.41), 2),
                'left_wall_length': 4.17,
                'right_wall_length': 4.23,
                'front_wall_width': 2.83,
                'rear_wall_width': 2.83,
                'ceiling_height_left': 2.51,
                'ceiling_height_right': 2.31,
                'walls': [
                    {
                        'name': 'Front Wall',
                        'materials': [{'type': 'drywall', 'thickness_mm': 12.5}],
                        'openings': [],
                    },
                    {
                        'name': 'Rear Wall',
                        'materials': [{'type': 'drywall', 'thickness_mm': 12.5}],
                        'openings': [],
                    },
                    {
                        'name': 'Left Wall',
                        'materials': [
                            {'type': 'concrete_block', 'notes': 'structural'},
                            {'type': 'drywall', 'thickness_mm': 12.5, 'notes': 'on top'},
                        ],
                        'openings': [{'type': 'door', 'width_m': 0.90, 'height_m': 2.0}],
                    },
                    {
                        'name': 'Right Wall',
                        'materials': [
                            {'type': 'concrete_block', 'notes': 'structural'},
                            {'type': 'pine_wood_cladding', 'notes': '3cm air gap behind'},
                        ],
                        'openings': [{'type': 'window', 'width_m': 1.0, 'height_m': 1.0}],
                    },
                ],
                'beams': [
                    {
                        'width_m': 0.22,
                        'depth_left_m': 0.24,
                        'depth_right_m': 0.10,
                        'height_under_m': 2.21,
                        'distance_from_left_wall_m': 1.75,
                        'distance_from_right_wall_m': 0.86,
                        'material': 'reinforced_concrete',
                    }
                ],
                'ceilings': [
                    {
                        'name': 'Main ceiling',
                        'material': 'drywall',
                        'height': 2.41,
                        'slope_direction': 'left_to_right',
                        'height_left': 2.51,
                        'height_right': 2.31,
                        'notes': 'Sloped ceiling, higher on left side',
                    }
                ],
                'floor': {
                    'material': 'concrete_slab',
                    'covering': 'carpet',
                    'notes': 'Concrete slab with carpet covering',
                },
            },
            tags=['mixing', 'mastering', 'asymmetric', 'sloped-ceiling'],
            notes='Asymmetric room with structural beam dividing the ceiling. Left wall is 4.17m, right wall is 4.23m. Ceiling slopes from 2.51m (left) to 2.31m (right).',
            created_at=now,
            updated_at=now,
        )
        self._save()

    def list_all(self) -> List[Project]:
        return list(self._projects.values())

    def get(self, project_id: str) -> Optional[Project]:
        return self._projects.get(project_id)

    def create(self, name: str, description: str = '', room_type: str = 'mixing_mastering',
               geometry: dict = None, tags: list = None, notes: str = '') -> Project:
        now = datetime.utcnow().isoformat()
        pid = str(uuid.uuid4())[:8]
        p = Project(
            id=pid, name=name, description=description, room_type=room_type,
            geometry=geometry, tags=tags or [], notes=notes,
            created_at=now, updated_at=now,
        )
        self._projects[pid] = p
        self._save()
        return p

    def update(self, project_id: str, updates: dict) -> Optional[Project]:
        p = self._projects.get(project_id)
        if not p:
            return None
        for key in ('name', 'description', 'room_type', 'geometry', 'tags', 'notes'):
            if key in updates:
                setattr(p, key, updates[key])
        p.updated_at = datetime.utcnow().isoformat()
        self._save()
        return p

    def delete(self, project_id: str) -> bool:
        if project_id in self._projects:
            del self._projects[project_id]
            self._save()
            return True
        return False
