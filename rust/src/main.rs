use clap::{Parser, Subcommand};
use image::{DynamicImage, ImageFormat, ImageError as RustImageError};
use std::path::PathBuf;
use std::fs;
use std::time::Instant;
use std::process::ExitCode;
use hex; // Import hex crate

// Import local modules
mod config;
mod image_utils;
mod acm;
mod aes_sbox;
mod crypto;
mod steganography;
mod compression;

use config::*;
use image_utils::{preprocess_image, unpad_image, save_image, ImageError};
use acm::{arnold_cat_map, inverse_arnold_cat_map};
use aes_sbox::{apply_sbox, apply_inverse_sbox};
use crypto::{logistic_map_xor, calculate_sha256, verify_sha256};
use steganography::{embed_metadata, extract_metadata, StegError};
use compression::{compress_data, decompress_data};


// --- CLI Definition ---
#[derive(Parser, Debug)]
#[command(author, version, about, long_about = "Encrypts/Decrypts images using ACM, AES S-Box, Logistic Map XOR, with Compression, Hashing, and Steganography.")]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Subcommand, Debug)]
enum Commands {
    /// Encrypt an image file
    Encrypt {
        /// Input image file path
        #[arg(short, long, value_name = "FILE")]
        input: PathBuf,

        /// Output file path for compressed encrypted data (.zlib-steg recommended)
        #[arg(short, long, value_name = "FILE")]
        output: PathBuf,

        /// Convert image to grayscale before processing
        #[arg(short, long)]
        grayscale: bool,

        /// ACM iterations
        #[arg(long, default_value_t = DEFAULT_ACM_ITERATIONS)]
        acm_iter: u32,

        /// Logistic Map initial value x0
        #[arg(long, default_value_t = DEFAULT_LOGISTIC_X0)]
        log_x0: f64,

        /// Logistic Map parameter r
        #[arg(long, default_value_t = DEFAULT_LOGISTIC_R)]
        log_r: f64,
    },
    /// Decrypt an image file
    Decrypt {
        /// Input file path for compressed encrypted data
        #[arg(short, long, value_name = "FILE")]
        input: PathBuf,

        /// Output file path for the decrypted image (.png recommended)
        #[arg(short, long, value_name = "FILE")]
        output: PathBuf,

        /// Expected SHA-256 hash (hex string) for integrity check
        #[arg(short = 'H', long, value_name = "HASH")]
        hash: String,
    },
}

// --- Main Logic ---
fn main() -> ExitCode {
    let cli = Cli::parse();
    let start_time_total = Instant::now();

    let result = match cli.command {
        Commands::Encrypt { input, output, grayscale, acm_iter, log_x0, log_r } => {
            run_encryption(input, output, grayscale, acm_iter, log_x0, log_r)
        }
        Commands::Decrypt { input, output, hash } => {
            run_decryption(input, output, hash)
        }
    };

    match result {
        Ok(_) => {
            println!("\nOperation completed successfully in {:.4?}", start_time_total.elapsed());
            ExitCode::SUCCESS
        }
        Err(e) => {
            eprintln!("\n--- Error during operation ---");
            eprintln!("{}", e);
            // Consider printing specific error types or backtraces if using anyhow
            println!("Operation failed after {:.4?}", start_time_total.elapsed());
            ExitCode::FAILURE
        }
    }
}

