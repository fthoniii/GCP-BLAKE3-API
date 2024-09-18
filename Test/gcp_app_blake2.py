from flask import Flask, request, jsonify, send_file, Response
from google.cloud import storage, firestore
import os
import io
import psutil
import time
from blake3 import blake3

app = Flask(__name__)

# Konfigurasi Google Cloud Storage
BUCKET_NAME = "blake3-api-storage"

# Konfigurasi Firestore
db = firestore.Client()

# Regular_hash function
def blake3_regular_hash(file_data: bytes) -> str:
   hash_value = blake3(file_data,  max_threads=blake3.AUTO).digest().hex()
   return hash_value

# Keyed_hash function
def blake3_keyed_hash(file_data: bytes, key_bytes: bytes) -> str:
    hash_value = blake3(file_data, key=key_bytes, max_threads=blake3.AUTO).digest().hex()
    return hash_value

# Derive_keyed_hash function
def blake3_derive_keyed_hash(file_data: bytes, context: bytes) -> str:
    hash_value = blake3(file_data, derive_key_context=context, max_threads=blake3.AUTO).digest().hex()
    return hash_value

# Fungsi untuk mengunggah data ke Google Cloud Storage
def upload_to_gcs(data: bytes, file_name: str):
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    blob.upload_from_string(data)

# Fungsi untuk mengunduh data dari Google Cloud Storage
def download_from_gcs(file_name: str) -> bytes:
    client = storage.Client()
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(file_name)
    return blob.download_as_bytes()

def get_cpu_frequency():
    return psutil.cpu_freq().current

@app.route('/upload-keyed-hash', methods=['POST'])
def upload_keyed_hash():
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    key = request.form.get('key')
    if key is None or len(key) != 32:
        return jsonify({"error": "Key must be provided and be exactly 32 bytes long"}), 400
    
    #file_bytes = file_data.encode('utf-8')
    key_bytes = key.encode('utf-8')
    hash_value = blake3_keyed_hash(file_data, key_bytes)
    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'hash_value': hash_value,
        'hash_type': "keyed"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem) / 1024  # Convert to KB

    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes  # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "hash_value": hash_value,
        "time_elapsed": elapsed_time,
        "memory_usage_MB": memory_usage,
        "throughput_cpb": throughput
    })

@app.route('/upload-derive-keyed-hash', methods=['POST'])
def upload_derive_keyed_hash():

    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    # Generate context from file metadata
    last_modified = request.form.get('last_modified')
    hash_type = request.form.get('hash_type')
    context = f"{file_name} derive"
    
    hash_value = blake3_derive_keyed_hash(file_data, context)
    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'hash_value': hash_value,
        'hash_type': "derive_keyed"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem) / 1024  # Convert to KB

    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes  # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "hash_value": hash_value,
        "time_elapsed": elapsed_time,
        "memory_usage_MB": memory_usage,
        "throughput_cpb": throughput,
        "context": context
    })

@app.route('/upload-regular-hash', methods=['POST'])
def upload():
    start_time = time.time()
    process = psutil.Process(os.getpid())
    start_mem = process.memory_info().rss

    file = request.files['file']
    file_data = file.read()
    file_name = file.filename

    hash_value = blake3_regular_hash(file_data)
    gcs_file_name = f"{file_name}"
    upload_to_gcs(file_data, gcs_file_name)

    # Simpan metadata ke Firestore
    doc_ref = db.collection("file_metadata").document()
    doc_ref.set({
        'file_name': gcs_file_name,
        'hash_value': hash_value,
        'hash_type': "regular"
    })

    end_time = time.time()
    end_mem = process.memory_info().rss

    elapsed_time = end_time - start_time
    memory_usage = (end_mem - start_mem) / 1024  # Convert to KB

    cpu_freq = get_cpu_frequency()
    cycles = elapsed_time * cpu_freq
    file_size_bytes = len(file_data)
    throughput = cycles / file_size_bytes  # cycles per byte

    return jsonify({
        "file_name": gcs_file_name,
        "hash_value": hash_value,
        "time_elapsed": elapsed_time,
        "memory_usage_MB": memory_usage,
        "throughput_cpb": throughput
    })

@app.route('/check-regular-hash/<hash_value>', methods=['GET'])
def check_regular_hash(hash_value):
    metadata_ref = db.collection('file_metadata').where('hash_value', '==', hash_value).where('hash_type', '==', 'regular').limit(1).get()
    metadata = metadata_ref[0].to_dict() if metadata_ref else None
    if not metadata:
        return jsonify({"error": "File not found"}), 404

    file_data = download_from_gcs(metadata['file_name'])
    
    data_download_hash = blake3_regular_hash(file_data)
    if data_download_hash != hash_value:
        return jsonify({"Status": "Data Integrity Check Failed!"})
    return jsonify({"Status": "Success", "hash_value": data_download_hash})


