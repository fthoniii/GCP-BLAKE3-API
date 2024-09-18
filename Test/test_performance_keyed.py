import requests
import time
import psutil
import os

# URL endpoint
url_keyed = "http://34.128.122.39:8080/upload-hmac-sha256" # Change the value according to which endpoint that we use

# File to upload
file_path = "data_test_resources/32MiB.txt" # Change the value according to which file that we use

# Key for keyed hash
key = "10c9a7fdfdd3ade1025895293e0b9412"

# Function to upload file and get time, memory usage, and throughput
def upload_file(url, files, data = None):

    response = requests.post(url, files=files, data=data)

    try:
        response_json = response.json()
    except ValueError:
        print("Failed to parse JSON response:", response.text)
        response_json = None

    return response_json

total_time_keyed = 0
total_throughput_keyed = 0
total_memory_keyed = 0

# Read file data
with open(file_path, 'rb') as file:
    file_data = file.read()

files = {'file': (os.path.basename(file_path), file_data)}

# Perform 10 requests for keyed hash
data_keyed = {'key': key}
for _ in range(10):
    response = upload_file(url_keyed, files, data_keyed)
    total_time_keyed += response.get("time_elapsed", 0) # get data time elapsed from server's responds
    total_throughput_keyed += response.get("throughput_cpb", 0) # get data thorughput from server's responds 
    total_memory_keyed += response.get("memory_usage", 0)  # get data memory usage from server's responds
    print("Keyed hash response:", response)

average_time_keyed = total_time_keyed / 10
average_memory_keyed = total_memory_keyed / 10
average_throughput_keyed = total_throughput_keyed / 10

print("Average time for keyed hash: {:.4f} seconds".format(average_time_keyed))
print("Average memory usage for keyed hash: {:.4f} KB".format(average_memory_keyed))
print("Average throughput for keyed hash: {:.4f} cpb".format(average_throughput_keyed))
