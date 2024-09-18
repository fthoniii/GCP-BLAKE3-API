from flask import Flask, request, jsonify
from google.cloud import storage, firestore
import os
import psutil
import time
import hashlib  # Import hashlib for SHA-256
from hmac import new as hmac_new
from multiprocessing import Pool, cpu_count

app = Flask(__name__)

# Konfigurasi Google Cloud Storage
BUCKET_NAME = "blake3-api-storage"

# Konfigurasi Firestore
db = firestore.Client()

# Fungsi pembantu untuk pemrosesan paralel dengan SHA-256
def sha256_hash_chunk(chunk):
    hasher = hashlib.sha256()
    hasher.update(chunk)
    return hasher.digest()

# Fungsi pembantu untuk pemrosesan paralel HMAC-SHA256
def hmac_sha256_hash_chunk(args):
    chunk, key = args
    h = hmac_new(key, chunk, hashlib.sha256)
    return h.digest()

# Fungsi untuk mengunggah data ke Google Cloud Storage
def upload_to_gcs(data: bytes, file_name: str):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    blob.upload_from_string(data)

def get_cpu_frequency():
    return psutil.cpu_freq().current

@app.route('/upload-regular-sha256', methods=['POST'])
def upload_regular_sha256():
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    # Divide data into chunks
    num_chunks = cpu_count()
    chunk_size = len(file_data) // num_chunks
    chunks = [file_data[i * chunk_size:(i + 1) * chunk_size] for i in range(num_chunks)]
    if len(file_data) % num_chunks != 0:
        chunks.append(file_data[num_chunks * chunk_size:])

    # Process chunks in parallel
    with Pool(num_chunks) as pool:
        results = pool.map(sha256_hash_chunk, chunks)
    
    # Combine results
    final_hasher = hashlib.sha256()
    for result in results:
        final_hasher.update(result)
    hash_value = final_hasher.hexdigest()

    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'hash_value': hash_value,
        'hash_type': "regular_sha256"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem) / 1024 # memory in KB

    # Throughput calculation (cps)
    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes  # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "hash": hash_value,
        "time_elapsed": elapsed_time,
        "memory_usage": memory_usage,
        "throughput_cpb": throughput
    })

@app.route('/upload-hmac-sha256', methods=['POST'])
def upload_hmac_sha256():
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    key = request.form.get('key')
    if key is None or len(key) != 32:
        return jsonify({"error": "Key must be provided and be exactly 32 bytes long"}), 400
    
    key_bytes = key.encode('utf-8')

    # Divide data into chunks
    num_chunks = cpu_count()
    chunk_size = len(file_data) // num_chunks
    chunks = [file_data[i * chunk_size:(i + 1) * chunk_size] for i in range(num_chunks)]
    if len(file_data) % num_chunks != 0:
        chunks.append(file_data[num_chunks * chunk_size:])
    
    # Process chunks in parallel
    with Pool(num_chunks) as pool:
        results = pool.map(hmac_sha256_hash_chunk, [(chunk, key_bytes) for chunk in chunks])
    
    # Combine results
    final_hasher = hmac_new(key_bytes, digestmod=hashlib.sha256)
    for result in results:
        final_hasher.update(result)
    hash_value = final_hasher.hexdigest()

    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'hash_value': hash_value,
        'hash_type': "hmac_sha256"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem) / 1024 # memory in KB

    # Throughput calculation (cps)
    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes  # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "hash": hash_value,
        "time_elapsed": elapsed_time,
        "memory_usage": memory_usage,
        "throughput_cpb": throughput
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)
