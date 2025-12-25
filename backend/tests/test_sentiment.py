import pytest
import io
from unittest.mock import patch

pytestmark = pytest.mark.sentiment  # markiere alle tests in dieser datei als "sentiment"-tests

def create_dummy_image():
    return ("test.jpg", io.BytesIO(b"fake_image_content"), "image/jpeg")

def test_create_post_blocks_negative_sentiment(client):
    with patch("simple_social_backend.api.check_sentiment_rpc", return_value="Negative"):
        response = client.post(
            "/posts",
            data={"text": "I hate everything", "user": "grumpy_cat"},
            files={"image": create_dummy_image()},
        )
    assert response.status_code == 400
    assert "Only Positive/Neutral vibes allowed" in response.json()["detail"]

def test_create_post_allows_positive_sentiment(client):
    with patch("simple_social_backend.api.check_sentiment_rpc", return_value="Positive"), \
         patch("simple_social_backend.api.publish_image_resize") as mock_resize:
        response = client.post(
            "/posts",
            data={"text": "I love this app!", "user": "happy_dog"},
            files={"image": create_dummy_image()},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["text"] == "I love this app!"
    assert data["user"] == "happy_dog"
    mock_resize.assert_called_once()
