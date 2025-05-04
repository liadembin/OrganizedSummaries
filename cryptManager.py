import base64
import unittest
from termcolor import colored
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
import hashlib
from typing import Tuple, Optional
import pytest
PRINT_PLAIN = False
# import logging


def log_success(message):
    print(f"\033[32m{message}\033[0m")  # Green for success


def log_failure(message):
    print(f"\033[31m{message}\033[0m")  # Red for failure


class CryptManager:
    def __init__(self, rsa_key=None):
        self.rsa_key = RSA.generate(2048) if rsa_key is None else rsa_key
        self.rsa_cipher = PKCS1_OAEP.new(self.rsa_key)
        self.aes_key: Optional[bytes] = None

    def hash_pass(self, password: str, salt: bytes, paper: bytes) -> str:
        # encrypt using Sha256 and hashlib
        return hashlib.sha256(password.encode() + salt + paper).hexdigest()

    def encrypt_data(self, data: bytes) -> Tuple[bytes, bytes]:
        # encrypt using AES Cbc
        if self.aes_key is None:
            raise ValueError("AES Key is not set.")
        iv = get_random_bytes(16)
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        # print("IV: ", iv, "KEY: ", self.aes_key, "DATA: ", data)
        if PRINT_PLAIN:
            print("ENC(rypting)>>>", data)
        return aes_cipher.encrypt(pad(data, 16)), iv

    def generate_aes_key(self):
        self.aes_key = get_random_bytes(16)

    def decrypt_data(self, data: bytes, iv: bytes) -> bytes:
        if self.aes_key is None:
            raise ValueError("AES Key is not set.")
        # print("IV: ", iv, "KEY: ", self.aes_key, "DATA: ", data)
        if PRINT_PLAIN:
            print("DEC>>>", data)
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        return unpad(aes_cipher.decrypt(data), 16)

    def encrypt_rsa(self, data: bytes, public_key: bytes) -> bytes:
        """
        Encrypts data using the given RSA public key.
        """
        rsa_key = RSA.import_key(public_key)
        print(rsa_key.export_key() == public_key)
        rsa_ciph = PKCS1_OAEP.new(rsa_key)  # Public key for encryption
        return rsa_ciph.encrypt(data)

    def decrypt_rsa(self, data: bytes) -> bytes:
        """
        Decrypts data using the RSA private key.
        """
        return self.rsa_cipher.decrypt(data)

    def generate_random_bytes(self, length: int) -> bytes:
        return get_random_bytes(length)

    def check_hash(
        self, password: str, hashed_password: bytes, salt: bytes, paper: bytes
    ) -> bool:
        return hashed_password == self.hash_pass(password, salt, paper)

    def get_public_key(self) -> str:
        return base64.b64encode(self.rsa_key.publickey().export_key()).decode()

@pytest.fixture
def crypt_manager():
    """Fixture to create a fresh CryptManager instance for each test."""
    return CryptManager()


@pytest.fixture
def sample_data():
    """Fixture to provide common test data."""
    return {
        "password": "password123",
        "salt": get_random_bytes(16),
        "paper": get_random_bytes(16),
        "data": b"Secret data"
    }


class TestHashFunctions:
    """Tests for password hashing functions."""

    def test_hash_pass_consistent(self, crypt_manager, sample_data):
        """Test that hash_pass produces consistent results with same inputs."""
        hashed1 = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        hashed2 = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        assert hashed1 == hashed2, "Hash function should be deterministic"

    def test_hash_pass_different_with_different_inputs(self, crypt_manager, sample_data):
        """Test that hash_pass produces different results with different inputs."""
        hashed1 = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        # Different password
        hashed2 = crypt_manager.hash_pass(
            "different_password", 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        assert hashed1 != hashed2, "Different passwords should produce different hashes"

        # Different salt
        different_salt = get_random_bytes(16)
        hashed3 = crypt_manager.hash_pass(
            sample_data["password"], 
            different_salt, 
            sample_data["paper"]
        )
        
        assert hashed1 != hashed3, "Different salts should produce different hashes"

        # Different paper
        different_paper = get_random_bytes(16)
        hashed4 = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            different_paper
        )
        
        assert hashed1 != hashed4, "Different papers should produce different hashes"

    def test_check_hash_valid(self, crypt_manager, sample_data):
        """Test that check_hash validates correct passwords."""
        hashed = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        assert crypt_manager.check_hash(
            sample_data["password"], 
            hashed, 
            sample_data["salt"], 
            sample_data["paper"]
        ), "check_hash should return True for valid password"

    def test_check_hash_invalid(self, crypt_manager, sample_data):
        """Test that check_hash rejects wrong passwords."""
        hashed = crypt_manager.hash_pass(
            sample_data["password"], 
            sample_data["salt"], 
            sample_data["paper"]
        )
        
        assert not crypt_manager.check_hash(
            "wrong_password", 
            hashed, 
            sample_data["salt"], 
            sample_data["paper"]
        ), "check_hash should return False for invalid password"


