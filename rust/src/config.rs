use serde::{Serialize, Deserialize};

// Default encryption parameters (can be overridden by CLI args)
pub const DEFAULT_ACM_ITERATIONS: u32 = 10;
pub const DEFAULT_ACM_A: i64 = 1;
pub const DEFAULT_ACM_B: i64 = 1;
pub const DEFAULT_LOGISTIC_X0: f64 = 0.3141592653589793;
pub const DEFAULT_LOGISTIC_R: f64 = 3.9999999;
pub const COMPRESSION_LEVEL: u32 = 7; // zlib compression level (0-9)

// Metadata structure for steganography
#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct DecryptionMetadata {
    pub encrypted_by: String,
    pub description: String,
    pub timestamp: String, // Consider using chrono crate for proper timestamps
    pub encryption_params: EncryptionParams,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct EncryptionParams {
    pub acm_iterations: u32,
    pub acm_a: i64,
    pub acm_b: i64,
    pub logistic_x0: f64,
    pub logistic_r: f64,
    // Store original dimensions (height, width) before padding
    pub original_shape_unpadded: (u32, u32),
    // Store dimensions after padding (which is square)
    pub original_shape_padded: (u32, u32, u8), // height, width, channels (e.g., 1 for Luma, 3 for RGB)
    pub grayscale: bool,
    pub padded: bool,
    // Shape/type of the data *before* compression (which includes steg LSB mods)
    pub pre_steg_shape: (u32, u32, u8), // height, width, channels
    // Dtype is implicitly u8 for image buffers
}
