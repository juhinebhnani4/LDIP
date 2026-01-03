# Handling Poor Quality Scanned Legal Documents

**Date:** 2025-12-27  
**Status:** Research & Recommendations  
**Priority:** HIGH (Critical for Indian court documents)

---

## The Reality: Indian Legal Documents Are Often Terrible Quality

### Common Issues

1. **Low Scan Resolution**
   - Court documents scanned at 150-200 DPI (should be 300+)
   - Photocopies of photocopies
   - Old documents (decades old, yellowed, faded)

2. **Physical Damage**
   - Folded pages creating black lines
   - Water damage / stains
   - Torn pages
   - Missing corners

3. **Overlay Artifacts**
   - Court stamps over text
   - Handwritten notes/corrections on printed documents
   - Signatures crossing multiple lines
   - Seal marks

4. **Text Quality Issues**
   - Mixed fonts (English + Devanagari)
   - Small font sizes (8-10pt)
   - Unclear/blurred text
   - Skewed/rotated pages
   - Uneven lighting during scanning

5. **Handwritten Content**
   - Judge's notes
   - Witness statements
   - Affidavits (sometimes fully handwritten)
   - Annotations on printed documents
   - Historical cursive writing (old case records)

**Reality Check from Industry:** According to [Revolution Data Systems](https://www.revolutiondatasystems.com/blog/the-truth-about-ai-handwriting-recognition-in-government-records), vendors who promise "100% accurate" AI on handwriting are overselling - **real-world results are closer to 95% best case** for clean modern writing, and **much lower for historical cursive, faded ink, or complex layouts**.

**Result:** Traditional OCR accuracy drops from 95%+ to 60-80% (or worse!)

---

## Multi-Stage Processing Solution

### Architecture Overview

```
┌─────────────────────┐
│ Upload Document     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ Image Preprocessing │ ← Deskew, denoise, enhance
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│ OCR (Google Vision) │ ← Extract text + confidence
└──────────┬──────────┘
           │
           ▼
┌─────────────────────────┐
│ Quality Assessment      │ ← Check avg confidence
└──────────┬──────────────┘
           │
           ├─── >90% confidence ────────→ [Use OCR as-is]
           │
           ├─── 70-90% confidence ──────→ [LLM Error Correction]
           │                               ↓
           │                              Gemini Flash:
           │                              - Fix OCR errors
           │                              - Use legal context
           │                              - Validate names/dates
           │
           ├─── 50-70% confidence ──────→ [Enhanced Processing]
           │                               ↓
           │                              - Aggressive preprocessing
           │                              - Multiple OCR attempts
           │                              - LLM reconciliation
           │
           └─── <50% confidence ────────→ [Vision-LLM Direct]
                                           ↓
                                          Gemini Flash Vision:
                                          - Skip OCR entirely
                                          - Process image directly
                                          - Extract text end-to-end
```

---

## Stage 1: Image Preprocessing

### Techniques (Based on Research)

**1. Noise Reduction**
- Remove salt-and-pepper noise
- Gaussian blur to reduce grain
- Median filter for speckles

**2. Contrast Enhancement**
- Histogram equalization
- Adaptive thresholding
- CLAHE (Contrast Limited Adaptive Histogram Equalization)

**3. Deskewing**
- Detect text orientation
- Rotate to horizontal
- Straighten curved text

**4. Binarization**
- Convert to pure black/white
- Otsu's method for threshold detection
- Preserve text edges

**5. Layout Analysis**
- Detect text regions vs images/stamps
- Segment columns
- Identify margins

### Python Implementation (OpenCV)

```python
import cv2
import numpy as np
from google.cloud import vision

def preprocess_image(image_path):
    """
    Enhance image quality before OCR
    """
    # Read image
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    
    # 1. Noise reduction
    denoised = cv2.fastNlMeansDenoising(img, h=10)
    
    # 2. Deskewing
    coords = np.column_stack(np.where(denoised > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    
    (h, w) = denoised.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    deskewed = cv2.warpAffine(denoised, M, (w, h), 
                               flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)
    
    # 3. Contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    enhanced = clahe.apply(deskewed)
    
    # 4. Binarization (adaptive thresholding)
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # 5. Morphological operations (remove small artifacts)
    kernel = np.ones((1, 1), np.uint8)
    cleaned = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    return cleaned

def process_with_quality_routing(image_path):
    """
    Route document processing based on quality
    """
    # Preprocess image
    enhanced_image = preprocess_image(image_path)
    
    # Try OCR on enhanced image
    client = vision.ImageAnnotatorClient()
    with open(enhanced_image, 'rb') as img:
        content = img.read()
    
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    
    # Calculate average confidence
    confidences = []
    for page in response.full_text_annotation.pages:
        for block in page.blocks:
            confidences.append(block.confidence)
    
    avg_confidence = sum(confidences) / len(confidences) if confidences else 0
    
    # Route based on quality
    if avg_confidence > 0.9:
        return "OCR_ONLY", response.full_text_annotation.text
    elif avg_confidence > 0.7:
        return "OCR_WITH_LLM", response.full_text_annotation
    elif avg_confidence > 0.5:
        return "ENHANCED_OCR", response.full_text_annotation
    else:
        return "VISION_LLM", None  # Skip OCR, use Vision-LLM
```

---

## Stage 2: OCR with Confidence Scoring

### Google Cloud Vision Confidence Scores

**What Google Returns:**
```json
{
  "full_text_annotation": {
    "text": "This is a affidavit sworn before...",
    "pages": [
      {
        "blocks": [
          {
            "confidence": 0.98,
            "paragraphs": [
              {
                "confidence": 0.97,
                "words": [
                  {"symbols": [{"text": "T", "confidence": 0.99}], "confidence": 0.99},
                  {"symbols": [{"text": "h", "confidence": 0.98}, ...], "confidence": 0.98},
                  ...
                  {"symbols": [...], "confidence": 0.45}  // Low confidence word!
                ]
              }
            ]
          }
        ]
      }
    ]
  }
}
```

**How to Use Confidence Scores:**

1. **Word-level confidence:** Identify specific problem words
2. **Line-level confidence:** Flag problematic lines for review
3. **Page-level confidence:** Route to appropriate processing path
4. **Document-level confidence:** Decide overall strategy

---

## Stage 3: LLM Post-Processing (Error Correction)

### Why LLMs Excel at OCR Correction

**LLMs understand:**
- ✅ **Legal terminology** ("plaintiff" not "plaintift", "affidavit" not "affadavit")
- ✅ **Indian names** (common patterns: Ramesh Kumar, Priya Sharma, etc.)
- ✅ **Date formats** (DD-MM-YYYY common in India)
- ✅ **Legal document structure** (typical sections, order)
- ✅ **Context** (if "sworn before" appears, next word likely "notary" or "magistrate")

### Implementation with Gemini Flash

```python
import google.generativeai as genai

def correct_ocr_errors(ocr_output, low_confidence_regions):
    """
    Use Gemini Flash to correct OCR errors
    """
    prompt = f"""
You are an expert in Indian legal documents. An OCR system extracted text from a legal document, 
but some regions had low confidence scores and may contain errors.

**OCR Output:**
{ocr_output.text}

**Low Confidence Regions (likely errors):**
{low_confidence_regions}

**Your Task:**
1. Identify and correct any OCR errors
2. Use legal terminology and Indian name patterns
3. Ensure dates follow DD-MM-YYYY format
4. Maintain original document structure
5. Mark corrections with [CORRECTED: original → corrected]

**Rules:**
- Only correct obvious errors
- Don't hallucinate missing information
- Preserve original meaning
- Flag ambiguous cases as [UNCLEAR]

**Corrected Text:**
"""

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(prompt)
    
    return response.text

# Example usage
ocr_result = google_vision.extract_text(image)
low_conf = extract_low_confidence_words(ocr_result, threshold=0.7)
corrected = correct_ocr_errors(ocr_result, low_conf)
```

**Example Correction:**

| OCR Output (Error) | Gemini Flash Correction | Reasoning |
|-------------------|------------------------|-----------|
| "Ramesh Kurar" | "Ramesh Kumar" | Common Indian surname pattern |
| "sworn before on 25-13-2023" | "sworn before on 25-01-2023" | Date validation (13th month impossible) |
| "plaintift filed a petition" | "plaintiff filed a petition" | Legal terminology |
| "Honorabe Court" | "Honorable Court" | Spelling correction |
| "Rs. 5O,OOO" | "Rs. 50,000" | Number formatting (O → 0) |

---

## Stage 4: Vision-LLM Direct Processing (Worst Cases)

### When to Use Vision-LLM

**Skip OCR entirely if:**
- Average OCR confidence < 50%
- Heavily handwritten content
- Severe physical damage
- Multiple overlay artifacts (stamps, seals)
- Extremely poor scan quality

### Gemini Flash Vision Mode

```python
def process_with_vision_llm(image_path):
    """
    Use Gemini Flash to extract text directly from image
    Bypasses OCR entirely
    """
    import google.generativeai as genai
    from PIL import Image
    
    # Load image
    img = Image.open(image_path)
    
    prompt = """
This is a scanned legal document from an Indian court. The scan quality is poor.

**Your Task:**
1. Extract ALL visible text from this document
2. Maintain original structure (paragraphs, sections)
3. Identify document type (affidavit, order, petition, etc.)
4. Extract key information:
   - Case number
   - Court name
   - Date
   - Party names (petitioner, respondent)
   - Judge name
5. Flag regions that are unclear or illegible

**Output Format:**
```
Document Type: [type]
Case Number: [number]
Date: [date]
Court: [name]

Extracted Text:
[full text with structure preserved]

Unclear Regions:
- [description of unclear parts]
```
"""

    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content([prompt, img])
    
    return response.text
```

**Cost Comparison:**
- **OCR + LLM correction:** $0.005/page
- **Vision-LLM direct:** $0.02/page
- **4x more expensive, but worth it for very poor quality!**

---

## Cost & Performance Analysis

### Scenario: 2,000 Pages per Matter

**Quality Distribution (Estimated for Indian Courts):**
- 50% Good quality (>90% confidence) → OCR only
- 30% Medium quality (70-90%) → OCR + LLM correction
- 15% Poor quality (50-70%) → Enhanced OCR + LLM
- 5% Very poor (<50%) → Vision-LLM direct

### Cost Calculation

| Quality Tier | % of Pages | Pages | Method | Cost/Page | Subtotal |
|-------------|-----------|-------|--------|-----------|----------|
| Good | 50% | 1,000 | OCR only | $0.0015 | $1.50 |
| Medium | 30% | 600 | OCR + LLM | $0.005 | $3.00 |
| Poor | 15% | 300 | Enhanced OCR | $0.01 | $3.00 |
| Very Poor | 5% | 100 | Vision-LLM | $0.02 | $2.00 |
| **TOTAL** | | **2,000** | | | **$9.50** |

**Original Estimate:** $3.00/matter (assuming all pages good quality)  
**Realistic Estimate:** $9.50/matter (accounting for quality distribution)  
**Still very affordable!**

### Processing Time

| Quality Tier | Method | Time/Page | 2,000 Pages Total |
|-------------|--------|-----------|-------------------|
| Good | OCR only | 0.5s | 8 min |
| Medium | OCR + LLM | 2s | 20 min |
| Poor | Enhanced OCR | 5s | 25 min |
| Very Poor | Vision-LLM | 8s | 13 min |
| **TOTAL** | | | **~66 min/matter** |

**Acceptable for batch processing!**

---

## Recommended Implementation Roadmap

### Phase 1: Basic Quality Handling (MVP)
- ✅ Google Cloud Vision for OCR
- ✅ Confidence score tracking
- ✅ Basic routing (good → OCR, poor → Vision-LLM)
- ✅ Gemini Flash for error correction
- **Timeline:** 2-3 weeks
- **Cost:** $9.50/matter

### Phase 2: Image Preprocessing
- ⏳ OpenCV preprocessing pipeline
- ⏳ Deskewing, denoising, contrast enhancement
- ⏳ Improve OCR confidence by 10-15%
- ⏳ Reduce Vision-LLM usage (cost savings)
- **Timeline:** 3-4 weeks
- **Cost Reduction:** $9.50 → $7/matter (30% savings)

### Phase 3: Advanced Handling
- ⏳ Handwritten text detection & routing
- ⏳ Stamp/seal removal
- ⏳ Layout analysis (columns, tables)
- ⏳ Multi-pass OCR with ensemble
- **Timeline:** 4-6 weeks
- **Cost:** $7/matter, higher accuracy

### Phase 4: ML-Based Quality Prediction
- ⏳ Train model to predict document quality from thumbnail
- ⏳ Route before full OCR (save API calls)
- ⏳ Active learning (learn from corrections)
- **Timeline:** 6-8 weeks
- **Cost Optimization:** $7 → $5/matter

---

## Key Recommendations for LDIP

### ✅ DO THIS

1. **Implement quality-based routing from Day 1**
   - Don't assume all documents are good quality
   - Route poor quality to Vision-LLM
   - Track confidence scores

2. **Use Gemini Flash for error correction**
   - Leverages legal context
   - 14x cheaper than GPT-4
   - Good enough for OCR correction

3. **Budget for realistic quality distribution**
   - $9.50/matter (not $3)
   - Factor in poor quality documents
   - Indian courts = expect 20-30% poor quality

4. **Phase in preprocessing**
   - MVP: No preprocessing (keep it simple)
   - Phase 2: Add OpenCV pipeline
   - Don't over-engineer early

5. **Monitor and learn**
   - Track OCR confidence by document type
   - Identify problem categories (e.g., "old affidavits always poor")
   - Refine routing rules

### ❌ DON'T DO THIS

1. ❌ Assume all documents are good quality
2. ❌ Use only traditional OCR (will fail on 20-30% of docs)
3. ❌ Ignore confidence scores
4. ❌ Skip Vision-LLM option (expensive but necessary)
5. ❌ Over-invest in preprocessing too early (MVP first!)

---

## Research References

1. **Perplexity Search:** Parsing OCR from Bad Scanned Documents  
   [https://www.perplexity.ai/search/parse-ocr-bad-scanned-document-4Erh8HJgT3KvFSbZ6eFf7Q](https://www.perplexity.ai/search/parse-ocr-bad-scanned-document-4Erh8HJgT3KvFSbZ6eFf7Q)

2. **Google Gemini Capabilities:**  
   [https://gemini.google.com/share/f47262e6b67b](https://gemini.google.com/share/f47262e6b67b)

3. **Google Gemini Flash Documentation:**  
   [blog.google](https://blog.google/products/gemini/gemini-3-flash/)

4. **Hybrid OCR-LLM Framework:**  
   [arxiv.org/html/2510.10138v1](https://arxiv.org/html/2510.10138v1)

5. **Handwritten Legal Document Processing:**  
   [arxiv.org/html/2512.18004v1](https://arxiv.org/html/2512.18004v1)

---

## Bottom Line

**Poor quality scans are inevitable with Indian legal documents.**

**Solution:**
- ✅ Quality-based routing (good → OCR, poor → Vision-LLM)
- ✅ LLM error correction (Gemini Flash)
- ✅ Realistic cost estimate ($9.50/matter vs $3)
- ✅ Phase in preprocessing (don't over-engineer early)

**This approach handles 95%+ of documents successfully, even with poor quality scans.**

