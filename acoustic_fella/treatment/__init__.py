"""
Treatment modules for Acoustic Fella
"""

from .recommendation_engine import (
    TreatmentRecommendationEngine,
    TreatmentPlan,
    TreatmentItem,
    generate_quick_recommendations
)
from .speaker_placement import (
    SpeakerPlacementOptimizer,
    SpeakerPlacement,
    quick_speaker_placement
)
from .panel_calculator import (
    PanelConstructionCalculator,
    PanelSpec,
    get_panel_designs_for_room
)

__all__ = [
    'TreatmentRecommendationEngine',
    'TreatmentPlan',
    'TreatmentItem',
    'generate_quick_recommendations',
    'SpeakerPlacementOptimizer',
    'SpeakerPlacement',
    'quick_speaker_placement',
    'PanelConstructionCalculator',
    'PanelSpec',
    'get_panel_designs_for_room'
]
