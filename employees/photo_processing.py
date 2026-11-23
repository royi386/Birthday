from functools import lru_cache
from io import BytesIO

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError


@lru_cache(maxsize=1)
def _face_detector():
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    if cascade.empty():
        raise RuntimeError("OpenCV's frontal face detector could not be loaded.")
    return cascade


def centered_face_jpeg(photo):
    """Return a square JPEG crop centered on the largest detected face, or None."""
    try:
        photo.seek(0)
        with Image.open(photo) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError):
        return None
    finally:
        try:
            photo.seek(0)
        except (AttributeError, OSError):
            pass

    width, height = image.size
    if not width or not height:
        return None

    max_detection_dimension = 1400
    detection_scale = min(1.0, max_detection_dimension / max(width, height))
    detection_image = image
    if detection_scale < 1.0:
        detection_image = image.resize(
            (round(width * detection_scale), round(height * detection_scale)),
            Image.Resampling.LANCZOS,
        )
    rgb = np.asarray(detection_image)
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    faces = _face_detector().detectMultiScale(
        gray,
        scaleFactor=1.1,
        minNeighbors=5,
        minSize=(30, 30),
    )
    if len(faces) == 0:
        return None

    face_x, face_y, face_width, face_height = max(
        faces, key=lambda box: int(box[2]) * int(box[3])
    )
    center_x = (face_x + face_width / 2) / detection_scale
    center_y = (face_y + face_height / 2) / detection_scale
    face_size = max(face_width, face_height) / detection_scale
    crop_size = max(96, round(face_size * 2.7))
    crop_size = min(crop_size, max(width, height))

    left = round(center_x - crop_size / 2)
    top = round(center_y - crop_size / 2)
    right = left + crop_size
    bottom = top + crop_size
    pad_left = max(0, -left)
    pad_top = max(0, -top)
    pad_right = max(0, right - width)
    pad_bottom = max(0, bottom - height)

    pixels = np.asarray(image)
    if pad_left or pad_top or pad_right or pad_bottom:
        edge_pixels = np.concatenate(
            (pixels[0], pixels[-1], pixels[:, 0], pixels[:, -1]), axis=0
        )
        edge_color = tuple(
            int(channel) for channel in np.median(edge_pixels, axis=0)
        )
        pixels = cv2.copyMakeBorder(
            pixels,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            cv2.BORDER_CONSTANT,
            value=edge_color,
        )
    crop = pixels[
        top + pad_top : top + pad_top + crop_size,
        left + pad_left : left + pad_left + crop_size,
    ]
    if crop.shape[0] != crop_size or crop.shape[1] != crop_size:
        return None

    output = BytesIO()
    Image.fromarray(crop).save(output, format="JPEG", quality=92, optimize=True)
    return output.getvalue()
