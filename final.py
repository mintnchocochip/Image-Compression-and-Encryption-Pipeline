import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
from io import BytesIO
import time
import math
from skimage.metrics import mean_squared_error as mse
from skimage.metrics import peak_signal_noise_ratio as psnr
from skimage.metrics import structural_similarity as ssim
from skimage.measure import shannon_entropy
import hashlib
import warnings
import os 
import base64 
import zlib 
import traceback 
import json 


try:
    from google.colab import files
    ENV = 'colab'
except ImportError:
    print("Not running in Google Colab. File upload/download will require manual steps or alternative libraries (like ipywidgets).")
    
    try:
        from IPython.display import display, HTML
        import ipywidgets as widgets 
        ENV = 'jupyter'
    except ImportError:
        print("IPython/ipywidgets not available. Download links may not be generated automatically.")
        ENV = 'other'



warnings.filterwarnings("ignore", category=UserWarning, module='skimage')
warnings.filterwarnings("ignore", category=UserWarning, module='PIL')
warnings.filterwarnings("ignore", category=FutureWarning, module='skimage')




def preprocess_image(img_input, target_size=None, grayscale=False, simulate_low_bandwidth=False, low_bw_size=(128, 128)):
    
    try:
        if isinstance(img_input, (BytesIO, bytes)):
            
            if isinstance(img_input, bytes):
                img_input = BytesIO(img_input)
            img_input.seek(0) 
            img = Image.open(img_input)
            print("Loaded image from uploaded data.")
        elif isinstance(img_input, str): 
            
            if img_input.startswith('http://') or img_input.startswith('https://'):
                 
                 
                 
                 
                 
                 
                 raise NotImplementedError("URL loading currently disabled. Upload file or use local path.")
            else:
                 img = Image.open(img_input)
                 print(f"Loaded image from Path: {img_input}")
        elif isinstance(img_input, Image.Image):
            img = img_input
            print("Processing provided PIL image object.")
        elif img_input is None: 
             raise ValueError("No valid image input provided.")
        else:
             raise ValueError(f"Unsupported input type for preprocess_image: {type(img_input)}")

    except FileNotFoundError:
        print(f"Error: File not found at path '{img_input}'.")
        print("Using a fallback procedural image.")
        img_array = np.zeros((256, 256, 3), dtype=np.uint8)
        img_array[:, :, 0] = np.linspace(0, 255, 256) 
        img_array[:, :, 1] = np.linspace(0, 255, 256).T 
        img_array[:, :, 2] = 128 
        img = Image.fromarray(img_array)
    except Exception as e:
        print(f"Error loading image: {e}")
        
        print("Using a fallback procedural image.")
        img_array = np.zeros((256, 256, 3), dtype=np.uint8)
        img_array[:, :, 0] = np.linspace(0, 255, 256) 
        img_array[:, :, 1] = np.linspace(0, 255, 256).T 
        img_array[:, :, 2] = 128 
        img = Image.fromarray(img_array)


    original_mode = img.mode
    original_size_before_processing = img.size
    print(f"Original image mode: {original_mode}, size: {original_size_before_processing}")

    if grayscale and img.mode != 'L':
        img = img.convert('L')
        print(f"Converted to grayscale. New mode: {img.mode}")
    elif not grayscale and img.mode not in ['RGB', 'RGBA']:
         print(f"Converting mode {img.mode} to RGB for consistency.")
         img = img.convert('RGB')

    if img.mode == 'RGBA':
        print("Converting RGBA to RGB by blending onto a white background.")
        
        bg = Image.new("RGB", img.size, (255, 255, 255))
        
        try:
            
            bg.paste(img, mask=img.split()[3])
        except IndexError:
             print("Warning: Could not get alpha channel for RGBA conversion. Using image directly.")
             bg.paste(img) 
        img = bg 

    
    if simulate_low_bandwidth:
        print(f"Simulating low bandwidth. Resizing image to {low_bw_size}...")
        img = img.resize(low_bw_size, Image.Resampling.LANCZOS)
        print(f"Resized image size: {img.size}")
    elif target_size:
        
        if isinstance(target_size, (list, tuple)) and len(target_size) == 2:
            print(f"Resizing image to {target_size}...")
            img = img.resize(target_size, Image.Resampling.LANCZOS)
            print(f"Resized image size: {img.size}")
        else:
            print(f"Warning: Invalid target_size {target_size}. Skipping resize.")


    img_array = np.array(img, dtype=np.uint8)

    
    h, w = img_array.shape[:2]
    padded = False
    if h != w:
        padded = True
        print(f"Image is not square ({h}x{w}). Padding to make it square.")
        max_dim = max(h, w)
        pad_h = max_dim - h
        pad_w = max_dim - w
        
        
        if img_array.ndim == 3: 
            
            pad_width = ((pad_h // 2, pad_h - pad_h // 2), (pad_w // 2, pad_w - pad_w // 2), (0, 0))
        else: 
            
            pad_width = ((pad_h // 2, pad_h - pad_h // 2), (pad_w // 2, pad_w - pad_w // 2))
        
        img_array = np.pad(img_array, pad_width, mode='constant', constant_values=0)
        print(f"Padded image size: {img_array.shape[:2]}")

    
    return img_array, original_size_before_processing, padded






def arnold_cat_map(img_array, iterations, a=1, b=1):
    
    if img_array.ndim not in [2, 3]:
        raise ValueError("Input must be a 2D (grayscale) or 3D (color) image array.")
    if img_array.shape[0] != img_array.shape[1]:
        raise ValueError("Arnold's Cat Map requires a square image. Please pad first.")

    rows, cols = img_array.shape[:2]
    is_color = img_array.ndim == 3

    
    x, y = np.meshgrid(np.arange(rows), np.arange(cols), indexing='ij')
    
    coords = np.stack([x.flatten(), y.flatten()], axis=1)

    
    for i in range(iterations):
        new_coords = np.zeros_like(coords)
        
        new_coords[:, 0] = (coords[:, 0] + b * coords[:, 1]) % rows
        new_coords[:, 1] = (a * coords[:, 0] + (a * b + 1) * coords[:, 1]) % cols
        coords = new_coords 
        
        

    
    shuffled_img = np.zeros_like(img_array)
    orig_indices = (x.flatten(), y.flatten()) 
    new_indices = (coords[:, 0], coords[:, 1]) 

    
    if is_color:
        for c in range(img_array.shape[2]):
            shuffled_img[new_indices[0], new_indices[1], c] = img_array[orig_indices[0], orig_indices[1], c]
    else: 
        shuffled_img[new_indices[0], new_indices[1]] = img_array[orig_indices[0], orig_indices[1]]

    
    return shuffled_img.reshape(img_array.shape)

def inverse_arnold_cat_map(shuffled_img_array, iterations, a=1, b=1):
    
    if shuffled_img_array.ndim not in [2, 3]:
        raise ValueError("Input must be a 2D (grayscale) or 3D (color) image array.")
    if shuffled_img_array.shape[0] != shuffled_img_array.shape[1]:
        raise ValueError("Inverse Arnold's Cat Map requires a square image.")

    rows, cols = shuffled_img_array.shape[:2]
    is_color = shuffled_img_array.ndim == 3

    
    x_shuffled, y_shuffled = np.meshgrid(np.arange(rows), np.arange(cols), indexing='ij')
    coords_shuffled = np.stack([x_shuffled.flatten(), y_shuffled.flatten()], axis=1)

    
    
    inv_coeff_00 = a * b + 1
    inv_coeff_01 = -b
    inv_coeff_10 = -a
    inv_coeff_11 = 1

    for i in range(iterations):
        coords_orig = np.zeros_like(coords_shuffled)
        
        coords_orig[:, 0] = (inv_coeff_00 * coords_shuffled[:, 0] + inv_coeff_01 * coords_shuffled[:, 1]) % rows
        coords_orig[:, 1] = (inv_coeff_10 * coords_shuffled[:, 0] + inv_coeff_11 * coords_shuffled[:, 1]) % cols
        coords_shuffled = coords_orig 
        
        

    
    unshuffled_img = np.zeros_like(shuffled_img_array)
    shuffled_indices = (x_shuffled.flatten(), y_shuffled.flatten()) 
    original_indices = (coords_shuffled[:, 0], coords_shuffled[:, 1]) 

    
    if is_color:
        for c in range(shuffled_img_array.shape[2]):
            unshuffled_img[original_indices[0], original_indices[1], c] = shuffled_img_array[shuffled_indices[0], shuffled_indices[1], c]
    else: 
        unshuffled_img[original_indices[0], original_indices[1]] = shuffled_img_array[shuffled_indices[0], shuffled_indices[1]]

    return unshuffled_img.reshape(shuffled_img_array.shape)


def generate_logistic_map_sequence(x0, r, size):
    
    
    x0 = float(x0)
    r = float(r)
    sequence = np.zeros(size, dtype=np.float64) 
    x = x0
    
    
    for _ in range(100): 
        x = r * x * (1.0 - x)
    
    
    for i in range(size):
        x = r * x * (1.0 - x)
        sequence[i] = x
        
        if x == 0.0 or x == 1.0:
            
            
            
            
            
            pass

    return sequence

def logistic_map_encrypt_decrypt(img_array, x0, r):
    
    if img_array.ndim not in [2, 3]:
        raise ValueError("Input must be a 2D (grayscale) or 3D (color) image array.")
    img_dtype = img_array.dtype
    if img_dtype != np.uint8:
        print(f"Warning: Input image array dtype is {img_dtype}. Converting to uint8 for XOR.")
        img_array = img_array.astype(np.uint8)

    is_color = img_array.ndim == 3
    total_pixels = img_array.size 

    
    if not (3.57 <= r <= 4.0):
        print(f"Warning: Logistic map parameter r={r} might not be in the typical chaotic range [3.57, 4.0]. Results may be insecure.")
    if not (0 < x0 < 1):
         print(f"Warning: Logistic map initial value x0={x0} should be between 0 and 1. Clipping to avoid issues.")
         
         x0 = np.clip(x0, 1e-6, 1.0 - 1e-6)

    try:
        
        keystream_float = generate_logistic_map_sequence(x0, r, total_pixels)
        
        
        keystream_uint8 = (keystream_float * 255.999999).astype(np.uint8)
    except OverflowError:
        print(f"FATAL: OverflowError during logistic map generation with r={r}, x0={x0}. This usually indicates unstable parameters. Stopping.")
        
        raise ValueError(f"Logistic map overflowed with r={r}, x0={x0}.")
        

    
    
    keystream_reshaped = keystream_uint8 
    img_flat = img_array.flatten()

    if len(img_flat) != len(keystream_reshaped):
         raise ValueError(f"Image flat size ({len(img_flat)}) and keystream size ({len(keystream_reshaped)}) mismatch.")

    
    processed_flat = np.bitwise_xor(img_flat, keystream_reshaped)

    
    processed_img = processed_flat.reshape(img_array.shape)
    
    return processed_img.astype(np.uint8)




s_box_list = [
    0x63, 0x7c, 0x77, 0x7b, 0xf2, 0x6b, 0x6f, 0xc5, 0x30, 0x01, 0x67, 0x2b, 0xfe, 0xd7, 0xab, 0x76,
    0xca, 0x82, 0xc9, 0x7d, 0xfa, 0x59, 0x47, 0xf0, 0xad, 0xd4, 0xa2, 0xaf, 0x9c, 0xa4, 0x72, 0xc0,
    0xb7, 0xfd, 0x93, 0x26, 0x36, 0x3f, 0xf7, 0xcc, 0x34, 0xa5, 0xe5, 0xf1, 0x71, 0xd8, 0x31, 0x15,
    0x04, 0xc7, 0x23, 0xc3, 0x18, 0x96, 0x05, 0x9a, 0x07, 0x12, 0x80, 0xe2, 0xeb, 0x27, 0xb2, 0x75,
    0x09, 0x83, 0x2c, 0x1a, 0x1b, 0x6e, 0x5a, 0xa0, 0x52, 0x3b, 0xd6, 0xb3, 0x29, 0xe3, 0x2f, 0x84,
    0x53, 0xd1, 0x00, 0xed, 0x20, 0xfc, 0xb1, 0x5b, 0x6a, 0xcb, 0xbe, 0x39, 0x4a, 0x4c, 0x58, 0xcf,
    0xd0, 0xef, 0xaa, 0xfb, 0x43, 0x4d, 0x33, 0x85, 0x45, 0xf9, 0x02, 0x7f, 0x50, 0x3c, 0x9f, 0xa8,
    0x51, 0xa3, 0x40, 0x8f, 0x92, 0x9d, 0x38, 0xf5, 0xbc, 0xb6, 0xda, 0x21, 0x10, 0xff, 0xf3, 0xd2,
    0xcd, 0x0c, 0x13, 0xec, 0x5f, 0x97, 0x44, 0x17, 0xc4, 0xa7, 0x7e, 0x3d, 0x64, 0x5d, 0x19, 0x73,
    0x60, 0x81, 0x4f, 0xdc, 0x22, 0x2a, 0x90, 0x88, 0x46, 0xee, 0xb8, 0x14, 0xde, 0x5e, 0x0b, 0xdb,
    0xe0, 0x32, 0x3a, 0x0a, 0x49, 0x06, 0x24, 0x5c, 0xc2, 0xd3, 0xac, 0x62, 0x91, 0x95, 0xe4, 0x79,
    0xe7, 0xc8, 0x37, 0x6d, 0x8d, 0xd5, 0x4e, 0xa9, 0x6c, 0x56, 0xf4, 0xea, 0x65, 0x7a, 0xae, 0x08,
    0xba, 0x78, 0x25, 0x2e, 0x1c, 0xa6, 0xb4, 0xc6, 0xe8, 0xdd, 0x74, 0x1f, 0x4b, 0xbd, 0x8b, 0x8a,
    0x70, 0x3e, 0xb5, 0x66, 0x48, 0x03, 0xf6, 0x0e, 0x61, 0x35, 0x57, 0xb9, 0x86, 0xc1, 0x1d, 0x9e,
    0xe1, 0xf8, 0x98, 0x11, 0x69, 0xd9, 0x8e, 0x94, 0x9b, 0x1e, 0x87, 0xe9, 0xce, 0x55, 0x28, 0xdf,
    0x8c, 0xa1, 0x89, 0x0d, 0xbf, 0xe6, 0x42, 0x68, 0x41, 0x99, 0x2d, 0x0f, 0xb0, 0x54, 0xbb, 0x16
]

s_box_np = np.array(s_box_list, dtype=np.uint8)


inv_s_box_list = [
    0x52, 0x09, 0x6a, 0xd5, 0x30, 0x36, 0xa5, 0x38, 0xbf, 0x40, 0xa3, 0x9e, 0x81, 0xf3, 0xd7, 0xfb,
    0x7c, 0xe3, 0x39, 0x82, 0x9b, 0x2f, 0xff, 0x87, 0x34, 0x8e, 0x43, 0x44, 0xc4, 0xde, 0xe9, 0xcb,
    0x54, 0x7b, 0x94, 0x32, 0xa6, 0xc2, 0x23, 0x3d, 0xee, 0x4c, 0x95, 0x0b, 0x42, 0xfa, 0xc3, 0x4e,
    0x08, 0x2e, 0xa1, 0x66, 0x28, 0xd9, 0x24, 0xb2, 0x76, 0x5b, 0xa2, 0x49, 0x6d, 0x8b, 0xd1, 0x25,
    0x72, 0xf8, 0xf6, 0x64, 0x86, 0x68, 0x98, 0x16, 0xd4, 0xa4, 0x5c, 0xcc, 0x5d, 0x65, 0xb6, 0x92,
    0x6c, 0x70, 0x48, 0x50, 0xfd, 0xed, 0xb9, 0xda, 0x5e, 0x15, 0x46, 0x57, 0xa7, 0x8d, 0x9d, 0x84,
    0x90, 0xd8, 0xab, 0x00, 0x8c, 0xbc, 0xd3, 0x0a, 0xf7, 0xe4, 0x58, 0x05, 0xb8, 0xb3, 0x45, 0x06,
    0xd0, 0x2c, 0x1e, 0x8f, 0xca, 0x3f, 0x0f, 0x02, 0xc1, 0xaf, 0xbd, 0x03, 0x01, 0x13, 0x8a, 0x6b,
    0x3a, 0x91, 0x11, 0x41, 0x4f, 0x67, 0xdc, 0xea, 0x97, 0xf2, 0xcf, 0xce, 0xf0, 0xb4, 0xe6, 0x73,
    0x96, 0xac, 0x74, 0x22, 0xe7, 0xad, 0x35, 0x85, 0xe2, 0xf9, 0x37, 0xe8, 0x1c, 0x75, 0xdf, 0x6e,
    0x47, 0xf1, 0x1a, 0x71, 0x1d, 0x29, 0xc5, 0x89, 0x6f, 0xb7, 0x62, 0x0e, 0xaa, 0x18, 0xbe, 0x1b,
    0xfc, 0x56, 0x3e, 0x4b, 0xc6, 0xd2, 0x79, 0x20, 0x9a, 0xdb, 0xc0, 0xfe, 0x78, 0xcd, 0x5a, 0xf4,
    0x1f, 0xdd, 0xa8, 0x33, 0x88, 0x07, 0xc7, 0x31, 0xb1, 0x12, 0x10, 0x59, 0x27, 0x80, 0xec, 0x5f,
    0x60, 0x51, 0x7f, 0xa9, 0x19, 0xb5, 0x4a, 0x0d, 0x2d, 0xe5, 0x7a, 0x9f, 0x93, 0xc9, 0x9c, 0xef,
    0xa0, 0xe0, 0x3b, 0x4d, 0xae, 0x2a, 0xf5, 0xb0, 0xc8, 0xeb, 0xbb, 0x3c, 0x83, 0x53, 0x99, 0x61,
    0x17, 0x2b, 0x04, 0x7e, 0xba, 0x77, 0xd6, 0x26, 0xe1, 0x69, 0x14, 0x63, 0x55, 0x21, 0x0c, 0x7d
]

inv_s_box_np = np.array(inv_s_box_list, dtype=np.uint8)

def apply_aes_sbox(img_array):
    
    if img_array.dtype != np.uint8:
        print("Warning: Converting image array to uint8 for S-box application.")
        img_array = img_array.astype(np.uint8)
    
    sbox_applied_img = s_box_np[img_array]
    return sbox_applied_img

def apply_inverse_aes_sbox(img_array):
    
    if img_array.dtype != np.uint8:
        print("Warning: Converting image array to uint8 for inverse S-box application.")
        img_array = img_array.astype(np.uint8)
    
    inv_sbox_applied_img = inv_s_box_np[img_array]
    return inv_sbox_applied_img




def encrypt_image(img_array, acm_iterations, logistic_x0, logistic_r, acm_a=1, acm_b=1):
     
    print("Starting Encryption Process...")
    start_time = time.time()

    
    print(f"Applying Arnold's Cat Map with {acm_iterations} iterations (a={acm_a}, b={acm_b})...")
    try:
        
        if img_array.dtype != np.uint8:
            print(f"  Converting image to uint8 before ACM.")
            img_array = img_array.astype(np.uint8)
        shuffled_img = arnold_cat_map(img_array, acm_iterations, acm_a, acm_b)
    except ValueError as e:
        print(f"Error during ACM: {e}. Returning original image.")
        return img_array, 0 

    
    print(f"Applying AES S-box substitution...")
    try:
        sbox_applied_img = apply_aes_sbox(shuffled_img)
    except Exception as e: 
        print(f"Error during AES S-box application: {e}. Returning shuffled image.")
        return shuffled_img, time.time() - start_time 

    
    print(f"Applying Logistic Map encryption (x0={logistic_x0}, r={logistic_r})...")
    try:
        
        encrypted_img = logistic_map_encrypt_decrypt(sbox_applied_img, logistic_x0, logistic_r) 
    except ValueError as e:
        print(f"Error during Logistic Map encryption: {e}. Returning S-box applied image.")
        return sbox_applied_img, time.time() - start_time 

    end_time = time.time()
    encryption_time = end_time - start_time
    print(f"Encryption completed in {encryption_time:.4f} seconds.")
    return encrypted_img, encryption_time




def compress_data(data_array):
    
    print("Starting Compression...")
    start_time = time.time()
    
    try:
        original_bytes = data_array.tobytes()
    except AttributeError:
         print("Error: Input data_array does not support .tobytes(). Is it a NumPy array?")
         return None, 0

    
    compression_level = 7 
    compressed_bytes = zlib.compress(original_bytes, level=compression_level)
    end_time = time.time()
    compression_time = end_time - start_time

    original_size = len(original_bytes)
    compressed_size = len(compressed_bytes)
    ratio = compressed_size / original_size if original_size > 0 else 0
    print(f"Compression (zlib level {compression_level}) completed in {compression_time:.4f} seconds.")
    print(f"Original size: {original_size} bytes, Compressed size: {compressed_size} bytes, Ratio: {ratio:.4f}")
    return compressed_bytes, compression_time

def calculate_hash_bytes(byte_data):
    
    if not isinstance(byte_data, bytes):
        raise TypeError("Input for hashing must be bytes.")
    hasher = hashlib.sha256()
    hasher.update(byte_data)
    return hasher.hexdigest()


def steghide_embed_metadata(image_data, metadata_dict):
    
    print("
--- Performing Steganography: Hiding Metadata ---")

    
    if not isinstance(image_data, np.ndarray):
        print("Error: Image data must be a NumPy array for steganography")
        return image_data, False

    
    steg_img = image_data.copy()

    
    try:
        
        metadata_json = json.dumps(metadata_dict, separators=(',', ':')) 
        metadata_bytes = metadata_json.encode('utf-8')

        
        length_bytes = len(metadata_bytes).to_bytes(4, byteorder='big')
        full_payload = length_bytes + metadata_bytes

        print(f"Metadata size: {len(metadata_bytes)} bytes")
        print(f"Total payload with header: {len(full_payload)} bytes ({len(full_payload)*8} bits)")

        
        required_bits = len(full_payload) * 8
        available_bits = steg_img.size 

        if required_bits > available_bits:
            print(f"Error: Image too small for metadata ({required_bits} bits needed, {available_bits} available)")
            return image_data, False

        
        flat_img = steg_img.flatten()

        
        payload_bits = []
        for byte in full_payload:
            for bit_index in range(8):
                payload_bits.append((byte >> bit_index) & 1)

        
        for i, bit in enumerate(payload_bits):
            if i >= len(flat_img):
                print(f"Error: Ran out of pixels at index {i} while embedding bit {bit}. Should not happen if capacity check passed.")
                return image_data, False 

            
            flat_img[i] = (flat_img[i] & 0xFE) | bit

        
        steg_img = flat_img.reshape(image_data.shape)

        print(f"Successfully embedded {len(payload_bits)} bits of metadata")
        return steg_img, True

    except Exception as e:
        print(f"Steganography embedding failed: {e}")
        traceback.print_exc()
        return image_data, False

def steghide_extract_metadata(steg_img):
    
    print("
--- Extracting Hidden Metadata from Steganography ---")

    if not isinstance(steg_img, np.ndarray):
        print("Error: Image data must be a NumPy array for extraction")
        return None

    try:
        
        flat_img = steg_img.flatten()

        
        length_bits = []
        if len(flat_img) < 32:
             print("Error: Image too small to contain metadata length header.")
             return None
        for i in range(32):
             length_bits.append(flat_img[i] & 1)


        
        length_bytes = bytearray()
        for i in range(0, 32, 8):
            byte = 0
            for bit_index in range(8):
                if i + bit_index < len(length_bits):
                    byte |= (length_bits[i+bit_index] << bit_index)
            length_bytes.append(byte)

        
        metadata_length = int.from_bytes(length_bytes, byteorder='big')
        print(f"Detected metadata length: {metadata_length} bytes")

        
        max_possible_length = (flat_img.size - 32) // 8
        if metadata_length <= 0 or metadata_length > max_possible_length:
            print(f"Invalid metadata length detected ({metadata_length}), possibly corrupted or no metadata. Max possible: {max_possible_length}")
            return None

        
        num_metadata_bits = metadata_length * 8
        if 32 + num_metadata_bits > len(flat_img):
            print(f"Error: Image not large enough to contain declared metadata length ({num_metadata_bits} bits needed after header, only {len(flat_img)-32} available).")
            return None

        metadata_bits = []
        for i in range(32, 32 + num_metadata_bits):
             metadata_bits.append(flat_img[i] & 1)


        
        metadata_bytes = bytearray()
        for i in range(0, len(metadata_bits), 8):
            byte = 0
            for bit_index in range(8):
                if i+bit_index < len(metadata_bits):
                    byte |= (metadata_bits[i+bit_index] << bit_index)
            metadata_bytes.append(byte)

        
        
        metadata_json = metadata_bytes.decode('utf-8')
        metadata_dict = json.loads(metadata_json)

        print(f"Successfully extracted metadata: {len(metadata_dict)} fields")
        return metadata_dict

    except json.JSONDecodeError as e:
        print(f"Metadata extraction failed: Could not decode JSON - {e}")
        
        return None
    except Exception as e:
        print(f"Metadata extraction failed: {e}")
        traceback.print_exc()
        return None



def decompress_data(compressed_bytes, original_shape, original_dtype):
    
    print("Starting Decompression...")
    start_time = time.time()
    if not isinstance(compressed_bytes, bytes):
         print("Error: Input for decompression must be bytes.")
         return None, 0

    try:
        decompressed_bytes = zlib.decompress(compressed_bytes)

        
        
        try:
             dtype_itemsize = np.dtype(original_dtype).itemsize
             
             expected_bytes = int(np.prod(original_shape)) * dtype_itemsize 
        except TypeError as e:
             print(f"Error calculating expected size: Invalid shape {original_shape} or dtype {original_dtype}? {e}")
             
             raise ValueError("Cannot determine expected size from shape/dtype.")

        
        if len(decompressed_bytes) != expected_bytes:
             print(f"FATAL: Decompressed byte count ({len(decompressed_bytes)}) does not match expected count ({expected_bytes}) based on provided shape {original_shape} and dtype {original_dtype}.")
             print("This indicates data corruption, incorrect shape/dtype passed, or compression issues.")
             
             return None, time.time() - start_time 

        
        
        data_array = np.frombuffer(decompressed_bytes, dtype=original_dtype)
        
        data_array = data_array.reshape(original_shape)

        end_time = time.time()
        decompression_time = end_time - start_time
        print(f"Decompression completed in {decompression_time:.4f} seconds.")
        return data_array, decompression_time

    except zlib.error as e:
        print(f"Error during zlib decompression: {e}. Data may be corrupted.")
        return None, time.time() - start_time
    except ValueError as e:
        
        print(f"Error reshaping decompressed data (likely size mismatch or shape/dtype error): {e}")
        return None, time.time() - start_time
    except Exception as e:
        print(f"An unexpected error occurred during decompression: {e}")
        traceback.print_exc() 
        return None, time.time() - start_time

def decrypt_image(encrypted_img_array, acm_iterations, logistic_x0, logistic_r, original_shape_before_padding, padded, acm_a=1, acm_b=1):
     
    
    if encrypted_img_array is None:
         print("Error: Cannot decrypt None input.")
         return None, 0

    print("Starting Decryption Process (on decompressed data)...")
    start_time = time.time()

    
    print(f"Applying Logistic Map decryption (x0={logistic_x0}, r={logistic_r})...")
    try:
        
        logistic_decrypted_img = logistic_map_encrypt_decrypt(encrypted_img_array, logistic_x0, logistic_r) 
    except ValueError as e:
         print(f"Error during Logistic Map decryption: {e}. Returning None.")
         return None, time.time() - start_time

    
    print(f"Applying Inverse AES S-box substitution...")
    try:
        
        inv_sbox_applied_img = apply_inverse_aes_sbox(logistic_decrypted_img) 
    except Exception as e:
        print(f"Error during Inverse AES S-box application: {e}. Returning logistic decrypted image.")
        return logistic_decrypted_img, time.time() - start_time 

    
    print(f"Applying Inverse Arnold's Cat Map with {acm_iterations} iterations (a={acm_a}, b={acm_b})...")
    try:
        
        unshuffled_padded_img = inverse_arnold_cat_map(inv_sbox_applied_img, acm_iterations, acm_a, acm_b) 
    except ValueError as e:
         print(f"Error during Inverse ACM: {e}. Cannot unpad. Returning partially decrypted (inv-S-box applied) image.")
         
         return inv_sbox_applied_img, time.time() - start_time

    
    final_decrypted_img = unshuffled_padded_img 
    if padded: 
        current_h, current_w = unshuffled_padded_img.shape[:2]
        
        orig_h, orig_w = original_shape_before_padding[:2]

        
        if orig_h > current_h or orig_w > current_w:
             print(f"Error: Original dimensions ({orig_h}x{orig_w}) seem larger than current image dimensions ({current_h}x{current_w}) after inverse ACM. Cannot unpad.")
             
             return unshuffled_padded_img, time.time() - start_time

        
        if current_h != orig_h or current_w != orig_w:
            print(f"Removing padding to restore original size {original_shape_before_padding}...")
            
            pad_h_total = current_h - orig_h
            pad_w_total = current_w - orig_w
            
            pad_top = pad_h_total // 2
            pad_left = pad_w_total // 2

            
            try:
                if unshuffled_padded_img.ndim == 3: 
                    final_decrypted_img = unshuffled_padded_img[pad_top : pad_top + orig_h, pad_left : pad_left + orig_w, :]
                else: 
                    final_decrypted_img = unshuffled_padded_img[pad_top : pad_top + orig_h, pad_left : pad_left + orig_w]
                print(f"Final decrypted size after unpadding: {final_decrypted_img.shape[:2]}")
            except IndexError as e:
                 print(f"Error during unpadding slice (calculated indices might be wrong): {e}")
                 print(f"  current={current_h}x{current_w}, orig={orig_h}x{orig_w}, top={pad_top}, left={pad_left}")
                 
                 return unshuffled_padded_img, time.time() - start_time
        else:
            
             print("Padding flag was set, but dimensions seem to match the original size. No padding removed.")
             final_decrypted_img = unshuffled_padded_img 
    else:
        print("No padding was added initially, skipping unpadding step.")

    end_time = time.time()
    decryption_time = end_time - start_time
    print(f"Decryption completed in {decryption_time:.4f} seconds.")
    
    return final_decrypted_img.astype(np.uint8), decryption_time

def verify_integrity_compressed(received_compressed_data, original_compressed_hash):
    
    print(f"
--- Tamper Verification (Compressed Data) ---")
    if not isinstance(received_compressed_data, bytes):
        print("Error: Received data for hash verification is not bytes.")
        return False
    if not isinstance(original_compressed_hash, str) or len(original_compressed_hash) != 64:
        print("Error: Original hash for comparison is invalid.")
        return False

    print(f"Expected Hash:  {original_compressed_hash}")
    
    try:
        calculated_hash = calculate_hash_bytes(received_compressed_data)
        print(f"Calculated Hash:{calculated_hash}")
    except Exception as e:
        print(f"Error calculating hash of received data: {e}")
        return False

    if original_compressed_hash == calculated_hash:
        print("Integrity Check PASSED: Compressed data hashes match.")
        return True
    else:
        print("Integrity Check FAILED: Compressed data hashes DO NOT match. Data may be corrupted or tampered with.")
        return False



def calculate_metrics(img_orig, img_processed, data_range=255):
    
    
    if not isinstance(img_orig, np.ndarray) or not isinstance(img_processed, np.ndarray):
        print("Error: Inputs for metrics must be NumPy arrays.")
        
        entropy_orig = shannon_entropy(img_orig) if isinstance(img_orig, np.ndarray) else float('nan')
        return {'mse': float('inf'), 'psnr': 0, 'ssim': 0, 'entropy_orig': entropy_orig, 'entropy_proc': float('nan')}

    
    
    if img_orig.dtype != np.uint8:
         
         img_orig = img_orig.astype(np.uint8)
    if img_processed.dtype != np.uint8:
         
         img_processed = img_processed.astype(np.uint8)

    
    if img_orig.shape != img_processed.shape:
        print(f"Warning: Original ({img_orig.shape}) and processed ({img_processed.shape}) images have different shapes for metrics calculation.")
        print("This often happens if decryption/unpadding failed.")
        print("Metrics calculation skipped due to shape mismatch.")
        
        entropy_orig_val = float('nan')
        try:
             entropy_orig_val = shannon_entropy(img_orig)
        except Exception as e:
             print(f"Error calculating original entropy: {e}")
        return {'mse': float('inf'), 'psnr': 0, 'ssim': 0, 'entropy_orig': entropy_orig_val, 'entropy_proc': float('nan')}


    
    try:
        mse_val = mse(img_orig, img_processed)
    except Exception as e:
        print(f"Error calculating MSE: {e}")
        mse_val = float('inf')

    try:
        
        psnr_val = psnr(img_orig, img_processed, data_range=data_range)
    except Exception as e:
        print(f"Error calculating PSNR: {e}")
        psnr_val = 0 

    
    ssim_val = 0 
    try:
        multichannel = img_orig.ndim == 3
        min_dim = min(img_orig.shape[:2])
        
        
        win_size = min(7, min_dim)
        if win_size < 3:
             print(f"Image dimensions ({img_orig.shape[:2]}) too small for SSIM. Setting SSIM to 0.")
        elif win_size % 2 == 0:
             win_size -= 1 

        if win_size >= 3:
             
             c_axis = 2 if multichannel else None
             ssim_val = ssim(img_orig, img_processed, data_range=data_range,
                             multichannel=multichannel, channel_axis=c_axis,
                             win_size=win_size)
    except ValueError as e:
         
         print(f"Error calculating SSIM (check window size vs image dim): {e}. Setting SSIM to 0.")
         ssim_val = 0
    except Exception as e:
         print(f"Unexpected error calculating SSIM: {e}")
         ssim_val = 0


    
    try:
        entropy_orig_val = shannon_entropy(img_orig)
    except Exception as e:
        print(f"Error calculating original entropy: {e}")
        entropy_orig_val = float('nan')
    try:
        entropy_proc_val = shannon_entropy(img_processed)
    except Exception as e:
        print(f"Error calculating processed entropy: {e}")
        entropy_proc_val = float('nan')


    metrics = {
        'mse': mse_val,
        'psnr': psnr_val,
        'ssim': ssim_val,
        'entropy_orig': entropy_orig_val,
        'entropy_proc': entropy_proc_val
    }
    return metrics

def plot_histograms(img_orig, img_encrypted, img_decrypted):
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    fig.suptitle('Image Histograms', fontsize=16)
    colors = ('r', 'g', 'b')
    labels = ('Original (Unpadded)', 'Encrypted (Padded)', 'Decrypted (Final)')
    images = (img_orig, img_encrypted, img_decrypted)

    for i, img in enumerate(images):
        ax = axes[i]
        if img is None or not isinstance(img, np.ndarray): 
            ax.set_title(f"{labels[i]} (Not Available)")
            ax.text(0.5, 0.5, 'N/A', ha='center', va='center', transform=ax.transAxes, fontsize=12, color='red')
            ax.set_xticks([])
            ax.set_yticks([])
            continue

        
        ax.set_title(labels[i] + f" {img.shape}") 
        ax.set_xlabel('Pixel Intensity'); ax.set_ylabel('Frequency')
        try:
            if img.ndim == 3: 
                
                for c_idx, color in enumerate(colors):
                    if c_idx < img.shape[2]: 
                        
                        hist, bin_edges = np.histogram(img[:, :, c_idx].ravel(), bins=256, range=[0, 256])
                        ax.plot(bin_edges[:-1], hist, color=color, alpha=0.7, label=f'Ch {color.upper()}')
                if img.shape[2] > 1 : ax.legend(loc='upper right') 
            elif img.ndim == 2: 
                hist, bin_edges = np.histogram(img.ravel(), bins=256, range=[0, 256])
                ax.plot(bin_edges[:-1], hist, color='black')
            else:
                 ax.text(0.5, 0.5, f'Invalid Dim {img.ndim}', ha='center', va='center', transform=ax.transAxes)


            ax.set_xlim([0, 255])
            ax.grid(True, linestyle='--', alpha=0.6)
        except Exception as e:
             print(f"Error plotting histogram for {labels[i]}: {e}")
             ax.text(0.5, 0.5, 'Plotting Error', ha='center', va='center', transform=ax.transAxes, color='red')


    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) 
    plt.show()

def display_images(img_orig, img_encrypted, img_decrypted):
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    fig.suptitle('Image Encryption Results', fontsize=16)
    titles = ['Original Image (Unpadded)', 'Encrypted Image (Padded)', 'Decrypted Image (Final)']
    images = [img_orig, img_encrypted, img_decrypted]

    for ax, img, title in zip(axes, images, titles):
        ax.set_title(title)
        ax.axis('off') 
        if img is not None and isinstance(img, np.ndarray):
            
            cmap = 'gray' if img.ndim == 2 else None
            try:
                ax.imshow(img, cmap=cmap)
            except Exception as e:
                 print(f"Error displaying image '{title}': {e}")
                 ax.text(0.5, 0.5, 'Display Error', ha='center', va='center', transform=ax.transAxes, color='red')

        else:
             
             ax.text(0.5, 0.5, 'N/A', ha='center', va='center', transform=ax.transAxes, fontsize=12, color='red')

    plt.tight_layout(rect=[0, 0.03, 1, 0.95]) 
    plt.show()


def create_download_link_jupyter(filename, data_bytes, link_text, mime_type='application/octet-stream'):
    
    if ENV != 'jupyter' or not isinstance(data_bytes, bytes):
        return "" 
    try:
        b64 = base64.b64encode(data_bytes).decode('ascii') 
        
        base_filename = os.path.basename(filename)
        href = f'<a href="data:{mime_type};base64,{b64}" download="{base_filename}">{link_text}</a>'
        return href
    except Exception as e:
        print(f"Error creating download link for {filename}: {e}")
        return f"<span>Error creating link for {filename}</span>"







ACM_ITERATIONS = 10 
ACM_A = 1; ACM_B = 1 
LOGISTIC_X0 = 0.3141592653589793 
LOGISTIC_R = 3.9999999          


USE_GRAYSCALE = False             
SIMULATE_LOW_BANDWIDTH = False    
RESIZE_TARGET = None 



COMPRESSED_ENCRYPTED_FILENAME = "encrypted_compressed_data.zlib-steg" 
DECRYPTED_FILENAME = "decrypted_image.png" 


original_image_unpadded = None
original_image_padded = None
encrypted_image = None 
encrypted_image_before_steg = None 
compressed_encrypted_data = None
transmitted_hash = None
decompressed_encrypted_image = None
final_decrypted_image = None
integrity_check_passed = False 
encryption_time = 0
compression_time = 0
decompression_time = 0
decryption_time = 0
original_size_before_padding = (0,0)
was_padded = False
encrypted_shape = None 
encrypted_dtype = None 



uploaded_file_name = None
img_data_input = None 

print("--- Starting Setup ---") 

if ENV == 'colab':
    print("Environment: Google Colab")
    print("Please upload an image file:")
    try:
        uploaded = files.upload()
        if uploaded:
            
            uploaded_file_name = next(iter(uploaded))
            img_data_input = uploaded[uploaded_file_name] 
            print(f"Successfully uploaded: {uploaded_file_name} ({len(img_data_input)} bytes)")
        else:
            print("No file uploaded. Will use fallback image.")
            img_data_input = None 
    except Exception as e:
        print(f"An error occurred during Colab upload: {e}")
        img_data_input = None 

elif ENV == 'jupyter':
     print("Environment: Jupyter Notebook/Lab")
     print("Please use the widget below to upload an image file:")
     
     uploader = widgets.FileUpload(
         accept='image/*', 
         multiple=False, 
         description="Upload Image" 
     )
     display(uploader) 
     
     
     
     
     

else: 
    print("Environment: Other (e.g., script)")
    
    
    try:
        
        file_path = "input_image.png" 
        
        if os.path.exists(file_path):
            img_data_input = file_path 
            uploaded_file_name = os.path.basename(file_path)
            print(f"Using local file: {file_path}")
        else:
             print(f"File not found at specified path: {file_path}.")
             print("Will use fallback image.")
             img_data_input = None 
    except Exception as e:
        print(f"Error accessing local file path '{file_path}': {e}")
        img_data_input = None 







if ENV == 'jupyter' and 'uploader' in locals() and uploader.value:
    try:
        
        uploaded_file_key = list(uploader.value.keys())[0] 
        uploaded_file_info = uploader.value[uploaded_file_key] 

        uploaded_file_name = uploaded_file_info['metadata']['name']
        
        img_data_input = uploaded_file_info['content']
        print(f"Processing uploaded file (Jupyter): {uploaded_file_name} ({len(img_data_input)} bytes)")
        
        
        
    except Exception as e:
        print(f"Error processing Jupyter upload: {e}")
        
        img_data_input = None





print("--- Starting Image Processing Pipeline ---")

try:
    
    print("--- Task 1: Preprocessing ---")
    
    original_image_padded, original_size_before_padding, was_padded = preprocess_image(
        img_data_input, 
        target_size=RESIZE_TARGET,
        grayscale=USE_GRAYSCALE,
        simulate_low_bandwidth=SIMULATE_LOW_BANDWIDTH
    )

    if original_image_padded is None:
        raise ValueError("Preprocessing failed to produce an image array.")

    
    
    h_orig, w_orig = original_size_before_padding
    if was_padded:
        
        pad_h_total = original_image_padded.shape[0] - h_orig
        pad_w_total = original_image_padded.shape[1] - w_orig
        pad_top = pad_h_total // 2
        pad_left = pad_w_total // 2
        
        if original_image_padded.ndim == 3:
            original_image_unpadded = original_image_padded[pad_top : pad_top + h_orig, pad_left : pad_left + w_orig, :].copy()
        else: 
            original_image_unpadded = original_image_padded[pad_top : pad_top + h_orig, pad_left : pad_left + w_orig].copy()
    else:
        
        original_image_unpadded = original_image_padded.copy()

    print(f"Original image dimensions stored for metrics: {original_image_unpadded.shape}")
    print(f"Image array type after preprocessing: {original_image_padded.dtype}, shape: {original_image_padded.shape}")


    
    print("
--- Task 2: Encryption (ACM + S-Box + Logistic Map) ---")
    
    
    encrypted_image_before_steg, encryption_time = encrypt_image(
        original_image_padded, 
        acm_iterations=ACM_ITERATIONS,
        logistic_x0=LOGISTIC_X0, logistic_r=LOGISTIC_R,
        acm_a=ACM_A, acm_b=ACM_B
    )
    if encrypted_image_before_steg is None:
        raise ValueError("Encryption failed.")

    
    encrypted_shape = encrypted_image_before_steg.shape
    encrypted_dtype = encrypted_image_before_steg.dtype
    print(f"Encrypted image shape (before steg): {encrypted_shape}, dtype: {encrypted_dtype}")

    
    encrypted_image = encrypted_image_before_steg.copy()

    
    print("
--- Task 2.5: Steganography - Embedding Metadata ---")
    
    
    metadata = {
        "encrypted_by": "Enhanced Image Security System",
        "description": "Encrypted using ACM, AES S-box, Logistic Map, Compressed with zlib, Metadata via LSB Steg.",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S %Z"), 
        "encryption_params": {
            "acm_iterations": ACM_ITERATIONS,
            "acm_a": ACM_A,
            "acm_b": ACM_B,
            "logistic_x0": LOGISTIC_X0, 
            "logistic_r": LOGISTIC_R,   
            "original_shape_unpadded": list(original_image_unpadded.shape) if original_image_unpadded is not None else None,
            "original_shape_padded": list(original_image_padded.shape) if original_image_padded is not None else None,
            "dtype": str(original_image_padded.dtype) if original_image_padded is not None else None,
            "grayscale": USE_GRAYSCALE,
            "padded": was_padded,
            "pre_steg_shape": list(encrypted_shape), 
            "pre_steg_dtype": str(encrypted_dtype)   
        }
        
    }

    
    try:
        
        encrypted_image_with_steg, steg_success = steghide_embed_metadata(encrypted_image, metadata)

        if steg_success:
            encrypted_image = encrypted_image_with_steg  
            print("✅ Successfully embedded metadata using LSB steganography.")
            
        else:
            print("⚠️ Steganography embedding failed, using original encrypted data (without embedded metadata).")
            
    except Exception as e:
        print(f"Error during steganography embedding process: {e}")
        traceback.print_exc()
        print("Continuing with original encrypted data (without embedded metadata).")
        

    print(f"Final encrypted image shape (after steg attempt): {encrypted_image.shape}, dtype: {encrypted_image.dtype}")

    print("--- Task 3: Compression (zlib) ---")
    
    compressed_encrypted_data, compression_time = compress_data(encrypted_image)
    if compressed_encrypted_data is None:
        raise ValueError("Compression failed.")


    
    print("--- Task 4: Hashing Compressed Data ---")
    
    transmitted_hash = calculate_hash_bytes(compressed_encrypted_data)
    print(f"Calculated SHA-256 Hash of Compressed Data: {transmitted_hash}")


    
    
    
    received_compressed_data = compressed_encrypted_data
    received_hash = transmitted_hash 

    
    integrity_check_passed = verify_integrity_compressed(received_compressed_data, received_hash)


    
    extracted_metadata = None 
    if integrity_check_passed:
        print("--- Task 5: Decompression (zlib) ---")
        
        
        
        decompressed_encrypted_image, decompression_time = decompress_data(
            received_compressed_data,
            encrypted_shape, 
            encrypted_dtype  
        )
        if decompressed_encrypted_image is None:
            print("Decompression failed. Cannot proceed with decryption.")
            
            integrity_check_passed = False 
        else:
            print(f"Decompressed image shape: {decompressed_encrypted_image.shape}, dtype: {decompressed_encrypted_image.dtype}")
            
            
            
            print("--- Task 5.5: Extracting Metadata from Steganography ---")
            try:
                extracted_metadata = steghide_extract_metadata(decompressed_encrypted_image)

                if extracted_metadata:
                    print("
--- Steganography Metadata Retrieved ---")
                    
                    print(json.dumps(extracted_metadata, indent=2))
                    print("--------------------------------------
")
                    
                else:
                     print("No metadata could be extracted (or extraction failed).")
            except Exception as e:
                print(f"Metadata extraction process failed unexpectedly: {e}")
                traceback.print_exc()
                
    else:
        print("Skipping Decompression and Metadata Extraction due to failed integrity check.")
        decompressed_encrypted_image = None


    
    
    if integrity_check_passed and decompressed_encrypted_image is not None:
        print("--- Task 6: Decryption (Logistic Map -> Inv S-Box -> Inv ACM -> Unpad) ---")
        
        
        
        
        dec_acm_iter = extracted_metadata['encryption_params']['acm_iterations'] if extracted_metadata and 'acm_iterations' in extracted_metadata.get('encryption_params', {}) else ACM_ITERATIONS
        dec_acm_a = extracted_metadata['encryption_params']['acm_a'] if extracted_metadata and 'acm_a' in extracted_metadata.get('encryption_params', {}) else ACM_A
        dec_acm_b = extracted_metadata['encryption_params']['acm_b'] if extracted_metadata and 'acm_b' in extracted_metadata.get('encryption_params', {}) else ACM_B
        dec_log_x0 = extracted_metadata['encryption_params']['logistic_x0'] if extracted_metadata and 'logistic_x0' in extracted_metadata.get('encryption_params', {}) else LOGISTIC_X0
        dec_log_r = extracted_metadata['encryption_params']['logistic_r'] if extracted_metadata and 'logistic_r' in extracted_metadata.get('encryption_params', {}) else LOGISTIC_R
        
        dec_orig_shape = tuple(extracted_metadata['encryption_params']['original_shape_unpadded']) if extracted_metadata and extracted_metadata.get('encryption_params', {}).get('original_shape_unpadded') else original_size_before_padding
        dec_padded_flag = extracted_metadata['encryption_params']['padded'] if extracted_metadata and 'padded' in extracted_metadata.get('encryption_params', {}) else was_padded

        print(f"Using Decryption Parameters: ACM iter={dec_acm_iter}, a={dec_acm_a}, b={dec_acm_b}, x0={dec_log_x0}, r={dec_log_r}")
        print(f"Target Original Shape: {dec_orig_shape}, Padding Applied Originally: {dec_padded_flag}")

        final_decrypted_image, decryption_time = decrypt_image(
            decompressed_encrypted_image,
            acm_iterations=dec_acm_iter,
            logistic_x0=dec_log_x0,
            logistic_r=dec_log_r,
            original_shape_before_padding=dec_orig_shape, 
            padded=dec_padded_flag, 
            acm_a=dec_acm_a,
            acm_b=dec_acm_b
        )
        if final_decrypted_image is None:
             print("Decryption process failed to produce final image.")
             
             integrity_check_passed = False 
        else:
            print(f"Final decrypted image shape: {final_decrypted_image.shape}, dtype: {final_decrypted_image.dtype}")


    else:
        
        print("Skipping Decryption.")
        final_decrypted_image = None


    
    print("--- Task 7: Performance & Security Analysis ---")
    print("--- Timing ---")
    print(f"Encryption Time:   {encryption_time:.4f}s")
    print(f"Compression Time:  {compression_time:.4f}s")
    print(f"Decompression Time:{decompression_time:.4f}s")
    print(f"Decryption Time:   {decryption_time:.4f}s")
    total_time = encryption_time + compression_time + decompression_time + decryption_time
    print(f"Total Time (Enc->Comp->Decomp->Dec): {total_time:.4f}s")
    if original_image_padded is not None:
         print(f"Image dimensions processed (padded): {original_image_padded.shape}")
    if original_image_unpadded is not None:
         print(f"Original unpadded dimensions: {original_image_unpadded.shape}")

    print("--- Similarity Metrics (Original Unpadded vs Final Decrypted) ---")
    
    if integrity_check_passed and final_decrypted_image is not None:
        
        metrics_decrypted = calculate_metrics(original_image_unpadded, final_decrypted_image)
        print(f"MSE:  {metrics_decrypted.get('mse', 'N/A'):.4f}")
        
        psnr_val = metrics_decrypted.get('psnr', 0)
        psnr_str = f"{psnr_val:.4f} dB" if np.isfinite(psnr_val) else "inf (Perfect Reconstruction)"
        print(f"PSNR: {psnr_str}")
        print(f"SSIM: {metrics_decrypted.get('ssim', 'N/A'):.4f}")
        print(f"Entropy (Original):  {metrics_decrypted.get('entropy_orig', 'N/A'):.4f}")
        print(f"Entropy (Decrypted): {metrics_decrypted.get('entropy_proc', 'N/A'):.4f}")

        
        if metrics_decrypted.get('mse', 1) < 1e-6 and metrics_decrypted.get('ssim', 0) > 0.999: 
             print("✅ Metrics suggest Decryption SUCCESSFUL (Low MSE, High PSNR/SSIM).")
        else:
             print("⚠️ Warning: Metrics indicate differences between original and decrypted images.")
    else:
        print("Skipping decrypted metrics calculation (Integrity check failed or decryption error).")
        
        if original_image_unpadded is not None:
             try:
                  print(f"Entropy (Original):  {shannon_entropy(original_image_unpadded):.4f}")
             except Exception as e:
                  print(f"Could not calculate original entropy: {e}")


    print("--- Security Analysis (Original Unpadded vs Encrypted) ---")
    
    
    if original_image_unpadded is not None and encrypted_image_before_steg is not None:
         try:
              entropy_original = shannon_entropy(original_image_unpadded)
              entropy_encrypted = shannon_entropy(encrypted_image_before_steg) 
              print(f"Entropy (Original Unpadded): {entropy_original:.4f}")
              print(f"Entropy (Encrypted - Pre Steg):  {entropy_encrypted:.4f}")
              
              ideal_entropy = 8.0 
              entropy_diff = entropy_encrypted - entropy_original
              
              good_entropy_threshold = 7.5 
              significant_increase_threshold = 0.5 

              if entropy_encrypted > good_entropy_threshold and entropy_diff > significant_increase_threshold:
                  print("Entropy increased significantly towards ideal random distribution (Good).")
              elif entropy_diff > 0.1: 
                  print("Entropy increased after encryption (Okay).")
              else:
                  print("Warning: Entropy did not increase significantly after encryption. Encryption might be weak or ineffective.")
         except Exception as e:
              print(f"Could not perform entropy analysis: {e}")
    else:
         print("Cannot perform entropy comparison (missing original or pre-steg encrypted image).")


    print("--- Histograms & Image Display ---")
    
    
    plot_histograms(original_image_unpadded,
                    encrypted_image, 
                    final_decrypted_image if integrity_check_passed else None)
    display_images(original_image_unpadded,
                   encrypted_image, 
                   final_decrypted_image if integrity_check_passed else None)


    
    print("--- Key Sensitivity Test ---")
    
    
    if integrity_check_passed and decompressed_encrypted_image is not None:
        
        
        wrong_logistic_x0 = LOGISTIC_X0 + 1e-9 
        print(f"Attempting decryption with slightly modified key (x0 = {wrong_logistic_x0:.15f})...")

        
        
        decrypted_wrong_key, _ = decrypt_image(
            decompressed_encrypted_image, 
            ACM_ITERATIONS, 
            wrong_logistic_x0, 
            LOGISTIC_R,     
            original_size_before_padding, 
            was_padded, 
            ACM_A, ACM_B 
            )

        if decrypted_wrong_key is not None:
            
            metrics_wrong = calculate_metrics(original_image_unpadded, decrypted_wrong_key)
            print(f"Resulting PSNR (Wrong Key): {metrics_wrong.get('psnr', 0):.4f} dB")
            print(f"Resulting SSIM (Wrong Key): {metrics_wrong.get('ssim', 0):.4f}")
            
            if metrics_wrong.get('psnr', 100) < 15 and metrics_wrong.get('ssim', 1) < 0.1:
                print("✅ Key sensitivity test PASSED: Decryption with slightly wrong key produced significantly different result.")
            else:
                print("❌ Key sensitivity test FAILED: Decryption with slightly wrong key did not produce a significantly different result (PSNR/SSIM too high). Check algorithm/parameters.")
            
            
        else:
            print("Decryption with wrong key failed to produce an image for comparison.")
    else:
        print("Skipping key sensitivity test (Integrity check failed or decompressed data unavailable).")


    
    print("--- Task 8: Saving and Downloading Output ---")

    
    if compressed_encrypted_data is not None:
        try:
            with open(COMPRESSED_ENCRYPTED_FILENAME, "wb") as f:
                f.write(compressed_encrypted_data)
            print(f"Compressed encrypted data saved as: {COMPRESSED_ENCRYPTED_FILENAME}")
        except Exception as e:
            print(f"Error saving compressed encrypted data: {e}")
    else:
        print("Compressed encrypted data not available to save.")

    
    dec_img_pil = None
    
    if integrity_check_passed and final_decrypted_image is not None:
        try:
            
            if final_decrypted_image.dtype != np.uint8:
                 final_decrypted_image = final_decrypted_image.astype(np.uint8)
            dec_img_pil = Image.fromarray(final_decrypted_image)
            dec_img_pil.save(DECRYPTED_FILENAME)
            print(f"Final decrypted image saved as: {DECRYPTED_FILENAME}")
        except Exception as e:
            print(f"Error saving decrypted image: {e}")
            
            dec_img_pil = None
    else:
         print("Final decrypted image not saved (Integrity check failed or decryption error).")

    
    if ENV == 'colab':
        print("Initiating Colab downloads (if files were saved)...")
        
        if os.path.exists(COMPRESSED_ENCRYPTED_FILENAME):
             try:
                  files.download(COMPRESSED_ENCRYPTED_FILENAME)
             except Exception as e:
                  print(f"Colab download failed for {COMPRESSED_ENCRYPTED_FILENAME}: {e}")
        
        if dec_img_pil is not None and os.path.exists(DECRYPTED_FILENAME):
             try:
                  files.download(DECRYPTED_FILENAME)
             except Exception as e:
                  print(f"Colab download failed for {DECRYPTED_FILENAME}: {e}")

    elif ENV == 'jupyter':
        print("Generating Jupyter download links (if files were saved)...")
        links_html = []
        
        if compressed_encrypted_data is not None:
            link1 = create_download_link_jupyter(
                COMPRESSED_ENCRYPTED_FILENAME,
                compressed_encrypted_data, 
                f"Download Compressed Encrypted Data ({COMPRESSED_ENCRYPTED_FILENAME})",
                'application/zlib' 
             )
            if link1: links_html.append(link1) 

        
        if dec_img_pil is not None and os.path.exists(DECRYPTED_FILENAME):
             try:
                 with open(DECRYPTED_FILENAME, "rb") as f:
                     dec_png_bytes = f.read()
                 link2 = create_download_link_jupyter(
                     DECRYPTED_FILENAME,
                     dec_png_bytes, 
                     f"Download Decrypted Image ({DECRYPTED_FILENAME})",
                     'image/png' 
                 )
                 if link2: links_html.append(link2) 
             except Exception as e:
                  print(f"Could not read decrypted PNG file for download link: {e}")

        if links_html:
             display(HTML("<br>".join(links_html))) 
        else:
             print("No files available for download link generation.")

    else: 
        print("Output Files (if saved):")
        if os.path.exists(COMPRESSED_ENCRYPTED_FILENAME):
             print(f"- Compressed encrypted data: {os.path.abspath(COMPRESSED_ENCRYPTED_FILENAME)}")
        if dec_img_pil is not None and os.path.exists(DECRYPTED_FILENAME):
             print(f"- Final decrypted image: {os.path.abspath(DECRYPTED_FILENAME)}")
        print("(Manual download/retrieval required if not in Colab/Jupyter)")



except Exception as e:
    print(f"--- AN UNHANDLED ERROR OCCURRED IN THE MAIN PIPELINE ---")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Message: {e}")
    print("Traceback:")
    traceback.print_exc() 
    print("--- Pipeline Halted Due to Error ---")



finally:
    print("--- Image Processing Script Execution Finished ---")
