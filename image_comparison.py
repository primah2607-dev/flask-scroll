import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import os
from typing import List, Tuple, Dict

# Try to import pytesseract for OCR (optional)
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("Warning: pytesseract not available. OCR features will be disabled.")


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
    
    def merge_nearby_boxes(self, boxes, merge_threshold=30):
        """
        Merge bounding boxes that are close to each other to reduce clutter.
        
        Args:
            boxes: List of (x, y, w, h) tuples
            merge_threshold: Maximum distance between boxes to merge them (in pixels)
        
        Returns:
            List of merged bounding boxes
        """
        if not boxes:
            return []
        
        # Convert to list of lists for easier manipulation
        boxes_list = [list(box) for box in boxes]
        merged = []
        used = [False] * len(boxes_list)
        
        for i, (x1, y1, w1, h1) in enumerate(boxes_list):
            if used[i]:
                continue
            
            # Start with current box
            merged_box = [x1, y1, w1, h1]
            used[i] = True
            
            # Try to merge with nearby boxes
            changed = True
            while changed:
                changed = False
                for j, (x2, y2, w2, h2) in enumerate(boxes_list):
                    if used[j]:
                        continue
                    
                    # Calculate centers and distances
                    cx1, cy1 = x1 + w1/2, y1 + h1/2
                    cx2, cy2 = x2 + w2/2, y2 + h2/2
                    distance = np.sqrt((cx1 - cx2)**2 + (cy1 - cy2)**2)
                    
                    # Check if boxes are close (considering box sizes)
                    max_size = max(w1, h1, w2, h2)
                    if distance < merge_threshold + max_size * 0.5:
                        # Merge boxes
                        min_x = min(x1, x2)
                        min_y = min(y1, y2)
                        max_x = max(x1 + w1, x2 + w2)
                        max_y = max(y1 + h1, y2 + h2)
                        
                        merged_box = [min_x, min_y, max_x - min_x, max_y - min_y]
                        used[j] = True
                        changed = True
                        
                        # Update current box for next iteration
                        x1, y1, w1, h1 = merged_box
            
            merged.append(tuple(merged_box))
        
        return merged
    
    def get_bounding_boxes(self, difference_mask, merge_boxes=False):
        """Extract bounding boxes around difference regions."""
        # Find contours
        contours, _ = cv2.findContours(difference_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bounding_boxes = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area >= self.min_area:
                x, y, w, h = cv2.boundingRect(contour)
                # Add padding for better visibility
                padding = 8
                x = max(0, x - padding)
                y = max(0, y - padding)
                w = min(difference_mask.shape[1] - x, w + 2 * padding)
                h = min(difference_mask.shape[0] - y, h + 2 * padding)
                bounding_boxes.append((x, y, w, h))
        
        # Only merge if there are too many boxes (more than 20) and they're very close
        if merge_boxes and len(bounding_boxes) > 20:
            bounding_boxes = self.merge_nearby_boxes(bounding_boxes, merge_threshold=15)
        
        return bounding_boxes
    
    def extract_text_from_region(self, image_region):
        """
        Extract text from an image region using OCR.
        Returns the extracted text or None if OCR is not available or fails.
        """
        if not OCR_AVAILABLE:
            return None
        
        try:
            # Preprocess image for better OCR
            if len(image_region.shape) == 3:
                gray = cv2.cvtColor(image_region, cv2.COLOR_BGR2GRAY)
            else:
                gray = image_region
            
            # Enhance contrast
            gray = cv2.convertScaleAbs(gray, alpha=1.5, beta=30)
            
            # Resize if too small
            if gray.shape[0] < 20 or gray.shape[1] < 20:
                scale = max(20 / gray.shape[0], 20 / gray.shape[1])
                new_w = int(gray.shape[1] * scale)
                new_h = int(gray.shape[0] * scale)
                gray = cv2.resize(gray, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
            
            # Use OCR to extract text
            text = pytesseract.image_to_string(gray, config='--psm 7 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.,!?()[]{}:;-\'" ').strip()
            return text if text else None
        except Exception as e:
            return None
    
    def detect_element_presence(self, baseline_region, actual_region):
        """
        Detect if an element is present in one image but not the other.
        Returns a description of presence/absence.
        """
        # Convert to grayscale
        baseline_gray = cv2.cvtColor(baseline_region, cv2.COLOR_BGR2GRAY) if len(baseline_region.shape) == 3 else baseline_region
        actual_gray = cv2.cvtColor(actual_region, cv2.COLOR_BGR2GRAY) if len(actual_region.shape) == 3 else actual_region
        
        # Calculate non-empty pixel ratio
        baseline_non_empty = np.sum(baseline_gray > 10) / baseline_gray.size if baseline_gray.size > 0 else 0
        actual_non_empty = np.sum(actual_gray > 10) / actual_gray.size if actual_gray.size > 0 else 0
        
        # Threshold for considering an element "present"
        presence_threshold = 0.1
        
        if baseline_non_empty < presence_threshold and actual_non_empty > presence_threshold:
            # Element present in actual but not in baseline
            return "present_in_actual"
        elif baseline_non_empty > presence_threshold and actual_non_empty < presence_threshold:
            # Element present in baseline but not in actual
            return "present_in_baseline"
        else:
            return None
    
    def get_color_name(self, bgr_color):
        """Convert BGR color to a human-readable color name."""
        b, g, r = bgr_color
        # Convert to RGB for easier naming
        rgb = (r, g, b)
        
        # Common color ranges
        if max(rgb) - min(rgb) < 30:  # Grayscale
            avg = sum(rgb) / 3
            if avg < 50:
                return "black"
            elif avg < 100:
                return "dark grey"
            elif avg < 150:
                return "grey"
            elif avg < 200:
                return "light grey"
            else:
                return "white"
        else:
            # Colored
            if r > 200 and g < 100 and b < 100:
                return "red"
            elif r < 100 and g > 200 and b < 100:
                return "green"
            elif r < 100 and g < 100 and b > 200:
                return "blue"
            elif r > 200 and g > 200 and b < 100:
                return "yellow"
            elif r > 200 and g < 100 and b > 200:
                return "magenta"
            elif r < 100 and g > 200 and b > 200:
                return "cyan"
            elif r > 150 and g > 100 and b < 100:
                return "orange"
            elif r < 100 and g < 100 and b > 150:
                return "blue"
            else:
                return f"RGB({r},{g},{b})"
    
    def calculate_spacing(self, image, x, y, w, h):
        """Calculate spacing/padding around an element."""
        # Check spacing on all sides
        spacing_info = {}
        
        # Top spacing
        top_region = image[max(0, y-50):y, x:x+w] if y > 0 else None
        if top_region is not None and top_region.size > 0:
            top_gray = cv2.cvtColor(top_region, cv2.COLOR_BGR2GRAY) if len(top_region.shape) == 3 else top_region
            # Find where content starts from top
            top_content = np.where(np.any(top_gray < 250, axis=1))[0]
            if len(top_content) > 0:
                spacing_info['top'] = len(top_gray) - top_content[-1] - 1
            else:
                spacing_info['top'] = len(top_gray)
        
        # Bottom spacing
        bottom_region = image[y+h:min(image.shape[0], y+h+50), x:x+w] if y+h < image.shape[0] else None
        if bottom_region is not None and bottom_region.size > 0:
            bottom_gray = cv2.cvtColor(bottom_region, cv2.COLOR_BGR2GRAY) if len(bottom_region.shape) == 3 else bottom_region
            bottom_content = np.where(np.any(bottom_gray < 250, axis=1))[0]
            if len(bottom_content) > 0:
                spacing_info['bottom'] = bottom_content[0] if len(bottom_content) > 0 else len(bottom_gray)
            else:
                spacing_info['bottom'] = len(bottom_gray)
        
        # Left spacing
        left_region = image[y:y+h, max(0, x-50):x] if x > 0 else None
        if left_region is not None and left_region.size > 0:
            left_gray = cv2.cvtColor(left_region, cv2.COLOR_BGR2GRAY) if len(left_region.shape) == 3 else left_region
            left_content = np.where(np.any(left_gray < 250, axis=0))[0]
            if len(left_content) > 0:
                spacing_info['left'] = len(left_gray[0]) - left_content[-1] - 1
            else:
                spacing_info['left'] = len(left_gray[0])
        
        # Right spacing
        right_region = image[y:y+h, x+w:min(image.shape[1], x+w+50)] if x+w < image.shape[1] else None
        if right_region is not None and right_region.size > 0:
            right_gray = cv2.cvtColor(right_region, cv2.COLOR_BGR2GRAY) if len(right_region.shape) == 3 else right_region
            right_content = np.where(np.any(right_gray < 250, axis=0))[0]
            if len(right_content) > 0:
                spacing_info['right'] = right_content[0] if len(right_content) > 0 else len(right_gray[0])
            else:
                spacing_info['right'] = len(right_gray[0])
        
        return spacing_info
    
    def detect_element_type(self, region, w, h):
        """
        Detect what type of element is in the region: icon, text, image, button, etc.
        Returns: 'icon', 'text', 'image', 'button', 'unknown'
        """
        if region.size == 0:
            return 'unknown'
        
        # Convert to grayscale
        if len(region.shape) == 3:
            gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
        else:
            gray = region
        
        # Calculate characteristics
        area = w * h
        non_zero_pixels = np.sum(gray > 10)
        fill_ratio = non_zero_pixels / area if area > 0 else 0
        
        # Detect edges
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / area if area > 0 else 0
        
        # Aspect ratio
        aspect_ratio = w / h if h > 0 else 1
        
        # Icon detection: small, square-ish, high edge density, moderate fill
        if area < 2500 and 0.7 < aspect_ratio < 1.4 and edge_density > 0.1 and 0.2 < fill_ratio < 0.8:
            return 'icon'
        
        # Text detection: horizontal, low fill ratio, high edge density
        if w > h * 1.5 and fill_ratio < 0.3 and edge_density > 0.05:
            return 'text'
        
        # Image detection: large area, high fill ratio
        if area > 10000 and fill_ratio > 0.5:
            return 'image'
        
        # Button detection: rectangular, moderate size, moderate fill
        if 500 < area < 5000 and 2 < aspect_ratio < 5 and 0.3 < fill_ratio < 0.7:
            return 'button'
        
        return 'unknown'
    
    def analyze_region_difference(self, baseline, actual, x, y, w, h):
        """
        Analyze a specific region to determine what type of discrepancy exists.
        Returns a descriptive text about the difference with specific measurements.
        """
        # Extract regions with some context
        context_padding = 20
        x_start = max(0, x - context_padding)
        y_start = max(0, y - context_padding)
        x_end = min(baseline.shape[1], x + w + context_padding)
        y_end = min(baseline.shape[0], y + h + context_padding)
        
        baseline_region = baseline[y_start:y_end, x_start:x_end]
        actual_region = actual[y_start:y_end, x_start:x_end]
        baseline_region_exact = baseline[y:y+h, x:x+w]
        actual_region_exact = actual[y:y+h, x:x+w]
        
        if baseline_region.size == 0 or actual_region.size == 0:
            return "Region difference detected"
        
        # Detect element type FIRST to guide analysis
        baseline_element_type = self.detect_element_type(baseline_region_exact, w, h)
        actual_element_type = self.detect_element_type(actual_region_exact, w, h)
        
        # Check for element presence/absence
        presence_info = self.detect_element_presence(baseline_region_exact, actual_region_exact)
        
        # Try to extract text from both regions (only if it's likely text)
        baseline_text = None
        actual_text = None
        if baseline_element_type == 'text' or actual_element_type == 'text' or (w < 200 and h < 50):
            baseline_text = self.extract_text_from_region(baseline_region_exact)
            actual_text = self.extract_text_from_region(actual_region_exact)
        
        # Build detailed description with specific measurements
        detailed_differences = []
        
        # Determine element name based on type
        element_name = "element"
        if baseline_element_type == 'icon' or actual_element_type == 'icon':
            element_name = "icon"
        elif baseline_element_type == 'text' or actual_element_type == 'text':
            element_name = "text"
        elif baseline_element_type == 'image' or actual_element_type == 'image':
            element_name = "image"
        elif baseline_element_type == 'button' or actual_element_type == 'button':
            element_name = "button"
        
        # 1. Color differences with specific color names (for icons, buttons, images)
        if len(baseline_region_exact.shape) == 3 and len(actual_region_exact.shape) == 3:
            baseline_mean_color = np.mean(baseline_region_exact, axis=(0, 1)).astype(int)
            actual_mean_color = np.mean(actual_region_exact, axis=(0, 1)).astype(int)
            color_diff = np.linalg.norm(baseline_mean_color - actual_mean_color)
            
            if color_diff > 30:  # Significant color difference
                baseline_color_name = self.get_color_name(baseline_mean_color)
                actual_color_name = self.get_color_name(actual_mean_color)
                if baseline_color_name != actual_color_name:
                    detailed_differences.append(f"In baseline image the {element_name} color is {baseline_color_name}, but in actual image it's {actual_color_name}.")
        
        # 2. Size differences with specific pixel measurements
        baseline_area = np.sum(cv2.cvtColor(baseline_region_exact, cv2.COLOR_BGR2GRAY) > 0) if len(baseline_region_exact.shape) == 3 else np.sum(baseline_region_exact > 0)
        actual_area = np.sum(cv2.cvtColor(actual_region_exact, cv2.COLOR_BGR2GRAY) > 0) if len(actual_region_exact.shape) == 3 else np.sum(actual_region_exact > 0)
        
        # Calculate element dimensions
        baseline_gray = cv2.cvtColor(baseline_region_exact, cv2.COLOR_BGR2GRAY) if len(baseline_region_exact.shape) == 3 else baseline_region_exact
        actual_gray = cv2.cvtColor(actual_region_exact, cv2.COLOR_BGR2GRAY) if len(actual_region_exact.shape) == 3 else actual_region_exact
        
        baseline_non_zero = np.where(baseline_gray > 10)
        actual_non_zero = np.where(actual_gray > 10)
        
        if len(baseline_non_zero[0]) > 0 and len(actual_non_zero[0]) > 0:
            baseline_height = baseline_non_zero[0].max() - baseline_non_zero[0].min() + 1 if len(baseline_non_zero[0]) > 0 else h
            baseline_width = baseline_non_zero[1].max() - baseline_non_zero[1].min() + 1 if len(baseline_non_zero[1]) > 0 else w
            actual_height = actual_non_zero[0].max() - actual_non_zero[0].min() + 1 if len(actual_non_zero[0]) > 0 else h
            actual_width = actual_non_zero[1].max() - actual_non_zero[1].min() + 1 if len(actual_non_zero[1]) > 0 else w
            
            if abs(baseline_width - actual_width) > 5 or abs(baseline_height - actual_height) > 5:
                detailed_differences.append(f"In baseline image the {element_name} size is {baseline_width}×{baseline_height} pixels, but in actual image it's {actual_width}×{actual_height} pixels.")
        
        # 3. Spacing/Padding differences with specific pixel measurements
        baseline_spacing = self.calculate_spacing(baseline, x, y, w, h)
        actual_spacing = self.calculate_spacing(actual, x, y, w, h)
        
        spacing_diffs = []
        for side in ['top', 'bottom', 'left', 'right']:
            if side in baseline_spacing and side in actual_spacing:
                if abs(baseline_spacing[side] - actual_spacing[side]) > 3:
                    spacing_diffs.append(f"{side} spacing: {baseline_spacing[side]}px (baseline) vs {actual_spacing[side]}px (actual)")
        
        if spacing_diffs:
            detailed_differences.append(f"Spacing difference: {', '.join(spacing_diffs)}.")
        
        # 4. Text content differences
        content_info = ""
        if baseline_text and actual_text and baseline_text != actual_text:
            content_info = f"In baseline image text is '{baseline_text}', but in actual image it's '{actual_text}'."
            detailed_differences.append(content_info)
        elif baseline_text and not actual_text:
            content_info = f"In baseline image text is '{baseline_text}', but in actual image no text is detected."
            detailed_differences.append(content_info)
        elif not baseline_text and actual_text:
            content_info = f"In baseline image no text is detected, but in actual image text is '{actual_text}'."
            detailed_differences.append(content_info)
        
        # 5. Detailed font analysis (ONLY if it's actually text, not icons)
        # Only analyze font if element type is text, not icon
        if (baseline_element_type == 'text' or actual_element_type == 'text') and w < 200 and h < 50:
            font_differences = []
            
            # Font size analysis
            baseline_edges = cv2.Canny(baseline_gray, 50, 150)
            actual_edges = cv2.Canny(actual_gray, 50, 150)
            baseline_char_height = np.sum(baseline_edges, axis=1)
            actual_char_height = np.sum(actual_edges, axis=1)
            
            baseline_avg_height = np.mean(baseline_char_height[baseline_char_height > 0]) if np.any(baseline_char_height > 0) else 0
            actual_avg_height = np.mean(actual_char_height[actual_char_height > 0]) if np.any(actual_char_height > 0) else 0
            
            if baseline_avg_height > 0 and actual_avg_height > 0:
                baseline_font_size = int(baseline_avg_height * 0.8)  # Approximate font size
                actual_font_size = int(actual_avg_height * 0.8)
                
                if abs(baseline_font_size - actual_font_size) > 1:
                    font_differences.append(f"font size is {baseline_font_size}px, but in actual image it's {actual_font_size}px.")
            
            # Font weight analysis (bold vs normal)
            baseline_edge_density = np.sum(baseline_edges > 0) / (w * h) if w * h > 0 else 0
            actual_edge_density = np.sum(actual_edges > 0) / (w * h) if w * h > 0 else 0
            
            if abs(baseline_edge_density - actual_edge_density) > 0.05:
                baseline_weight = "bold" if baseline_edge_density > 0.15 else "normal"
                actual_weight = "bold" if actual_edge_density > 0.15 else "normal"
                if baseline_weight != actual_weight:
                    font_differences.append(f"font weight is {baseline_weight}, but in actual image it's {actual_weight}")
                elif baseline_edge_density > actual_edge_density + 0.05:
                    font_differences.append(f"font weight is heavier/bolder in baseline compared to actual")
                elif actual_edge_density > baseline_edge_density + 0.05:
                    font_differences.append(f"font weight is heavier/bolder in actual compared to baseline")
            
            # Font style analysis (italic detection)
            # Analyze character slant/angle
            baseline_contours, _ = cv2.findContours(baseline_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            actual_contours, _ = cv2.findContours(actual_edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if len(baseline_contours) > 0 and len(actual_contours) > 0:
                # Calculate average angle of text (for italic detection)
                baseline_angles = []
                actual_angles = []
                
                for contour in baseline_contours[:5]:  # Check first few characters
                    if len(contour) >= 5:
                        rect = cv2.minAreaRect(contour)
                        angle = rect[2]
                        if angle != 0:
                            baseline_angles.append(abs(angle))
                
                for contour in actual_contours[:5]:
                    if len(contour) >= 5:
                        rect = cv2.minAreaRect(contour)
                        angle = rect[2]
                        if angle != 0:
                            actual_angles.append(abs(angle))
                
                if len(baseline_angles) > 0 and len(actual_angles) > 0:
                    baseline_avg_angle = np.mean(baseline_angles)
                    actual_avg_angle = np.mean(actual_angles)
                    
                    # Italic text typically has angles between 10-20 degrees
                    baseline_is_italic = 10 < baseline_avg_angle < 20
                    actual_is_italic = 10 < actual_avg_angle < 20
                    
                    if baseline_is_italic != actual_is_italic:
                        if baseline_is_italic:
                            font_differences.append(f"font style is italic, but in actual image it's normal")
                        else:
                            font_differences.append(f"font style is normal, but in actual image it's italic")
            
            # Letter spacing analysis
            baseline_horizontal_density = np.sum(baseline_edges, axis=0)
            actual_horizontal_density = np.sum(actual_edges, axis=0)
            
            baseline_char_gaps = []
            actual_char_gaps = []
            
            # Find gaps between characters
            baseline_non_zero = np.where(baseline_horizontal_density > 0)[0]
            actual_non_zero = np.where(actual_horizontal_density > 0)[0]
            
            if len(baseline_non_zero) > 1:
                baseline_gaps = np.diff(baseline_non_zero)
                baseline_char_gaps = baseline_gaps[baseline_gaps > 3]  # Gaps between characters
            
            if len(actual_non_zero) > 1:
                actual_gaps = np.diff(actual_non_zero)
                actual_char_gaps = actual_gaps[actual_gaps > 3]
            
            if len(baseline_char_gaps) > 0 and len(actual_char_gaps) > 0:
                baseline_avg_spacing = np.mean(baseline_char_gaps)
                actual_avg_spacing = np.mean(actual_char_gaps)
                
                if abs(baseline_avg_spacing - actual_avg_spacing) > 2:
                    font_differences.append(f"letter spacing is approximately {int(baseline_avg_spacing)}px, but in actual image it's approximately {int(actual_avg_spacing)}px")
            
            # Combine all font differences into a comprehensive description
            if font_differences:
                # Format each font difference properly - they already have "but in actual image" format
                for font_diff in font_differences:
                    # Font differences are already formatted with "but in actual image it's Xpx"
                    # Just add "In baseline image" prefix if not already there
                    if not font_diff.startswith("In baseline image"):
                        detailed_differences.append(f"In baseline image {font_diff}")
                    else:
                        detailed_differences.append(font_diff)
            else:
                # If no specific font differences detected but it's a text region, provide general description
                detailed_differences.append("The font characteristics (size, weight, style, or spacing) differ between baseline and actual images.")
        
        # Add presence/absence information
        presence_description = ""
        if presence_info == "present_in_actual":
            if w > 200 or h > 100:
                element_type = "element or banner"
            elif w < 100 and h < 50:
                element_type = "text or icon"
            else:
                element_type = "element"
            presence_description = f"This {element_type} is present in the actual image but not present in the baseline image."
        elif presence_info == "present_in_baseline":
            if w > 200 or h > 100:
                element_type = "element or banner"
            elif w < 100 and h < 50:
                element_type = "text or icon"
            else:
                element_type = "element"
            presence_description = f"This {element_type} is present in the baseline image but not present in the actual image."
        
        # Generate descriptive text with detailed measurements
        # Build the final description combining all detailed differences
        
        # Categorize differences by type for better organization
        # Filter to avoid double-counting (e.g., "letter spacing" should be in font_diffs, not spacing_diffs)
        font_diffs = [d for d in detailed_differences if any(keyword in d.lower() for keyword in ["font", "letter spacing"])]
        color_diffs = [d for d in detailed_differences if "color" in d.lower() and "font" not in d.lower()]
        spacing_diffs = [d for d in detailed_differences if ("spacing" in d.lower() or "padding" in d.lower()) and "letter spacing" not in d.lower()]
        size_diffs = [d for d in detailed_differences if "element size" in d.lower()]
        text_diffs = [d for d in detailed_differences if "text is" in d.lower()]
        other_diffs = [d for d in detailed_differences if d not in font_diffs + color_diffs + spacing_diffs + size_diffs + text_diffs]
        
        # Count how many types of differences we have
        diff_types_count = sum([
            len(font_diffs) > 0,
            len(color_diffs) > 0,
            len(spacing_diffs) > 0,
            len(size_diffs) > 0,
            len(text_diffs) > 0
        ])
        
        # Determine the main discrepancy type (priority order)
        # If multiple types, prioritize font over color, or use combined type
        if presence_description:
            if presence_info == "present_in_actual":
                main_type = "Element Presence Difference"
            else:
                main_type = "Element Absence Difference"
        elif diff_types_count > 1:
            # Multiple types of differences - prioritize font if present, otherwise use combined
            if font_diffs and color_diffs:
                main_type = "Font and Color Discrepancy"
            elif font_diffs:
                main_type = "Font Discrepancy"
            elif color_diffs:
                main_type = "Color Discrepancy"
            else:
                main_type = "Multiple Discrepancies"
        elif font_diffs:
            main_type = "Font Discrepancy"
        elif color_diffs:
            main_type = "Color Discrepancy"
        elif spacing_diffs:
            main_type = "Spacing/Padding Discrepancy"
        elif size_diffs:
            main_type = "Size Discrepancy"
        elif text_diffs:
            main_type = "Data/Content Change"
        else:
            main_type = "Visual Difference"
        
        # Build description parts in logical order (clean, without redundant prefixes)
        description_parts = []
        
        # Add presence/absence first if present
        if presence_description:
            description_parts.append(presence_description)
        
        # Add font differences FIRST (before color) so heading matches description
        for diff in font_diffs:
            clean_diff = diff.replace("Font Discrepancy: ", "").replace("Font discrepancy: ", "").replace("Font difference: ", "").replace("Font differences: ", "").strip()
            # Clean up redundant text like "in baseline but" -> ", but"
            clean_diff = clean_diff.replace(" in baseline but", ", but").replace(" in actual", "")
            description_parts.append(clean_diff)
        
        # Add color differences (clean up any prefixes)
        for diff in color_diffs:
            clean_diff = diff.replace("Color Discrepancy: ", "").replace("Color discrepancy: ", "").strip()
            description_parts.append(clean_diff)
        
        # Add size differences
        description_parts.extend(size_diffs)
        
        # Add spacing differences
        description_parts.extend(spacing_diffs)
        
        # Add text content differences
        description_parts.extend(text_diffs)
        
        # Add other differences
        description_parts.extend(other_diffs)
        
        # Combine into final description
        if description_parts:
            full_description = " ".join(description_parts)
            return full_description
        
        # Fallback if no detailed differences detected - analyze what visual differences exist
        if presence_description:
            return presence_description
        
        # If we have no specific differences but there IS a difference, analyze what it could be
        # Always analyze to provide descriptive information
        baseline_gray = cv2.cvtColor(baseline_region_exact, cv2.COLOR_BGR2GRAY) if len(baseline_region_exact.shape) == 3 else baseline_region_exact
        actual_gray = cv2.cvtColor(actual_region_exact, cv2.COLOR_BGR2GRAY) if len(actual_region_exact.shape) == 3 else actual_region_exact
        
        # Calculate difference metrics
        diff = cv2.absdiff(baseline_gray, actual_gray)
        diff_percentage = (np.sum(diff > 20) / diff.size) * 100 if diff.size > 0 else 0
        
        # Calculate structural similarity using edges
        baseline_edges = cv2.Canny(baseline_gray, 50, 150)
        actual_edges = cv2.Canny(actual_gray, 50, 150)
        edge_diff = cv2.absdiff(baseline_edges, actual_edges)
        edge_diff_percentage = (np.sum(edge_diff > 0) / edge_diff.size) * 100 if edge_diff.size > 0 else 0
        
        # Calculate color difference (if color images)
        color_diff = 0
        baseline_color_name = None
        actual_color_name = None
        if len(baseline_region_exact.shape) == 3 and len(actual_region_exact.shape) == 3:
            baseline_mean_color = np.mean(baseline_region_exact, axis=(0, 1)).astype(int)
            actual_mean_color = np.mean(actual_region_exact, axis=(0, 1)).astype(int)
            color_diff = np.linalg.norm(baseline_mean_color - actual_mean_color)
            baseline_color_name = self.get_color_name(baseline_mean_color)
            actual_color_name = self.get_color_name(actual_mean_color)
        
        # Calculate size differences
        baseline_non_zero = np.where(baseline_gray > 10)
        actual_non_zero = np.where(actual_gray > 10)
        
        baseline_area = len(baseline_non_zero[0]) if len(baseline_non_zero[0]) > 0 else 0
        actual_area = len(actual_non_zero[0]) if len(actual_non_zero[0]) > 0 else 0
        area_diff_percentage = abs(baseline_area - actual_area) / baseline_area * 100 if baseline_area > 0 else 0
        
        # Calculate position differences
        baseline_center_x = np.mean(baseline_non_zero[1]) if len(baseline_non_zero[1]) > 0 else w/2
        baseline_center_y = np.mean(baseline_non_zero[0]) if len(baseline_non_zero[0]) > 0 else h/2
        actual_center_x = np.mean(actual_non_zero[1]) if len(actual_non_zero[1]) > 0 else w/2
        actual_center_y = np.mean(actual_non_zero[0]) if len(actual_non_zero[0]) > 0 else h/2
        
        position_diff_x = abs(baseline_center_x - actual_center_x)
        position_diff_y = abs(baseline_center_y - actual_center_y)
        
        # Build descriptive message based on detected differences
        visual_differences = []
        
        # Always include pixel difference if significant
        if diff_percentage > 5:
            visual_differences.append(f"approximately {int(diff_percentage)}% of pixels differ")
        
        # Include structural differences
        if edge_diff_percentage > 10:
            visual_differences.append("structural or shape differences")
        
        # Include color differences
        if color_diff > 15 and baseline_color_name and actual_color_name:
            if baseline_color_name != actual_color_name:
                visual_differences.append(f"color difference (baseline: {baseline_color_name}, actual: {actual_color_name})")
            else:
                visual_differences.append(f"color intensity difference")
        
        # Include size/area differences
        if area_diff_percentage > 10:
            if baseline_area > actual_area:
                visual_differences.append(f"size reduction (approximately {int(area_diff_percentage)}% smaller in actual)")
            else:
                visual_differences.append(f"size increase (approximately {int(area_diff_percentage)}% larger in actual)")
        
        # Include position differences
        if position_diff_x > 3 or position_diff_y > 3:
            if position_diff_x > position_diff_y:
                visual_differences.append(f"horizontal position shift (approximately {int(position_diff_x)}px)")
            else:
                visual_differences.append(f"vertical position shift (approximately {int(position_diff_y)}px)")
        
        # Return descriptive message
        if len(visual_differences) > 0:
            if len(visual_differences) == 1:
                return f"Visual difference detected in this {element_name}: {visual_differences[0]}."
            elif len(visual_differences) == 2:
                return f"Visual difference detected in this {element_name}: {visual_differences[0]} and {visual_differences[1]}."
            else:
                return f"Visual difference detected in this {element_name}: {', '.join(visual_differences[:-1])}, and {visual_differences[-1]}."
        
        # If no specific differences detected but we know there's a difference, provide generic but informative message
        return f"Visual difference detected in this {element_name} (appearance, shape, or content differs between baseline and actual images)."
    
    def draw_differences(self, actual_image, bounding_boxes, difference_mask=None):
        """Draw bounding boxes on the actual image highlighting differences with box numbers - neat and clear."""
        result = actual_image.copy()
        
        # Don't draw overlay mask - just show clean boxes
        # This makes the image much more understandable
        
        # Define distinct, bright colors for better visibility
        colors = [
            (0, 0, 255),      # Red (BGR)
            (0, 255, 0),      # Green
            (255, 0, 0),      # Blue
            (0, 255, 255),    # Yellow
            (255, 0, 255),    # Magenta
            (255, 255, 0),    # Cyan
            (128, 0, 128),    # Purple
            (0, 165, 255),    # Orange
            (255, 128, 0),    # Light Blue
            (0, 255, 128),    # Lime
        ]
        
        # Draw bounding boxes with clear, visible borders
        for idx, (x, y, w, h) in enumerate(bounding_boxes):
            # Use distinct color for each box
            color = colors[idx % len(colors)]
            
            # Draw rectangle with thick, visible border
            # Use consistent thickness for all boxes (3-4px) for neat appearance
            border_thickness = 3
            cv2.rectangle(result, (x, y), (x + w, y + h), color, border_thickness)
            
            # Draw box number label - make it very visible
            box_number = str(idx + 1)
            
            # Calculate text size - make it readable
            font = cv2.FONT_HERSHEY_SIMPLEX
            # Use consistent, readable font size
            font_scale = 0.8
            thickness = 2
            
            # Get text size to position label properly
            (text_width, text_height), baseline = cv2.getTextSize(box_number, font, font_scale, thickness)
            
            # Position label at top-left corner of box
            label_padding = 8
            label_x = x + label_padding
            label_y = y + text_height + label_padding
            
            # Ensure label doesn't go outside image bounds
            if label_x + text_width + label_padding > result.shape[1]:
                label_x = max(0, x + w - text_width - label_padding)
            if label_y - text_height - label_padding < 0:
                label_y = min(result.shape[0] - label_padding, y + h - label_padding)
            
            # Draw filled rectangle background for label - use solid color for better visibility
            bg_color = (0, 0, 0)  # Black background for maximum contrast
            label_bg_padding = 4
            cv2.rectangle(result, 
                         (label_x - label_bg_padding, label_y - text_height - label_bg_padding),
                         (label_x + text_width + label_bg_padding, label_y + baseline + label_bg_padding),
                         bg_color, -1)
            
            # Draw colored border around label matching the box color
            cv2.rectangle(result, 
                         (label_x - label_bg_padding, label_y - text_height - label_bg_padding),
                         (label_x + text_width + label_bg_padding, label_y + baseline + label_bg_padding),
                         color, 2)
            
            # Draw white text on black background for maximum readability
            cv2.putText(result, box_number, (label_x, label_y), 
                       font, font_scale, (255, 255, 255), thickness, cv2.LINE_AA)
        
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
                - box_descriptions: list of descriptive texts for each bounding box
        """
        # Load images
        baseline, actual = self.load_images(baseline_path, actual_path)
        
        # Detect differences
        difference_mask, similarity_score = self.detect_differences(baseline, actual)
        
        # Get bounding boxes
        bounding_boxes = self.get_bounding_boxes(difference_mask)
        
        # Analyze each bounding box and generate descriptions
        box_descriptions = []
        for x, y, w, h in bounding_boxes:
            description = self.analyze_region_difference(baseline, actual, x, y, w, h)
            box_descriptions.append(description)
        
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
            'box_descriptions': box_descriptions,
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
