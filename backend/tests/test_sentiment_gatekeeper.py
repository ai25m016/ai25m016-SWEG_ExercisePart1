import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from simple_social_backend.api import app 

# Initialize TestClient
client = TestClient(app)

# Helper to create a dummy image for upload
def create_dummy_image():
    return (
        "test.jpg", 
        io.BytesIO(b"fake_image_content"), 
        "image/jpeg"
    )

def test_create_post_blocks_negative_sentiment():
    """
    Test ensuring that a 'Negative' response from the AI blocks the post (HTTP 400).
    """
    # We patch 'check_sentiment_rpc' inside api.py to return "Negative"
    # This bypasses RabbitMQ completely!
    with patch("simple_social_backend.api.check_sentiment_rpc", return_value="Negative"):
        
        response = client.post(
            "/posts",
            data={"text": "I hate everything", "user": "grumpy_cat"},
            files={"image": create_dummy_image()}
        )

        # Assertions
        assert response.status_code == 400
        assert "Only Positive/Neutral vibes allowed" in response.json()["detail"]

def test_create_post_allows_positive_sentiment():
    """
    Test ensuring that a 'Positive' response allows the post (HTTP 200).
    """
    # 1. Mock Sentiment to return "Positive"
    # 2. ALSO Mock Image Resize (so we don't try to connect to RabbitMQ for resizing)
    with patch("simple_social_backend.api.check_sentiment_rpc", return_value="Positive"), \
         patch("simple_social_backend.api.publish_image_resize") as mock_resize:
        
        response = client.post(
            "/posts",
            data={"text": "I love this app!", "user": "happy_dog"},
            files={"image": create_dummy_image()}
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["text"] == "I love this app!"
        assert data["user"] == "happy_dog"
        
        # Verify that the image resize event was actually triggered
        mock_resize.assert_called_once()
