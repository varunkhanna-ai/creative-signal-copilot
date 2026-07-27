import pytest


@pytest.fixture
def sample_creative():
    return {
        "creative_id": "t3_001",
        "advertiser": "ExampleCo",
        "platform": "meta",
        "headline": "Glow in 7 days",
        "body_copy": "Our serum delivers results you can see.",
    }
