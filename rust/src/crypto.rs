use image::DynamicImage;
use sha2::{Sha256, Digest};
use crate::image_utils::ImageError;

const BURN_IN_ITERATIONS: usize = 100;

// Generate Logistic Map sequence (simplified)
fn generate_logistic_map_sequence(x0: f64, r: f64, size: usize) -> Result<Vec<f64>, &'static str> {
    if !(0.0 < x0 && x0 < 1.0) || !(3.57 <= r && r <= 4.0) {
         // Basic parameter check, could be more nuanced
         // eprintln!("Warning: Logistic map parameters might be unstable (x0={}, r={})", x0, r);
         // Allow execution but warn, or return Err
         // return Err("Logistic map parameters potentially unstable");
    }

    let mut sequence = Vec::with_capacity(size);
    let mut x = x0;

    // Burn-in
    for _ in 0..BURN_IN_ITERATIONS {
        x = r * x * (1.0 - x);
        // Check for convergence to fixed points (0 or (r-1)/r) - simplified check
         if x < 1e-9 || (x - (r-1.0)/r).abs() < 1e-9 {
              // This indicates potential issues with chosen parameters
              // eprintln!("Warning: Logistic map potentially converged during burn-in.");
         }
    }

    // Generate sequence
    for _ in 0..size {
        x = r * x * (1.0 - x);
        sequence.push(x);
        // Add checks for overflow/underflow or convergence if needed
        if !x.is_finite() {
            return Err("Logistic map generated non-finite value.");
        }
         if x < 1e-15 || (1.0-x) < 1e-15 {
              // Reached near 0 or 1, might become stable. Could add perturbation or error out.
              // eprintln!("Warning: Logistic map sequence near 0 or 1.");
         }
    }

    Ok(sequence)
}

// Encrypt/Decrypt using Logistic Map XOR (operates on raw bytes)
pub fn logistic_map_xor(
    img: &DynamicImage,
    x0: f64,
    r: f64,
) -> Result<DynamicImage, ImageError> {
    let mut processed_img = img.clone();
    let buf = processed_img.as_mut_bytes();
    let total_bytes = buf.len();

    let sequence = generate_logistic_map_sequence(x0, r, total_bytes)
        .map_err(|e| ImageError::InvalidDimensions)?; // Map error type

    // Convert sequence to u8 keystream and XOR
    for (i, byte) in buf.iter_mut().enumerate() {
        // Scale float (0, 1) to u8 [0, 255]
        let key_byte = (sequence[i] * 255.999999).floor() as u8;
        *byte ^= key_byte;
    }

    Ok(processed_img)
}

// Calculate SHA-256 hash of byte data
pub fn calculate_sha256(data: &[u8]) -> Vec<u8> {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hasher.finalize().to_vec()
}

// Verify hash (takes expected hash as hex string)
pub fn verify_sha256(data: &[u8], expected_hash_hex: &str) -> bool {
    let calculated_hash = calculate_sha256(data);
    let calculated_hash_hex = hex::encode(calculated_hash);
    println!("Expected Hash:  {}", expected_hash_hex);
    println!("Calculated Hash:{}", calculated_hash_hex);
    calculated_hash_hex == expected_hash_hex
}
