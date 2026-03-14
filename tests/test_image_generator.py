from unittest.mock import patch, MagicMock, PropertyMock
from PIL import Image
import io

from image_generator import generate_image, _resize_to_square


def test_generate_image_returns_resized_png():
    """generate_image should call SD Turbo and return 1024x1024 PNG bytes."""
    # Create a fake 512x512 image as if the pipeline returned it
    fake_img = Image.new("RGB", (512, 512), color=(255, 0, 128))

    mock_pipeline = MagicMock()
    mock_pipeline.return_value.images = [fake_img]

    with patch("image_generator._get_pipeline", return_value=mock_pipeline):
        result = generate_image("test prompt")

    # Verify pipeline was called with the prompt
    mock_pipeline.assert_called_once()
    call_kwargs = mock_pipeline.call_args[1]
    assert call_kwargs["prompt"] == "test prompt"
    assert call_kwargs["guidance_scale"] == 0.0

    # Verify result is 1024x1024 PNG
    img = Image.open(io.BytesIO(result))
    assert img.size == (1024, 1024)


def test_resize_to_square_crops_and_resizes():
    """Non-square images should be center-cropped then resized."""
    rect_img = Image.new("RGB", (800, 600), color=(0, 255, 0))
    result = _resize_to_square(rect_img, 1024)
    img = Image.open(io.BytesIO(result))
    assert img.size == (1024, 1024)