class TestAESEncryption:
    """Tests for AES encryption functions."""

    def test_generate_aes_key(self, crypt_manager):
        """Test that generate_aes_key creates a valid key."""
        crypt_manager.generate_aes_key()
        assert crypt_manager.aes_key is not None, "AES key should be set"
        assert len(crypt_manager.aes_key) == 16, "AES key should be 16 bytes"

    def test_encrypt_decrypt_data(self, crypt_manager, sample_data):
        """Test AES encryption and decryption cycle."""
        crypt_manager.generate_aes_key()
        encrypted_data, iv = crypt_manager.encrypt_data(sample_data["data"])
        
        # Verify encrypted data is different from original
        assert encrypted_data != sample_data["data"], "Encrypted data should differ from original"
        
        # Verify decryption returns original data
        decrypted_data = crypt_manager.decrypt_data(encrypted_data, iv)
        assert decrypted_data == sample_data["data"], "Decrypted data should match original"

    def test_encrypt_data_no_key(self, crypt_manager, sample_data):
        """Test that encrypt_data raises ValueError when AES key is not set."""
        with pytest.raises(ValueError, match="AES Key is not set."):
            crypt_manager.encrypt_data(sample_data["data"])

    def test_decrypt_data_no_key(self, crypt_manager, sample_data):
        """Test that decrypt_data raises ValueError when AES key is not set."""
        iv = get_random_bytes(16)
        with pytest.raises(ValueError, match="AES Key is not set."):
            crypt_manager.decrypt_data(sample_data["data"], iv)


class TestRSAEncryption:
    """Tests for RSA encryption functions."""

    def test_rsa_encryption_decryption(self, crypt_manager, sample_data):
        """Test RSA encryption and decryption cycle."""
        public_key = crypt_manager.rsa_key.publickey().export_key()
        encrypted_data = crypt_manager.encrypt_rsa(sample_data["data"], public_key)
        
        # Verify encrypted data is different from original
        assert encrypted_data != sample_data["data"], "RSA encrypted data should differ from original"
        
        # Verify decryption returns original data
        decrypted_data = crypt_manager.decrypt_rsa(encrypted_data)
        assert decrypted_data == sample_data["data"], "RSA decrypted data should match original"

    def test_encrypt_rsa_invalid_key(self, crypt_manager, sample_data):
        """Test that encrypt_rsa raises an error with invalid key."""
        invalid_key = b"invalid_key_data"
        with pytest.raises(ValueError):
            crypt_manager.encrypt_rsa(sample_data["data"], invalid_key)

    def test_get_public_key(self, crypt_manager):
        """Test that get_public_key returns a valid base64 encoded key."""
        public_key = crypt_manager.get_public_key()
        
        # Verify it's a non-empty string
        assert isinstance(public_key, str), "Public key should be a string"
        assert public_key, "Public key should not be empty"
        
        # Verify it can be decoded as base64
        try:
            decoded = base64.b64decode(public_key)
            assert decoded, "Decoded public key should not be empty"
        except Exception as e:
            pytest.fail(f"Failed to decode public key as base64: {e}")


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_generate_random_bytes(self, crypt_manager):
        """Test generate_random_bytes produces correct length output."""
        lengths = [8, 16, 32, 64]
        
        for length in lengths:
            random_bytes = crypt_manager.generate_random_bytes(length)
            assert len(random_bytes) == length, f"Random bytes should be {length} bytes long"
            
            # Generate another set and verify they're different (extremely unlikely to be the same)
            another_random = crypt_manager.generate_random_bytes(length)
            assert random_bytes != another_random, "Random bytes should be different on each call"

