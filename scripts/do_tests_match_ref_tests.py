#!/usr/bin/env python3

import glob
import hashlib
import os
import tarfile
import tempfile
import urllib.request


def download_latest_tests(output_dir):
    """
    Download the authoritative Sila consensus-spec-tests main tree.

    Sila reference tests are tracked directly in sila-chain/consensus-spec-tests
    rather than published as GitHub release assets.
    """
    file_name = os.path.join(output_dir, "consensus-spec-tests-main.tar.gz")
    download_url = (
        "https://github.com/sila-chain/consensus-spec-tests/"
        "archive/refs/heads/main.tar.gz"
    )

    print(f"Downloading: {download_url}")
    with urllib.request.urlopen(download_url) as download_response:
        with open(file_name, "wb") as file:
            file.write(download_response.read())

    return file_name


def extract_tarfile(tests_tarfile, temp_dir):
    """
    The release artifact is a tar.gz file, this will extract it.
    """
    extract_dir = os.path.join(temp_dir, tests_tarfile + ".extracted")
    os.makedirs(extract_dir, exist_ok=True)
    with tarfile.open(tests_tarfile, "r:gz") as tar:
        tar.extractall(path=extract_dir)
    return extract_dir


def find_data_yaml_files(root_dir):
    """
    Get a list of all of the data.yaml files in the directory.
    """
    pattern = os.path.join(root_dir, "**", "data.yaml")
    data_yaml_files = glob.glob(pattern, recursive=True)
    return [
        f
        for f in data_yaml_files
        if "/kzg-sila-mainnet/" in f or "/kzg-sila_mainnet/" in f
    ]


def sha256_hash_file(file_path):
    """
    Get the SHA-256 hash for a file.

    GitHub source archives contain Git LFS pointer files rather than the
    corresponding large objects. For those pointers, the recorded SHA-256 OID
    is the content hash of the authoritative object, so compare against that
    instead of hashing the pointer text itself.
    """
    with open(file_path, "rb") as f:
        prefix = f.read(256)
        if prefix.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
            for line in prefix.splitlines():
                if line.startswith(b"oid sha256:"):
                    return line.removeprefix(b"oid sha256:").decode("ascii")

    sha256_hash = hashlib.sha256()
    with open(file_path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


def create_normalized_file_to_hash_dict(files):
    """
    This creates a dictionary of normalized_path:sha256hash. By normalized, we
    mean the parts of the path which are different between local/reference
    tests are removed. If both test directories contain the same tests, these
    dictionaries are expected to be the same. If there is a missing/extra test,
    it will be caught.
    """
    d = {}
    for file in files:
        parts = file.split(os.path.sep)
        test_root = (
            "kzg-sila-mainnet"
            if "kzg-sila-mainnet" in parts
            else "kzg-sila_mainnet"
        )
        index = parts.index(test_root) - 1
        normalized_parts = parts[index:]
        normalized_parts[1] = "kzg-sila-mainnet"
        key = os.path.sep.join(normalized_parts)
        d[key] = sha256_hash_file(file)
    return d


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        local_tests_dir = os.path.join(script_dir, "../tests")
        local_tests = find_data_yaml_files(local_tests_dir)
        local_dict = create_normalized_file_to_hash_dict(local_tests)

        tests_tarfile = download_latest_tests(temp_dir)
        reference_tests_dir = extract_tarfile(tests_tarfile, temp_dir)
        reference_tests = find_data_yaml_files(reference_tests_dir)
        reference_dict = create_normalized_file_to_hash_dict(reference_tests)

        assert len(local_dict) == len(reference_dict)
        for key in reference_dict:
            assert local_dict[key] == reference_dict[key], key

        print("The local tests match the reference tests")