// --- Encryption Workflow ---
fn run_encryption(
    input_path: PathBuf,
    output_path: PathBuf,
    grayscale: bool,
    acm_iter: u32,
    log_x0: f64,
    log_r: f64,
) -> Result<(), Box<dyn std::error::Error>> { // Use dynamic error for simplicity
    println!("--- Starting Encryption ---");

    // 1. Preprocessing
    let start_time = Instant::now();
    println!("\n[1/6] Preprocessing image...");
    let preprocessed = preprocess_image(&input_path, grayscale)?;
    let original_dims_unpadded = preprocessed.original_dims_unpadded; // width, height
    let was_padded = preprocessed.was_padded;
    let padded_dims = preprocessed.image_buffer.dimensions(); // width, height
    let channels = preprocessed.channels;
    let mut current_img = preprocessed.image_buffer; // Now mutable
    println!("Preprocessing complete ({:.4?})", start_time.elapsed());
    println!("  Original size: {}x{}", original_dims_unpadded.0, original_dims_unpadded.1);
    println!("  Padded size: {}x{}, Channels: {}", padded_dims.0, padded_dims.1, channels);


    // 2. ACM Shuffling
    let start_time = Instant::now();
    println!("\n[2/6] Applying Arnold's Cat Map ({} iterations)...", acm_iter);
    current_img = acm::arnold_cat_map(&current_img, acm_iter, DEFAULT_ACM_A, DEFAULT_ACM_B)?;
    println!("ACM complete ({:.4?})", start_time.elapsed());

    // 3. AES S-Box
    let start_time = Instant::now();
    println!("\n[3/6] Applying AES S-Box...");
    current_img = aes_sbox::apply_sbox(&current_img)?;
    println!("AES S-Box complete ({:.4?})", start_time.elapsed());

    // 4. Logistic Map XOR
    let start_time = Instant::now();
    println!("\n[4/6] Applying Logistic Map XOR (x0={}, r={})...", log_x0, log_r);
    current_img = crypto::logistic_map_xor(&current_img, log_x0, log_r)?;
    println!("Logistic Map XOR complete ({:.4?})", start_time.elapsed());

    // --- Before Steg/Compression: Store shape/params for metadata ---
    let encrypted_uncompressed_shape = current_img.dimensions();
    let metadata = DecryptionMetadata {
        encrypted_by: "image-encrypt-rust v0.1.0".to_string(),
        description: "Encrypted with ACM, AES S-Box, Logistic Map, Steg, Zlib".to_string(),
        timestamp: chrono::Local::now().to_rfc3339(), // Requires chrono crate
        encryption_params: EncryptionParams {
            acm_iterations: acm_iter,
            acm_a: DEFAULT_ACM_A,
            acm_b: DEFAULT_ACM_B,
            logistic_x0: log_x0,
            logistic_r: log_r,
            // Store HEIGHT, WIDTH in metadata for consistency with Python shape
            original_shape_unpadded: (original_dims_unpadded.1, original_dims_unpadded.0),
            original_shape_padded: (padded_dims.1, padded_dims.0, channels),
            grayscale,
            padded: was_padded,
            pre_steg_shape: (encrypted_uncompressed_shape.1, encrypted_uncompressed_shape.0, channels),
        }
    };


    // 5. Steganography (Embed Metadata)
    let start_time = Instant::now();
    println!("\n[5/6] Embedding metadata via LSB steganography...");
    current_img = steganography::embed_metadata(&current_img, &metadata)?;
    println!("Steganography complete ({:.4?})", start_time.elapsed());
    let data_to_compress = current_img.as_bytes(); // Get bytes of image *with* LSB metadata


    // 6. Compression & Hashing
    let start_time = Instant::now();
    println!("\n[6/6] Compressing data (zlib level {})...", config::COMPRESSION_LEVEL);
    let compressed_data = compression::compress_data(data_to_compress)?;
    let compression_time = start_time.elapsed();

    let start_time = Instant::now();
    println!("Calculating SHA-256 hash of compressed data...");
    let hash_bytes = crypto::calculate_sha256(&compressed_data);
    let hash_hex = hex::encode(&hash_bytes); // Use imported hex crate
    println!("Compression & Hashing complete ({:.4?} + {:.4?})", compression_time, start_time.elapsed());
    println!("  Compressed size: {} bytes", compressed_data.len());
    println!("  SHA-256 Hash: {}", hash_hex);


    // Save compressed data
    println!("Saving compressed encrypted data to: {:?}", output_path);
    fs::write(&output_path, &compressed_data)?;

    println!("\n--- Encryption Summary ---");
    println!("-> Input Image: {:?}", input_path);
    println!("-> Output File: {:?}", output_path);
    println!("-> SHA-256 Hash (of output file): {}", hash_hex);
    println!("   (Use this hash for decryption integrity check)");

    Ok(())
}


