from flask import Flask, request, jsonify
from google.cloud import storage, firestore
import os
import psutil
import time
from Crypto.Hash import SHA3_256, HMAC
from Crypto.Protocol.KDF import HKDF
from Crypto.Random import get_random_bytes
from multiprocessing import Pool, cpu_count

app = Flask(__name__)

# Konfigurasi Google Cloud Storage
BUCKET_NAME = "blake3-api-storage"

# Konfigurasi Firestore
db = firestore.Client()

# Fungsi pembantu untuk pemrosesan paralel
def sha3_hash_chunk(chunk):
    hasher = SHA3_256.new()
    hasher.update(chunk)
    return hasher.digest()

# Fungsi pembantu untuk pemrosesan paralel HMAC-SHA3
def hmac_sha3_hash_chunk(args):
    chunk, key = args
    h = HMAC.new(key, msg=chunk, digestmod=SHA3_256)
    return h.digest()

# Fungsi pembantu untuk pemrosesan paralel HKDF-SHA3
def hkdf_sha3_key_chunk(args):
    chunk, salt, context = args
    return HKDF(chunk, 32, salt, SHA3_256, context=context)

# Fungsi untuk mengunggah data ke Google Cloud Storage
def upload_to_gcs(data: bytes, file_name: str):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    blob.upload_from_string(data)

def get_cpu_frequency():
    return psutil.cpu_freq().current

@app.route('/upload-regular-sha3', methods=['POST'])
def upload_regular_sha3():
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
        results = pool.map(sha3_hash_chunk, chunks)
    
    # Combine results
    final_hasher = SHA3_256.new()
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
        'hash_type': "regular_sha3"
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

@app.route('/upload-hmac-sha3', methods=['POST'])
def upload_hmac_sha3():
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
        results = pool.map(hmac_sha3_hash_chunk, [(chunk, key_bytes) for chunk in chunks])
    
    # Combine results
    final_hasher = HMAC.new(key_bytes, digestmod=SHA3_256)
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
        'hash_type': "hmac_sha3"
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

@app.route('/upload-hkdf-sha3', methods=['POST'])
def upload_hkdf_sha3():
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    # Generate context from file metadata
    context = "hkdf"
    
    # Divide data into chunks
    num_chunks = cpu_count()
    chunk_size = len(file_data) // num_chunks
    chunks = [file_data[i * chunk_size:(i + 1) * chunk_size] for i in range(num_chunks)]
    if len(file_data) % num_chunks != 0:
        chunks.append(file_data[num_chunks * chunk_size:])
    
    salt = get_random_bytes(16)

    # Process chunks in parallel
    with Pool(num_chunks) as pool:
        results = pool.map(hkdf_sha3_key_chunk, [(chunk, salt, context.encode('utf-8')) for chunk in chunks])
    
    # Combine results
    final_key = b"".join(results)
    derived_key = final_key.hex()

    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'derived_key': derived_key,
        'hash_type': "hkdf_sha3"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem)  # Memory in KB

    # Throughput calculation (cps)
    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes / 1024 # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "derived_key": derived_key,
        "time_elapsed": elapsed_time,
        "memory_usage": memory_usage,
        "throughput_cpb": throughput,
        "context": context
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)