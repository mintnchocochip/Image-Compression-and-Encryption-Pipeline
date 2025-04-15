use flate2::write::ZlibEncoder;
use flate2::read::ZlibDecoder;
use flate2::Compression;
use std::io::{Read, Write};
use crate::config; // To get compression level

// Compress data using zlib
pub fn compress_data(data: &[u8]) -> Result<Vec<u8>, std::io::Error> {
    let mut encoder = ZlibEncoder::new(Vec::new(), Compression::new(config::COMPRESSION_LEVEL));
    encoder.write_all(data)?;
    encoder.finish()
}

// Decompress data using zlib
pub fn decompress_data(compressed_data: &[u8]) -> Result<Vec<u8>, std::io::Error> {
    let mut decoder = ZlibDecoder::new(compressed_data);
    let mut decompressed_data = Vec::new();
    decoder.read_to_end(&mut decompressed_data)?;
    Ok(decompressed_data)
}
