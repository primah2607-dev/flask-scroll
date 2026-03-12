import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import os


class ImageComparator:
    """AI-powered image comparison with difference detection and bounding box generation."""
    
    def __init__(self, threshold=0.3, min_area=100):
        """
        Initialize the comparator.
        
        Args:
            threshold: Threshold for difference detection (0-1, lower = more sensitive)
            min_area: Minimum area of difference region to draw a box (in pixels)
        """
        self.threshold = threshold
        self.min_area = min_area
    
    def load_images(self, baseline_path, actual_path):
        """Load and preprocess images."""
        baseline = cv2.imread(baseline_path)
        actual = cv2.imread(actual_path)
        
        if baseline is None:
            raise ValueError(f"Cannot load baseline image: {baseline_path}")
        if actual is None:
            raise ValueError(f"Cannot load actual image: {actual_path}")
        
        # Resize actual to match baseline dimensions if different
        if baseline.shape != actual.shape:
            actual = cv2.resize(actual, (baseline.shape[1], baseline.shape[0]))
        
        return baseline, actual
    
    def detect_differences(self, baseline, actual):
        """
        Detect differences between two images using multiple CV techniques.
        Returns: difference_mask, bounding_boxes
        """
        # Convert to grayscale
        gray_baseline = cv2.cvtColor(baseline, cv2.COLOR_BGR2GRAY)
        gray_actual = cv2.cvtColor(actual, cv2.COLOR_BGR2GRAY)
        
        # Method 1: Absolute difference
        diff = cv2.absdiff(gray_baseline, gray_actual)
        
        # Method 2: Structural Similarity Index (SSIM) for better detection
        score, diff_ssim = ssim(gray_baseline, gray_actual, full=True)
        diff_ssim = (1 - diff_ssim) * 255
        diff_ssim = diff_ssim.astype(np.uint8)
        
        # Combine both methods
        combined_diff = cv2.addWeighted(diff, 0.5, diff_ssim, 0.5, 0)
        
        # Apply threshold
        _, thresh = cv2.threshold(combined_diff, int(255 * self.threshold), 255, cv2.THRESH_BINARY)
        
        # Apply morphological operations to clean up noise
        kernel = np.ones((5, 5), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Dilate to merge nearby differences
        thresh = cv2.dilate(thresh, kernel, iterations=2)
        
        return thresh, score
    
    def get_bounding_boxes(self, difference_mask):
        """Extract bounding boxes around difference regions."""
        # Find contours
        contours, _ = cv2.findContours(difference_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Add padding
                padding = 5
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(difference_mask.shape[1] - x, w + 2 * padding)
                h = min(difference_mask.shape[0] - y, h + 2 * padding)
                bounding_boxes.append((x, y, w, h))
        
        return bounding_boxes
    
    def draw_differences(self, actual_image, bounding_boxes, difference_mask=None):
        """Draw bounding boxes on the actual image highlighting differences."""
        result = actual_image.copy()
        
        # Draw semi-transparent overlay for difference regions
        if difference_mask is not None:
            overlay = result.copy()
            # Create colored mask (red tint)
            mask_colored = cv2.applyColorMap(difference_mask, cv2.COLORMAP_HOT)
            # Blend with original
            cv2.addWeighted(overlay, 0.3, mask_colored, 0.3, 0, overlay)
            # Apply only where differences exist
            mask_bool = difference_mask > 0
            result[mask_bool] = overlay[mask_bool]
        
        # Draw bounding boxes
        for x, y, w, h in bounding_boxes:
            # Draw rectangle with red border
            cv2.rectangle(result, (x, y), (x + w, y + h), (0, 0, 255), 3)
            # Draw filled rectangle with transparency
            overlay = result.copy()
            cv2.rectangle(overlay, (x, y), (x + w, y + h), (0, 0, 255), -1)
            cv2.addWeighted(overlay, 0.2, result, 0.8, 0, result)
        
        return result
    
    def compare(self, baseline_path, actual_path, output_path=None):
        """
        Main comparison method.
        
        Returns:
            dict with:
                - output_image: annotated actual image
                - similarity_score: SSIM score (0-1, higher = more similar)
                - num_differences: number of difference regions
                - bounding_boxes: list of (x, y, w, h) tuples
        """
        # Load images
        baseline, actual = self.load_images(baseline_path, actual_path)
        
        # Detect differences
        difference_mask, similarity_score = self.detect_differences(baseline, actual)
        
        # Get bounding boxes
        bounding_boxes = self.get_bounding_boxes(difference_mask)
        
        # Draw differences on actual image
        output_image = self.draw_differences(actual, bounding_boxes, difference_mask)
        
        # Save output if path provided
        if output_path:
            cv2.imwrite(output_path, output_image)
        
        return {
            'output_image': output_image,
            'similarity_score': float(similarity_score),
            'num_differences': len(bounding_boxes),
            'bounding_boxes': bounding_boxes,
            'difference_mask': difference_mask
        }


def compare_images(baseline_path, actual_path, output_path, threshold=0.3, min_area=100):
    """
    Convenience function for comparing images.
    
    Args:
        baseline_path: Path to baseline screenshot
        actual_path: Path to actual screenshot
        output_path: Path to save annotated output image
        threshold: Difference detection threshold (0-1)
        min_area: Minimum area for bounding boxes
    
    Returns:
        Comparison results dictionary
    """
    comparator = ImageComparator(threshold=threshold, min_area=min_area)
    return comparator.compare(baseline_path, actual_path, output_path)