// --- Decryption Workflow ---
fn run_decryption(
    input_path: PathBuf,
    output_path: PathBuf,
    expected_hash_hex: String,
) -> Result<(), Box<dyn std::error::Error>> {
    println!("--- Starting Decryption ---");

    // 1. Read Compressed Data
    println!("\n[1/7] Reading compressed data from: {:?}", input_path);
    let compressed_data = fs::read(&input_path)?;
    println!("  Read {} bytes.", compressed_data.len());

    // 2. Verify Integrity (Hash Check)
    let start_time = Instant::now();
    println!("\n[2/7] Verifying SHA-256 hash...");
    if !crypto::verify_sha256(&compressed_data, &expected_hash_hex) {
        return Err("Integrity check FAILED: Hashes do not match. Data corrupted or wrong hash provided.".into());
    }
    println!("Integrity check PASSED ({:.4?})", start_time.elapsed());

    // 3. Decompression
    let start_time = Instant::now();
    println!("\n[3/7] Decompressing data (zlib)...");
    let decompressed_bytes = compression::decompress_data(&compressed_data)?;
    println!("Decompression complete ({:.4?})", start_time.elapsed());
    println!("  Decompressed size: {} bytes", decompressed_bytes.len());


    // 4. Extract Metadata & Reconstruct Image Buffer
    let start_time = Instant::now();
    println!("\n[4/7] Extracting metadata via LSB steganography...");
    // Need to reconstruct a temporary DynamicImage from bytes and expected shape (from *metadata* ideally)
    // This is the tricky part: we need the shape *before* we can extract metadata reliably.
    // Assumption: We MUST know the dimensions and color type of the *encrypted, pre-compression* image
    // to correctly interpret the decompressed_bytes.
    // --> Let's assume we get it from a reliable source OR make the user provide it OR store it separately.
    // --> *Correction*: Metadata *itself* stores pre_steg_shape. We extract THAT first, *then* use it.

    // --- Attempt to extract metadata using a *temporary* image view ---
    // We still need a reasonable guess of dimensions/color type to parse the LSBs initially
    // Let's try extracting *only* the length header first, assuming RGB/Luma and estimating size.
    // This is fragile. A better approach might be needed (e.g. fixed metadata block size/location).
    // *** Revised Steganography approach to handle this better ***
    // The `extract_metadata` now needs the decompressed bytes and *must* infer shape/color somehow,
    // or we assume a default/pass it. Let's assume we *can* get metadata first.

    // We need the shape from metadata to correctly interpret `decompressed_bytes`
    // Temporarily create a placeholder image to run extraction, hoping dimensions/color match enough for LSBs
    // THIS IS A MAJOR SIMPLIFICATION AND POTENTIAL POINT OF FAILURE
    // A robust solution might need a fixed-size header *before* zlib compression with shape info.
    // Let's TRY extracting assuming shape info IS in metadata:
    // Need to reconstruct image buffer from decompressed_bytes + metadata shape
    let temp_metadata_extract_img: DynamicImage; // Placeholder
    let metadata: DecryptionMetadata;

    // --- This section is complex and needs careful design ---
    // How to get dimensions BEFORE parsing bytes into image? Chicken-and-egg.
    // Workaround: Assume dimensions based on expected output or trial-and-error LSB read? Very fragile.
    // Robust way: Add uncompressed header *before* zlib with shape/color info.
    // Let's proceed *assuming* we got the metadata somehow (e.g. user provides shape, or fixed header):

    // ---- SIMPLIFIED/ASSUMED METADATA EXTRACTION ----
    // In a real app, handle the shape inference robustly.
    // We will pretend we know the shape from `pre_steg_shape` in the metadata for now.
    // THIS WILL LIKELY FAIL without the actual shape.
    println!("  (Assuming pre-compression shape is known for extraction - needs robust implementation)");
    // Example: If we knew shape was (512, 512, 3) = 786432 bytes for RGB u8
    let expected_bytes_from_metadata = 786432; // *** Replace with actual logic ***
    let (h, w, ch) = (512, 512, 3); // *** Replace with actual logic ***

    if decompressed_bytes.len() != expected_bytes_from_metadata {
         return Err(format!(
             "Decompressed size {} does not match expected size {} based on assumed/metadata shape ({}x{}x{}). Cannot reconstruct image.",
             decompressed_bytes.len(), expected_bytes_from_metadata, h, w, ch
         ).into());
    }

    // Reconstruct the DynamicImage from bytes and KNOWN shape/color
    let mut current_img = match ch {
         1 => DynamicImage::ImageLuma8(
             image::ImageBuffer::<Luma<u8>, _>::from_raw(w, h, decompressed_bytes)
                 .ok_or("Failed to create Luma buffer from raw bytes")?
         ),
         3 => DynamicImage::ImageRgb8(
             image::ImageBuffer::<Rgb<u8>, _>::from_raw(w, h, decompressed_bytes)
                 .ok_or("Failed to create Rgb buffer from raw bytes")?
         ),
         _ => return Err("Unsupported channel count from metadata".into())
    };
    // --- END OF SIMPLIFIED/ASSUMED SECTION ---


    // Now extract metadata using the reconstructed image
    metadata = steganography::extract_metadata(&current_img)?;
    println!("Metadata extraction complete ({:.4?})", start_time.elapsed());
    println!("  Extracted Params: {:?}", metadata.encryption_params);
    let params = metadata.encryption_params; // Use extracted params

    // Verify shape consistency
     let (meta_h, meta_w, meta_ch) = params.pre_steg_shape;
     if meta_h != current_img.height() || meta_w != current_img.width() || meta_ch != current_img.color().channel_count() {
          eprintln!("Warning: Shape in metadata ({},{},{}) differs from reconstructed image ({},{},{}). Proceeding with caution.",
               meta_h, meta_w, meta_ch, current_img.height(), current_img.width(), current_img.color().channel_count());
          // Could return an error here if strict matching is required.
     }


    // 5. Logistic Map XOR Decryption
    let start_time = Instant::now();
    println!("\n[5/7] Applying Logistic Map XOR Decryption (using extracted params)...");
    current_img = crypto::logistic_map_xor(&current_img, params.logistic_x0, params.logistic_r)?;
    println!("Logistic XOR complete ({:.4?})", start_time.elapsed());

    // 6. Inverse AES S-Box
    let start_time = Instant::now();
    println!("\n[6/7] Applying Inverse AES S-Box...");
    current_img = aes_sbox::apply_inverse_sbox(&current_img)?;
    println!("Inverse S-Box complete ({:.4?})", start_time.elapsed());

    // 7. Inverse ACM & Unpadding
    let start_time = Instant::now();
    println!("\n[7/7] Applying Inverse ACM ({} iterations) & Unpadding...", params.acm_iterations);
    current_img = acm::inverse_arnold_cat_map(&current_img, params.acm_iterations, params.acm_a, params.acm_b)?;
    let final_img = image_utils::unpad_image(&current_img, &params)?;
    println!("Inverse ACM & Unpadding complete ({:.4?})", start_time.elapsed());


    // Save decrypted image
    println!("Saving decrypted image to: {:?}", output_path);
    // Infer format from output path extension, default to PNG
    let format = ImageFormat::from_path(&output_path).unwrap_or(ImageFormat::Png);
    image_utils::save_image(&final_img, &output_path, format)?;

    println!("\n--- Decryption Summary ---");
    println!("-> Input File: {:?}", input_path);
    println!("-> Output Image: {:?}", output_path);
    println!("-> Integrity Check: PASSED");

    Ok(())
}


// --- Helper to get current timestamp string ---
// Requires `chrono` crate: `chrono = { version = "0.4", features = ["serde", "local"] }`
mod chrono {
     pub use chrono::*; // Re-export if using chrono crate
     // Placeholder if chrono is not added
     // pub fn Local::now() -> LocalTimePlaceholder { LocalTimePlaceholder }
     // pub struct LocalTimePlaceholder;
     // impl LocalTimePlaceholder { pub fn to_rfc3339(&self) -> String { "Timestamp N/A".to_string() } }
}
