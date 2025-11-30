"""
QuikSafe Bot - Encryption Utilities
Provides AES-256 encryption/decryption using Fernet for sensitive data.
"""

from cryptography.fernet import Fernet
from typing import Optional
import base64


class EncryptionManager:
    """Handles encryption and decryption of sensitive data."""
    
    def __init__(self, encryption_key: str):
        """
        Initialize encryption manager with a Fernet key.
        
        Args:
            encryption_key: Base64-encoded Fernet key (44 characters)
        """
        try:
            self.cipher = Fernet(encryption_key.encode())
        except Exception as e:
            raise ValueError(f"Invalid encryption key: {e}")
    
    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt plaintext string.
        
        Args:
            plaintext: String to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return ""
        
        try:
            encrypted_bytes = self.cipher.encrypt(plaintext.encode('utf-8'))
            return encrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt encrypted string.
        
        Args:
            ciphertext: Base64-encoded encrypted string
            
        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ""
        
        try:
            decrypted_bytes = self.cipher.decrypt(ciphertext.encode('utf-8'))
            return decrypted_bytes.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")
    
    def encrypt_dict(self, data: dict, fields: list[str]) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing data
            fields: List of field names to encrypt
            
        Returns:
            Dictionary with specified fields encrypted
        """
        encrypted_data = data.copy()
        for field in fields:
            if field in encrypted_data and encrypted_data[field]:
                encrypted_data[field] = self.encrypt(str(encrypted_data[field]))
        return encrypted_data
    
    def decrypt_dict(self, data: dict, fields: list[str]) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary containing encrypted data
            fields: List of field names to decrypt
            
        Returns:
            Dictionary with specified fields decrypted
        """
        decrypted_data = data.copy()
        for field in fields:
            if field in decrypted_data and decrypted_data[field]:
                decrypted_data[field] = self.decrypt(decrypted_data[field])
        return decrypted_data


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded encryption key (44 characters)
    """
    return Fernet.generate_key().decode()


# Example usage
if __name__ == "__main__":
    # Generate a new key
    key = generate_encryption_key()
    print(f"Generated encryption key: {key}")
    print(f"Add this to your .env file as ENCRYPTION_KEY={key}")
    
    # Test encryption/decryption
    manager = EncryptionManager(key)
    
    test_password = "MySecurePassword123!"
    encrypted = manager.encrypt(test_password)
    decrypted = manager.decrypt(encrypted)
    
    print(f"\nOriginal: {test_password}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    print(f"Match: {test_password == decrypted}")
