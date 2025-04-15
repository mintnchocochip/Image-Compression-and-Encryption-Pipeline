use image::{DynamicImage, GenericImageView, ImageBuffer, Rgb, Luma, ImageFormat, imageops};
use crate::config::EncryptionParams; // Assuming metadata is used here
use std::path::Path;
use std::cmp::max;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum ImageError {
    #[error("Image loading failed: {0}")]
    LoadError(#[from] image::ImageError),
    #[error("Unsupported color type")]
    UnsupportedColor,
    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),
    #[error("Invalid dimensions for operation")]
    InvalidDimensions,
}

// Represents the state after preprocessing
pub struct PreprocessedImage {
    pub image_buffer: DynamicImage, // Padded image data
    pub original_dims_unpadded: (u32, u32), // width, height
    pub was_padded: bool,
    pub is_grayscale: bool,
    pub channels: u8, // 1 for Luma, 3 for RGB
}

// Simplified preprocessing - load, convert, pad to square
pub fn preprocess_image<P: AsRef<Path>>(
    path: P,
    grayscale: bool,
) -> Result<PreprocessedImage, ImageError> {
    let img = image::open(path)?;
    let original_dims_unpadded = img.dimensions(); // (width, height)

    // Convert to Grayscale (Luma8) or RGB8
    let mut working_img = if grayscale {
        DynamicImage::ImageLuma8(img.into_luma8())
    } else {
        // Handle RGBA -> RGB conversion if necessary
        match img {
            DynamicImage::ImageRgba8(rgba) => {
                // Simple blend on white background
                let (w, h) = rgba.dimensions();
                let mut rgb_img = ImageBuffer::from_pixel(w, h, Rgb([255u8, 255, 255]));
                for x in 0..w {
                    for y in 0..h {
                        let pixel = rgba.get_pixel(x, y);
                        if pixel[3] == 255 { // Opaque
                           rgb_img.put_pixel(x, y, Rgb([pixel[0], pixel[1], pixel[2]]));
                        } else if pixel[3] > 0 { // Semi-transparent
                           // Simple alpha blending (approximate) - can be more sophisticated
                           let alpha_f = pixel[3] as f32 / 255.0;
                           let r = (pixel[0] as f32 * alpha_f + 255.0 * (1.0 - alpha_f)) as u8;
                           let g = (pixel[1] as f32 * alpha_f + 255.0 * (1.0 - alpha_f)) as u8;
                           let b = (pixel[2] as f32 * alpha_f + 255.0 * (1.0 - alpha_f)) as u8;
                           rgb_img.put_pixel(x, y, Rgb([r,g,b]));
                        } // else: Fully transparent, leave as white
                    }
                }
                DynamicImage::ImageRgb8(rgb_img)
            }
            DynamicImage::ImageRgb8(_) => img, // Already RGB
            DynamicImage::ImageLuma8(_) => if grayscale { img } else { DynamicImage::ImageRgb8(img.into_rgb8()) },
            DynamicImage::ImageLumaA8(_) => if grayscale { DynamicImage::ImageLuma8(img.into_luma8()) } else { DynamicImage::ImageRgb8(img.into_rgb8()) }, // Approx conversion
            _ => return Err(ImageError::UnsupportedColor), // Or handle other types
        }
    };

    let (current_w, current_h) = working_img.dimensions();
    let mut was_padded = false;
    let channels = match working_img {
        DynamicImage::ImageLuma8(_) => 1,
        DynamicImage::ImageRgb8(_) => 3,
        _ => return Err(ImageError::UnsupportedColor), // Should not happen after conversion
    };

    // Pad to square if needed
    if current_w != current_h {
        was_padded = true;
        let max_dim = max(current_w, current_h);
        let pad_w = max_dim - current_w;
        let pad_h = max_dim - current_h;
        let pad_left = pad_w / 2;
        let pad_top = pad_h / 2;

        // Create a new black canvas and place the image
        working_img = match working_img {
             DynamicImage::ImageLuma8(buf) => {
                 let mut padded_buf = ImageBuffer::from_pixel(max_dim, max_dim, Luma([0u8]));
                 imageops::overlay(&mut padded_buf, &buf, pad_left.into(), pad_top.into());
                 DynamicImage::ImageLuma8(padded_buf)
             },
             DynamicImage::ImageRgb8(buf) => {
                 let mut padded_buf = ImageBuffer::from_pixel(max_dim, max_dim, Rgb([0u8, 0, 0]));
                 imageops::overlay(&mut padded_buf, &buf, pad_left.into(), pad_top.into());
                 DynamicImage::ImageRgb8(padded_buf)
             },
             _ => unreachable!(), // Should be Luma8 or Rgb8
         };

        println!("Padded image to {}x{}", max_dim, max_dim);
    }

    Ok(PreprocessedImage {
        image_buffer: working_img,
        original_dims_unpadded: original_dims_unpadded,
        was_padded,
        is_grayscale: grayscale,
        channels,
    })
}

// Simplified postprocessing - unpad image based on metadata
pub fn unpad_image(
    img: &DynamicImage,
    params: &EncryptionParams,
) -> Result<DynamicImage, ImageError> {
    if !params.padded {
        return Ok(img.clone()); // No padding to remove
    }

    let (current_w, current_h) = img.dimensions();
    let (orig_w, orig_h) = params.original_shape_unpadded;

    if orig_h > current_h || orig_w > current_w {
        eprintln!("Warning: Original dimensions larger than current dimensions, cannot unpad.");
        return Err(ImageError::InvalidDimensions);
    }

    if orig_h == current_h && orig_w == current_w {
         println!("Padding flag was set, but dimensions match original. No unpadding performed.");
         return Ok(img.clone());
    }

    let pad_h_total = current_h - orig_h;
    let pad_w_total = current_w - orig_w;
    let pad_top = pad_h_total / 2;
    let pad_left = pad_w_total / 2;

    println!("Removing padding to restore original size {}x{}", orig_w, orig_h);

    // Use crop_imm for immutable borrowing if possible, or clone/crop
    let cropped_img = img.crop_imm(pad_left, pad_top, orig_w, orig_h);
    Ok(cropped_img)
}

pub fn save_image<P: AsRef<Path>>(
    img: &DynamicImage,
    path: P,
    format: ImageFormat,
) -> Result<(), ImageError> {
    img.save_with_format(path, format)?;
    Ok(())
}
