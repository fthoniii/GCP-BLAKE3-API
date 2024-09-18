import hashlib
import requests
from blake3 import blake3
import time

url_test_preimage_attack = "http://34.101.126.135:8080/test-second-preimage-keyed"
MAX_TIME = 30 * 60  # Maksimum waktu dalam detik (30 menit)

# Function to get response from the server
def get_responds(url):
    response = requests.post(url)
    try:
        response_json = response.json()
    except ValueError:
        print("Failed to parse JSON response:", response.text)
        response_json = None
    return response_json

# Function to generate incremental bit sequences
def generate_incremental_bits():
    bit_length = 1
    while True:
        for value in range(2 ** bit_length):
            yield value.to_bytes((bit_length + 7) // 8, 'big')
        bit_length += 1

# Function for second preimage attack on keyed BLAKE3 hash
def second_preimage_attack_keyed(target_data, target_hash, max_time=MAX_TIME):
    start_time = time.time()
    attempts = 0

    for bit_sequence in generate_incremental_bits():
        
        key = bytearray(32)
        key[:len(bit_sequence)] = bit_sequence

        hash_value = blake3(bit_sequence, key=key, max_threads=blake3.AUTO).digest()
        attempts += 1

        if hash_value == target_hash and bit_sequence != target_data:
            return bit_sequence, attempts

        # Check if the time limit has been reached
        if time.time() - start_time >= max_time:
            break
    
    return None, attempts

# Get response from the server
response = get_responds(url_test_preimage_attack)
responds_message = response.get("message")
responds_hash_value = response.get("hash_value")

# Perform second preimage attack
second_message, second_preimage_attempts = second_preimage_attack_keyed(responds_message, responds_hash_value)
if second_message:
    print(f"Second preimage for '{responds_message}' with keyed hash is '{second_message}'")
else:
    print(f"No second preimage found within the given time limit. Total attempts: {second_preimage_attempts}")
