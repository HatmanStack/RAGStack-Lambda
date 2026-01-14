from ragstack_common.storage import parse_s3_uri


def test_parse_s3_uri():
    bucket, key = parse_s3_uri("s3://my-bucket/path/to/file.pdf")
    assert bucket == "my-bucket"
    assert key == "path/to/file.pdf"
    print("✓ S3 URI parsing works")


def test_parse_s3_uri_root():
    bucket, key = parse_s3_uri("s3://my-bucket/")
    assert bucket == "my-bucket"
    assert key == ""
    print("✓ S3 URI parsing (root) works")


def test_parse_s3_uri_https_format():
    """Test parsing HTTPS S3 URLs returned by AWS Transcribe."""
    url = "https://s3.us-east-1.amazonaws.com/my-bucket/transcripts/doc-id/file.json"
    bucket, key = parse_s3_uri(url)
    assert bucket == "my-bucket"
    assert key == "transcripts/doc-id/file.json"
    print("✓ HTTPS S3 URL parsing works")


if __name__ == "__main__":
    test_parse_s3_uri()
    test_parse_s3_uri_root()
    test_parse_s3_uri_https_format()
    print("Storage utility tests passed!")
