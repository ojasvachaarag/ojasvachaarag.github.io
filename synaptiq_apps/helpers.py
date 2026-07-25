"""
This is a solid use case for **envelope encryption**. The important property is:

* The application server **can encrypt**, but **cannot decrypt**.
* The compliance team **can decrypt**, but only by accessing the recovery private key from the vault.
* The ciphertext never changes; only the encrypted data key changes depending on who is allowed to access it.

I'll use **Python** because the cryptography library is well designed and maps closely to similar APIs in Go, Rust, Java, C#, etc.

## Overall architecture

```
                    One API Key
                         │
                         ▼
        Generate random 256-bit AES key (DEK)
                         │
                         ▼
          AES-256-GCM encrypts API key
                         │
                         ▼
               Ciphertext + Nonce + Tag
                         │
        ┌────────────────┴───────────────┐
        ▼                                ▼
Encrypt DEK with                Encrypt DEK with
User Public Key                 Recovery Public Key
        │                                │
        ▼                                ▼
Encrypted User DEK            Encrypted Recovery DEK
```

The AES key (called the **Data Encryption Key** or DEK) is random for every API key.

---

# Encryption

```python
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
```

Since X25519 is a key agreement algorithm rather than an encryption algorithm, we derive a wrapping key with HKDF.

```python
def wrap_key(public_key: x25519.X25519PublicKey, key_to_wrap: bytes):
    ephemeral = x25519.X25519PrivateKey.generate()

    shared_secret = ephemeral.exchange(public_key)

    wrapping_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"wrap-key",
    ).derive(shared_secret)

    nonce = os.urandom(12)

    wrapped = AESGCM(wrapping_key).encrypt(
        nonce,
        key_to_wrap,
        None
    )

    return {
        "ephemeral_public_key":
            ephemeral.public_key().public_bytes(
                serialization.Encoding.Raw,
                serialization.PublicFormat.Raw
            ),

        "nonce": nonce,
        "wrapped_key": wrapped
    }
```

Main encryption:

```python
def encrypt_api_key(
        api_key: str,
        user_public_key,
        recovery_public_key):

    dek = os.urandom(32)

    nonce = os.urandom(12)

    encrypted_api_key = AESGCM(dek).encrypt(
        nonce,
        api_key.encode(),
        None
    )

    user_wrapped = wrap_key(user_public_key, dek)

    recovery_wrapped = wrap_key(
        recovery_public_key,
        dek
    )

    return {

        "ciphertext": encrypted_api_key,

        "nonce": nonce,

        "user": user_wrapped,

        "recovery": recovery_wrapped

    }
```

---

# Decryption

```python
def unwrap_key(
        private_key,
        wrapped):

    ephemeral = x25519.X25519PublicKey.from_public_bytes(
        wrapped["ephemeral_public_key"]
    )

    shared = private_key.exchange(ephemeral)

    wrapping_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b"wrap-key",
    ).derive(shared)

    dek = AESGCM(wrapping_key).decrypt(
        wrapped["nonce"],
        wrapped["wrapped_key"],
        None
    )

    return dek
```

```python
def decrypt_api_key(
        encrypted_package,
        private_key):

    dek = unwrap_key(
        private_key,
        encrypted_package
    )

    plaintext = AESGCM(dek).decrypt(
        encrypted_package["nonce"],
        encrypted_package["ciphertext"],
        None
    )

    return plaintext.decode()
```

Usage:

```
user_api_key = decrypt_api_key(
    encrypted_package["user"],
    user_private_key
)
```

Recovery:

```
recovered = decrypt_api_key(
    encrypted_package["recovery"],
    recovery_private_key
)
```

(For production code, you'd pass the full encrypted package plus either the `"user"` or `"recovery"` wrapped-key record into the decryption function; the snippet above illustrates the flow.)

---

# What gets stored?

For each API key record in your database:

| Field                         | Stored? | Purpose                      |
| ----------------------------- | ------- | ---------------------------- |
| ciphertext                    | ✓       | Encrypted API key            |
| nonce                         | ✓       | AES-GCM nonce                |
| user.ephemeral_public_key     | ✓       | Required for user unwrap     |
| user.nonce                    | ✓       | Required for user unwrap     |
| user.wrapped_key              | ✓       | Encrypted DEK for user       |
| recovery.ephemeral_public_key | ✓       | Required for recovery        |
| recovery.nonce                | ✓       | Required for recovery        |
| recovery.wrapped_key          | ✓       | Encrypted DEK for compliance |

---

Elsewhere:

**User**

```
Private key
```

Never sent to the server.

Server stores only:

```
User public key
```

---

Compliance Vault

```
Recovery private key
```

This is the most sensitive key in the system.

---

Application configuration

```
Recovery public key
```

This is safe to distribute to all application servers because it's only used to encrypt the DEK.

---

# Why the ephemeral key?

If you encrypted the DEK directly with a static public/private keypair, the same public key would always produce the same shared secret. Using a fresh ephemeral X25519 keypair for each wrapped DEK means every wrapping operation produces a unique shared secret, giving the wrapped key semantic security and forward secrecy properties for the wrapping step.

---

# Why AES-GCM?

AES-GCM provides both confidentiality and integrity:

* If someone modifies the ciphertext, decryption fails.
* If someone modifies the wrapped DEK, unwrapping fails.
* You don't need a separate HMAC because the authentication tag is built into the algorithm.

---

# One improvement for production

Although the above demonstrates the cryptographic building blocks, in production I would recommend using a standard hybrid-encryption construction rather than assembling X25519 + HKDF + AES-GCM manually. Libraries such as **libsodium** (`crypto_box_seal`) or standards like **HPKE (Hybrid Public Key Encryption, RFC 9180)** implement this pattern with well-reviewed, interoperable designs and reduce the risk of subtle implementation mistakes.

The overall architecture remains exactly the same:

* Generate a random DEK.
* Encrypt the API key with AES-256-GCM using the DEK.
* Wrap the DEK once for the user and once for the compliance recovery key.
* Store both wrapped DEKs alongside the ciphertext.
* Keep the recovery private key in your vault, accessible only through your compliance process. This gives you a controlled recovery path without giving the application servers routine decryption capability.
"""