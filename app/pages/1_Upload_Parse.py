"""Upload & Parse Page - Document ingestion with Landing AI ADE."""

import streamlit as st
from pathlib import Path
import sys
import os
import tempfile
import time

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Upload & Parse | Jaanch Lite", page_icon="📄", layout="wide")

st.markdown("## 📄 Upload & Parse Document")
st.markdown("Upload a legal PDF to parse with Landing AI ADE. Each chunk includes bounding box coordinates for visual grounding.")

# Check API key
if not os.getenv("VISION_AGENT_API_KEY"):
    st.error("⚠️ VISION_AGENT_API_KEY not set. Add it to your .env file.")
    st.stop()

# File uploader
uploaded_file = st.file_uploader(
    "Choose a PDF file",
    type=["pdf"],
    help="Upload a legal document (PDF format)"
)

if uploaded_file:
    st.success(f"📎 Uploaded: {uploaded_file.name} ({uploaded_file.size / 1024:.1f} KB)")

    col1, col2 = st.columns([2, 1])

    with col1:
        # Parse button
        if st.button("🔍 Parse Document", type="primary", use_container_width=True):
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(uploaded_file.getvalue())
                tmp_path = tmp.name

            try:
                with st.spinner("Parsing document with Landing AI ADE..."):
                    # Import parser
                    from src.parsers.ade_parser import parse_document

                    # Progress tracking
                    progress_bar = st.progress(0, text="Initializing parser...")
                    start_time = time.time()

                    progress_bar.progress(10, text="Sending to Landing AI ADE...")

                    # Parse document
                    chunks = parse_document(
                        tmp_path,
                        document_id=uploaded_file.name,
                        matter_id="streamlit_session"
                    )

                    progress_bar.progress(80, text="Processing chunks...")

                    # Store in session state
                    st.session_state.chunks = chunks
                    st.session_state.current_doc = uploaded_file.name
                    st.session_state.documents[uploaded_file.name] = {
                        "chunks": chunks,
                        "parsed_at": time.time(),
                    }

                    # Store PDF bytes for viewer
                    st.session_state.pdf_bytes = uploaded_file.getvalue()

                    progress_bar.progress(100, text="Done!")
                    elapsed = time.time() - start_time

                st.success(f"✅ Parsed {len(chunks)} chunks in {elapsed:.1f}s")

                # Show stats
                col_a, col_b, col_c = st.columns(3)
                col_a.metric("Total Chunks", len(chunks))

                pages = set(c.page for c in chunks)
                col_b.metric("Pages", len(pages))

                with_bbox = sum(1 for c in chunks if c.bbox)
                col_c.metric("With BBox", with_bbox)

            except Exception as e:
                st.error(f"❌ Parsing failed: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

            finally:
                # Cleanup temp file
                Path(tmp_path).unlink(missing_ok=True)

    with col2:
        st.markdown("### ℹ️ About ADE")
        st.markdown("""
        **Landing AI ADE** provides:
        - OCR for scanned PDFs
        - Table extraction
        - Figure detection
        - **Bounding boxes** for each chunk
        """)

# Display parsed chunks
if st.session_state.get("chunks"):
    st.divider()
    st.markdown("### 📋 Parsed Chunks")

    chunks = st.session_state.chunks

    # Filter options
    col1, col2, col3 = st.columns(3)

    with col1:
        pages = sorted(set(c.page for c in chunks))
        selected_page = st.selectbox("Filter by page", ["All"] + pages)

    with col2:
        chunk_types = sorted(set(c.chunk_type.value for c in chunks))
        selected_type = st.selectbox("Filter by type", ["All"] + chunk_types)

    with col3:
        show_bbox = st.checkbox("Show bounding boxes", value=True)

    # Filter chunks
    filtered = chunks
    if selected_page != "All":
        filtered = [c for c in filtered if c.page == selected_page]
    if selected_type != "All":
        filtered = [c for c in filtered if c.chunk_type.value == selected_type]

    st.markdown(f"Showing {len(filtered)} of {len(chunks)} chunks")

    # Display chunks
    for i, chunk in enumerate(filtered[:20]):  # Limit to 20
        with st.expander(f"Chunk {i+1} | Page {chunk.page} | {chunk.chunk_type.value}", expanded=i==0):
            col1, col2 = st.columns([3, 1])

            with col1:
                st.markdown("**Text:**")
                st.text_area(
                    "Content",
                    chunk.text,
                    height=150,
                    key=f"chunk_{i}",
                    label_visibility="collapsed"
                )

            with col2:
                st.markdown("**Metadata:**")
                st.json({
                    "chunk_id": chunk.chunk_id[:20] + "...",
                    "page": chunk.page,
                    "type": chunk.chunk_type.value,
                    "tokens": chunk.token_count,
                })

                if show_bbox and chunk.bbox:
                    st.markdown("**BBox:**")
                    st.json({
                        "x0": f"{chunk.bbox.x0:.3f}",
                        "y0": f"{chunk.bbox.y0:.3f}",
                        "x1": f"{chunk.bbox.x1:.3f}",
                        "y1": f"{chunk.bbox.y1:.3f}",
                    })

    if len(filtered) > 20:
        st.info(f"Showing first 20 of {len(filtered)} chunks. Use filters to narrow down.")

# Sidebar status
with st.sidebar:
    st.markdown("### 📊 Document Status")

    if st.session_state.get("current_doc"):
        st.success(f"📄 {st.session_state.current_doc}")
        st.metric("Chunks", len(st.session_state.chunks))

        if st.button("🗑️ Clear Document"):
            st.session_state.chunks = []
            st.session_state.current_doc = None
            st.session_state.citations = []
            st.rerun()
    else:
        st.info("No document loaded")

    st.divider()
    st.markdown("### 🔗 Next Steps")
    st.markdown("""
    1. Go to **Citations** to extract legal references
    2. Go to **Q&A** to ask questions about the document
    """)
