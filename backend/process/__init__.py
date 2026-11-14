"""Process module for pothole detection"""

from .process import (
    process_image,
    process_video,
    update_report_with_location,
    get_model,
    model
)

__all__ = [
    'process_image',
    'process_video',
    'update_report_with_location',
    'get_model',
    'model'
]
