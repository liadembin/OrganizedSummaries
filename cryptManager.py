import base64
import unittest
from termcolor import colored
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES, PKCS1_OAEP
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import pad, unpad
from base64 import b64encode, b64decode
import os
import hashlib
from typing import Tuple, Optional

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
            raise ValueError("AES key is not set.")
        iv = get_random_bytes(16)
        aes_cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        # print("IV: ", iv, "KEY: ", self.aes_key, "DATA: ", data)
        print("ENC(rypting)>>>", data)
        return aes_cipher.encrypt(pad(data, 16)), iv

    def generate_aes_key(self):
        self.aes_key = get_random_bytes(16)

    def decrypt_data(self, data: bytes, iv: bytes) -> bytes:
        if self.aes_key is None:
            raise ValueError("AES Key is not set.")
        # print("IV: ", iv, "KEY: ", self.aes_key, "DATA: ", data)
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


def run_test_case(description, func, expected_success, *args, **kwargs):
    """
    Runs a test case and prints the result in color.
    If `expected_success` is True, it checks for success.
    If `expected_success` is False, it expects a failure.
    """
    try:
        print(colored(f"Running: {description}", "blue"))
        result = func(*args, **kwargs)

        if expected_success:
            print(colored(f"✅ PASS: {description}", "green"))
            print(f"Result: {result}\n")
        else:
            print(colored(f"❌ FAIL: {description} (Unexpected success)", "red"))
            print(f"Result: {result}\n")

    except Exception as e:
        if expected_success:
            print(colored(f"❌ FAIL: {description}", "red"))
            print("Error:", traceback.format_exc())
        else:
            print(colored(f"✅ PASS: {description} (Expected failure)", "green"))
        print()


class TestCryptManager(unittest.TestCase):
    def setUp(self):
        # This will run before each test
        self.manager = CryptManager()

    def test_hash_pass_valid(self):
        password = "password123"
        salt = get_random_bytes(16)
        paper = get_random_bytes(16)
        hashed_password = self.manager.hash_pass(password, salt, paper)

        # Check if hashing is correct by using the same inputs
        if hashed_password != self.manager.hash_pass(password, salt, paper):
            log_failure("Failed hash comparison (valid inputs).")
            self.assertTrue(False)
        else:
            log_success("Hashing test passed (valid inputs).")

    def test_hash_pass_invalid(self):
        password = "password123"
        salt = get_random_bytes(16)
        paper = get_random_bytes(16)
        invalid_paper = get_random_bytes(16)

        # Check invalid paper should fail
        if self.manager.hash_pass(password, salt, paper) == self.manager.hash_pass(
            password, salt, invalid_paper
        ):
            log_failure("Failed hash comparison (invalid paper).")
            self.assertTrue(False)
        else:
            log_success("Hashing test passed (invalid inputs).")

    def test_encrypt_data_valid(self):
        self.manager.aes_key = get_random_bytes(16)  # Set AES key for encryption
        data = b"Secret data"
        encrypted_data, iv = self.manager.encrypt_data(data)

        # Check if decryption works
        decrypted_data = self.manager.decrypt_data(encrypted_data, iv)
        if decrypted_data != data:
            log_failure("Failed encryption-decryption test (valid AES key).")
            self.assertTrue(False)
        else:
            log_success("Encryption-decryption test passed (valid AES key).")

    def test_encrypt_data_no_aes_key(self):
        # AES key not set, should raise ValueError
        data = b"Secret data"
        try:
            self.manager.encrypt_data(data)
            log_failure("Expected ValueError when AES key is not set.")
            self.assertTrue(False)
        except ValueError:
            log_success("AES key not set test passed.")

    def test_decrypt_data_no_aes_key(self):
        # AES key not set, should raise ValueError
        data = b"Secret data"
        iv = get_random_bytes(16)
        try:
            self.manager.decrypt_data(data, iv)
            log_failure("Expected ValueError when AES key is not set.")
            self.assertTrue(False)
        except ValueError:
            log_success("AES key not set test passed.")

    def test_encrypt_rsa_valid(self):
        public_key = self.manager.rsa_key.publickey().export_key()
        data = b"Secret data"
        encrypted_data = self.manager.encrypt_rsa(data, public_key)

        # Check if decryption with private key works
        decrypted_data = self.manager.decrypt_rsa(encrypted_data)
        if decrypted_data != data:
            log_failure("Failed RSA encryption-decryption test (valid RSA key).")
            self.assertTrue(False)
        else:
            log_success("RSA encryption-decryption test passed (valid RSA key).")

    def test_encrypt_rsa_invalid_key(self):
        invalid_public_key = get_random_bytes(2048)  # Invalid key
        data = b"Secret data"
        try:
            self.manager.encrypt_rsa(data, invalid_public_key)
            log_failure("Expected error with invalid RSA key.")
            self.assertTrue(False)
        except ValueError:
            log_success("RSA encryption with invalid key test passed.")

    def test_generate_random_bytes_valid(self):
        length = 16
        random_bytes = self.manager.generate_random_bytes(length)

        # Check if the length of random bytes is correct
        if len(random_bytes) != length:
            log_failure(f"Failed random byte generation test (length {length}).")
            self.assertTrue(False)
        else:
            log_success(f"Random byte generation test passed (length {length}).")

    def test_check_hash_valid(self):
        password = "password123"
        salt = get_random_bytes(16)
        paper = get_random_bytes(16)
        hashed_password = self.manager.hash_pass(password, salt, paper)

        # Check if the check_hash method works
        if not self.manager.check_hash(password, hashed_password, salt, paper):
            log_failure("Failed check_hash (valid password).")
            self.assertTrue(False)
        else:
            log_success("check_hash test passed (valid password).")

    def test_check_hash_invalid(self):
        password = "password123"
        salt = get_random_bytes(16)
        paper = get_random_bytes(16)
        wrong_password = "wrongpassword"
        hashed_password = self.manager.hash_pass(password, salt, paper)

        # Check if the check_hash method fails with incorrect password
        if self.manager.check_hash(wrong_password, hashed_password, salt, paper):
            log_failure("Failed check_hash (invalid password).")
            self.assertTrue(False)
        else:
            log_success("check_hash test passed (invalid password).")


if __name__ == "__main__":
    unittest.main()
