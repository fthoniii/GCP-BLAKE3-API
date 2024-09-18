import requests
import time
import os

# URL endpoint
url_derive = "http://34.128.94.36:8080/upload-hkdf-sha3" # Change the value according to which endpoint that we use

# File to upload
file_path = "data_test_resources/64MiB.txt" # Change the value according to which file that we use

# Function to upload file and get time, memory usage, and throughput
def upload_file(url, files):

    response = requests.post(url, files=files)

    try:
        response_json = response.json()
    except ValueError:
        print("Failed to parse JSON response:", response.text)
        response_json = None

    return response_json

total_time_derive = 0
total_throughput_derive = 0
total_memory_derive = 0

# Read file data
with open(file_path, 'rb') as file:
    file_data = file.read()
    file_name = os.path.basename(file_path)

files = {'file': (file_name, file_data)}

# Perform 7 requests for derive hash
for _ in range(10):
    response = upload_file(url_derive, files)
    if response is not None:
        total_time_derive += response.get("time_elapsed", 0) # get data time elapsed from server's responds
        total_throughput_derive += response.get("throughput_cpb", 0) # get data thorughput from server's responds 
        total_memory_derive += response.get("memory_usage", 0)  # get data memory usage from server's responds
    print("Derive hash response:", response)

average_time_derive = total_time_derive / 10
average_memory_derive = total_memory_derive / 10
average_throughput_derive = total_throughput_derive / 10

print("Average time for derive hash: {:.4f} seconds".format(average_time_derive))
print("Average memory usage for derive hash: {:.4f} KB".format(average_memory_derive))
print("Average throughput for derive hash: {:.4f} cpb".format(average_throughput_derive))