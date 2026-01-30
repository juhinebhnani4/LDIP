"""Citations Page - Extract and display legal citations."""

import streamlit as st
from pathlib import Path
import sys
import os
import pandas as pd

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from dotenv import load_dotenv
load_dotenv()

st.set_page_config(page_title="Citations | Jaanch Lite", page_icon="📜", layout="wide")

st.markdown("## 📜 Citation Extraction")
st.markdown("Extract legal citations from your document using hybrid regex + LLM approach.")

# Check if document is loaded
if not st.session_state.get("chunks"):
    st.warning("⚠️ No document loaded. Please upload a document first.")
    st.page_link("pages/1_Upload_Parse.py", label="Go to Upload & Parse", icon="📄")
    st.stop()

# Display current document
st.info(f"📄 Current document: **{st.session_state.get('current_doc', 'Unknown')}** ({len(st.session_state.chunks)} chunks)")

# Extraction options
col1, col2 = st.columns(2)

with col1:
    use_llm = st.checkbox(
        "Use LLM for extraction",
        value=bool(os.getenv("GOOGLE_API_KEY")),
        help="Enable Gemini 2.5 Flash for better extraction (requires GOOGLE_API_KEY)"
    )

with col2:
    extraction_method = "Hybrid (Regex + Gemini)" if use_llm else "Regex only"
    st.markdown(f"**Method:** {extraction_method}")

# Extract button
if st.button("🔍 Extract Citations", type="primary", use_container_width=True):
    with st.spinner("Extracting citations..."):
        try:
            from src.citations.extractor import CitationExtractor

            extractor = CitationExtractor(
                provider="gemini",
                use_llm=use_llm and bool(os.getenv("GOOGLE_API_KEY"))
            )

            # Extract from all chunks
            result = extractor.extract_from_chunks(st.session_state.chunks)

            # Store in session state
            st.session_state.citations = result.citations

            st.success(f"✅ Found {len(result.citations)} citations using {result.extraction_method} extraction")

        except Exception as e:
            st.error(f"❌ Extraction failed: {str(e)}")
            import traceback
            st.code(traceback.format_exc())

# Display citations
if st.session_state.get("citations"):
    st.divider()

    citations = st.session_state.citations

    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total Citations", len(citations))

    acts = set(c.act_name for c in citations)
    col2.metric("Unique Acts", len(acts))

    high_conf = sum(1 for c in citations if c.confidence >= 0.8)
    col3.metric("High Confidence", high_conf)

    with_bbox = sum(1 for c in citations if c.source_bbox)
    col4.metric("With Location", with_bbox)

    st.divider()

    # View options
    view_mode = st.radio(
        "View mode",
        ["Table", "Cards", "By Act"],
        horizontal=True
    )

    if view_mode == "Table":
        # Create DataFrame
        df_data = []
        for c in citations:
            df_data.append({
                "Act": c.act_name,
                "Section": c.section,
                "Subsection": c.subsection or "-",
                "Page": c.source_page or "-",
                "Confidence": f"{c.confidence:.0%}",
                "Method": c.extraction_method,
            })

        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        # Download button
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            "citations.csv",
            "text/csv",
        )

    elif view_mode == "Cards":
        # Display as cards
        cols = st.columns(2)

        for i, citation in enumerate(citations):
            with cols[i % 2]:
                conf_color = "green" if citation.confidence >= 0.8 else "orange" if citation.confidence >= 0.5 else "red"

                st.markdown(f"""
                <div style="border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin-bottom: 1rem;">
                    <h4 style="margin: 0;">Section {citation.section}</h4>
                    <p style="color: #666; margin: 0.5rem 0;">{citation.act_name}</p>
                    <div style="display: flex; gap: 1rem; font-size: 0.85rem;">
                        <span>📄 Page {citation.source_page or '?'}</span>
                        <span style="color: {conf_color};">●</span>
                        <span>{citation.confidence:.0%}</span>
                        <span style="color: #888;">{citation.extraction_method}</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    elif view_mode == "By Act":
        # Group by act
        from collections import defaultdict
        by_act = defaultdict(list)
        for c in citations:
            by_act[c.act_name].append(c)

        for act_name, act_citations in sorted(by_act.items()):
            with st.expander(f"**{act_name}** ({len(act_citations)} citations)", expanded=True):
                sections = sorted(set(c.section for c in act_citations))
                st.markdown(f"Sections: {', '.join(sections)}")

                for c in act_citations:
                    col1, col2, col3 = st.columns([2, 1, 1])
                    col1.markdown(f"**S. {c.section}**{c.subsection or ''}")
                    col2.markdown(f"Page {c.source_page or '?'}")
                    col3.markdown(f"{c.confidence:.0%} ({c.extraction_method})")

    # Citation details expander
    st.divider()
    st.markdown("### 📝 Raw Citation Data")

    with st.expander("View raw extraction data"):
        for i, c in enumerate(citations[:10]):
            st.markdown(f"**Citation {i+1}:** Section {c.section} of {c.act_name}")
            st.markdown(f"*Raw text:* `{c.raw_text}`")
            if c.source_bbox:
                st.markdown(f"*BBox:* [{c.source_bbox.x0:.3f}, {c.source_bbox.y0:.3f}, {c.source_bbox.x1:.3f}, {c.source_bbox.y1:.3f}]")
            st.divider()

else:
    st.info("👆 Click 'Extract Citations' to find legal references in the document.")

# Sidebar
with st.sidebar:
    st.markdown("### 📊 Citation Stats")

    if st.session_state.get("citations"):
        citations = st.session_state.citations

        st.metric("Total", len(citations))

        # Top acts
        from collections import Counter
        act_counts = Counter(c.act_name for c in citations)
        top_acts = act_counts.most_common(5)

        st.markdown("**Top Acts:**")
        for act, count in top_acts:
            short_name = act[:30] + "..." if len(act) > 30 else act
            st.markdown(f"- {short_name}: {count}")
    else:
        st.info("Extract citations to see stats")

    st.divider()

    st.markdown("### 📚 Supported Formats")
    st.markdown("""
    - Section 138 of NI Act
    - u/s 302 IPC
    - S. 420 Indian Penal Code
    - Article 21 Constitution
    - धारा 302 भारतीय दंड संहिता
    """)
