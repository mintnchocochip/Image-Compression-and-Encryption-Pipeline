use image::{DynamicImage, GenericImageView, GenericImage, Pixel};
use crate::image_utils::ImageError; // Re-use error type

// Helper for modulo arithmetic with potentially negative results
fn modulo(a: i64, n: i64) -> i64 {
    ((a % n) + n) % n
}

// Apply Arnold's Cat Map (Simplified: operates directly on DynamicImage)
pub fn arnold_cat_map(
    img: &DynamicImage,
    iterations: u32,
    a: i64,
    b: i64,
) -> Result<DynamicImage, ImageError> {
    let (width, height) = img.dimensions();
    if width != height {
        return Err(ImageError::InvalidDimensions); // Must be square
    }
    let n = width as i64; // Dimension for modulo

    let mut current_img = img.clone(); // Work on a mutable copy

    for _iter in 0..iterations {
        let mut next_img = current_img.clone(); // Create buffer for next state
        for x in 0..width {
            for y in 0..height {
                let x_i64 = x as i64;
                let y_i64 = y as i64;

                // ACM formula: x' = (x + b*y) mod N, y' = (a*x + (a*b+1)*y) mod N
                let next_x = modulo(x_i64 + b * y_i64, n);
                let next_y = modulo(a * x_i64 + (a * b + 1) * y_i64, n);

                // Copy pixel from (x, y) in current_img to (next_x, next_y) in next_img
                let pixel = current_img.get_pixel(x, y);
                // put_pixel expects u32 coordinates
                next_img.put_pixel(next_x as u32, next_y as u32, pixel);
            }
        }
        current_img = next_img; // Update for next iteration
    }
    Ok(current_img)
}

// Apply Inverse Arnold's Cat Map
pub fn inverse_arnold_cat_map(
    img: &DynamicImage,
    iterations: u32,
    a: i64,
    b: i64,
) -> Result<DynamicImage, ImageError> {
    let (width, height) = img.dimensions();
    if width != height {
        return Err(ImageError::InvalidDimensions);
    }
    let n = width as i64;

    // Inverse transform coefficients
    let inv_coeff_00 = a * b + 1;
    let inv_coeff_01 = -b;
    let inv_coeff_10 = -a;
    let inv_coeff_11 = 1;

    let mut current_img = img.clone();

    for _iter in 0..iterations {
        let mut prev_img = current_img.clone(); // Buffer for the previous state (original locations)
        for next_x in 0..width { // Iterate through the *target* coordinates
            for next_y in 0..height {
                let next_x_i64 = next_x as i64;
                let next_y_i64 = next_y as i64;

                // Inverse ACM formula: x = ((a*b+1)*x' - b*y') mod N, y = (-a*x' + y') mod N
                let x = modulo(inv_coeff_00 * next_x_i64 + inv_coeff_01 * next_y_i64, n);
                let y = modulo(inv_coeff_10 * next_x_i64 + inv_coeff_11 * next_y_i64, n);

                // Copy pixel from (next_x, next_y) in current_img to (x, y) in prev_img
                let pixel = current_img.get_pixel(next_x, next_y);
                 // put_pixel expects u32 coordinates
                prev_img.put_pixel(x as u32, y as u32, pixel);
            }
        }
        current_img = prev_img; // Update for next iteration
    }
    Ok(current_img)
}
