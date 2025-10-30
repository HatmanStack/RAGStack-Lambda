from .bedrock import BedrockClient


def test_backoff_calculation():
    client = BedrockClient(region="us-east-1")

    # Test exponential backoff
    backoff0 = client._calculate_backoff(0)
    backoff1 = client._calculate_backoff(1)
    backoff2 = client._calculate_backoff(2)

    # Should be approximately 2s, 4s, 8s (with jitter)
    assert 2.0 <= backoff0 <= 3.0
    assert 4.0 <= backoff1 <= 5.0
    assert 8.0 <= backoff2 <= 9.0

    print(f"✓ Backoff calculation works: {backoff0:.2f}s, {backoff1:.2f}s, {backoff2:.2f}s")


def test_metering_data():
    client = BedrockClient(region="us-east-1")

    # Initially empty
    assert client.get_metering_data() == {}
    print("✓ Metering data initialization works")


def test_client_initialization():
    # Test default region
    client1 = BedrockClient()
    assert client1.region == "us-east-1"

    # Test custom region
    client2 = BedrockClient(region="us-west-2")
    assert client2.region == "us-west-2"

    # Test retry settings
    assert client1.max_retries == 7
    assert client1.initial_backoff == 2
    assert client1.max_backoff == 300

    print("✓ Client initialization works")


if __name__ == "__main__":
    test_backoff_calculation()
    test_metering_data()
    test_client_initialization()
    print("Bedrock client tests passed!")
