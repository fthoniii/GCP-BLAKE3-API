import requests
import sys
import os

# URL endpoint
url_upload = "http://34.101.237.78:8080/upload-derive-keyed-hash"

# Function to read file and return its content as binary string
def read_file_as_binary(file_path):
    with open(file_path, 'rb') as file:
        binary_content = file.read()
    # Convert the file content to binary string
    binary_string = ''.join(format(byte, '08b') for byte in binary_content)
    return binary_string

# Function to write binary string back to file
def write_binary_to_file(binary_string, file_path):
    with open(file_path, 'wb') as file:
        # Split binary string into chunks of 8 bits and convert to bytes
        byte_array = bytearray(int(binary_string[i:i+8], 2) for i in range(0, len(binary_string), 8))
        file.write(byte_array)

# Function to flip bit at a specific index in binary string
def flip_bit(binary_string, bit_index):
    flipped_bit = '1' if binary_string[bit_index] == '0' else '0'
    return binary_string[:bit_index] + flipped_bit + binary_string[bit_index+1:]

# Function to upload file and get hash response
def upload_file_and_get_hash(file_path, key):
    with open(file_path, 'rb') as file:
        files = {'file': file}
        data = {'key': key}
        response = requests.post(url_upload, files=files, data=data)
        response_json = response.json()
        if 'hash_value' in response_json:
            return response_json['hash_value']
        else:
            raise ValueError("No hash_value in response")

# Function to count bit differences between two hash values
def bit_difference_count(hash_1, hash_2):
    if hash_1 is None or hash_2 is None:
        raise ValueError("One or both hash values are None")
    return bin(int(hash_1, 16) ^ int(hash_2, 16)).count('1')

# Function to perform the avalanche test
def avalanche_test(hash_ori, hash_mod):
    # Calculate avalanche effect
    d = bit_difference_count(hash_ori, hash_mod)
    n = len(hash_ori) * 4  # Each hex digit represents 4 bits
    
    avalanche_effect = (d / n) * 100
    return avalanche_effect

# Main function to perform flip bit mechanism and upload files
def flip_bits_and_test_avalanche(file_path, key):
    binary_string = read_file_as_binary(file_path)
    binary_length = len(binary_string)
    
    # Upload original file and get hash
    original_hash = upload_file_and_get_hash(file_path, key)
    print(f"Original file hash: {original_hash}")
    
    avalanche_scores = []

    for i in range(binary_length):
        # Flip bit at index i
        flipped_binary_string = flip_bit(binary_string, i)
        flipped_file_path = f"flipped_bit_{i+1}.bin"
        write_binary_to_file(flipped_binary_string, flipped_file_path)

        # Upload flipped file and get hash
        flipped_hash = upload_file_and_get_hash(flipped_file_path, key)
        print(f"Flipped bit at index {i} file hash: {flipped_hash}")

        # Perform avalanche test
        avalanche_score = avalanche_test(original_hash, flipped_hash)
        avalanche_scores.append(avalanche_score)
        print(f"Avalanche Effect for bit {i+1}: {avalanche_score:.2f}%")

    # Calculate and print average avalanche effect
    average_avalanche_effect = sum(avalanche_scores) / len(avalanche_scores)
    print(f"Average Avalanche Effect: {average_avalanche_effect:.2f}%")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python flip_bits_and_test_avalanche.py <file_path>")
        sys.exit(1)
    
    input_file_path = sys.argv[1]

    key = "10c9a7fdfdd3ade1025895293e0b9412"
    flip_bits_and_test_avalanche(input_file_path, key)
    print(read_file_as_binary(input_file_path))