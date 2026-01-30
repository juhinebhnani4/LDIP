"""Visual Grounding Page - Display PDF with bounding box overlays."""

import streamlit as st
from pathlib import Path
import sys
import os
import base64

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Visual Grounding | Jaanch Lite", page_icon="🎯", layout="wide")

st.markdown("## 🎯 Visual Grounding")
st.markdown("View document chunks and citations with their exact locations on the page.")

# Check if document is loaded
if not st.session_state.get("chunks"):
    st.warning("⚠️ No document loaded. Please upload a document first.")
    st.page_link("pages/1_Upload_Parse.py", label="Go to Upload & Parse", icon="📄")
    st.stop()

# Check if PDF bytes are available
if not st.session_state.get("pdf_bytes"):
    st.warning("⚠️ PDF data not available. Please re-upload the document.")
    st.page_link("pages/1_Upload_Parse.py", label="Go to Upload & Parse", icon="📄")
    st.stop()

# Display current document
st.info(f"📄 Current document: **{st.session_state.get('current_doc', 'Unknown')}** ({len(st.session_state.chunks)} chunks)")

st.divider()

# Layout
col_pdf, col_info = st.columns([2, 1])

with col_info:
    st.markdown("### 📍 Select Content")

    # Choose what to view
    view_type = st.radio(
        "View",
        ["Chunks", "Citations"],
        horizontal=True
    )

    if view_type == "Chunks":
        chunks = st.session_state.chunks

        # Filter by page
        pages = sorted(set(c.page for c in chunks))
        selected_page = st.selectbox("Page", pages, key="chunk_page")

        # Filter chunks for selected page
        page_chunks = [c for c in chunks if c.page == selected_page]

        st.markdown(f"**{len(page_chunks)} chunks on page {selected_page}**")

        # List chunks
        selected_chunk_idx = st.selectbox(
            "Select chunk",
            range(len(page_chunks)),
            format_func=lambda i: f"Chunk {i+1}: {page_chunks[i].text[:50]}..."
        )

        if page_chunks:
            selected_chunk = page_chunks[selected_chunk_idx]

            st.divider()
            st.markdown("### 📝 Chunk Details")

            st.markdown(f"**Type:** {selected_chunk.chunk_type.value}")
            st.markdown(f"**Tokens:** {selected_chunk.token_count}")

            st.markdown("**Text:**")
            st.text_area("Content", selected_chunk.text, height=150, key="chunk_text", label_visibility="collapsed")

            if selected_chunk.bbox:
                st.markdown("**Bounding Box:**")
                bbox = selected_chunk.bbox
                st.json({
                    "x0": f"{bbox.x0:.4f}",
                    "y0": f"{bbox.y0:.4f}",
                    "x1": f"{bbox.x1:.4f}",
                    "y1": f"{bbox.y1:.4f}",
                })

                # Calculate pixel coordinates (assuming 612x792 PDF)
                st.markdown("**Pixel coords (612x792):**")
                st.code(f"({int(bbox.x0*612)}, {int(bbox.y0*792)}) to ({int(bbox.x1*612)}, {int(bbox.y1*792)})")

    else:  # Citations
        citations = st.session_state.get("citations", [])

        if not citations:
            st.warning("No citations extracted yet.")
            st.page_link("pages/2_Citations.py", label="Go to Citations", icon="📜")
        else:
            # Filter citations with bboxes
            citations_with_bbox = [c for c in citations if c.source_bbox]

            if not citations_with_bbox:
                st.warning("No citations have bounding boxes.")
            else:
                # Filter by page
                pages = sorted(set(c.source_page for c in citations_with_bbox if c.source_page))
                selected_page = st.selectbox("Page", pages, key="citation_page")

                # Filter citations for selected page
                page_citations = [c for c in citations_with_bbox if c.source_page == selected_page]

                st.markdown(f"**{len(page_citations)} citations on page {selected_page}**")

                # List citations
                selected_citation_idx = st.selectbox(
                    "Select citation",
                    range(len(page_citations)),
                    format_func=lambda i: f"S. {page_citations[i].section} {page_citations[i].act_name[:30]}"
                )

                if page_citations:
                    selected_citation = page_citations[selected_citation_idx]

                    st.divider()
                    st.markdown("### 📜 Citation Details")

                    st.markdown(f"**Act:** {selected_citation.act_name}")
                    st.markdown(f"**Section:** {selected_citation.section}")
                    if selected_citation.subsection:
                        st.markdown(f"**Subsection:** {selected_citation.subsection}")
                    st.markdown(f"**Confidence:** {selected_citation.confidence:.0%}")
                    st.markdown(f"**Method:** {selected_citation.extraction_method}")

                    st.markdown("**Raw text:**")
                    st.code(selected_citation.raw_text)

                    if selected_citation.source_bbox:
                        st.markdown("**Bounding Box:**")
                        bbox = selected_citation.source_bbox
                        st.json({
                            "x0": f"{bbox.x0:.4f}",
                            "y0": f"{bbox.y0:.4f}",
                            "x1": f"{bbox.x1:.4f}",
                            "y1": f"{bbox.y1:.4f}",
                        })

