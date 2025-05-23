import io
import os
import random
import sys
import tempfile
import time
from unittest.mock import patch

import numpy as np
import pytesseract  # Make sure Tesseract is installed and in PATH
import pytest
from PIL import Image, ImageDraw, ImageFont
from sumy.nlp.stemmers import Stemmer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
# Use a simpler summarizer like Luhn for faster testing if LSA or Transformers are too slow/heavy
# from sumy.summarizers.luhn import LuhnSummarizer
from sumy.summarizers.lsa import LsaSummarizer  # Keeping LSA as in original
from sumy.utils import get_stop_words
from termcolor import colored

# --- Configuration ---
SAMPLE_TEXT = """This benchmark evaluates AI models on accuracy, speed, and efficiency across various tasks such as image recognition, natural language understanding, and reasoning.
It includes standardized datasets and scoring metrics to ensure fair comparisons between models.
The goal is to identify strengths, weaknesses, and suitability of models for real-world applications."""

# Simulate having multiple test images with varying simple text
NUM_SIMULATED_IMAGES = 5  # Reduced from 10 for faster testing
SIMULATED_BENCHMARK_TEXTS = [
    f"Benchmark image. Contains standard test patterns.",
    f"Simple text for OCR testing, case.",
    f"Image recognition task input.",
]

# --- Core Functions (Unchanged) ---
HAS_SHITTONE_OF_RAM = (
    False  # Keep this flag, though the test skips the transformer part
)
summarizer_transformers = None


