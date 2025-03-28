from transformers import pipeline
import nltk
from sumy.utils import get_stop_words
from sumy.nlp.stemmers import Stemmer
from sumy.summarizers.luhn import LuhnSummarizer
from sumy.nlp.tokenizers import Tokenizer
from sumy.parsers.plaintext import PlaintextParser
import pytesseract
from PIL import Image
from sumy.summarizers.lsa import LsaSummarizer

# nltk.download("punkt")


def ExtractText(path):
    img = Image.open(path)
    text = pytesseract.image_to_string(img, lang="eng")
    return text


HAS_SHITTONE_OF_RAM = False
summarizer = None


def summarize_paragraph(paragraph: str, sentences_count=5) -> str:
    if len(paragraph) < 10:
        return paragraph  # If the paragraph is too short, don't summarize it
    if HAS_SHITTONE_OF_RAM:
        global summarizer
        if summarizer is None:
            summarizer = pipeline("summarization", model="facebook/bart-large-cnn")
        return summarizer(
            paragraph,
            max_length=len(paragraph) - 1,
            min_length=min(len(paragraph) - 1, 10),
        )[0]["summary_text"]

    parser = PlaintextParser.from_string(paragraph, Tokenizer("english"))

    summarizer = LsaSummarizer(Stemmer("english"))
    summarizer.stop_words = get_stop_words("english")

    summary = summarizer(parser.document, sentences_count)
    s = ""
    for i in summary:
        s += str(i) + " "
    return s
