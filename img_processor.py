import cv2
import numpy as np
from typing import Union, Tuple


def format_frame_for_vlm(
    image_input: Union[str, np.ndarray], 
    target_size: Tuple[int, int] = (1024, 1024), 
    pad_color: Tuple[int, int, int] = (0, 0, 0) # Black Color Padding
) -> np.ndarray:
    """
    Resizes and letterboxes an image to a strict target size while preserving aspect ratio.
    Optimized for spatial computing and VLM ingestion.
    """
    # 1. Handle both file paths
    if isinstance(image_input, str):
        image: np = cv2.imread(image_input)
        if image is None:
            raise FileNotFoundError(f"Could not read image at {image_input}")
        else:
            image = image_input


    original_h, original_w = image.shape[:2]
    target_w, target_h = target_size

    # 2. Calculate the exact scaling factor to prevent any stretching
    scale: float = min(target_w / original_w, target_h / original_h)
    new_w, new_h = int(original_w * scale), int(original_h * scale)

    # 3. Resize the image
    resized_image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    # 4. Create the blank canvas (the letterbox background)
    canvas = np.full((target_h, target_w, 3), pad_color, dtype=np.uint8)


    # 5. Calculate center coordinates to paste the resized image
    x_offset: int = (target_w - new_w) // 2
    y_offset: int = (target_h - new_h) // 2

    # 6. Paste the image into the center of the canvas using rapid matrix slicing
    canvas[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = resized_image

    return canvas