def summarize_paragraph(
    paragraph: str, sentences_count=2
) -> str:  # Default to fewer sentences for summarization tests
    """Summarizes a paragraph using Sumy LSA or Transformers."""
    if len(paragraph.split()) < 10:  # Check word count instead of char count
        return paragraph  # Too short to summarize meaningfully

    if HAS_SHITTONE_OF_RAM:
        # Placeholder for potential future use, skipped in current tests
        global summarizer_transformers
        if summarizer_transformers is None:
            from transformers import pipeline

            summarizer_transformers = pipeline(
                "summarization", model="facebook/bart-large-cnn"
            )
        # Simplified length constraints for testing
        max_len = max(30, len(paragraph.split()) // 2)
        min_len = min(10, max_len // 2)
        try:
            summary_result = summarizer_transformers(
                paragraph, max_length=max_len, min_length=min_len, truncation=True
            )
            return summary_result[0]["summary_text"]
        except Exception as e:
            print(f"Transformer summarization failed: {e}")
            # Fallback to Sumy if transformer fails
            pass

    # Sumy LSA Summarizer (Default/Fallback)
    try:
        parser = PlaintextParser.from_string(paragraph, Tokenizer("english"))
        stemmer = Stemmer("english")
        summarizer_lsa = LsaSummarizer(stemmer)
        summarizer_lsa.stop_words = get_stop_words("english")
        summary = summarizer_lsa(parser.document, sentences_count)
        return " ".join([str(sentence) for sentence in summary])
    except Exception as e:
        print(f"Sumy summarization failed: {e}")
        return f"Error during summarization. Original length: {len(paragraph)}"


def ExtractText(image_path: str) -> str:
    """Extracts text from an image using Tesseract OCR."""
    try:
        img = Image.open(image_path)
        text = pytesseract.image_to_string(
            img, lang="eng", config="--psm 6"
        )  # PSM 6 assumes a single uniform block of text
        return text.strip()
    except pytesseract.TesseractNotFoundError:
        pytest.skip("Tesseract is not installed or not found in PATH.")
    except FileNotFoundError:
        print(f"Error: Image file not found at {image_path}")
        return ""
    except Exception as e:
        print(f"Error during OCR: {e}")
        return ""


# --- Test Utilities ---
def create_test_image(text, file_prefix="test_img_", width=600, height=100):
    """Creates a simple PNG image with the given text."""
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    try:
        # Try a common font, fallback to default
        font = ImageFont.truetype("arial.ttf", 15)
    except IOError:
        font = ImageFont.load_default()
    draw.text((10, 10), text, fill="black", font=font)

    # Use NamedTemporaryFile to manage cleanup
    temp_file = tempfile.NamedTemporaryFile(
        prefix=file_prefix, suffix=".png", delete=False
    )
    image.save(temp_file.name)
    temp_file.close()  # Close the file handle but keep the file
    return temp_file.name


@pytest.fixture(scope="module")
def simulated_image_paths():
    """Fixture to create multiple simulated benchmark images for testing."""
    paths = []
    print(f"\nCreating {NUM_SIMULATED_IMAGES} simulated test images...")
    for i in range(NUM_SIMULATED_IMAGES):
        text = random.choice(SIMULATED_BENCHMARK_TEXTS).format(i=i)
        path = create_test_image(text, file_prefix=f"sim_bench_{i}_")
        paths.append(path)
        print(f"  Created: {os.path.basename(path)} with text: '{text[:30]}...'")

    yield paths  # Provide the list of paths to the tests

    # Cleanup: Remove the created image files after tests run
    print("\nCleaning up simulated test images...")
    for path in paths:
        try:
            os.remove(path)
            print(f"  Removed: {os.path.basename(path)}")
        except OSError as e:
            print(f"  Error removing {os.path.basename(path)}: {e}")


# Store statistics globally for simplicity in this script
test_stats = {
    "ocr_times": [],
    "ocr_char_counts": [],
    "ocr_accuracy_simulated": [],
    "sum_times": [],
    "sum_compression_ratios": [],
    "sum_consistency": [],
}

# --- Pytest Tests ---


# 1. OCR Tests (ExtractText)
class TestOCRExtraction:

    def test_ocr_basic_extraction(self, simulated_image_paths):
        """Tests if OCR extracts *some* text from the first simulated image."""
        if not simulated_image_paths:
            pytest.skip("No simulated images were created.")

        image_path = simulated_image_paths[0]
        start_time = time.time()
        extracted_text = ExtractText(image_path)
        duration = time.time() - start_time
        test_stats["ocr_times"].append(duration)

        print(f"\n  OCR Basic Test on {os.path.basename(image_path)}:")
        print(f"    Extracted Text: '{extracted_text[:50]}...'")
        print(f"    Execution Time: {duration:.4f}s")

        assert (
            extracted_text is not None
        ), "OCR function should return a string, even if empty."
        assert (
            len(extracted_text) > 5
        ), "Expected some text to be extracted from the image."
        test_stats["ocr_char_counts"].append(len(extracted_text))
        # Simple simulated accuracy: check if common words are present
        expected_words = ["benchmark", "test", "image", "ocr", "case", "input", "text"]
        found_words = [
            word for word in expected_words if word in extracted_text.lower()
        ]
        sim_acc = len(found_words) > 0
        test_stats["ocr_accuracy_simulated"].append(sim_acc)
        assert sim_acc, f"Expected extracted text to contain some relevant keywords."

    def test_ocr_statistical_performance(self, simulated_image_paths):
        """Runs OCR on all simulated images and calculates average time and basic metrics."""
        if len(simulated_image_paths) < 2:
            pytest.skip("Need at least 2 simulated images for statistical test.")

        print(f"\n  OCR Statistical Test on {len(simulated_image_paths)} images:")
        times = []
        char_counts = []
        accuracies = []

        for image_path in simulated_image_paths:
            start_time = time.time()
            text = ExtractText(image_path)
            duration = time.time() - start_time
            times.append(duration)
            char_counts.append(len(text))
            # Simulate accuracy check (e.g., non-empty and contains expected word)
            expected_words = [
                "benchmark",
                "test",
                "image",
                "ocr",
                "case",
                "input",
                "text",
            ]
            found_words = [word for word in expected_words if word in text.lower()]
            accuracies.append(len(text) > 0 and len(found_words) > 0)
            print(
                f"    Processed {os.path.basename(image_path)} ({len(text)} chars) in {duration:.4f}s - AccOK: {accuracies[-1]}"
            )

        avg_time = np.mean(times) if times else 0
        avg_chars = np.mean(char_counts) if char_counts else 0
        avg_accuracy = np.mean(accuracies) * 100 if accuracies else 0

        test_stats["ocr_times"].extend(times)  # Add all times
        test_stats["ocr_char_counts"].extend(char_counts)
        test_stats["ocr_accuracy_simulated"].extend(accuracies)

        print(f"    Average OCR Time: {avg_time:.4f}s")
        print(f"    Average Character Count: {avg_chars:.2f}")
        print(f"    Simulated Accuracy Rate: {avg_accuracy:.2f}%")

        assert (
            avg_time < 10
        ), "Average OCR time should be reasonable (<10s)."  # Generous limit
        assert avg_chars > 5, "Average extracted text length should be > 5."
        assert (
            avg_accuracy > 50
        ), "Simulated accuracy should be over 50%."  # Expect most simple images to work


# 2. Summarization Tests (summarize_paragraph)
class TestSummarization:

    def test_summarize_short_text(self):
        """Tests that very short text is returned as is."""
        short_text = "Too short to summarize."
        summary = summarize_paragraph(short_text)
        print(f"\n  Summarize Short Text Test:")
        print(f"    Input: '{short_text}'")
        print(f"    Output: '{summary}'")
        assert summary == short_text, "Short text should not be summarized."

    def test_summarize_empty_text(self):
        """Tests handling of empty string input."""
        empty_text = ""
        summary = summarize_paragraph(empty_text)
        print(f"\n  Summarize Empty Text Test:")
        print(f"    Input: ''")
        print(f"    Output: '{summary}'")
        assert summary == empty_text, "Empty text should return empty."

    def test_summarization_statistical_performance(self):
        """Runs summarization multiple times on SAMPLE_TEXT for stats."""
        num_trials = 3  # Fewer trials for faster testing
        times = []
        ratios = []
        summaries = []

        print(
            f"\n  Summarization Statistical Test ({num_trials} trials on SAMPLE_TEXT):"
        )
        original_length = len(SAMPLE_TEXT)

        for i in range(num_trials):
            start_time = time.time()
            summary = summarize_paragraph(SAMPLE_TEXT)
            duration = time.time() - start_time

            times.append(duration)
            summary_length = len(summary)
            ratio = summary_length / original_length if original_length > 0 else 0
            ratios.append(ratio)
            summaries.append(summary)
            print(
                f"    Trial {i+1}: Time={duration:.4f}s, Len={summary_length}, Ratio={ratio:.2f}"
            )
            print(f"      Summary: '{summary[:60]}...'")

        avg_time = np.mean(times) if times else 0
        avg_ratio = np.mean(ratios) if ratios else 0

        # Basic consistency check: Compare summaries (LSA should be fairly deterministic)
        consistency_scores = []
        if len(summaries) > 1:
            base_summary_words = set(summaries[0].lower().split())
            for i in range(1, len(summaries)):
                current_summary_words = set(summaries[i].lower().split())
                common = len(base_summary_words.intersection(current_summary_words))
                total = len(base_summary_words.union(current_summary_words))
                score = (
                    common / total if total > 0 else 1.0
                )  # Consider identical as 100%
                consistency_scores.append(score)

        avg_consistency = (
            np.mean(consistency_scores) * 100 if consistency_scores else 100.0
        )

        test_stats["sum_times"].extend(times)
        test_stats["sum_compression_ratios"].extend(
            [1 - r for r in ratios]
        )  # Store as reduction ratio
        test_stats["sum_consistency"].append(avg_consistency)

        print(f"    Average Summarization Time: {avg_time:.4f}s")
        print(
            f"    Average Compression Ratio: {(1 - avg_ratio)*100:.2f}%"
        )  # Output reduction %
        print(f"    Average Consistency (vs first run): {avg_consistency:.2f}%")

        assert avg_time < 5, "Average summarization time should be reasonable (<5s)."
        assert (
            0 < avg_ratio < 1
        ), "Summarization ratio should be between 0 and 1 (exclusive)."
        assert avg_consistency > 70, "Summaries should be reasonably consistent (>70%)."


# 3. Integration Test
def test_full_pipeline_integration(simulated_image_paths):
    """Tests the full flow: Image -> OCR -> Summarization."""
    if not simulated_image_paths:
        pytest.skip("No simulated images were created.")

    image_path = simulated_image_paths[-1]  # Use the last image
    print(f"\n  Full Pipeline Integration Test on {os.path.basename(image_path)}:")
    pipeline_start_time = time.time()

    # 1. OCR
    ocr_start_time = time.time()
    extracted_text = ExtractText(image_path)
    ocr_duration = time.time() - ocr_start_time
    print(f"    1. OCR Result ({ocr_duration:.4f}s): '{extracted_text[:50]}...'")
    assert len(extracted_text) > 5, "OCR step failed to extract sufficient text."

    # 2. Summarization
    sum_start_time = time.time()
    summary = summarize_paragraph(extracted_text)
    sum_duration = time.time() - sum_start_time
    print(f"    2. Summarization Result ({sum_duration:.4f}s): '{summary[:60]}...'")
    assert len(summary) > 0, "Summarization step failed to produce output."
    # Summary should be shorter than extracted text if text was long enough
    if len(extracted_text.split()) >= 10:
        assert len(summary) < len(
            extracted_text
        ), "Summary should be shorter than extracted text."

    pipeline_duration = time.time() - pipeline_start_time
    print(f"    End-to-End Pipeline Time: {pipeline_duration:.4f}s")
    assert (
        pipeline_duration < 15
    ), "Full pipeline should complete reasonably fast (<15s)."


# --- Statistics Reporting ---
# Use pytest's built-in reporting capabilities and add a final summary.
# We can use a session-scoped fixture or pytest_sessionfinish hook for final stats print.


def pytest_sessionfinish(session):
    """Hook to print summary statistics after all tests are run."""
    print("\n" + "=" * 70)
    print(colored("STATISTICAL METRICS SUMMARY", "cyan", attrs=["bold"]))
    print("=" * 70)

    if test_stats["ocr_times"]:
        print(colored("\nOCR Statistics:", "white", attrs=["bold"]))
        print(f"  Average Time:       {np.mean(test_stats['ocr_times']):.4f}s")
        print(f"  Std Dev Time:       {np.std(test_stats['ocr_times']):.4f}s")
        print(f"  Average Char Count: {np.mean(test_stats['ocr_char_counts']):.2f}")
        # Ensure simulated accuracy list contains booleans or 0/1
        sim_acc_numeric = [
            1 if acc else 0 for acc in test_stats["ocr_accuracy_simulated"]
        ]
        print(f"  Simulated Accuracy: {np.mean(sim_acc_numeric)*100:.2f}%")
    else:
        print(colored("\nOCR Statistics: No data collected.", "yellow"))

    if test_stats["sum_times"]:
        print(colored("\nSummarization Statistics:", "white", attrs=["bold"]))
        print(f"  Average Time:           {np.mean(test_stats['sum_times']):.4f}s")
        print(f"  Std Dev Time:           {np.std(test_stats['sum_times']):.4f}s")
        print(
            f"  Average Compression:    {np.mean(test_stats['sum_compression_ratios'])*100:.2f}%"
        )
        # Assuming sum_consistency stores the avg consistency from the stat test
        print(
            f"  Average Consistency:    {np.mean(test_stats['sum_consistency']):.2f}%"
        )
    else:
        print(colored("\nSummarization Statistics: No data collected.", "yellow"))

    print("\n" + "=" * 70)