with col_pdf:
    st.markdown("### 📄 Document View")

    # Try to use streamlit-pdf-viewer if available
    try:
        from streamlit_pdf_viewer import pdf_viewer

        # Get annotations for highlighting
        annotations = []

        if view_type == "Chunks" and 'selected_chunk' in dir() and selected_chunk and selected_chunk.bbox:
            bbox = selected_chunk.bbox
            annotations.append({
                "page": selected_page,
                "x": bbox.x0,
                "y": bbox.y0,
                "width": bbox.x1 - bbox.x0,
                "height": bbox.y1 - bbox.y0,
                "color": "yellow",
            })

        elif view_type == "Citations" and 'selected_citation' in dir() and selected_citation and selected_citation.source_bbox:
            bbox = selected_citation.source_bbox
            annotations.append({
                "page": selected_page,
                "x": bbox.x0,
                "y": bbox.y0,
                "width": bbox.x1 - bbox.x0,
                "height": bbox.y1 - bbox.y0,
                "color": "red",
            })

        # Display PDF with annotations
        pdf_viewer(
            st.session_state.pdf_bytes,
            width=700,
            height=800,
            annotations=annotations if annotations else None,
            pages_to_render=[selected_page] if 'selected_page' in dir() else None,
        )

    except ImportError:
        st.warning("streamlit-pdf-viewer not installed. Showing basic PDF display.")

        # Fallback: show PDF as embedded object
        base64_pdf = base64.b64encode(st.session_state.pdf_bytes).decode('utf-8')
        pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="800"
            type="application/pdf"
        ></iframe>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)

        st.info("Install streamlit-pdf-viewer for bounding box highlighting: `uv pip install streamlit-pdf-viewer`")

    except Exception as e:
        st.error(f"Error displaying PDF: {str(e)}")

        # Fallback to basic display
        base64_pdf = base64.b64encode(st.session_state.pdf_bytes).decode('utf-8')
        pdf_display = f'''
        <iframe
            src="data:application/pdf;base64,{base64_pdf}"
            width="100%"
            height="800"
            type="application/pdf"
        ></iframe>
        '''
        st.markdown(pdf_display, unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("### 🎯 Grounding Info")

    chunks = st.session_state.chunks
    with_bbox = sum(1 for c in chunks if c.bbox)

    st.metric("Chunks with BBox", f"{with_bbox}/{len(chunks)}")

    citations = st.session_state.get("citations", [])
    if citations:
        citations_with_bbox = sum(1 for c in citations if c.source_bbox)
        st.metric("Citations with BBox", f"{citations_with_bbox}/{len(citations)}")

    st.divider()

    st.markdown("### ℹ️ About Visual Grounding")
    st.markdown("""
    **Visual grounding** links extracted text to
    its exact location on the page.

    **Landing AI ADE** provides native
    bounding boxes for each chunk - no
    fuzzy matching required!

    Coordinates are normalized (0-1).
    """)

    st.divider()

    st.markdown("### 🎨 Legend")
    st.markdown("""
    - 🟡 **Yellow** - Document chunks
    - 🔴 **Red** - Legal citations
    """)