@app.route('/check-keyed-hash/<hash_value>', methods=['GET'])
def check_keyed_hash(hash_value):
    metadata_ref = db.collection('file_metadata').where('hash_value', '==', hash_value).where('hash_type', '==', 'keyed').limit(1).get()
    metadata = metadata_ref[0].to_dict() if metadata_ref else None
    if not metadata:
        return jsonify({"error": "File not found"}), 404
    
    key = request.form.get('key')
    if key is None or len(key) != 32:
        return jsonify({"error": "Key must be provided and be exactly 32 bytes long"}), 400
    file_data = download_from_gcs(metadata['file_name'])
    key_bytes = key.encode('utf-8')

    data_download_hash = blake3_keyed_hash(file_data, key_bytes)
    if data_download_hash != hash_value:
        return jsonify({"Status": "Data Integrity Check Failed!"})
    return jsonify({"Status": "Success", "hash_value": data_download_hash})

@app.route('/check-derive-keyed-hash/<hash_value>', methods=['GET'])
def check_derive_keyed_hash(hash_value):
    metadata_ref = db.collection('file_metadata').where('hash_value', '==', hash_value).where('hash_type', '==', 'derive_keyed').limit(1).get()
    metadata = metadata_ref[0].to_dict() if metadata_ref else None
    if not metadata:
        return jsonify({"error": "File not found"}), 404
    
    context = request.form.get('context')

    file_data = download_from_gcs(metadata['file_name'])

    data_download_hash = blake3_derive_keyed_hash(file_data, context)
    if data_download_hash != hash_value:
        return jsonify({"Status": "Data Integrity Check Failed!"})
    return jsonify({"Status": "Success", "hash_value": data_download_hash})

@app.route('/download/<hash_value>', methods=['GET'])
def download_file(hash_value):
    try:
        metadata_ref = db.collection('file_metadata').where('hash_value', '==', hash_value).stream()
        metadata = next(metadata_ref, None)
        if not metadata:
            return jsonify({"error": "File not found"}), 404

        metadata_dict = metadata.to_dict()
        file_name = metadata_dict['file_name']
        
        file_data = download_from_gcs(file_name)
        return send_file(io.BytesIO(file_data), download_name=file_name, as_attachment=True)
    except Exception as e:
        return jsonify({"error": str(e)}), 404


@app.route('/keyed', methods=['POST'])
def keyed():
    text = "\x00\x01"
    key = "whats the Elvish word for friend"

    text_bytes = text.encode('utf-8')
    key_bytes = key.encode('utf-8')
    hash_value = blake3_keyed_hash(text_bytes, key_bytes)
    
    return jsonify({
        "text": text,
        "key": key,
        "hash_value": hash_value
    })
    
@app.route('/regular', methods=['POST'])
def reguler():
    text = "\x00\x01"
    
    text_bytes = text.encode('utf-8')
    hash_value = blake3_regular_hash(text_bytes)
    
    return jsonify({
        "text": text,
        "hash_value": hash_value
    })
    
@app.route('/derived', methods=['POST'])
def derive():
    text = "\x00\x01"
    context = "BLAKE3 2019-12-27 16:29:52 test vectors context"
    
    text_bytes = text.encode('utf-8')
    hash_value = blake3_derive_keyed_hash(text_bytes, context)
    
    return jsonify({
        "text": text,
        "context": context,
        "hash_value": hash_value
    })

@app.route('/test-second-preimage-regular', methods=['POST'])
def test_second_preimage_regular():
    message = "ini adalah pesan rahasia"
    
    message_bytes = message.encode('utf-8')
    hash_value = blake3_regular_hash(message_bytes)
    
    return jsonify({
        "message": message,
        "hash_value": hash_value
    })

@app.route('/test-second-preimage-keyed', methods=['POST'])
def test_second_preimage_keyed():
    message = "ini adalah pesan rahasia"
    key = "9ce463671338a2a2966dd8470296daa5"

    message_bytes = message.encode('utf-8')
    key_bytes = key.encode('utf-8')
    hash_value = blake3_keyed_hash(message_bytes, key_bytes)
    
    return jsonify({
        "message": message,
        "hash_value": hash_value,
        "key": key
    })

@app.route('/test-second-preimage-derive-keyed', methods=['POST'])
def test_second_preimage_derive_keyed():
    message = "ini adalah pesan rahasia"
    context = "blake3 2024-08-20 12:00:00 test second preimage"

    message_bytes = message.encode('utf-8')
    hash_value = blake3_regular_hash(message_bytes)
    
    return jsonify({
        "message": message,
        "hash_value": hash_value,
        "context": context
    })

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=8080)