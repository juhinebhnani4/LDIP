"""Jaanch Lite - Streamlit UI

A simplified legal document intelligence interface.
"""

import streamlit as st
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Page configuration
st.set_page_config(
    page_title="Jaanch Lite",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a2744;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #666;
        margin-bottom: 2rem;
    }
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 10px;
        color: white;
        margin-bottom: 1rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">⚖️ Jaanch Lite</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Simplified Legal Document Intelligence</p>', unsafe_allow_html=True)

# Introduction
st.markdown("""
**Jaanch Lite** is a proof-of-concept for analyzing Indian legal documents using modern AI tools:

- **Landing AI ADE** - Document parsing with visual grounding
- **Voyage AI** - Legal-specific embeddings & reranking
- **Gemini 2.5 Flash** - Structured citation extraction
""")

st.divider()

# Features
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### 📄 Document Parsing")
    st.markdown("""
    Upload PDFs and get:
    - Automatic text extraction
    - Table & figure detection
    - **Bounding box grounding**
    """)

with col2:
    st.markdown("### 📜 Citation Extraction")
    st.markdown("""
    Find legal citations:
    - Section references (S. 138 NI Act)
    - Article references (Art. 21)
    - Bharatiya codes (BNS, BNSS)
    """)

with col3:
    st.markdown("### 💬 Q&A Search")
    st.markdown("""
    Ask questions:
    - Semantic search
    - Legal reranking
    - Source citations
    """)

st.divider()

# Quick start
st.markdown("### 🚀 Quick Start")

st.markdown("""
1. **Upload** - Go to the **Upload & Parse** page and upload a legal PDF
2. **Extract** - View extracted citations on the **Citations** page
3. **Search** - Ask questions on the **Q&A** page
""")

# Session state initialization
if "documents" not in st.session_state:
    st.session_state.documents = {}

if "current_doc" not in st.session_state:
    st.session_state.current_doc = None

if "chunks" not in st.session_state:
    st.session_state.chunks = []

if "citations" not in st.session_state:
    st.session_state.citations = []

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Sidebar - Status
with st.sidebar:
    st.markdown("### 📊 Session Status")

    docs_count = len(st.session_state.documents)
    chunks_count = len(st.session_state.chunks)
    citations_count = len(st.session_state.citations)

    col1, col2 = st.columns(2)
    col1.metric("Documents", docs_count)
    col2.metric("Chunks", chunks_count)

    col1, col2 = st.columns(2)
    col1.metric("Citations", citations_count)
    col2.metric("Messages", len(st.session_state.chat_history))

    if st.session_state.current_doc:
        st.success(f"Active: {st.session_state.current_doc}")

    st.divider()

    # API Status
    st.markdown("### 🔑 API Status")

    import os
    from dotenv import load_dotenv
    load_dotenv()

    apis = {
        "Landing AI": bool(os.getenv("VISION_AGENT_API_KEY")),
        "Voyage AI": bool(os.getenv("VOYAGE_API_KEY")),
        "Gemini": bool(os.getenv("GOOGLE_API_KEY")),
    }

    for name, status in apis.items():
        if status:
            st.markdown(f"✅ {name}")
        else:
            st.markdown(f"❌ {name}")

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9rem;">
    Jaanch Lite POC | Built with Streamlit, Landing AI, Voyage AI, Gemini
</div>
""", unsafe_allow_html=True)
