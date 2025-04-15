use image::{DynamicImage, GenericImageView, Pixel};
use crate::config::DecryptionMetadata;
use crate::image_utils::ImageError;
use serde_json;
use byteorder::{BigEndian, WriteBytesExt, ReadBytesExt};
use std::io::Cursor;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum StegError {
    #[error("Image capacity insufficient: {needed} bits needed, {available} available")]
    InsufficientCapacity { needed: usize, available: usize },
    #[error("JSON serialization/deserialization error: {0}")]
    JsonError(#[from] serde_json::Error),
    #[error("I/O error during byte conversion: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Invalid metadata length detected")]
    InvalidLength,
    #[error("Image error: {0}")]
    ImageError(#[from] ImageError), // Propagate image errors
    #[error("Ran out of pixels during operation")]
    PixelRanOut,
}

// Embed metadata using LSB
pub fn embed_metadata(
    img: &DynamicImage,
    metadata: &DecryptionMetadata,
) -> Result<DynamicImage, StegError> {
    let mut steg_img = img.clone();
    let metadata_json = serde_json::to_string(metadata)?;
    let metadata_bytes = metadata_json.as_bytes();

    // Prepare 4-byte length header
    let mut len_bytes = vec![];
    len_bytes.write_u32::<BigEndian>(metadata_bytes.len() as u32)?;
    if len_bytes.len() != 4 { /* Should not happen with u32 */ return Err(StegError::IoError(std::io::Error::new(std::io::ErrorKind::Other, "Length header incorrect size"))); }

    let full_payload = [len_bytes.as_slice(), metadata_bytes].concat();
    let required_bits = full_payload.len() * 8;
    let available_bits = (steg_img.width() * steg_img.height() * steg_img.color().channel_count() as u32) as usize;

    if required_bits > available_bits {
        return Err(StegError::InsufficientCapacity { needed: required_bits, available: available_bits });
    }

    // --- Manual LSB Embedding ---
    let mut bit_index = 0;
    let (width, height) = steg_img.dimensions();

    'outer: for y in 0..height {
        for x in 0..width {
            // Get pixel mutable
            let mut pixel = steg_img.get_pixel(x, y);
            let channels = pixel.channels_mut(); // Get mutable slice of channels [R, G, B] or [L]

            for channel_index in 0..channels.len() {
                 if bit_index >= required_bits {
                     break 'outer; // All bits embedded
                 }

                 let byte_index = bit_index / 8;
                 let bit_in_byte_index = bit_index % 8;
                 let payload_bit = (full_payload[byte_index] >> bit_in_byte_index) & 1;

                 // Modify LSB of the channel value
                 channels[channel_index] = (channels[channel_index] & 0xFE) | payload_bit;

                 bit_index += 1;
            }
             // Put the modified pixel back - THIS IS KEY
             steg_img.put_pixel(x, y, pixel);
        }
    }
     if bit_index != required_bits {
         // This check ensures we didn't somehow exit early without error
         eprintln!("Warning: Embedding finished but not all bits seem written ({}/{})", bit_index, required_bits);
          return Err(StegError::PixelRanOut); // Or handle differently
     }


    println!("Successfully embedded {} bits of metadata", required_bits);
    Ok(steg_img)
}


// Extract metadata using LSB
pub fn extract_metadata(img: &DynamicImage) -> Result<DecryptionMetadata, StegError> {
    let (width, height) = img.dimensions();
    let total_components = (width * height * img.color().channel_count() as u32) as usize;

    if total_components < 32 { // Need at least 32 bits for length header
        return Err(StegError::InsufficientCapacity { needed: 32, available: total_components });
    }

    let mut extracted_bits = Vec::with_capacity(32); // Start with length bits
    let mut bit_count = 0;

    // --- Manual LSB Extraction ---
    // 1. Extract Length Header (32 bits)
     'outer_len: for y in 0..height {
         for x in 0..width {
             let pixel = img.get_pixel(x, y);
             let channels = pixel.channels();
             for channel_value in channels {
                 if bit_count >= 32 {
                     break 'outer_len;
                 }
                 extracted_bits.push(*channel_value & 1); // Extract LSB
                 bit_count += 1;
             }
         }
     }

    if bit_count < 32 { /* Should have been caught by capacity check */ return Err(StegError::PixelRanOut); }

    // Convert length bits to u32
    let mut len_bytes = Vec::new();
    for chunk in extracted_bits.chunks(8) {
        let mut byte = 0u8;
        for (i, &bit) in chunk.iter().enumerate() {
            byte |= bit << i;
        }
        len_bytes.push(byte);
    }
    let mut cursor = Cursor::new(len_bytes);
    let metadata_length = cursor.read_u32::<BigEndian>()? as usize;

    println!("Detected metadata length: {} bytes", metadata_length);

    // Sanity check length
    let required_total_bits = 32 + metadata_length * 8;
    if metadata_length == 0 || required_total_bits > total_components {
        return Err(StegError::InvalidLength);
    }

    // 2. Extract Metadata Payload
    extracted_bits.clear(); // Reuse vec or create new one
    extracted_bits.reserve(metadata_length * 8);
    bit_count = 0; // Reset bit count for payload extraction phase
    let mut bits_to_extract = metadata_length * 8;
    let mut component_index = 0; // Track overall component index

     'outer_payload: for y in 0..height {
         for x in 0..width {
             let pixel = img.get_pixel(x, y);
             let channels = pixel.channels();
             for channel_value in channels {
                 component_index +=1;
                 // Skip components used for the length header
                 if component_index <= 32 {
                      continue;
                 }

                 if bit_count >= bits_to_extract {
                     break 'outer_payload;
                 }
                 extracted_bits.push(*channel_value & 1); // Extract LSB
                 bit_count += 1;
             }
         }
     }

    if bit_count != bits_to_extract {
        eprintln!("Error: Extracted {} bits, but expected {} based on header", bit_count, bits_to_extract);
        return Err(StegError::PixelRanOut); // Or InvalidLength?
    }

    // Convert metadata bits to bytes
    let mut metadata_bytes = Vec::new();
    for chunk in extracted_bits.chunks(8) {
        let mut byte = 0u8;
        for (i, &bit) in chunk.iter().enumerate() {
            byte |= bit << i;
        }
        metadata_bytes.push(byte);
    }

    // Decode bytes to JSON and parse
    let metadata_json = String::from_utf8(metadata_bytes)
        .map_err(|_| StegError::JsonError(serde_json::Error::custom("Invalid UTF-8 sequence")))?; // Map error type
    let metadata: DecryptionMetadata = serde_json::from_str(&metadata_json)?;

    println!("Successfully extracted metadata");
    Ok(metadata)
}

// Helper trait for serde_json::Error to implement Custom Error
use serde::de::Error as SerdeError;
struct CustomError(String);
impl SerdeError for CustomError {
    fn custom<T: std::fmt::Display>(msg: T) -> Self {
        CustomError(msg.to_string())
    }
}
impl std::fmt::Display for CustomError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        write!(f, "{}", self.0)
    }
}
impl std::fmt::Debug for CustomError {
     fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
         write!(f, "Custom Serde Error: {}", self.0)
     }
}
impl std::error::Error for CustomError {}
